from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from cf_ml_common.llm.token_tracker import tracking_context
from context_db.agents.clearfacts_navigation_agent.route_steps import (
    parse_legacy_route_step,
    typed_steps_for_navigation_path,
    wait_text_from_success_criteria,
)
from context_db.agents.clearfacts_navigation_agent.schemas import (
    ClearfactsNavigationResult,
    ExplorationAction,
    ExplorationActionType,
    NavigationEventRecord,
    NavigationExecutionStatus,
    NavigationOntologyDelta,
    NavigationPageEvidence,
    NavigationPathObservation,
    NavigationRouteStep,
)
from context_db.agents.clearfacts_navigation_agent.tools import (
    BLANK_PAGE_URLS,
    NavigationExecutionError,
    NavigationRunContext,
    PlaywrightMcpBrowser,
    PlaywrightToolExecutionError,
    _run_async_blocking,
    append_navigation_event,
    backfill_navigation_ontology_file,
    build_result,
    build_prompt_source_context,
    ensure_navigation_run,
    event_record,
    load_manifest,
    load_navigation_ontology,
    merge_navigation_ontology,
    next_navigation_step_index,
    prepare_navigation_action_target,
    prepare_playwright_run_config,
    read_navigation_events,
    read_recent_navigation_events,
    remap_snapshot_ref_target,
    resolve_role,
    resolve_role_credential,
    save_snapshot,
    should_retry_stale_ref,
    should_type_slowly,
    update_manifest,
)
from context_db.llm.config import get_azure_llm, init_token_tracking

from .prompts import (
    COORDINATOR_SYSTEM_PROMPT,
    COORDINATOR_USER_PROMPT_TEMPLATE,
    GOAL_ASSESSOR_SYSTEM_PROMPT,
    GOAL_ASSESSOR_USER_PROMPT_TEMPLATE,
    ONTOLOGY_BATCH_ANALYZER_SYSTEM_PROMPT,
    ONTOLOGY_BATCH_ANALYZER_USER_PROMPT_TEMPLATE,
    RECOVERY_ANALYZER_SYSTEM_PROMPT,
    RECOVERY_ANALYZER_USER_PROMPT_TEMPLATE,
    ROUTE_PLANNER_SYSTEM_PROMPT,
    ROUTE_PLANNER_USER_PROMPT_TEMPLATE,
    VALIDATION_ASSESSOR_SYSTEM_PROMPT,
    VALIDATION_ASSESSOR_USER_PROMPT_TEMPLATE,
)
from .schemas import (
    BrowserExecutionOperation,
    CachedRouteExecutionStatus,
    CachedRouteExecutionTaskInput,
    CachedRouteExecutionTaskOutput,
    CachedRouteStepResult,
    ClearfactsNavigationDeepAgentRequest,
    ClearfactsNavigationDeepAgentResult,
    ClearfactsNavigationOntologyUpdateRequest,
    ClearfactsNavigationOntologyUpdateResult,
    ClearfactsNavigationValidationRequest,
    ClearfactsNavigationValidationResult,
    DeepAgentCoordinatorStructuredResponse,
    DeepAgentExecutionStatus,
    GoalAssessmentTaskInput,
    GoalAssessmentTaskOutput,
    NavigationExecutionTaskInput,
    NavigationExecutionTaskOutput,
    OntologyBatchAnalysisTaskOutput,
    RecoveryAnalysisTaskInput,
    RecoveryAnalysisTaskOutput,
    RoutePlanningTaskInput,
    RoutePlanningTaskOutput,
    ValidationAssessmentTaskInput,
    ValidationAssessmentTaskOutput,
)
from .model_config import (
    NavigationAgentModelProfile,
    NavigationAgentRoleModelConfig,
    load_navigation_agent_model_profile,
    single_model_navigation_agent_model_profile,
)
from .tools import (
    build_execution_result_yaml,
    build_trace_references,
    write_trace_artifact,
)
from .runtime_tools import build_navigation_runtime_tools

logger = logging.getLogger(__name__)


_GOAL_SATISFACTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "app",
    "clearfacts",
    "go",
    "move",
    "navigate",
    "open",
    "page",
    "section",
    "show",
    "the",
    "to",
}


def _goal_tokens(goal: str) -> list[str]:
    return [
        token
        for token in "".join(char.lower() if char.isalnum() else " " for char in goal).split()
        if len(token) >= 3 and token not in _GOAL_SATISFACTION_STOPWORDS
    ]


def _page_likely_satisfies_goal(
    goal: str,
    page: NavigationPageEvidence | None,
    *,
    message: str | None = None,
) -> bool:
    if page is None:
        return False
    tokens = _goal_tokens(goal)
    if not tokens:
        return False

    url = (page.url or "").lower()
    if any(token in url for token in tokens):
        return True

    haystack = " ".join(
        value.lower()
        for value in [
            page.title,
            page.text_excerpt,
            page.page_summary,
            message,
        ]
        if value
    )
    return all(token in haystack for token in tokens)


def _navigation_result_likely_satisfies_goal(goal: str, latest_navigation: ClearfactsNavigationResult) -> bool:
    return _page_likely_satisfies_goal(
        goal,
        latest_navigation.current_page,
        message=latest_navigation.message,
    )


@dataclass(frozen=True)
class OntologyEvidenceBatch:
    all_event_count: int
    candidate_event_count: int
    selected_events: list[NavigationEventRecord]
    payloads: list[dict[str, Any]]
    selected_event_ids: list[str]
    processed_event_id: str | None
    processed_event_count: int
    payload_chars: int


