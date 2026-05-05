from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from context_db.agents.clearfacts_navigation_deepagent.schemas import (
    ClearfactsNavigationDeepAgentResult,
    ClearfactsNavigationOntologyUpdateResult,
    DeepAgentTraceReference,
)


class ExplorationTaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


class ClearfactsExplorationRequest(BaseModel):
    source_name: str = Field(
        default="navigation_agent_clearfacts",
        description="Source identifier that resolves to agents/sources/<source_name>.yaml.",
    )
    scenario_seed_path: str | None = Field(
        default=None,
        description="Optional seed scenario path. When omitted, the first seed for the source is used.",
    )
    role: str | None = Field(default=None, description="Optional role override for scenario tasks.")
    run_timestamp: str | None = Field(default=None, description="Exploration run timestamp to create or resume.")
    workspace_dir: str | None = Field(default=None, description="Workspace root. Defaults to repository workspace/.")
    force: bool = Field(default=False, description="Overwrite an existing exploration run with the same timestamp.")
    resume_latest: bool = Field(
        default=True,
        description="When run_timestamp is omitted, resume the latest active run for the selected scenario seed if available.",
    )
    retry_blocked: bool = Field(
        default=False,
        description="When true, retry blocked scenario tasks and resume the latest blocked run when no active run exists.",
    )
    include_snapshot: bool = Field(default=True, description="Whether child navigation observations should include snapshots.")
    use_persistent_browser: bool = Field(
        default=True,
        description="Start and reuse one persistent Playwright MCP browser session when no browser is supplied.",
    )
    navigation_run_timestamp: str | None = Field(
        default=None,
        description="Optional navigation run timestamp to use when an external browser session is supplied.",
    )
    max_tasks: int = Field(default=20, ge=1, le=100, description="Maximum pending scenario tasks to attempt.")
    navigation_execution_max_iterations: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Per child navigation execution budget.",
    )


class ExplorationScenarioTask(BaseModel):
    task_id: str
    title: str
    instruction: str
    status: ExplorationTaskStatus = ExplorationTaskStatus.PENDING
    priority: str | None = None
    max_minutes: int = Field(default=3, ge=1, le=60)
    role: str | None = None
    navigation_run_timestamp: str | None = None
    outcome: str | None = None

    @model_validator(mode="after")
    def validate_text_fields(self) -> "ExplorationScenarioTask":
        self.task_id = self.task_id.strip()
        self.title = self.title.strip()
        self.instruction = self.instruction.strip()
        if not self.task_id:
            raise ValueError("Scenario task_id cannot be empty.")
        if not self.title:
            raise ValueError("Scenario task title cannot be empty.")
        if not self.instruction:
            raise ValueError(f"Scenario task '{self.task_id}' instruction cannot be empty.")
        return self


class ExplorationEventRecord(BaseModel):
    event_id: str
    event_type: str
    status: str
    message: str | None = None
    task_id: str | None = None
    navigation_run_timestamp: str | None = None
    trace_paths: list[str] = Field(default_factory=list)


class ExplorationTaskResult(BaseModel):
    task: ExplorationScenarioTask
    status: ExplorationTaskStatus
    navigation_result: ClearfactsNavigationDeepAgentResult | None = None
    ontology_update_result: ClearfactsNavigationOntologyUpdateResult | None = None
    message: str


class ClearfactsExplorationResult(BaseModel):
    status: ExplorationTaskStatus
    source_name: str
    run_timestamp: str
    run_folder: str
    scenario_path: str
    discoveries_path: str
    manifest_path: str
    events_path: str
    message: str
    attempted_task_count: int
    completed_task_count: int
    blocked_task_count: int
    skipped_task_count: int
    failed_task_count: int
    task_results: list[ExplorationTaskResult] = Field(default_factory=list)
    trace_references: list[DeepAgentTraceReference] = Field(default_factory=list)


@dataclass(frozen=True)
class ExplorationRunContext:
    source_name: str
    timestamp: str
    source_workspace_dir: Path
    run_dir: Path
    manifest_path: Path
    scenario_path: Path
    discoveries_path: Path
    events_path: Path
    logs_dir: Path
    child_navigation_runs_path: Path
    scenario_seed_path: Path
    index_path: Path
