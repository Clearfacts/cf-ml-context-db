from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import HumanMessage, SystemMessage

from cf_ml_common.llm.token_tracker import tracking_context
from context_db.llm.config import get_azure_llm, init_token_tracking

from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .schemas import (
    ClearfactsNavigationRequest,
    ExplorationActionType,
    ExplorationDecision,
    ExplorationDecisionState,
    NavigationExecutionStatus,
    NavigationOntologyDelta,
    NavigationPageEvidence,
)
from .tools import (
    BLANK_PAGE_URLS,
    PlaywrightMcpBrowser,
    PlaywrightToolExecutionError,
    _run_async_blocking,
    append_navigation_event,
    build_prompt_source_context,
    build_result,
    ensure_navigation_run,
    event_record,
    load_navigation_ontology,
    load_navigation_source,
    merge_navigation_ontology,
    prepare_playwright_run_config,
    read_recent_navigation_events,
    remap_snapshot_ref_target,
    resolve_role,
    resolve_role_credential,
    save_snapshot,
    update_manifest,
)

logger = logging.getLogger(__name__)


class ClearfactsNavigationAgent:
    AGENT_NAME = "clearfacts-navigation-agent"
    AGENT_OPERATION = "interactive-clearfacts-exploration"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens)
        self._planner = llm.with_structured_output(ExplorationDecision)

    def invoke(self, query: ClearfactsNavigationRequest, browser: Any | None = None):
        return _run_async_blocking(self._invoke_async(query, browser=browser))

    async def _invoke_async(self, query: ClearfactsNavigationRequest, browser: Any | None = None):
        source = load_navigation_source(query.source_name)
        role = resolve_role(source, query.role)
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        manifest = update_manifest(
            run.manifest_path,
            status="running",
            last_instruction=query.instruction,
            last_role=role,
        )

        runtime_config = prepare_playwright_run_config(source, run)

        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            if browser is None:
                async with PlaywrightMcpBrowser(runtime_config) as managed_browser:
                    return await self._run_navigation_loop(
                        query=query,
                        source=source,
                        role=role,
                        run=run,
                        manifest=manifest,
                        browser=managed_browser,
                    )
            return await self._run_navigation_loop(
                query=query,
                source=source,
                role=role,
                run=run,
                manifest=manifest,
                browser=browser,
            )

    async def _run_navigation_loop(self, *, query, source, role, run, manifest, browser):
        current_page: NavigationPageEvidence | None = None
        events = []
        tool_inventory = browser.tool_inventory()
        current_page, bootstrap_event = await self._bootstrap_browser(
            browser=browser,
            source=source,
            manifest=manifest,
            run=run,
            include_snapshot=query.include_snapshot,
        )
        append_navigation_event(run, bootstrap_event)
        events.append(bootstrap_event)
        update_manifest(
            run.manifest_path,
            last_observed_url=current_page.url,
            last_observed_title=current_page.title,
        )

        for step_index in range(1, query.max_iterations + 1):
            ontology = load_navigation_ontology(run.run_ontology)
            recent_events = read_recent_navigation_events(run, limit=6)
            decision = self._decide_next_step(
                query=query,
                role=role,
                run_folder=run.run_dir,
                source=source,
                ontology=ontology,
                current_page=current_page,
                recent_events=recent_events,
                step_index=step_index,
            )

            evidence_token = f"event:{step_index:02d}:observation"
            annotated_delta = self._annotate_ontology_delta(decision.ontology_update, evidence_token)
            if self._delta_has_content(annotated_delta):
                merge_navigation_ontology(run.run_ontology, annotated_delta)
                ontology_event = event_record(
                    step_index=step_index,
                    phase="ontology",
                    status="updated",
                    message="Merged ontology updates from the latest exploration decision.",
                    page=current_page,
                )
                append_navigation_event(run, ontology_event)
                events.append(ontology_event)

            decision_log = run.logs_dir / f"step_{step_index:02d}_decision.json"
            decision_log.write_text(
                json.dumps(decision.model_dump(mode="json"), indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            decision_event = event_record(
                step_index=step_index,
                phase="decision",
                status=decision.state.value,
                message=decision.summary,
                page=current_page,
            )
            append_navigation_event(run, decision_event)
            events.append(decision_event)

            if decision.state == ExplorationDecisionState.COMPLETED:
                update_manifest(
                    run.manifest_path,
                    status="completed",
                    last_observed_url=current_page.url if current_page else None,
                    last_observed_title=current_page.title if current_page else None,
                )
                return build_result(
                    status=NavigationExecutionStatus.COMPLETED,
                    run=run,
                    instruction=query.instruction,
                    role=role,
                    events=events,
                    current_page=current_page,
                    tool_inventory=tool_inventory,
                    message=decision.summary,
                )

            if decision.state == ExplorationDecisionState.NEEDS_USER_INPUT:
                update_manifest(
                    run.manifest_path,
                    status="needs_user_input",
                    last_observed_url=current_page.url if current_page else None,
                    last_observed_title=current_page.title if current_page else None,
                )
                return build_result(
                    status=NavigationExecutionStatus.NEEDS_USER_INPUT,
                    run=run,
                    instruction=query.instruction,
                    role=role,
                    events=events,
                    current_page=current_page,
                    tool_inventory=tool_inventory,
                    message=decision.summary,
                    question_for_user=decision.user_question,
                )

            if decision.state == ExplorationDecisionState.BLOCKED:
                update_manifest(
                    run.manifest_path,
                    status="blocked",
                    last_observed_url=current_page.url if current_page else None,
                    last_observed_title=current_page.title if current_page else None,
                )
                return build_result(
                    status=NavigationExecutionStatus.BLOCKED,
                    run=run,
                    instruction=query.instruction,
                    role=role,
                    events=events,
                    current_page=current_page,
                    tool_inventory=tool_inventory,
                    message=decision.summary,
                    question_for_user=decision.user_question,
                )

            action = decision.next_action
            assert action is not None  # validated by schema
            try:
                action_call = await self._execute_action(
                    browser=browser,
                    action=action,
                    role=role,
                    source=source,
                    current_page=current_page,
                )
            except PlaywrightToolExecutionError as exc:
                current_page = await browser.inspect_page(include_snapshot=True)
                failure_snapshot = save_snapshot(run, step_index=step_index, phase="action_failed", page=current_page)
                action_event = event_record(
                    step_index=step_index,
                    phase="action",
                    status="failed",
                    message=exc.message,
                    tool_name=exc.tool_name,
                    arguments=exc.arguments,
                    snapshot_path=failure_snapshot,
                    page=current_page,
                )
                append_navigation_event(run, action_event)
                events.append(action_event)
                update_manifest(
                    run.manifest_path,
                    status="blocked",
                    last_observed_url=current_page.url if current_page else None,
                    last_observed_title=current_page.title if current_page else None,
                )
                return build_result(
                    status=NavigationExecutionStatus.BLOCKED,
                    run=run,
                    instruction=query.instruction,
                    role=role,
                    events=events,
                    current_page=current_page,
                    tool_inventory=tool_inventory,
                    message=exc.message,
                )

            action_event = event_record(
                step_index=step_index,
                phase="action",
                status="completed",
                message=action_call.message or action.summary,
                tool_name=action_call.tool_name,
                arguments=action_call.arguments,
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
                message=action.expected_outcome,
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

        update_manifest(
            run.manifest_path,
            status="blocked",
            last_observed_url=current_page.url if current_page else None,
            last_observed_title=current_page.title if current_page else None,
        )
        return build_result(
            status=NavigationExecutionStatus.BLOCKED,
            run=run,
            instruction=query.instruction,
            role=role,
            events=events,
            current_page=current_page,
            tool_inventory=tool_inventory,
            message="The exploration loop reached max_iterations before the goal was clearly completed.",
        )

    async def _bootstrap_browser(self, *, browser, source, manifest, run, include_snapshot: bool):
        current_page = await browser.inspect_page(include_snapshot=include_snapshot)
        if current_page.url and current_page.url not in BLANK_PAGE_URLS:
            bootstrap_snapshot = save_snapshot(run, step_index=0, phase="bootstrap", page=current_page)
            bootstrap_event = event_record(
                step_index=0,
                phase="bootstrap",
                status="reused",
                message=f"Reused active browser session at {current_page.url}.",
                tool_name="persistent-browser-reuse",
                arguments={},
                snapshot_path=bootstrap_snapshot,
                page=current_page,
            )
            return current_page, bootstrap_event

        start_url = manifest.get("last_observed_url") or source.base_url
        bootstrap_call = await browser.navigate(start_url)
        current_page = await browser.inspect_page(include_snapshot=include_snapshot)
        bootstrap_snapshot = save_snapshot(run, step_index=0, phase="bootstrap", page=current_page)
        bootstrap_event = event_record(
            step_index=0,
            phase="bootstrap",
            status="completed",
            message=bootstrap_call.message,
            tool_name=bootstrap_call.tool_name,
            arguments=bootstrap_call.arguments,
            snapshot_path=bootstrap_snapshot,
            page=current_page,
        )
        return current_page, bootstrap_event

    def _decide_next_step(
        self,
        *,
        query: ClearfactsNavigationRequest,
        role: str | None,
        run_folder: Path,
        source,
        ontology,
        current_page: NavigationPageEvidence | None,
        recent_events,
        step_index: int,
    ) -> ExplorationDecision:
        prompt = USER_PROMPT_TEMPLATE.format(
            navigation_source_yaml=yaml.safe_dump(
                build_prompt_source_context(source, role),
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
                    "run_folder": str(run_folder),
                    "step_index": step_index,
                    "role": role,
                    "latest_observed_url": current_page.url if current_page else None,
                    "latest_observed_title": current_page.title if current_page else None,
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            current_page_yaml=yaml.safe_dump(
                (current_page.model_dump(mode="json", exclude_none=True) if current_page else {}),
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

        prompt_path = run_folder / "logs" / f"step_{step_index:02d}_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        logger.debug("Clearfacts exploration prompt for step %s:\n%s", step_index, prompt)

        return self._planner.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

    async def _execute_action(self, *, browser, action, role: str | None, source, current_page: NavigationPageEvidence | None):
        prepared_action = self._prepare_action_target(action=action, current_page=current_page)
        try:
            return await self._perform_action(browser=browser, action=prepared_action, role=role, source=source)
        except PlaywrightToolExecutionError as exc:            
            if not self._should_retry_stale_ref(action=prepared_action, error=exc):
                raise

            fresh_page = await browser.inspect_page(include_snapshot=True)
            retry_action = prepared_action.model_copy(deep=True)
            remapped_target = remap_snapshot_ref_target(
                prepared_action.target,
                previous_snapshot=current_page.snapshot if current_page else None,
                fresh_snapshot=fresh_page.snapshot,
            )
            if remapped_target:
                retry_action.target = remapped_target

            retry_call = await self._perform_action(browser=browser, action=retry_action, role=role, source=source)
            retry_message = retry_call.message or retry_action.summary
            if retry_action.target != prepared_action.target:
                retry_message = (
                    f"Recovered stale ref target `{prepared_action.target}` -> `{retry_action.target}`.\n\n{retry_message}"
                )
            else:
                retry_message = f"Recovered after refreshing page refs.\n\n{retry_message}"
            return type(retry_call)(
                tool_name=retry_call.tool_name,
                arguments=retry_call.arguments,
                message=retry_message,
            )

    def _prepare_action_target(self, *, action, current_page: NavigationPageEvidence | None):
        prepared_action = action.model_copy(deep=True)
        prepared_action.target = self._normalize_target(prepared_action.target)

        login_target = self._login_selector_target(prepared_action, current_page=current_page)
        if login_target is not None:
            prepared_action.target = login_target
            return prepared_action

        resolved_target = self._resolve_affordance_target(prepared_action, current_page=current_page)
        if resolved_target is not None:
            prepared_action.target = resolved_target
        return prepared_action

    @staticmethod
    def _normalize_target(target: str | None) -> str | None:
        if target is None:
            return None
        normalized = target.strip()
        if normalized.startswith("[ref=") and normalized.endswith("]"):
            normalized = normalized[1:-1]
        if normalized.startswith("[ref:") and normalized.endswith("]"):
            normalized = normalized[1:-1]
        if normalized.startswith("ref="):
            return normalized.split("=", 1)[1].strip() or None
        if normalized.startswith("ref:"):
            return normalized.split(":", 1)[1].strip() or None
        return normalized

    @staticmethod
    def _is_snapshot_ref_target(target: str | None) -> bool:
        if target is None:
            return False
        return re.fullmatch(r"(?:[a-z]\d+)*e\d+", target) is not None

    @staticmethod
    def _is_direct_execution_target(target: str | None) -> bool:
        if target is None:
            return False
        return (
            target.startswith(("#", ".", "a[", "button", "input", "textarea", "select", "["))
            or ":has-text(" in target
            or ClearfactsNavigationAgent._is_snapshot_ref_target(target)
        )

    def _resolve_affordance_target(self, action, *, current_page: NavigationPageEvidence | None) -> str | None:
        target = action.target
        if target is None or self._is_direct_execution_target(target) or current_page is None:
            return target

        affordances = current_page.affordances
        if not affordances:
            return target

        for affordance in affordances:
            if affordance.key == target:
                return affordance.selector or (f'a[href="{affordance.href}"]' if affordance.href else None) or target

        lowered_target = target.lower()
        for affordance in affordances:
            label = (affordance.label or "").lower()
            if lowered_target == label or lowered_target in label:
                return affordance.selector or (f'a[href="{affordance.href}"]' if affordance.href else None) or affordance.key

        return target

    @staticmethod
    def _login_selector_target(action, *, current_page: NavigationPageEvidence | None) -> str | None:
        current_url = (current_page.url or "").lower() if current_page else ""
        snapshot = current_page.snapshot or "" if current_page else ""
        if "/login" not in current_url and "Aanmelden op Clearfacts" not in snapshot:
            return None

        if action.action_type == ExplorationActionType.TYPE_ROLE_CREDENTIAL and action.credential_field is not None:
            if action.credential_field.value == "username":
                return "#username"
            if action.credential_field.value == "password":
                return "#password"
        if action.action_type == ExplorationActionType.CLICK:
            target = action.target or ""
            summary_text = " ".join(filter(None, [action.summary, action.expected_outcome, target]))
            if "Aanmelden" in summary_text or "_submit" in target:
                return "#_submit"
        return None

    async def _perform_action(self, *, browser, action, role: str | None, source):
        if action.action_type == ExplorationActionType.NAVIGATE_URL:
            return await browser.navigate(action.url or "")
        if action.action_type == ExplorationActionType.CLICK:
            return await browser.click(action.target or "")
        if action.action_type == ExplorationActionType.TYPE_TEXT:
            return await browser.type_text(action.target or "", action.text or "", slowly=self._should_type_slowly(action))
        if action.action_type == ExplorationActionType.TYPE_ROLE_CREDENTIAL:
            effective_role = action.role or role
            if effective_role is None:
                raise ValueError("A role is required to resolve credentials for type_role_credential.")
            value = resolve_role_credential(source, effective_role, action.credential_field.value)
            return await browser.type_text(action.target or "", value, slowly=self._should_type_slowly(action))
        if action.action_type == ExplorationActionType.PRESS_KEY:
            return await browser.press(action.key or "", target=action.target)
        if action.action_type == ExplorationActionType.WAIT_FOR_TEXT:
            return await browser.wait_for_text(action.text or "")
        if action.action_type == ExplorationActionType.CAPTURE_SNAPSHOT:
            return await browser.capture_snapshot(action.target)
        raise ValueError(f"Unsupported action type: {action.action_type}")

    @staticmethod
    def _should_type_slowly(action) -> bool:
        target = action.target or ""
        return target in {"#username", "#password"} or target.startswith("input:")

    @staticmethod
    def _should_retry_stale_ref(*, action, error: PlaywrightToolExecutionError) -> bool:
        if action.target is None or not ClearfactsNavigationAgent._is_snapshot_ref_target(action.target):
            return False
        if action.action_type not in {
            ExplorationActionType.CLICK,
            ExplorationActionType.TYPE_TEXT,
            ExplorationActionType.TYPE_ROLE_CREDENTIAL,
            ExplorationActionType.PRESS_KEY,
        }:
            return False
        normalized = error.message.lower()
        return "ref " in normalized and "not found" in normalized

    @staticmethod
    def _annotate_ontology_delta(delta: NavigationOntologyDelta, evidence: str) -> NavigationOntologyDelta:
        for item in delta.screens:
            if evidence not in item.evidence:
                item.evidence.append(evidence)
        for item in delta.actions:
            if evidence not in item.evidence:
                item.evidence.append(evidence)
        for item in delta.labels:
            if evidence not in item.evidence:
                item.evidence.append(evidence)
        for item in delta.navigation_paths:
            if evidence not in item.evidence:
                item.evidence.append(evidence)
        for item in delta.validation_notes:
            if evidence not in item.evidence:
                item.evidence.append(evidence)
        return delta

    @staticmethod
    def _delta_has_content(delta: NavigationOntologyDelta) -> bool:
        return any(
            [
                delta.screens,
                delta.actions,
                delta.labels,
                delta.navigation_paths,
                delta.validation_notes,
                delta.open_questions,
            ]
        )