class ClearfactsNavigationExecutionSubAgent:
    AGENT_NAME = "clearfacts-navigation-executor-subagent"
    AGENT_OPERATION = "execute-typed-browser-operation"

    def __init__(self, model_name: str = "gpt-5-2025-08-07", max_tokens: int = 4000) -> None:
        self._model_name = model_name
        self._max_tokens = max_tokens

    def invoke(
        self,
        query: NavigationExecutionTaskInput,
        *,
        browser: Any | None = None,
    ) -> NavigationExecutionTaskOutput:
        input_messages = [HumanMessage(content=query.model_dump_json(indent=2))]
        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            output = _run_async_blocking(self._invoke_async(query, browser=browser))
        run = ensure_navigation_run(query.source_name, timestamp=output.run_timestamp)
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="subagent",
            input_messages=input_messages,
            output_messages=[AIMessage(content=output.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=output,
            metadata={"subagent_name": "navigation-executor"},
        )
        output.trace_path = str(trace_path)
        return output

    async def _invoke_async(
        self,
        query: NavigationExecutionTaskInput,
        *,
        browser: Any | None = None,
    ) -> NavigationExecutionTaskOutput:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        role = resolve_role(run.source, query.role)
        update_manifest(
            run.manifest_path,
            status="running",
            last_instruction=query.instruction,
            last_role=role,
        )
        runtime_config = prepare_playwright_run_config(run.source, run)
        if browser is None:
            async with PlaywrightMcpBrowser(runtime_config) as managed_browser:
                return await self._run_operation(query=query, role=role, run=run, browser=managed_browser)
        return await self._run_operation(query=query, role=role, run=run, browser=browser)

    async def _run_operation(
        self,
        *,
        query: NavigationExecutionTaskInput,
        role: str | None,
        run: NavigationRunContext,
        browser: Any,
    ) -> NavigationExecutionTaskOutput:
        tool_inventory = browser.tool_inventory()
        step_index = next_navigation_step_index(run)
        events = []
        current_page, bootstrap_event = await self._bootstrap_browser(
            browser=browser,
            run=run,
            include_snapshot=query.include_snapshot,
        )
        if bootstrap_event is not None:
            append_navigation_event(run, bootstrap_event)
            events.append(bootstrap_event)
            step_index = next_navigation_step_index(run)

        if query.operation == BrowserExecutionOperation.INSPECT:
            snapshot_path = save_snapshot(run, step_index=step_index, phase="inspect", page=current_page)
            observation_event = event_record(
                step_index=step_index,
                phase="observation",
                status="captured",
                message="Captured current browser evidence.",
                tool_name="inspect_page",
                snapshot_path=snapshot_path,
                page=current_page,
            )
            append_navigation_event(run, observation_event)
            events.append(observation_event)
            update_manifest(
                run.manifest_path,
                last_observed_url=current_page.url,
                last_observed_title=current_page.title,
            )
            return self._build_output(
                query=query,
                run=run,
                role=role,
                status=NavigationExecutionStatus.COMPLETED,
                message="Captured current browser evidence.",
                events=events,
                current_page=current_page,
                tool_inventory=tool_inventory,
            )

        pre_snapshot = save_snapshot(run, step_index=step_index, phase="pre_action", page=current_page)
        pre_event = event_record(
            step_index=step_index,
            phase="observation",
            status="captured",
            message="Captured page evidence before executing the browser operation.",
            tool_name="inspect_page",
            snapshot_path=pre_snapshot,
            page=current_page,
        )
        append_navigation_event(run, pre_event)
        events.append(pre_event)

        action = self._task_to_action(query=query, role=role)
        prepared_action = prepare_navigation_action_target(action, current_page=current_page)
        try:
            action_call = await self._execute_action(
                browser=browser,
                action=prepared_action,
                role=role,
                source=run.source,
                current_page=current_page,
            )
        except PlaywrightToolExecutionError as exc:
            failure_page = await browser.inspect_page(include_snapshot=True)
            failure_snapshot = save_snapshot(run, step_index=step_index, phase="action_failed", page=failure_page)
            action_event = event_record(
                step_index=step_index,
                phase="action",
                status="failed",
                message=exc.message,
                tool_name=exc.tool_name,
                arguments=self._safe_arguments(exc.arguments, action=prepared_action),
                snapshot_path=failure_snapshot,
                page=failure_page,
            )
            append_navigation_event(run, action_event)
            events.append(action_event)
            update_manifest(
                run.manifest_path,
                status="blocked",
                last_observed_url=failure_page.url,
                last_observed_title=failure_page.title,
            )
            return self._build_output(
                query=query,
                run=run,
                role=role,
                status=NavigationExecutionStatus.BLOCKED,
                message=exc.message,
                events=events,
                current_page=failure_page,
                tool_inventory=tool_inventory,
            )

        action_event = event_record(
            step_index=step_index,
            phase="action",
            status="completed",
            message=action_call.message or prepared_action.summary,
            tool_name=action_call.tool_name,
            arguments=self._safe_arguments(action_call.arguments, action=prepared_action),
            page=current_page,
        )
        append_navigation_event(run, action_event)
        events.append(action_event)

        current_page = await browser.inspect_page(include_snapshot=query.include_snapshot)
        post_snapshot = save_snapshot(run, step_index=step_index, phase="post_action", page=current_page)
        observation_event = event_record(
            step_index=step_index,
            phase="observation",
            status="captured",
            message=query.expected_outcome or "Captured page evidence after the browser operation.",
            snapshot_path=post_snapshot,
            page=current_page,
        )
        append_navigation_event(run, observation_event)
        events.append(observation_event)
        update_manifest(
            run.manifest_path,
            last_observed_url=current_page.url,
            last_observed_title=current_page.title,
        )
        return self._build_output(
            query=query,
            run=run,
            role=role,
            status=NavigationExecutionStatus.COMPLETED,
            message=action_call.message or query.expected_outcome or prepared_action.summary,
            events=events,
            current_page=current_page,
            tool_inventory=tool_inventory,
        )

    async def _bootstrap_browser(
        self,
        *,
        browser: Any,
        run: NavigationRunContext,
        include_snapshot: bool,
    ) -> tuple[NavigationPageEvidence, Any | None]:
        current_page = await browser.inspect_page(include_snapshot=include_snapshot)
        if current_page.url and current_page.url not in BLANK_PAGE_URLS:
            return current_page, None

        manifest = run.manifest_path.exists() and yaml.safe_load(run.manifest_path.read_text(encoding="utf-8")) or {}
        start_url = manifest.get("last_observed_url") or run.source.base_url
        bootstrap_call = await browser.navigate(start_url)
        current_page = await browser.inspect_page(include_snapshot=include_snapshot)
        step_index = next_navigation_step_index(run)
        bootstrap_snapshot = save_snapshot(run, step_index=step_index, phase="bootstrap", page=current_page)
        return current_page, event_record(
            step_index=step_index,
            phase="bootstrap",
            status="completed",
            message=bootstrap_call.message,
            tool_name=bootstrap_call.tool_name,
            arguments=bootstrap_call.arguments,
            snapshot_path=bootstrap_snapshot,
            page=current_page,
        )

    @staticmethod
    def _task_to_action(*, query: NavigationExecutionTaskInput, role: str | None) -> ExplorationAction:
        operation_mapping = {
            BrowserExecutionOperation.NAVIGATE_URL: ExplorationActionType.NAVIGATE_URL,
            BrowserExecutionOperation.CLICK: ExplorationActionType.CLICK,
            BrowserExecutionOperation.TYPE_TEXT: ExplorationActionType.TYPE_TEXT,
            BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL: ExplorationActionType.TYPE_ROLE_CREDENTIAL,
            BrowserExecutionOperation.PRESS_KEY: ExplorationActionType.PRESS_KEY,
            BrowserExecutionOperation.WAIT_FOR_TEXT: ExplorationActionType.WAIT_FOR_TEXT,
            BrowserExecutionOperation.CAPTURE_SNAPSHOT: ExplorationActionType.CAPTURE_SNAPSHOT,
        }
        return ExplorationAction(
            action_type=operation_mapping[query.operation],
            summary=query.summary or query.instruction,
            url=query.url,
            target=query.target,
            text=query.text,
            key=query.key,
            role=query.role or role,
            credential_field=query.credential_field,
            expected_outcome=query.expected_outcome,
        )

    async def _execute_action(
        self,
        *,
        browser: Any,
        action: ExplorationAction,
        role: str | None,
        source: Any,
        current_page: NavigationPageEvidence | None,
    ):
        try:
            return await self._perform_action(browser=browser, action=action, role=role, source=source)
        except PlaywrightToolExecutionError as exc:
            if not should_retry_stale_ref(action=action, error=exc):
                raise

            fresh_page = await browser.inspect_page(include_snapshot=True)
            retry_action = action.model_copy(deep=True)
            remapped_target = remap_snapshot_ref_target(
                action.target,
                previous_snapshot=current_page.snapshot if current_page else None,
                fresh_snapshot=fresh_page.snapshot,
            )
            if remapped_target:
                retry_action.target = remapped_target

            retry_call = await self._perform_action(browser=browser, action=retry_action, role=role, source=source)
            retry_message = retry_call.message or retry_action.summary
            if retry_action.target != action.target:
                retry_message = f"Recovered stale ref target `{action.target}` -> `{retry_action.target}`.\n\n{retry_message}"
            else:
                retry_message = f"Recovered after refreshing page refs.\n\n{retry_message}"
            return type(retry_call)(
                tool_name=retry_call.tool_name,
                arguments=retry_call.arguments,
                message=retry_message,
            )

    @staticmethod
    async def _perform_action(*, browser: Any, action: ExplorationAction, role: str | None, source: Any):
        if action.action_type == ExplorationActionType.NAVIGATE_URL:
            return await browser.navigate(action.url or "")
        if action.action_type == ExplorationActionType.CLICK:
            return await browser.click(action.target or "")
        if action.action_type == ExplorationActionType.TYPE_TEXT:
            return await browser.type_text(action.target or "", action.text or "", slowly=should_type_slowly(action))
        if action.action_type == ExplorationActionType.TYPE_ROLE_CREDENTIAL:
            effective_role = action.role or role
            if effective_role is None:
                raise ValueError("A role is required to resolve credentials for type_role_credential.")
            value = resolve_role_credential(source, effective_role, action.credential_field.value)
            return await browser.type_text(action.target or "", value, slowly=should_type_slowly(action))
        if action.action_type == ExplorationActionType.PRESS_KEY:
            return await browser.press(action.key or "", target=action.target)
        if action.action_type == ExplorationActionType.WAIT_FOR_TEXT:
            return await browser.wait_for_text(action.text or "")
        if action.action_type == ExplorationActionType.CAPTURE_SNAPSHOT:
            return await browser.capture_snapshot(action.target)
        raise ValueError(f"Unsupported action type: {action.action_type}")

    @staticmethod
    def _safe_arguments(arguments: dict[str, object], *, action: ExplorationAction) -> dict[str, object]:
        safe_arguments = dict(arguments)
        if action.action_type == ExplorationActionType.TYPE_ROLE_CREDENTIAL or action.target == "#password":
            for key in ("text", "value"):
                if key in safe_arguments:
                    safe_arguments[key] = "<redacted>"
        return safe_arguments

    @staticmethod
    def _build_output(
        *,
        query: NavigationExecutionTaskInput,
        run: NavigationRunContext,
        role: str | None,
        status: NavigationExecutionStatus,
        message: str | None,
        events: list[Any],
        current_page: NavigationPageEvidence | None,
        tool_inventory: list[str],
    ) -> NavigationExecutionTaskOutput:
        result = build_result(
            status=status,
            run=run,
            instruction=query.instruction,
            role=role,
            events=events,
            current_page=current_page,
            tool_inventory=tool_inventory,
            message=message,
        )
        return NavigationExecutionTaskOutput(
            operation=query.operation,
            status=result.status,
            message=result.message,
            question_for_user=result.question_for_user,
            current_page=result.current_page,
            events=events,
            run_timestamp=result.run_timestamp,
            run_folder=result.run_folder,
            ontology_path=result.ontology_path,
            raw_result=result,
        )


class ClearfactsNavigationRouteCacheExecutor:
    AGENT_NAME = "clearfacts-navigation-route-cache"
    AGENT_OPERATION = "execute-deterministic-navigation-route"

    _GENERIC_TARGET_TERMS = {"page", "screen", "inbox", "postbus", "the", "naar"}
    _ALIASES = {
        "sales": {"sale", "sales", "verkoop"},
        "sale": {"sale", "sales", "verkoop"},
        "verkoop": {"sale", "sales", "verkoop"},
        "purchase": {"purchase", "aankoop"},
        "aankoop": {"purchase", "aankoop"},
        "dashboard": {"dashboard", "home"},
        "login": {"login", "aanmelden"},
        "archive": {"archive", "archief"},
        "archief": {"archive", "archief"},
        "payments": {"payments", "payment", "betalingen", "betaling"},
        "payment": {"payments", "payment", "betalingen", "betaling"},
        "betalingen": {"payments", "payment", "betalingen", "betaling"},
        "betaling": {"payments", "payment", "betalingen", "betaling"},
    }

    def __init__(self, execution: ClearfactsNavigationExecutionSubAgent) -> None:
        self._execution = execution

    def invoke(
        self,
        query: CachedRouteExecutionTaskInput,
        *,
        browser: Any | None = None,
    ) -> CachedRouteExecutionTaskOutput:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        ontology = load_navigation_ontology(run.run_ontology)
        chain, uncovered_targets = self._select_route_chain(ontology.navigation_paths, ontology, query.user_goal)
        if not chain:
            output = CachedRouteExecutionTaskOutput(
                status=CachedRouteExecutionStatus.NOT_FOUND,
                summary="No deterministic route cache entry matched the user goal.",
                source_name=run.source.source_name,
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
                remaining_goal=query.user_goal,
            )
            return self._write_trace(run=run, query=query, output=output)

        matched_paths = [path.description for path in chain]
        execution_steps = self._steps_for_chain(chain, source_base_url=run.source.base_url)
        if not execution_steps:
            output = CachedRouteExecutionTaskOutput(
                status=CachedRouteExecutionStatus.FAILED,
                summary="A route cache entry matched, but it does not contain executable typed or parseable route steps.",
                source_name=run.source.source_name,
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
                matched_paths=matched_paths,
                remaining_goal=query.user_goal,
            )
            return self._write_trace(run=run, query=query, output=output)

        executed_steps: list[CachedRouteStepResult] = []
        latest_result: ClearfactsNavigationResult | None = None
        step_budget = min(query.max_steps, len(execution_steps))
        if browser is not None:
            return self._execute_steps_fast(
                query=query,
                run=run,
                browser=browser,
                matched_paths=matched_paths,
                execution_steps=execution_steps,
                step_budget=step_budget,
                uncovered_targets=uncovered_targets,
            )

        for path, step in execution_steps[:step_budget]:
            task = self._execution_task_for_step(
                step,
                source_name=run.source.source_name,
                run_timestamp=run.timestamp,
                role=query.role,
                include_snapshot=query.include_snapshot,
            )
            result = self._execution.invoke(task, browser=browser)
            latest_result = result.raw_result
            current_page = result.current_page
            executed_steps.append(
                CachedRouteStepResult(
                    path_description=path.description,
                    operation=task.operation,
                    instruction=task.instruction,
                    status=result.status,
                    message=result.message,
                    current_page_url=current_page.url if current_page else None,
                    current_page_title=current_page.title if current_page else None,
                    trace_path=result.trace_path,
                )
            )
            if result.status != NavigationExecutionStatus.COMPLETED:
                output = CachedRouteExecutionTaskOutput(
                    status=CachedRouteExecutionStatus.FAILED,
                    summary=f"Deterministic route cache execution stopped at step: {task.instruction}",
                    source_name=run.source.source_name,
                    run_timestamp=run.timestamp,
                    run_folder=str(run.run_dir),
                    ontology_path=str(run.run_ontology),
                    matched_paths=matched_paths,
                    executed_steps=executed_steps,
                    remaining_goal=query.user_goal,
                    current_page=current_page,
                    latest_navigation_result=latest_result,
                )
                return self._write_trace(run=run, query=query, output=output)

        remaining_goal = self._remaining_goal(uncovered_targets)
        reached_goal = (
            latest_result is not None and _navigation_result_likely_satisfies_goal(query.user_goal, latest_result)
        )
        if reached_goal:
            remaining_goal = None
        if not reached_goal and step_budget < len(execution_steps):
            truncated_goal = f"continue cached route execution after {step_budget} step(s)"
            remaining_goal = f"{remaining_goal}; {truncated_goal}" if remaining_goal else truncated_goal
        status = CachedRouteExecutionStatus.PARTIAL if remaining_goal else CachedRouteExecutionStatus.COMPLETED
        summary = (
            "Executed the matching deterministic route cache path(s); remaining goal requires exploration."
            if remaining_goal
            else "Executed the matching deterministic route cache path(s)."
        )
        output = CachedRouteExecutionTaskOutput(
            status=status,
            summary=summary,
            source_name=run.source.source_name,
            run_timestamp=run.timestamp,
            run_folder=str(run.run_dir),
            ontology_path=str(run.run_ontology),
            matched_paths=matched_paths,
            executed_steps=executed_steps,
            remaining_goal=remaining_goal,
            current_page=latest_result.current_page if latest_result else None,
            latest_navigation_result=latest_result,
        )
        return self._write_trace(run=run, query=query, output=output)

    def _execute_steps_fast(
        self,
        *,
        query: CachedRouteExecutionTaskInput,
        run: NavigationRunContext,
        browser: Any,
        matched_paths: list[str],
        execution_steps: list[tuple[NavigationPathObservation, NavigationRouteStep]],
        step_budget: int,
        uncovered_targets: list[str],
    ) -> CachedRouteExecutionTaskOutput:
        return _run_async_blocking(
            self._execute_steps_fast_async(
                query=query,
                run=run,
                browser=browser,
                matched_paths=matched_paths,
                execution_steps=execution_steps,
                step_budget=step_budget,
                uncovered_targets=uncovered_targets,
            )
        )

    async def _execute_steps_fast_async(
        self,
        *,
        query: CachedRouteExecutionTaskInput,
        run: NavigationRunContext,
        browser: Any,
        matched_paths: list[str],
        execution_steps: list[tuple[NavigationPathObservation, NavigationRouteStep]],
        step_budget: int,
        uncovered_targets: list[str],
    ) -> CachedRouteExecutionTaskOutput:
        role = resolve_role(run.source, query.role)
        update_manifest(
            run.manifest_path,
            status="running",
            last_instruction=query.user_goal,
            last_role=role,
        )
        tool_inventory = browser.tool_inventory()
        executed_steps: list[CachedRouteStepResult] = []
        events: list[NavigationEventRecord] = []
        current_page: NavigationPageEvidence | None = None

        for path, step in execution_steps[:step_budget]:
            step_index = next_navigation_step_index(run)
            try:
                action_call = await self._perform_cached_step(browser=browser, step=step, role=role, source=run.source)
            except (NavigationExecutionError, PlaywrightToolExecutionError, ValueError) as exc:
                error_message = exc.message if isinstance(exc, PlaywrightToolExecutionError) else str(exc)
                error_tool_name = exc.tool_name if isinstance(exc, PlaywrightToolExecutionError) else "route_cache_fast_path"
                error_arguments = exc.arguments if isinstance(exc, PlaywrightToolExecutionError) else {}
                current_page = await browser.inspect_page(include_snapshot=True)
                snapshot_path = save_snapshot(run, step_index=step_index, phase="route_cache_failed", page=current_page)
                failure_event = event_record(
                    step_index=step_index,
                    phase="action",
                    status="failed",
                    message=error_message,
                    tool_name=error_tool_name,
                    arguments=self._safe_cached_arguments(error_arguments, step=step),
                    snapshot_path=snapshot_path,
                    page=current_page,
                )
                append_navigation_event(run, failure_event)
                events.append(failure_event)
                latest_result = build_result(
                    status=NavigationExecutionStatus.BLOCKED,
                    run=run,
                    instruction=query.user_goal,
                    role=role,
                    events=events,
                    current_page=current_page,
                    tool_inventory=tool_inventory,
                    message=error_message,
                )
                executed_steps.append(
                    CachedRouteStepResult(
                        path_description=path.description,
                        operation=BrowserExecutionOperation(step.operation.value),
                        instruction=step.instruction,
                        status=NavigationExecutionStatus.BLOCKED,
                        message=error_message,
                        current_page_url=current_page.url,
                        current_page_title=current_page.title,
                    )
                )
                update_manifest(
                    run.manifest_path,
                    status="blocked",
                    last_observed_url=current_page.url,
                    last_observed_title=current_page.title,
                )
                return self._write_trace(
                    run=run,
                    query=query,
                    output=CachedRouteExecutionTaskOutput(
                        status=CachedRouteExecutionStatus.FAILED,
                        summary=f"Fast deterministic route cache execution stopped at step: {step.instruction}",
                        source_name=run.source.source_name,
                        run_timestamp=run.timestamp,
                        run_folder=str(run.run_dir),
                        ontology_path=str(run.run_ontology),
                        matched_paths=matched_paths,
                        executed_steps=executed_steps,
                        remaining_goal=query.user_goal,
                        current_page=current_page,
                        latest_navigation_result=latest_result,
                    ),
                )

            action_event = event_record(
                step_index=step_index,
                phase="action",
                status="completed",
                message=action_call.message or step.expected_outcome or step.instruction,
                tool_name=action_call.tool_name,
                arguments=self._safe_cached_arguments(action_call.arguments, step=step),
            )
            append_navigation_event(run, action_event)
            events.append(action_event)
            executed_steps.append(
                CachedRouteStepResult(
                    path_description=path.description,
                    operation=BrowserExecutionOperation(step.operation.value),
                    instruction=step.instruction,
                    status=NavigationExecutionStatus.COMPLETED,
                    message=action_call.message or step.expected_outcome or step.instruction,
                )
            )

        step_index = next_navigation_step_index(run)
        current_page = await browser.inspect_page(include_snapshot=query.include_snapshot)
        snapshot_path = save_snapshot(run, step_index=step_index, phase="route_cache_final", page=current_page)
        observation_event = event_record(
            step_index=step_index,
            phase="observation",
            status="captured",
            message="Captured page evidence after fast deterministic route cache execution.",
            tool_name="inspect_page",
            snapshot_path=snapshot_path,
            page=current_page,
        )
        append_navigation_event(run, observation_event)
        events.append(observation_event)
        if executed_steps:
            executed_steps[-1].current_page_url = current_page.url
            executed_steps[-1].current_page_title = current_page.title

        remaining_goal = self._remaining_goal(uncovered_targets)
        reached_goal = _page_likely_satisfies_goal(query.user_goal, current_page)
        if reached_goal:
            remaining_goal = None
        if not reached_goal and step_budget < len(execution_steps):
            truncated_goal = f"continue cached route execution after {step_budget} step(s)"
            remaining_goal = f"{remaining_goal}; {truncated_goal}" if remaining_goal else truncated_goal
        status = CachedRouteExecutionStatus.PARTIAL if remaining_goal else CachedRouteExecutionStatus.COMPLETED
        summary = (
            "Fast-executed the matching deterministic route cache path(s); remaining goal requires exploration."
            if remaining_goal
            else "Fast-executed the matching deterministic route cache path(s)."
        )
        latest_result = build_result(
            status=NavigationExecutionStatus.COMPLETED,
            run=run,
            instruction=query.user_goal,
            role=role,
            events=events,
            current_page=current_page,
            tool_inventory=tool_inventory,
            message=summary,
        )
        update_manifest(
            run.manifest_path,
            status=status.value,
            last_observed_url=current_page.url,
            last_observed_title=current_page.title,
        )
        return self._write_trace(
            run=run,
            query=query,
            output=CachedRouteExecutionTaskOutput(
                status=status,
                summary=summary,
                source_name=run.source.source_name,
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
                matched_paths=matched_paths,
                executed_steps=executed_steps,
                remaining_goal=remaining_goal,
                current_page=current_page,
                latest_navigation_result=latest_result,
            ),
        )

    @staticmethod
    async def _perform_cached_step(*, browser: Any, step: NavigationRouteStep, role: str | None, source: Any):
        if step.operation == ExplorationActionType.NAVIGATE_URL:
            return await browser.navigate(step.url or "")
        if step.operation == ExplorationActionType.CLICK:
            return await browser.click(step.target or "")
        if step.operation == ExplorationActionType.TYPE_TEXT:
            return await browser.type_text(step.target or "", step.text or "", slowly=step.target in {"#username", "#password"})
        if step.operation == ExplorationActionType.TYPE_ROLE_CREDENTIAL:
            if role is None:
                raise ValueError("A role is required to resolve credentials for type_role_credential.")
            if step.credential_field is None:
                raise ValueError("A credential_field is required for type_role_credential.")
            value = resolve_role_credential(source, role, step.credential_field.value)
            return await browser.type_text(step.target or "", value, slowly=step.target in {"#username", "#password"})
        if step.operation == ExplorationActionType.PRESS_KEY:
            return await browser.press(step.key or "", target=step.target)
        if step.operation == ExplorationActionType.WAIT_FOR_TEXT:
            return await browser.wait_for_text(step.text or "")
        if step.operation == ExplorationActionType.CAPTURE_SNAPSHOT:
            return await browser.capture_snapshot(step.target)
        raise ValueError(f"Unsupported cached route operation: {step.operation}")

    @staticmethod
    def _safe_cached_arguments(arguments: dict[str, object], *, step: NavigationRouteStep) -> dict[str, object]:
        safe_arguments = dict(arguments)
        if step.operation == ExplorationActionType.TYPE_ROLE_CREDENTIAL or step.target == "#password":
            for key in ("text", "value"):
                if key in safe_arguments:
                    safe_arguments[key] = "<redacted>"
        return safe_arguments

    @classmethod
    def _select_route_chain(
        cls,
        paths: list[NavigationPathObservation],
        ontology: Any,
        user_goal: str,
    ) -> tuple[list[NavigationPathObservation], list[str]]:
        mentioned_targets = cls._mentioned_targets(ontology, user_goal)
        selected_paths: list[NavigationPathObservation] = []
        uncovered_targets: list[str] = []

        for target_name, _position in mentioned_targets:
            path = cls._path_to_target(paths, target_name)
            if path is None:
                uncovered_targets.append(target_name)
                continue
            selected_paths.append(path)

        for action, _position in cls._mentioned_actions(ontology, user_goal):
            target_name = cls._action_target_name(action)
            path = cls._path_to_target(paths, target_name)
            if path is not None:
                selected_paths.append(path)
                continue

            if action.page_name:
                prerequisite = cls._path_to_target(paths, action.page_name)
                if prerequisite is not None:
                    selected_paths.append(prerequisite)
            uncovered_targets.append(target_name)

        if not selected_paths:
            for path in paths:
                if path.to_screen and cls._goal_mentions_name(user_goal, path.to_screen):
                    selected_paths.append(path)

        chain: list[NavigationPathObservation] = []
        for path in selected_paths:
            for prerequisite in cls._prerequisite_chain(paths, path):
                if not any(existing.description == prerequisite.description for existing in chain):
                    chain.append(prerequisite)
            if not any(existing.description == path.description for existing in chain):
                chain.append(path)
        return chain, uncovered_targets

    @classmethod
    def _mentioned_targets(cls, ontology: Any, user_goal: str) -> list[tuple[str, int]]:
        candidates = [screen.name for screen in ontology.screens]
        candidates.extend(entry.name for entry in ontology.entry_points)
        seen: set[str] = set()
        mentions: list[tuple[str, int]] = []
        for name in candidates:
            normalized_name = name.strip().lower()
            if normalized_name in seen:
                continue
            position = cls._goal_name_position(user_goal, name)
            if position is None:
                continue
            mentions.append((name, position))
            seen.add(normalized_name)
        return sorted(mentions, key=lambda item: item[1])

    @classmethod
    def _mentioned_actions(cls, ontology: Any, user_goal: str) -> list[tuple[Any, int]]:
        mentions: list[tuple[Any, int]] = []
        seen: set[str] = set()
        for action in ontology.actions:
            candidate_names = [action.name]
            if action.description:
                candidate_names.append(action.description)
            position = cls._first_goal_name_position(user_goal, candidate_names)
            if position is None:
                continue
            target_name = cls._action_target_name(action)
            normalized_name = target_name.strip().lower()
            if normalized_name in seen:
                continue
            mentions.append((action, position))
            seen.add(normalized_name)
        return sorted(mentions, key=lambda item: item[1])

    @classmethod
    def _first_goal_name_position(cls, user_goal: str, names: list[str]) -> int | None:
        positions = [
            position
            for name in names
            if (position := cls._goal_name_position(user_goal, name)) is not None
        ]
        return min(positions) if positions else None

    @staticmethod
    def _action_target_name(action: Any) -> str:
        if action.name:
            parenthesized = re.findall(r"\(([^()]+)\)", action.name)
            if parenthesized:
                return parenthesized[-1].strip()
            quoted = re.findall(r"'([^']+)'", action.name)
            if quoted:
                return quoted[-1].strip()
            return action.name
        return action.description or "target action"

    @classmethod
    def _path_to_target(
        cls,
        paths: list[NavigationPathObservation],
        target_name: str,
    ) -> NavigationPathObservation | None:
        target_terms = cls._name_terms(target_name)
        for path in paths:
            if path.to_screen and target_terms.intersection(cls._name_terms(path.to_screen)):
                return path
        return None

    @classmethod
    def _prerequisite_chain(
        cls,
        paths: list[NavigationPathObservation],
        path: NavigationPathObservation,
        *,
        visited: set[str] | None = None,
    ) -> list[NavigationPathObservation]:
        if not path.from_screen:
            return []
        visited = visited or set()
        key = path.description.strip().lower()
        if key in visited:
            return []
        visited.add(key)

        from_terms = cls._name_terms(path.from_screen)
        for candidate in paths:
            if candidate is path or not candidate.to_screen:
                continue
            if from_terms.intersection(cls._name_terms(candidate.to_screen)):
                return [*cls._prerequisite_chain(paths, candidate, visited=visited), candidate]
        return []

    @classmethod
    def _goal_mentions_name(cls, user_goal: str, name: str) -> bool:
        return cls._goal_name_position(user_goal, name) is not None

    @classmethod
    def _goal_name_position(cls, user_goal: str, name: str) -> int | None:
        normalized_goal = cls._normalize_text(user_goal)
        goal_terms = set(normalized_goal.split())
        positions = [
            normalized_goal.find(term)
            for term in cls._name_terms(name)
            if term in goal_terms and normalized_goal.find(term) >= 0
        ]
        return min(positions) if positions else None

    @classmethod
    def _name_terms(cls, name: str) -> set[str]:
        terms = {
            token
            for token in cls._normalize_text(name).split()
            if len(token) >= 3 and token not in cls._GENERIC_TARGET_TERMS
        }
        expanded = set(terms)
        for term in terms:
            expanded.update(cls._ALIASES.get(term, set()))
        return expanded

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join("".join(char.lower() if char.isalnum() else " " for char in value).split())

    @classmethod
    def _steps_for_chain(
        cls,
        chain: list[NavigationPathObservation],
        *,
        source_base_url: str,
    ) -> list[tuple[NavigationPathObservation, NavigationRouteStep]]:
        steps: list[tuple[NavigationPathObservation, NavigationRouteStep]] = []
        for path in chain:
            path_steps = typed_steps_for_navigation_path(path, source_base_url=source_base_url)
            steps.extend((path, step) for step in path_steps)
        return steps

    _parse_legacy_route_step = staticmethod(parse_legacy_route_step)

    _wait_text_from_success_criteria = staticmethod(wait_text_from_success_criteria)

    @staticmethod
    def _remaining_goal(uncovered_targets: list[str]) -> str | None:
        if not uncovered_targets:
            return None
        if len(uncovered_targets) == 1:
            return f"go to {uncovered_targets[0]}"
        return "continue with " + ", then ".join(f"go to {target}" for target in uncovered_targets)

    @staticmethod
    def _execution_task_for_step(
        step: NavigationRouteStep,
        *,
        source_name: str,
        run_timestamp: str,
        role: str | None,
        include_snapshot: bool,
    ) -> NavigationExecutionTaskInput:
        return NavigationExecutionTaskInput(
            source_name=source_name,
            instruction=step.instruction,
            operation=BrowserExecutionOperation(step.operation.value),
            role=role,
            run_timestamp=run_timestamp,
            include_snapshot=include_snapshot,
            url=step.url,
            target=step.target,
            text=step.text,
            key=step.key,
            credential_field=step.credential_field,
            summary=step.instruction,
            expected_outcome=step.expected_outcome,
        )

    @classmethod
    def _write_trace(
        cls,
        *,
        run: NavigationRunContext,
        query: CachedRouteExecutionTaskInput,
        output: CachedRouteExecutionTaskOutput,
    ) -> CachedRouteExecutionTaskOutput:
        trace_path = write_trace_artifact(
            run=run,
            agent_name=cls.AGENT_NAME,
            trace_kind="route_cache",
            input_messages=[HumanMessage(content=query.model_dump_json(indent=2))],
            output_messages=[AIMessage(content=output.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=output,
            metadata={"subagent_name": "route-cache"},
        )
        return output.model_copy(update={"trace_path": str(trace_path)})


class ClearfactsNavigationRoutePlannerSubAgent:
    AGENT_NAME = "clearfacts-navigation-route-planner-subagent"
    AGENT_OPERATION = "plan-known-navigation-route"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
        reasoning: dict[str, Any] | None = None,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens, reasoning=reasoning)
        self._llm = llm.with_structured_output(RoutePlanningTaskOutput)

    def invoke(self, query: RoutePlanningTaskInput) -> RoutePlanningTaskOutput:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        current_ontology_yaml = query.current_ontology_yaml
        if not current_ontology_yaml:
            current_ontology_yaml = yaml.safe_dump(
                load_navigation_ontology(run.run_ontology).model_dump(mode="json"),
                sort_keys=False,
                allow_unicode=False,
            )
        prompt = ROUTE_PLANNER_USER_PROMPT_TEMPLATE.format(
            source_name=query.source_name,
            user_goal=query.user_goal,
            role=query.role,
            current_page_yaml=yaml.safe_dump(
                query.current_page.model_dump(mode="json", exclude_none=True) if query.current_page else {},
                sort_keys=False,
                allow_unicode=False,
            ),
            current_ontology_yaml=current_ontology_yaml,
        )
        input_messages: list[BaseMessage] = [
            SystemMessage(content=ROUTE_PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            response = self._llm.invoke(input_messages)
        response = response.model_copy(update={"subagent_name": "route-planner"})
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="subagent",
            input_messages=input_messages,
            output_messages=[AIMessage(content=response.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=response,
            metadata={"subagent_name": "route-planner"},
        )
        return response.model_copy(update={"trace_path": str(trace_path)})


class ClearfactsNavigationRecoverySubAgent:
    AGENT_NAME = "clearfacts-navigation-recovery-subagent"
    AGENT_OPERATION = "analyze-navigation-recovery"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
        reasoning: dict[str, Any] | None = None,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens, reasoning=reasoning)
        self._llm = llm.with_structured_output(RecoveryAnalysisTaskOutput)

    def invoke(self, query: RecoveryAnalysisTaskInput) -> RecoveryAnalysisTaskOutput:
        run = ensure_navigation_run(query.execution.raw_result.source_name, timestamp=query.execution.run_timestamp)
        prompt = RECOVERY_ANALYZER_USER_PROMPT_TEMPLATE.format(
            user_goal=query.user_goal,
            execution_result_yaml=build_execution_result_yaml(query.execution),
        )
        input_messages: list[BaseMessage] = [
            SystemMessage(content=RECOVERY_ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            response = self._llm.invoke(input_messages)
        response = response.model_copy(update={"subagent_name": "recovery-analyzer"})
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="subagent",
            input_messages=input_messages,
            output_messages=[AIMessage(content=response.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=response,
            metadata={"subagent_name": "recovery-analyzer"},
        )
        return response.model_copy(update={"trace_path": str(trace_path)})


class ClearfactsNavigationGoalAssessmentSubAgent:
    AGENT_NAME = "clearfacts-navigation-goal-assessor-subagent"
    AGENT_OPERATION = "assess-navigation-goal-progress"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
        reasoning: dict[str, Any] | None = None,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens, reasoning=reasoning)
        self._llm = llm.with_structured_output(GoalAssessmentTaskOutput)

    def invoke(self, query: GoalAssessmentTaskInput) -> GoalAssessmentTaskOutput:
        run = ensure_navigation_run(query.execution.raw_result.source_name, timestamp=query.execution.run_timestamp)
        prompt = GOAL_ASSESSOR_USER_PROMPT_TEMPLATE.format(
            user_goal=query.user_goal,
            execution_result_yaml=build_execution_result_yaml(query.execution),
        )
        input_messages: list[BaseMessage] = [
            SystemMessage(content=GOAL_ASSESSOR_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            response = self._llm.invoke(input_messages)
        response = response.model_copy(update={"subagent_name": "goal-assessor"})
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="subagent",
            input_messages=input_messages,
            output_messages=[AIMessage(content=response.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=response,
            metadata={"subagent_name": "goal-assessor"},
        )
        return response.model_copy(update={"trace_path": str(trace_path)})


class ClearfactsNavigationValidationSubAgent:
    AGENT_NAME = "clearfacts-navigation-validation-subagent"
    AGENT_OPERATION = "assess-navigation-validation-claim"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
        reasoning: dict[str, Any] | None = None,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens, reasoning=reasoning)
        self._llm = llm.with_structured_output(ValidationAssessmentTaskOutput)

    def invoke(self, query: ValidationAssessmentTaskInput) -> ValidationAssessmentTaskOutput:
        run = ensure_navigation_run(query.execution.source_name, timestamp=query.execution.run_timestamp)
        prompt = VALIDATION_ASSESSOR_USER_PROMPT_TEMPLATE.format(
            claim=query.claim,
            procedure_instruction=query.procedure_instruction,
            execution_result_yaml=yaml.safe_dump(
                query.execution.model_dump(mode="json", exclude_none=True),
                sort_keys=False,
                allow_unicode=False,
            ),
        )
        input_messages: list[BaseMessage] = [
            SystemMessage(content=VALIDATION_ASSESSOR_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            response = self._llm.invoke(input_messages)
        response = response.model_copy(update={"subagent_name": "validation-assessor"})
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="subagent",
            input_messages=input_messages,
            output_messages=[AIMessage(content=response.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=response,
            metadata={"subagent_name": "validation-assessor"},
        )
        return response.model_copy(update={"trace_path": str(trace_path)})


class ClearfactsNavigationOntologyBatchAnalyzer:
    AGENT_NAME = "clearfacts-navigation-ontology-batch-analyzer"
    AGENT_OPERATION = "analyze-navigation-evidence-for-ontology"
    SNAPSHOT_TEXT_LIMIT = 600
    EVENT_MESSAGE_LIMIT = 180
    EVENT_ARGUMENT_LIMIT = 350

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
        reasoning: dict[str, Any] | None = None,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(
            model_name=model_name,
            max_tokens=max_tokens,
            reasoning={"effort": "low"} if reasoning is None else reasoning,
        )
        self._llm = llm.with_structured_output(OntologyBatchAnalysisTaskOutput)

    def prepare_evidence_batch(
        self,
        run: NavigationRunContext,
        query: ClearfactsNavigationOntologyUpdateRequest,
    ) -> OntologyEvidenceBatch:
        all_events = read_navigation_events(run)
        manifest = load_manifest(run.manifest_path)
        candidate_events = self._events_after_ontology_marker(all_events, manifest)
        selected_events, processed_event = self._select_ontology_events(
            candidate_events,
            max_events=query.max_events,
        )
        payloads = self._event_payloads(selected_events)
        payload_chars = len(
            yaml.safe_dump(
                payloads,
                sort_keys=False,
                allow_unicode=False,
            )
        )
        processed_event_id = processed_event.event_id if processed_event else None
        processed_event_count = self._event_count_through(all_events, processed_event)
        if processed_event is None and not candidate_events and all_events:
            processed_event_id = all_events[-1].event_id
            processed_event_count = len(all_events)
        return OntologyEvidenceBatch(
            all_event_count=len(all_events),
            candidate_event_count=len(candidate_events),
            selected_events=selected_events,
            payloads=payloads,
            selected_event_ids=[event.event_id for event in selected_events],
            processed_event_id=processed_event_id,
            processed_event_count=processed_event_count,
            payload_chars=payload_chars,
        )

    def invoke(
        self,
        query: ClearfactsNavigationOntologyUpdateRequest,
        *,
        evidence_batch: OntologyEvidenceBatch | None = None,
    ) -> tuple[OntologyBatchAnalysisTaskOutput, str]:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        evidence_batch = evidence_batch or self.prepare_evidence_batch(run, query)
        ontology = load_navigation_ontology(run.run_ontology)
        prompt = ONTOLOGY_BATCH_ANALYZER_USER_PROMPT_TEMPLATE.format(
            navigation_source_yaml=yaml.safe_dump(
                build_prompt_source_context(run.source, query.role),
                sort_keys=False,
                allow_unicode=False,
            ),
            update_request_yaml=yaml.safe_dump(
                query.model_dump(mode="json", exclude_none=True),
                sort_keys=False,
                allow_unicode=False,
            ),
            current_ontology_yaml=yaml.safe_dump(
                ontology.model_dump(mode="json"),
                sort_keys=False,
                allow_unicode=False,
            ),
            events_yaml=yaml.safe_dump(
                evidence_batch.payloads,
                sort_keys=False,
                allow_unicode=False,
            ),
        )
        prompt_chars = len(prompt)
        input_messages: list[BaseMessage] = [
            SystemMessage(content=ONTOLOGY_BATCH_ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        trace_metadata = {
            "all_event_count": evidence_batch.all_event_count,
            "candidate_event_count": evidence_batch.candidate_event_count,
            "analyzed_event_count": len(evidence_batch.selected_events),
            "selected_event_ids": evidence_batch.selected_event_ids,
            "processed_event_id": evidence_batch.processed_event_id,
            "processed_event_count": evidence_batch.processed_event_count,
            "evidence_payload_chars": evidence_batch.payload_chars,
            "prompt_chars": prompt_chars,
        }
        try:
            with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
                response = self._llm.invoke(input_messages)
        except Exception as exc:
            trace_path = write_trace_artifact(
                run=run,
                agent_name=self.AGENT_NAME,
                trace_kind="ontology_batch_failed",
                input_messages=input_messages,
                output_messages=[],
                structured_input=query,
                structured_output={
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                metadata=trace_metadata,
            )
            raise RuntimeError(
                "Ontology batch analyzer failed after selecting "
                f"{len(evidence_batch.selected_events)} compact event(s). "
                f"Trace: {trace_path}. Original error: {exc}"
            ) from exc
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="ontology_batch",
            input_messages=input_messages,
            output_messages=[AIMessage(content=response.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=response,
            metadata=trace_metadata,
        )
        return response, str(trace_path)

    @classmethod
    def _event_payloads(cls, events: list[NavigationEventRecord]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for event in events:
            payload = {
                "event_id": event.event_id,
                "step_index": event.step_index,
                "phase": event.phase,
                "status": event.status,
            }
            if event.message:
                compact_message = cls._compact_event_message(event)
                if compact_message:
                    payload["message"] = compact_message
            if event.tool_name:
                payload["tool_name"] = event.tool_name
            if event.arguments:
                payload["arguments"] = cls._compact_value(event.arguments, max_chars=cls.EVENT_ARGUMENT_LIMIT)
            if event.page_url:
                payload["page_url"] = event.page_url
            if event.page_title:
                payload["page_title"] = event.page_title
            snapshot_path = event.snapshot_path
            if snapshot_path:
                path = Path(str(snapshot_path))
                payload["snapshot_ref"] = str(path)
                snapshot_evidence = cls._snapshot_evidence(path)
                if snapshot_evidence:
                    payload["snapshot_evidence"] = snapshot_evidence
            payloads.append(payload)
        return payloads

    @classmethod
    def _events_after_ontology_marker(
        cls,
        events: list[NavigationEventRecord],
        manifest: dict[str, Any],
    ) -> list[NavigationEventRecord]:
        marker_count = cls._as_int(manifest.get("last_ontology_update_event_count"))
        marker_id = manifest.get("last_ontology_update_event_id")
        if marker_count and marker_count <= len(events):
            marker_event = events[marker_count - 1]
            if not marker_id or marker_event.event_id == marker_id:
                return events[marker_count:]

        if marker_id:
            for index, event in enumerate(events):
                if event.event_id == marker_id:
                    return events[index + 1 :]

        return events

    @classmethod
    def _select_ontology_events(
        cls,
        candidate_events: list[NavigationEventRecord],
        *,
        max_events: int,
    ) -> tuple[list[NavigationEventRecord], NavigationEventRecord | None]:
        selected_events: list[NavigationEventRecord] = []
        seen_page_fingerprints: set[tuple[str | None, ...]] = set()
        processed_event: NavigationEventRecord | None = None

        for event in candidate_events:
            if cls._is_ontology_relevant_event(event, seen_page_fingerprints=seen_page_fingerprints):
                selected_events.append(event)
                fingerprint = cls._page_fingerprint(event)
                if fingerprint is not None:
                    seen_page_fingerprints.add(fingerprint)
                processed_event = event
                if len(selected_events) >= max_events:
                    return selected_events, processed_event
            else:
                processed_event = event

        if candidate_events and len(selected_events) < max_events:
            processed_event = candidate_events[-1]
        return selected_events, processed_event

    @staticmethod
    def _is_ontology_relevant_event(
        event: NavigationEventRecord,
        *,
        seen_page_fingerprints: set[tuple[str | None, ...]],
    ) -> bool:
        phase = event.phase.lower()
        status = event.status.lower()

        if status in {"failed", "blocked", "needs_user_input"}:
            return True
        if phase in {"action", "result", "decision", "ontology"}:
            return True
        if phase == "bootstrap":
            return bool(event.snapshot_path or event.page_url or event.page_title)
        if phase != "observation":
            return False
        if not (event.snapshot_path or event.page_url or event.page_title):
            return False

        fingerprint = ClearfactsNavigationOntologyBatchAnalyzer._page_fingerprint(event)
        return fingerprint is not None and fingerprint not in seen_page_fingerprints

    @staticmethod
    def _event_count_through(
        all_events: list[NavigationEventRecord],
        processed_event: NavigationEventRecord | None,
    ) -> int:
        if processed_event is None:
            return 0
        for index, event in enumerate(all_events):
            if event.event_id == processed_event.event_id:
                return index + 1
        return 0

    @classmethod
    def _snapshot_evidence(cls, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"missing": True}

        text = path.read_text(encoding="utf-8")
        evidence: dict[str, Any] = {"source_chars": len(text)}
        human_summary = cls._markdown_section(text, "Human summary")
        if human_summary:
            evidence["summary_facts"] = cls._compact_human_summary(human_summary)
        else:
            text_excerpt = cls._markdown_section(text, "Text excerpt")
            if text_excerpt:
                evidence["visible_text_excerpt"] = cls._truncate(
                    cls._compact_text_lines(text_excerpt),
                    cls.SNAPSHOT_TEXT_LIMIT,
                )
        return evidence

    @classmethod
    def _compact_event_message(cls, event: NavigationEventRecord) -> str | None:
        message = (event.message or "").strip()
        if not message:
            return None
        if message in {
            "Captured page evidence before executing the browser operation.",
            "Captured current browser evidence.",
        }:
            return None
        if message.startswith("### Ran Playwright code"):
            if event.phase.lower() == "action":
                return f"Browser action {event.status}."
            return f"Browser operation {event.status}."
        return cls._truncate(message, cls.EVENT_MESSAGE_LIMIT)

    @staticmethod
    def _markdown_section(text: str, heading: str) -> str:
        marker = f"## {heading}"
        start = text.find(marker)
        if start < 0:
            return ""
        section = text[start + len(marker) :]
        end = section.find("\n## ")
        if end >= 0:
            section = section[:end]
        lines = []
        for line in section.splitlines():
            stripped = line.strip()
            if stripped == "```":
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    @staticmethod
    def _compact_text_lines(text: str, *, max_lines: int = 80) -> str:
        lines: list[str] = []
        previous = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line == previous:
                continue
            lines.append(line)
            previous = line
            if len(lines) >= max_lines:
                break
        return "\n".join(lines)

    @classmethod
    def _compact_human_summary(cls, text: str) -> dict[str, Any]:
        facts: dict[str, Any] = {}
        for label, key in (
            ("Page title", "page_title"),
            ("URL", "url"),
        ):
            value = cls._inline_summary_value(text, label)
            if value:
                facts[key] = value

        section_specs = (
            ("Headings", "headings", 8),
            ("Buttons and clickable actions", "actions", 8),
            ("Links", "links", 12),
            ("Inputs and form fields", "inputs", 8),
        )
        for heading, key, limit in section_specs:
            values = cls._summary_list_section(text, heading, limit=limit)
            if values:
                facts[key] = values
        return facts

    @staticmethod
    def _inline_summary_value(text: str, label: str) -> str | None:
        pattern = re.compile(rf"^\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$", flags=re.MULTILINE)
        match = pattern.search(text)
        if not match:
            return None
        return match.group(1).strip()[:180] or None

    @staticmethod
    def _summary_list_section(text: str, heading: str, *, limit: int) -> list[str]:
        marker = f"**{heading}**"
        start = text.find(marker)
        if start < 0:
            return []
        section = text[start + len(marker) :]
        end_match = re.search(r"\n\*\*[^*]+?\*\*", section)
        if end_match:
            section = section[: end_match.start()]

        values: list[str] = []
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line.startswith("- "):
                continue
            value = line[2:].strip()
            if not value:
                continue
            values.append(value[:180])
            if len(values) >= limit:
                break
        return values

    @classmethod
    def _page_fingerprint(cls, event: NavigationEventRecord) -> tuple[str | None, ...] | None:
        if event.snapshot_path:
            path = Path(event.snapshot_path)
            if path.exists():
                summary = cls._markdown_section(path.read_text(encoding="utf-8"), "Human summary")
                facts = cls._compact_human_summary(summary) if summary else {}
                headings = tuple((facts.get("headings") or [])[:4])
                if headings:
                    return (
                        event.page_url,
                        event.page_title,
                        "|".join(headings),
                    )
        if event.page_url or event.page_title:
            return (event.page_url, event.page_title)
        return None

    @classmethod
    def _compact_value(cls, value: Any, *, max_chars: int) -> Any:
        if value is None or isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            return cls._truncate(value, max_chars)
        if isinstance(value, dict):
            compact: dict[str, Any] = {}
            for key, item in list(value.items())[:20]:
                compact[str(key)] = cls._compact_value(item, max_chars=max(120, max_chars // 4))
            return compact
        if isinstance(value, list):
            return [cls._compact_value(item, max_chars=max(120, max_chars // 4)) for item in value[:20]]
        return cls._truncate(str(value), max_chars)

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 20].rstrip() + "\n...[truncated]"

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None


class ClearfactsNavigationDeepAgent:
    AGENT_NAME = "clearfacts-navigation-deepagent"
    AGENT_OPERATION = "orchestrate-clearfacts-navigation"

    def __init__(
        self,
        model_name: str | None = None,
        max_tokens: int = 4000,
        model_profile: str | NavigationAgentModelProfile | None = None,
    ) -> None:
        init_token_tracking()
        if isinstance(model_profile, NavigationAgentModelProfile):
            resolved_profile = model_profile
        elif model_profile is not None or model_name is None:
            resolved_profile = load_navigation_agent_model_profile(model_profile)
        else:
            resolved_profile = single_model_navigation_agent_model_profile(
                model_name=model_name,
                max_tokens=max_tokens,
                ontology_reasoning={"effort": "low"},
            )
        self._model_profile = resolved_profile
        self._model_name = resolved_profile.coordinator.model_name
        self._max_tokens = resolved_profile.coordinator.max_tokens
        self._coordinator_model = self._build_llm(resolved_profile.coordinator)
        self._route_planner_subagent = ClearfactsNavigationRoutePlannerSubAgent(
            **self._role_model_kwargs(resolved_profile.route_planner)
        )
        self._execution_subagent = ClearfactsNavigationExecutionSubAgent(
            model_name=resolved_profile.coordinator.model_name,
            max_tokens=resolved_profile.coordinator.max_tokens,
        )
        self._route_cache_executor = ClearfactsNavigationRouteCacheExecutor(execution=self._execution_subagent)
        self._recovery_subagent = ClearfactsNavigationRecoverySubAgent(
            **self._role_model_kwargs(resolved_profile.recovery)
        )
        self._goal_assessment_subagent = ClearfactsNavigationGoalAssessmentSubAgent(
            **self._role_model_kwargs(resolved_profile.goal_assessor)
        )
        self._validation_subagent = ClearfactsNavigationValidationSubAgent(
            **self._role_model_kwargs(resolved_profile.validation)
        )
        self._ontology_batch_analyzer = ClearfactsNavigationOntologyBatchAnalyzer(
            **self._role_model_kwargs(resolved_profile.ontology_batch_analyzer)
        )

    @staticmethod
    def _build_llm(config: NavigationAgentRoleModelConfig):
        return get_azure_llm(
            model_name=config.model_name,
            max_tokens=config.max_tokens,
            reasoning=config.reasoning,
        )

    @staticmethod
    def _role_model_kwargs(config: NavigationAgentRoleModelConfig) -> dict[str, Any]:
        return {
            "model_name": config.model_name,
            "max_tokens": config.max_tokens,
            "reasoning": config.reasoning,
        }

    def invoke(
        self,
        query: ClearfactsNavigationDeepAgentRequest,
        browser: Any | None = None,
    ) -> ClearfactsNavigationDeepAgentResult:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        if browser is not None:
            cached_result = self._try_direct_cached_route(query=query, run=run, browser=browser)
            if cached_result is not None:
                return cached_result

        coordinator = self._build_agent(run=run, browser=browser)
        prompt = self._build_user_prompt(query=query, run=run)
        input_messages: list[BaseMessage] = [HumanMessage(content=prompt)]

        try:
            with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
                result = coordinator.invoke({"messages": [{"role": "user", "content": prompt}]})
        except Exception as exc:
            logger.exception("Clearfacts navigation coordinator failed.")
            structured_response = DeepAgentCoordinatorStructuredResponse(
                status=DeepAgentExecutionStatus.FAILED,
                summary=f"The navigation coordinator failed before returning a structured response: {exc}",
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
            )
            update_manifest(run.manifest_path, status=structured_response.status.value)
            write_trace_artifact(
                run=run,
                agent_name=self.AGENT_NAME,
                trace_kind="coordinator",
                input_messages=input_messages,
                output_messages=[],
                structured_input=query,
                structured_output=structured_response,
                metadata={"error": repr(exc)},
            )
            return ClearfactsNavigationDeepAgentResult(
                status=structured_response.status,
                source_name=query.source_name,
                instruction=query.instruction,
                role=query.role,
                message=structured_response.summary,
                question_for_user=structured_response.question_for_user,
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
                trace_references=build_trace_references(run),
            )

        structured_response = self._coordinator_structured_response(result, run=run, query=query)
        manifest_updates: dict[str, Any] = {"status": structured_response.status.value}
        if structured_response.latest_page_url is not None:
            manifest_updates["last_observed_url"] = structured_response.latest_page_url
        if structured_response.latest_page_title is not None:
            manifest_updates["last_observed_title"] = structured_response.latest_page_title
        update_manifest(run.manifest_path, **manifest_updates)
        write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="coordinator",
            input_messages=input_messages,
            output_messages=result["messages"],
            structured_input=query,
            structured_output=structured_response,
        )
        trace_references = build_trace_references(run)
        latest_navigation_result = self._latest_navigation_result_from_messages(result["messages"])
        current_page = latest_navigation_result.current_page if latest_navigation_result else None
        return ClearfactsNavigationDeepAgentResult(
            status=structured_response.status,
            source_name=query.source_name,
            instruction=query.instruction,
            role=query.role,
            message=structured_response.summary,
            question_for_user=structured_response.question_for_user,
            run_timestamp=structured_response.run_timestamp or run.timestamp,
            run_folder=structured_response.run_folder or str(run.run_dir),
            ontology_path=structured_response.ontology_path or str(run.run_ontology),
            current_page=current_page,
            latest_navigation_result=latest_navigation_result,
            trace_references=trace_references,
        )

    def _try_direct_cached_route(
        self,
        *,
        query: ClearfactsNavigationDeepAgentRequest,
        run: NavigationRunContext,
        browser: Any,
    ) -> ClearfactsNavigationDeepAgentResult | None:
        """Bypass the LLM coordinator when the deterministic cache fully solves the request."""
        ontology = load_navigation_ontology(run.run_ontology)
        chain, uncovered_targets = self._route_cache_executor._select_route_chain(
            ontology.navigation_paths,
            ontology,
            query.instruction,
        )
        if not chain or uncovered_targets:
            return None

        route_result = self._route_cache_executor.invoke(
            CachedRouteExecutionTaskInput(
                source_name=query.source_name,
                user_goal=query.instruction,
                role=query.role,
                run_timestamp=run.timestamp,
                include_snapshot=query.include_snapshot,
                max_steps=50,
            ),
            browser=browser,
        )
        latest_navigation = route_result.latest_navigation_result
        if (
            route_result.status != CachedRouteExecutionStatus.COMPLETED
            or latest_navigation is None
            or not _navigation_result_likely_satisfies_goal(query.instruction, latest_navigation)
        ):
            return None

        structured_response = self._response_from_latest_navigation(
            latest_navigation,
            run=run,
            query=query,
            reason="Completed directly from the deterministic route cache.",
        )
        manifest_updates: dict[str, Any] = {"status": structured_response.status.value}
        if structured_response.latest_page_url is not None:
            manifest_updates["last_observed_url"] = structured_response.latest_page_url
        if structured_response.latest_page_title is not None:
            manifest_updates["last_observed_title"] = structured_response.latest_page_title
        update_manifest(run.manifest_path, **manifest_updates)
        write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="coordinator",
            input_messages=[HumanMessage(content=query.instruction)],
            output_messages=[],
            structured_input=query,
            structured_output=structured_response,
            metadata={
                "short_circuit": "deterministic_route_cache",
                "route_cache_trace_path": route_result.trace_path,
            },
        )
        return ClearfactsNavigationDeepAgentResult(
            status=structured_response.status,
            source_name=query.source_name,
            instruction=query.instruction,
            role=query.role,
            message=structured_response.summary,
            question_for_user=structured_response.question_for_user,
            run_timestamp=structured_response.run_timestamp or run.timestamp,
            run_folder=structured_response.run_folder or str(run.run_dir),
            ontology_path=structured_response.ontology_path or str(run.run_ontology),
            current_page=latest_navigation.current_page,
            latest_navigation_result=latest_navigation,
            trace_references=build_trace_references(run),
        )

    def update_ontology(
        self,
        query: ClearfactsNavigationOntologyUpdateRequest,
    ) -> ClearfactsNavigationOntologyUpdateResult:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        evidence_batch = self._ontology_batch_analyzer.prepare_evidence_batch(run, query)
        if not evidence_batch.selected_events:
            summary = (
                "No new ontology-relevant navigation events were found since the last ontology update."
                if evidence_batch.candidate_event_count
                else "No new navigation events were found since the last ontology update."
            )
            backfilled_count = backfill_navigation_ontology_file(
                run.run_ontology,
                source_base_url=run.source.base_url,
            ) + backfill_navigation_ontology_file(
                run.baseline_ontology,
                source_base_url=run.source.base_url,
            )
            if backfilled_count:
                summary = f"{summary} Backfilled {backfilled_count} typed route step(s) from existing route steps."
            update_manifest(
                run.manifest_path,
                status="ontology_noop",
                last_ontology_update_summary=summary,
                last_ontology_update_trace=None,
                last_ontology_update_open_issues=[],
                last_ontology_update_event_count=evidence_batch.processed_event_count,
                last_ontology_update_event_id=evidence_batch.processed_event_id,
                last_ontology_update_candidate_event_count=evidence_batch.candidate_event_count,
                last_ontology_update_analyzed_event_count=0,
                last_ontology_update_payload_chars=0,
                last_ontology_update_backfilled_typed_route_steps=backfilled_count,
            )
            return ClearfactsNavigationOntologyUpdateResult(
                status="no_new_events",
                summary=summary,
                source_name=run.source.source_name,
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
                source_ontology_path=str(run.baseline_ontology),
                analyzed_event_count=0,
                merged_counts=self._delta_counts(NavigationOntologyDelta()),
                ontology_delta=NavigationOntologyDelta(),
                open_issues=[],
                trace_path=None,
                trace_references=build_trace_references(run),
            )

        try:
            analysis, trace_path = self._ontology_batch_analyzer.invoke(query, evidence_batch=evidence_batch)
        except Exception as exc:
            update_manifest(
                run.manifest_path,
                status="ontology_update_failed",
                last_ontology_update_summary=str(exc),
                last_ontology_update_candidate_event_count=evidence_batch.candidate_event_count,
                last_ontology_update_analyzed_event_count=len(evidence_batch.selected_events),
                last_ontology_update_payload_chars=evidence_batch.payload_chars,
                last_ontology_update_selected_event_ids=evidence_batch.selected_event_ids,
            )
            raise
        ontology_delta = analysis.ontology_delta
        if analysis.open_issues:
            ontology_delta = ontology_delta.model_copy(
                update={
                    "open_questions": list(dict.fromkeys([*ontology_delta.open_questions, *analysis.open_issues])),
                }
            )
        merge_navigation_ontology(run.run_ontology, ontology_delta, source_base_url=run.source.base_url)
        merge_navigation_ontology(run.baseline_ontology, ontology_delta, source_base_url=run.source.base_url)
        update_manifest(
            run.manifest_path,
            status="ontology_updated",
            last_ontology_update_summary=analysis.summary,
            last_ontology_update_trace=trace_path,
            last_ontology_update_open_issues=analysis.open_issues,
            last_ontology_update_source_ontology=str(run.baseline_ontology),
            last_ontology_update_event_count=evidence_batch.processed_event_count,
            last_ontology_update_event_id=evidence_batch.processed_event_id,
            last_ontology_update_candidate_event_count=evidence_batch.candidate_event_count,
            last_ontology_update_analyzed_event_count=len(evidence_batch.selected_events),
            last_ontology_update_payload_chars=evidence_batch.payload_chars,
            last_ontology_update_selected_event_ids=evidence_batch.selected_event_ids,
        )
        return ClearfactsNavigationOntologyUpdateResult(
            status="updated",
            summary=analysis.summary,
            source_name=run.source.source_name,
            run_timestamp=run.timestamp,
            run_folder=str(run.run_dir),
            ontology_path=str(run.run_ontology),
            source_ontology_path=str(run.baseline_ontology),
            analyzed_event_count=len(evidence_batch.selected_events),
            merged_counts=self._delta_counts(ontology_delta),
            ontology_delta=ontology_delta,
            open_issues=analysis.open_issues,
            trace_path=trace_path,
            trace_references=build_trace_references(run),
        )

    def validate(
        self,
        query: ClearfactsNavigationValidationRequest,
        browser: Any | None = None,
    ) -> ClearfactsNavigationValidationResult:
        procedure_instruction = query.procedure_instruction or query.claim
        execution_result = self.invoke(
            ClearfactsNavigationDeepAgentRequest(
                source_name=query.source_name,
                instruction=procedure_instruction,
                role=query.role,
                run_timestamp=query.run_timestamp,
                include_snapshot=query.include_snapshot,
                execution_max_iterations=query.execution_max_iterations,
            ),
            browser=browser,
        )
        assessment = self._validation_subagent.invoke(
            ValidationAssessmentTaskInput(
                claim=query.claim,
                procedure_instruction=procedure_instruction,
                execution=execution_result,
            )
        )
        run = ensure_navigation_run(query.source_name, timestamp=execution_result.run_timestamp)
        write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="validation",
            input_messages=[HumanMessage(content=query.model_dump_json(indent=2))],
            output_messages=[AIMessage(content=assessment.model_dump_json(indent=2))],
            structured_input=query,
            structured_output=assessment,
            metadata={"procedure_instruction": procedure_instruction},
        )
        return ClearfactsNavigationValidationResult(
            outcome=assessment.outcome,
            claim=query.claim,
            procedure_instruction=procedure_instruction,
            role=query.role,
            summary=assessment.summary,
            question_for_user=assessment.question_for_user,
            run_timestamp=execution_result.run_timestamp,
            run_folder=execution_result.run_folder,
            ontology_path=execution_result.ontology_path,
            observed_evidence=assessment.observed_evidence,
            contradictions=assessment.contradictions,
            missing_evidence=assessment.missing_evidence,
            execution_result=execution_result,
            trace_references=build_trace_references(run),
        )

    def _build_agent(self, *, run: NavigationRunContext, browser: Any | None = None):
        tools = build_navigation_runtime_tools(
            route_cache=self._route_cache_executor,
            route_planner=self._route_planner_subagent,
            execution=self._execution_subagent,
            recovery=self._recovery_subagent,
            goal_assessment=self._goal_assessment_subagent,
            browser=browser,
        )
        return create_agent(
            model=self._coordinator_model,
            tools=tools,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            response_format=DeepAgentCoordinatorStructuredResponse,
            name=self.AGENT_NAME,
        )

    @staticmethod
    def _delta_counts(delta: Any) -> dict[str, int]:
        return {
            "screens": len(delta.screens),
            "actions": len(delta.actions),
            "labels": len(delta.labels),
            "navigation_paths": len(delta.navigation_paths),
            "validation_notes": len(delta.validation_notes),
            "open_questions": len(delta.open_questions),
        }

    def _build_user_prompt(
        self,
        *,
        query: ClearfactsNavigationDeepAgentRequest,
        run: NavigationRunContext,
    ) -> str:
        source = run.source
        ontology = load_navigation_ontology(run.run_ontology)
        recent_events = read_recent_navigation_events(run, limit=8)
        return COORDINATOR_USER_PROMPT_TEMPLATE.format(
            navigation_source_yaml=yaml.safe_dump(
                build_prompt_source_context(source, query.role),
                sort_keys=False,
                allow_unicode=False,
            ),
            user_request_yaml=yaml.safe_dump(
                query.model_dump(mode="json", exclude_none=True),
                sort_keys=False,
                allow_unicode=False,
            ),
            run_context_yaml=yaml.safe_dump(
                {
                    "run_folder": str(run.run_dir),
                    "run_timestamp": run.timestamp,
                    "role": query.role,
                    "execution_max_iterations": query.execution_max_iterations,
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            current_ontology_yaml=yaml.safe_dump(
                ontology.model_dump(mode="json"),
                sort_keys=False,
                allow_unicode=False,
            ),
            recent_events_yaml=yaml.safe_dump(
                [event.model_dump(mode="json", exclude_none=True) for event in recent_events],
                sort_keys=False,
                allow_unicode=False,
            ),
        )

    @staticmethod
    def _coordinator_structured_response(
        result: dict[str, Any],
        *,
        run: NavigationRunContext,
        query: ClearfactsNavigationDeepAgentRequest,
    ) -> DeepAgentCoordinatorStructuredResponse:
        structured = result.get("structured_response")
        if isinstance(structured, DeepAgentCoordinatorStructuredResponse):
            return structured
        if isinstance(structured, dict):
            try:
                return DeepAgentCoordinatorStructuredResponse.model_validate(structured)
            except ValidationError as exc:
                return DeepAgentCoordinatorStructuredResponse(
                    status=DeepAgentExecutionStatus.FAILED,
                    summary=f"The navigation coordinator returned an invalid structured response: {exc}",
                    run_timestamp=run.timestamp,
                    run_folder=str(run.run_dir),
                    ontology_path=str(run.run_ontology),
                )

        latest_navigation = ClearfactsNavigationDeepAgent._latest_navigation_result_from_messages(result.get("messages", []))
        if structured is None:
            if latest_navigation is not None:
                return ClearfactsNavigationDeepAgent._response_from_latest_navigation(
                    latest_navigation,
                    run=run,
                    query=query,
                    reason="The navigation coordinator finished without a structured response.",
                )
            return DeepAgentCoordinatorStructuredResponse(
                status=DeepAgentExecutionStatus.FAILED,
                summary="The navigation coordinator finished without a structured response.",
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
            )

        return DeepAgentCoordinatorStructuredResponse(
            status=DeepAgentExecutionStatus.FAILED,
            summary=f"The navigation coordinator returned an unsupported structured response type: {type(structured).__name__}.",
            run_timestamp=run.timestamp,
            run_folder=str(run.run_dir),
            ontology_path=str(run.run_ontology),
        )

    @staticmethod
    def _response_from_latest_navigation(
        latest_navigation: ClearfactsNavigationResult,
        *,
        run: NavigationRunContext,
        query: ClearfactsNavigationDeepAgentRequest,
        reason: str,
    ) -> DeepAgentCoordinatorStructuredResponse:
        status_mapping = {
            NavigationExecutionStatus.NEEDS_USER_INPUT: DeepAgentExecutionStatus.NEEDS_USER_INPUT,
            NavigationExecutionStatus.BLOCKED: DeepAgentExecutionStatus.BLOCKED,
            NavigationExecutionStatus.FAILED: DeepAgentExecutionStatus.FAILED,
        }
        if latest_navigation.status == NavigationExecutionStatus.COMPLETED:
            status = (
                DeepAgentExecutionStatus.COMPLETED
                if ClearfactsNavigationDeepAgent._latest_navigation_likely_satisfies_goal(
                    query.instruction,
                    latest_navigation,
                )
                else DeepAgentExecutionStatus.FAILED
            )
        else:
            status = status_mapping.get(latest_navigation.status, DeepAgentExecutionStatus.FAILED)

        page = latest_navigation.current_page
        latest_page = f"{page.title or 'current page'} at {page.url}" if page and page.url else "the latest observed page"
        if status == DeepAgentExecutionStatus.COMPLETED:
            summary = f"Reached {latest_page}. {reason}"
        else:
            summary = f"{reason} Latest browser step ended at {latest_page}, but the goal was not confidently assessed."
        return DeepAgentCoordinatorStructuredResponse(
            status=status,
            summary=summary,
            question_for_user=latest_navigation.question_for_user,
            latest_page_url=page.url if page else None,
            latest_page_title=page.title if page else None,
            run_timestamp=latest_navigation.run_timestamp,
            run_folder=latest_navigation.run_folder,
            ontology_path=latest_navigation.ontology_path,
        )

    @staticmethod
    def _latest_navigation_likely_satisfies_goal(goal: str, latest_navigation: ClearfactsNavigationResult) -> bool:
        return _navigation_result_likely_satisfies_goal(goal, latest_navigation)

    @staticmethod
    def _latest_navigation_result_from_messages(messages: list[BaseMessage]) -> Any | None:
        latest: Any | None = None
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            tool_name = getattr(message, "name", None)
            payload = None
            if isinstance(message.content, str):
                try:
                    payload = json.loads(message.content)
                except json.JSONDecodeError:
                    payload = None
            if not isinstance(payload, dict):
                continue
            if tool_name == "execute_cached_route":
                try:
                    route_cache_result = CachedRouteExecutionTaskOutput.model_validate(payload)
                except ValidationError:
                    logger.warning("Skipping invalid route cache tool payload.", exc_info=True)
                    continue
                if route_cache_result.latest_navigation_result is not None:
                    latest = route_cache_result.latest_navigation_result
                continue
            if tool_name and tool_name != "execute_browser_operation":
                continue
            if not tool_name and payload.get("subagent_name") != "navigation-executor":
                continue
            required_execution_fields = {"raw_result", "run_timestamp", "run_folder", "ontology_path"}
            if not required_execution_fields.issubset(payload):
                continue
            try:
                latest = NavigationExecutionTaskOutput.model_validate(payload).raw_result
            except ValidationError:
                logger.warning("Skipping invalid navigation execution tool payload.", exc_info=True)
        return latest
