from __future__ import annotations

from pathlib import Path
from typing import Any

from context_db.agents.clearfacts_navigation_deepagent import ClearfactsNavigationDeepAgent
from context_db.agents.clearfacts_navigation_deepagent.schemas import (
    ClearfactsNavigationDeepAgentRequest,
    ClearfactsNavigationOntologyUpdateRequest,
    DeepAgentExecutionStatus,
)
from context_db.agents.clearfacts_navigation_agent.tools import (
    PersistentPlaywrightBrowserSession,
    load_navigation_run,
    load_manifest,
    prepare_playwright_run_config,
    setup_navigation_run,
    update_manifest,
)

from .schemas import (
    ClearfactsExplorationRequest,
    ClearfactsExplorationResult,
    ExplorationEventRecord,
    ExplorationRunContext,
    ExplorationScenarioTask,
    ExplorationTaskResult,
    ExplorationTaskStatus,
)
from .tools import (
    append_discovery,
    append_exploration_event,
    find_active_exploration_run,
    find_latest_exploration_run,
    load_exploration_run,
    load_scenario_metadata,
    load_scenario_tasks,
    record_child_navigation_run,
    setup_exploration_run,
    update_exploration_index,
    update_scenario_task,
)


class ClearfactsExplorationAgent:
    """Scenario-level exploration orchestrator built on the navigation deepagent."""

    AGENT_NAME = "clearfacts-exploration-agent"

    def __init__(
        self,
        *,
        navigation_agent: Any | None = None,
        navigation_model_profile: str | None = None,
    ) -> None:
        self._navigation_agent = navigation_agent or ClearfactsNavigationDeepAgent(model_profile=navigation_model_profile)

    def invoke(
        self,
        query: ClearfactsExplorationRequest,
        *,
        browser: Any | None = None,
    ) -> ClearfactsExplorationResult:
        run = self._ensure_run(query)
        update_manifest(run.manifest_path, status="running")
        update_exploration_index(run)
        scenario_metadata = load_scenario_metadata(run.scenario_path)
        scenario_default_role = self._optional_metadata_str(scenario_metadata.get("default_role"))
        tasks = load_scenario_tasks(run.scenario_path)
        resumable_tasks = [
            task
            for task in tasks
            if self._is_resumable_task(task, retry_blocked=query.retry_blocked)
        ]
        selected_tasks = resumable_tasks[: query.max_tasks]
        task_results: list[ExplorationTaskResult] = []
        managed_browser: PersistentPlaywrightBrowserSession | None = None
        active_browser = browser
        navigation_run_timestamp = query.navigation_run_timestamp

        if not selected_tasks:
            terminal_status = self._terminal_status(tasks)
            update_manifest(run.manifest_path, status=terminal_status.value, attempted_task_count=0)
            update_exploration_index(run)
            task_statuses = (
                "pending, in-progress, or blocked"
                if query.retry_blocked
                else "pending or in-progress"
            )
            return self._build_result(
                run=run,
                status=terminal_status,
                message=f"No {task_statuses} scenario tasks were found.",
                task_results=[],
            )

        if active_browser is None and query.use_persistent_browser:
            navigation_run = self._ensure_child_navigation_run(
                query.source_name,
                timestamp=navigation_run_timestamp or run.timestamp,
                workspace_dir=query.workspace_dir,
                force=query.force,
            )
            managed_browser = PersistentPlaywrightBrowserSession(
                prepare_playwright_run_config(navigation_run.source, navigation_run)
            )
            managed_browser.start()
            active_browser = managed_browser
            navigation_run_timestamp = navigation_run.timestamp

        try:
            for task in selected_tasks:
                effective_role = task.role or query.role or scenario_default_role
                task_results.append(
                    self._execute_task(
                        run=run,
                        query=query,
                        task=task,
                        role=effective_role,
                        browser=active_browser,
                        navigation_run_timestamp=navigation_run_timestamp,
                    )
                )
        finally:
            if managed_browser is not None:
                managed_browser.stop()

        status = self._overall_status(task_results)
        update_manifest(
            run.manifest_path,
            status=status.value,
            attempted_task_count=len(task_results),
            completed_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.COMPLETED),
            blocked_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.BLOCKED),
            skipped_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.SKIPPED),
            failed_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.FAILED),
        )
        update_exploration_index(run)
        return self._build_result(
            run=run,
            status=status,
            message=f"Attempted {len(task_results)} scenario task(s).",
            task_results=task_results,
        )

    def _ensure_run(self, query: ClearfactsExplorationRequest) -> ExplorationRunContext:
        if query.run_timestamp and not query.force:
            try:
                return load_exploration_run(
                    query.source_name,
                    timestamp=query.run_timestamp,
                    workspace_dir=query.workspace_dir,
                )
            except FileNotFoundError:
                pass
        if query.resume_latest and not query.force:
            active_run_timestamp = find_active_exploration_run(
                query.source_name,
                scenario_seed_path=query.scenario_seed_path,
                workspace_dir=query.workspace_dir,
            )
            if active_run_timestamp:
                return load_exploration_run(
                    query.source_name,
                    timestamp=active_run_timestamp,
                    workspace_dir=query.workspace_dir,
                )
            if query.retry_blocked:
                latest_run_timestamp = find_latest_exploration_run(
                    query.source_name,
                    scenario_seed_path=query.scenario_seed_path,
                    workspace_dir=query.workspace_dir,
                )
                if latest_run_timestamp:
                    latest_run = load_exploration_run(
                        query.source_name,
                        timestamp=latest_run_timestamp,
                        workspace_dir=query.workspace_dir,
                    )
                    if any(
                        task.status == ExplorationTaskStatus.BLOCKED
                        for task in load_scenario_tasks(latest_run.scenario_path)
                    ):
                        return latest_run
        return setup_exploration_run(
            query.source_name,
            scenario_seed_path=query.scenario_seed_path,
            workspace_dir=query.workspace_dir,
            timestamp=query.run_timestamp,
            force=query.force,
        )

    @staticmethod
    def _ensure_child_navigation_run(
        source_name: str,
        *,
        timestamp: str | None,
        workspace_dir: str | Path | None,
        force: bool,
    ):
        if timestamp and not force:
            try:
                return load_navigation_run(source_name, timestamp=timestamp, workspace_dir=workspace_dir)
            except FileNotFoundError:
                pass
        return setup_navigation_run(source_name, workspace_dir=workspace_dir, timestamp=timestamp, force=force)

    def _execute_task(
        self,
        *,
        run: ExplorationRunContext,
        query: ClearfactsExplorationRequest,
        task: ExplorationScenarioTask,
        role: str | None,
        browser: Any | None,
        navigation_run_timestamp: str | None,
    ) -> ExplorationTaskResult:
        navigation_instruction = self._task_navigation_instruction(task)
        if task.status == ExplorationTaskStatus.IN_PROGRESS:
            start_outcome = "Resumed scenario task that was left in progress."
        elif task.status == ExplorationTaskStatus.BLOCKED:
            start_outcome = "Retrying scenario task that was previously blocked."
        else:
            start_outcome = "Started scenario task."
        self._mark_task(
            run,
            task=task,
            status=ExplorationTaskStatus.IN_PROGRESS,
            outcome=start_outcome,
        )
        try:
            navigation_result = self._navigation_agent.invoke(
                ClearfactsNavigationDeepAgentRequest(
                    source_name=query.source_name,
                    instruction=navigation_instruction,
                    role=role,
                    run_timestamp=navigation_run_timestamp,
                    include_snapshot=query.include_snapshot,
                    execution_max_iterations=query.navigation_execution_max_iterations,
                ),
                browser=browser,
            )
            record_child_navigation_run(
                run,
                task_id=task.task_id,
                status=navigation_result.status.value,
                run_timestamp=navigation_result.run_timestamp,
                run_folder=navigation_result.run_folder,
                instruction=navigation_instruction,
            )
            if navigation_result.status == DeepAgentExecutionStatus.COMPLETED:
                ontology_update = self._navigation_agent.update_ontology(
                    ClearfactsNavigationOntologyUpdateRequest(
                        source_name=query.source_name,
                        run_timestamp=navigation_result.run_timestamp,
                        role=role,
                        instruction=f"Exploration scenario task {task.task_id}: {task.title}",
                    )
                )
                evidence = self._trace_paths(navigation_result) + self._trace_paths(ontology_update)
                self._mark_task(
                    run,
                    task=task,
                    status=ExplorationTaskStatus.COMPLETED,
                    outcome=navigation_result.message,
                    navigation_run_timestamp=navigation_result.run_timestamp,
                    evidence=evidence,
                )
                updated_task = self._updated_task(
                    task,
                    status=ExplorationTaskStatus.COMPLETED,
                    outcome=navigation_result.message,
                    navigation_run_timestamp=navigation_result.run_timestamp,
                )
                return ExplorationTaskResult(
                    task=updated_task,
                    status=ExplorationTaskStatus.COMPLETED,
                    navigation_result=navigation_result,
                    ontology_update_result=ontology_update,
                    message=navigation_result.message,
                )

            evidence = self._trace_paths(navigation_result)
            outcome = navigation_result.message or f"Navigation ended with status {navigation_result.status.value}."
            self._mark_task(
                run,
                task=task,
                status=ExplorationTaskStatus.BLOCKED,
                outcome=outcome,
                navigation_run_timestamp=navigation_result.run_timestamp,
                evidence=evidence,
            )
            append_discovery(run.discoveries_path, task_id=task.task_id, message=f"Review blocked target: {outcome}", evidence=evidence)
            updated_task = self._updated_task(
                task,
                status=ExplorationTaskStatus.BLOCKED,
                outcome=outcome,
                navigation_run_timestamp=navigation_result.run_timestamp,
            )
            return ExplorationTaskResult(
                task=updated_task,
                status=ExplorationTaskStatus.BLOCKED,
                navigation_result=navigation_result,
                message=outcome,
            )
        except Exception as exc:
            outcome = f"Scenario task failed before completion: {exc}"
            self._mark_task(run, task=task, status=ExplorationTaskStatus.FAILED, outcome=outcome)
            append_discovery(run.discoveries_path, task_id=task.task_id, message=outcome)
            updated_task = self._updated_task(task, status=ExplorationTaskStatus.FAILED, outcome=outcome)
            return ExplorationTaskResult(
                task=updated_task,
                status=ExplorationTaskStatus.FAILED,
                message=outcome,
            )

    def _mark_task(
        self,
        run: ExplorationRunContext,
        *,
        task: ExplorationScenarioTask,
        status: ExplorationTaskStatus,
        outcome: str,
        navigation_run_timestamp: str | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        update_scenario_task(
            run.scenario_path,
            task_id=task.task_id,
            status=status,
            outcome=outcome,
            navigation_run_timestamp=navigation_run_timestamp,
            evidence=evidence,
        )
        append_exploration_event(
            run,
            ExplorationEventRecord(
                event_id=f"{self._next_event_index(run):02d}-{task.task_id}-{status.value}",
                event_type="task",
                status=status.value,
                message=outcome,
                task_id=task.task_id,
                navigation_run_timestamp=navigation_run_timestamp,
                trace_paths=evidence or [],
            ),
        )
        update_exploration_index(run)

    @staticmethod
    def _is_resumable_task(task: ExplorationScenarioTask, *, retry_blocked: bool = False) -> bool:
        statuses = {ExplorationTaskStatus.PENDING, ExplorationTaskStatus.IN_PROGRESS}
        if retry_blocked:
            statuses.add(ExplorationTaskStatus.BLOCKED)
        return task.status in statuses

    @staticmethod
    def _terminal_status(tasks: list[ExplorationScenarioTask]) -> ExplorationTaskStatus:
        if any(task.status == ExplorationTaskStatus.FAILED for task in tasks):
            return ExplorationTaskStatus.FAILED
        if any(task.status == ExplorationTaskStatus.BLOCKED for task in tasks):
            return ExplorationTaskStatus.BLOCKED
        if any(task.status == ExplorationTaskStatus.SKIPPED for task in tasks):
            return ExplorationTaskStatus.SKIPPED
        return ExplorationTaskStatus.COMPLETED

    @staticmethod
    def _overall_status(task_results: list[ExplorationTaskResult]) -> ExplorationTaskStatus:
        if any(result.status == ExplorationTaskStatus.FAILED for result in task_results):
            return ExplorationTaskStatus.FAILED
        if any(result.status == ExplorationTaskStatus.BLOCKED for result in task_results):
            return ExplorationTaskStatus.BLOCKED
        if any(result.status == ExplorationTaskStatus.SKIPPED for result in task_results):
            return ExplorationTaskStatus.SKIPPED
        return ExplorationTaskStatus.COMPLETED

    @staticmethod
    def _next_event_index(run: ExplorationRunContext) -> int:
        return len([line for line in run.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]) + 1

    @staticmethod
    def _trace_paths(result: Any) -> list[str]:
        return [reference.path for reference in getattr(result, "trace_references", [])]

    @staticmethod
    def _task_navigation_instruction(task: ExplorationScenarioTask) -> str:
        return (
            f"{task.instruction}\n\n"
            f"Scenario task id: {task.task_id}. Time budget: about {task.max_minutes} minute(s). "
            "If the target cannot be reached within the navigation iteration budget, stop with a blocked result "
            "and preserve evidence for later review."
        )

    @staticmethod
    def _optional_metadata_str(value: Any) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @staticmethod
    def _updated_task(
        task: ExplorationScenarioTask,
        *,
        status: ExplorationTaskStatus,
        outcome: str,
        navigation_run_timestamp: str | None = None,
    ) -> ExplorationScenarioTask:
        return task.model_copy(
            update={
                "status": status,
                "outcome": outcome,
                "navigation_run_timestamp": navigation_run_timestamp or task.navigation_run_timestamp,
            }
        )

    @staticmethod
    def _build_result(
        *,
        run: ExplorationRunContext,
        status: ExplorationTaskStatus,
        message: str,
        task_results: list[ExplorationTaskResult],
    ) -> ClearfactsExplorationResult:
        manifest = load_manifest(run.manifest_path)
        return ClearfactsExplorationResult(
            status=status,
            source_name=run.source_name,
            run_timestamp=run.timestamp,
            run_folder=str(run.run_dir),
            scenario_path=str(run.scenario_path),
            discoveries_path=str(run.discoveries_path),
            manifest_path=str(run.manifest_path),
            events_path=str(run.events_path),
            message=message,
            attempted_task_count=int(manifest.get("attempted_task_count") or len(task_results)),
            completed_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.COMPLETED),
            blocked_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.BLOCKED),
            skipped_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.SKIPPED),
            failed_task_count=sum(1 for result in task_results if result.status == ExplorationTaskStatus.FAILED),
            task_results=task_results,
        )
