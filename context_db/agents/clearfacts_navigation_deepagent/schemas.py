from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from context_db.agents.clearfacts_navigation_agent.schemas import (
    ClearfactsNavigationResult,
    CredentialField,
    ExplorationActionType,
    NavigationExecutionStatus,
    NavigationEventRecord,
    NavigationOntologyDelta,
    NavigationPageEvidence,
)


def _optional_raw_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return str(value) if value not in (None, "") else None


class DeepAgentExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    BLOCKED = "blocked"
    FAILED = "failed"


class DeepAgentTraceReference(BaseModel):
    agent_name: str = Field(description="Agent or subagent that produced this trace.")
    trace_kind: str = Field(description="Trace type such as coordinator or subagent.")
    path: str = Field(description="Absolute path to the persisted trace artifact.")


class ClearfactsNavigationDeepAgentRequest(BaseModel):
    source_name: str = Field(
        default="navigation_agent_clearfacts",
        description="Source identifier that resolves to agents/sources/<source_name>.yaml.",
    )
    instruction: str = Field(description="Natural-language navigation objective.")
    role: str | None = Field(default=None, description="Optional role to use for the run.")
    run_timestamp: str | None = Field(default=None, description="Existing run timestamp to continue, if any.")
    include_snapshot: bool = Field(default=True, description="Whether browser observations should include snapshots.")
    execution_max_iterations: int = Field(default=6, ge=1, le=20, description="Per navigation execution budget.")

    @model_validator(mode="after")
    def validate_instruction(self) -> "ClearfactsNavigationDeepAgentRequest":
        self.instruction = self.instruction.strip()
        if not self.instruction:
            raise ValueError("Instruction cannot be empty.")
        return self


class ClearfactsNavigationValidationRequest(BaseModel):
    source_name: str = Field(
        default="navigation_agent_clearfacts",
        description="Source identifier that resolves to agents/sources/<source_name>.yaml.",
    )
    claim: str = Field(description="Claim or expected UI behavior to validate.")
    procedure_instruction: str | None = Field(
        default=None,
        description="Optional concrete navigation procedure to replay before assessing the claim.",
    )
    role: str | None = Field(default=None, description="Optional role to use for the run.")
    run_timestamp: str | None = Field(default=None, description="Existing run timestamp to continue, if any.")
    include_snapshot: bool = Field(default=True, description="Whether browser observations should include snapshots.")
    execution_max_iterations: int = Field(default=6, ge=1, le=20, description="Per navigation execution budget.")

    @model_validator(mode="after")
    def validate_claim(self) -> "ClearfactsNavigationValidationRequest":
        self.claim = self.claim.strip()
        if not self.claim:
            raise ValueError("Claim cannot be empty.")
        if self.procedure_instruction is not None:
            self.procedure_instruction = self.procedure_instruction.strip() or None
        return self


class BrowserExecutionOperation(str, Enum):
    INSPECT = "inspect"
    NAVIGATE_URL = "navigate_url"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    TYPE_ROLE_CREDENTIAL = "type_role_credential"
    PRESS_KEY = "press_key"
    WAIT_FOR_TEXT = "wait_for_text"
    CAPTURE_SNAPSHOT = "capture_snapshot"


class NavigationExecutionTaskInput(BaseModel):
    source_name: str
    instruction: str = Field(description="Natural-language context for why this browser operation is being performed.")
    operation: BrowserExecutionOperation = Field(
        default=BrowserExecutionOperation.INSPECT,
        description="Single typed browser operation to perform through the Playwright MCP adapter.",
    )
    role: str | None = None
    run_timestamp: str | None = None
    include_snapshot: bool = True
    max_iterations: int = Field(default=1, ge=1, le=20, description="Deprecated compatibility field; this executor runs one operation.")
    url: str | None = Field(default=None, description="URL for navigate_url operations.")
    target: str | None = Field(default=None, description="Stable selector, affordance key, label, or current snapshot ref.")
    text: str | None = Field(default=None, description="Text for type_text or wait_for_text operations.")
    key: str | None = Field(default=None, description="Keyboard key for press_key operations.")
    credential_field: CredentialField | None = Field(default=None, description="Credential field for type_role_credential.")
    summary: str | None = Field(default=None, description="Short rationale for the operation.")
    expected_outcome: str | None = Field(default=None, description="Expected observable result after the operation.")

    @model_validator(mode="after")
    def validate_operation_fields(self) -> "NavigationExecutionTaskInput":
        self.instruction = self.instruction.strip()
        if not self.instruction:
            raise ValueError("Instruction cannot be empty.")
        required_by_operation = {
            BrowserExecutionOperation.NAVIGATE_URL: ("url",),
            BrowserExecutionOperation.CLICK: ("target",),
            BrowserExecutionOperation.TYPE_TEXT: ("target", "text"),
            BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL: ("target", "credential_field"),
            BrowserExecutionOperation.PRESS_KEY: ("key",),
            BrowserExecutionOperation.WAIT_FOR_TEXT: ("text",),
        }
        missing = [
            field_name
            for field_name in required_by_operation.get(self.operation, ())
            if getattr(self, field_name) in (None, "")
        ]
        if missing:
            raise ValueError(
                f"Operation '{self.operation.value}' is missing required field(s): {', '.join(missing)}"
            )
        return self


class NavigationExecutionTaskOutput(BaseModel):
    subagent_name: Literal["navigation-executor"] = Field(default="navigation-executor")
    operation: BrowserExecutionOperation = Field(default=BrowserExecutionOperation.INSPECT)
    status: NavigationExecutionStatus
    message: str | None = None
    question_for_user: str | None = None
    current_page: NavigationPageEvidence | None = None
    events: list[NavigationEventRecord] = Field(default_factory=list)
    run_timestamp: str
    run_folder: str
    ontology_path: str
    trace_path: str | None = None
    raw_result: ClearfactsNavigationResult


class NavigationExecutionEvidence(BaseModel):
    """Compact execution evidence accepted by coordinator-side evaluator tools."""

    subagent_name: str | None = None
    operation: BrowserExecutionOperation | None = None
    status: NavigationExecutionStatus | None = None
    message: str | None = None
    question_for_user: str | None = None
    current_page: NavigationPageEvidence | None = None
    run_timestamp: str | None = None
    run_folder: str | None = None
    ontology_path: str | None = None
    trace_path: str | None = None
    source_name: str | None = None
    instruction: str | None = None
    role: str | None = None
    raw_result: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_model_payload(cls, value: Any) -> Any:
        if isinstance(value, NavigationExecutionTaskOutput | ClearfactsNavigationResult):
            return value.model_dump(mode="json", exclude_none=True)
        return value

    @model_validator(mode="after")
    def inherit_raw_result_identity(self) -> "NavigationExecutionEvidence":
        raw_result = self.raw_result if isinstance(self.raw_result, dict) else {}
        self.source_name = self.source_name or _optional_raw_str(raw_result, "source_name")
        self.run_timestamp = self.run_timestamp or _optional_raw_str(raw_result, "run_timestamp")
        self.run_folder = self.run_folder or _optional_raw_str(raw_result, "run_folder")
        self.ontology_path = self.ontology_path or _optional_raw_str(raw_result, "ontology_path")
        self.instruction = self.instruction or _optional_raw_str(raw_result, "instruction")
        self.role = self.role or _optional_raw_str(raw_result, "role")
        self.message = self.message or _optional_raw_str(raw_result, "message")
        if self.status is None and raw_result.get("status"):
            try:
                self.status = NavigationExecutionStatus(str(raw_result["status"]))
            except ValueError:
                pass
        if self.current_page is None and isinstance(raw_result.get("current_page"), dict):
            self.current_page = NavigationPageEvidence.model_validate(raw_result["current_page"])
        return self

    @property
    def missing_required_context(self) -> list[str]:
        missing: list[str] = []
        if not self.source_name:
            missing.append("execution.source_name or execution.raw_result.source_name")
        if not self.run_timestamp:
            missing.append("execution.run_timestamp or execution.raw_result.run_timestamp")
        if self.status is None:
            missing.append("execution.status")
        return missing


class CachedRouteExecutionStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class RoutePlanStep(BaseModel):
    operation: BrowserExecutionOperation
    instruction: str
    target: str | None = None
    url: str | None = None
    text: str | None = None
    key: str | None = None
    credential_field: CredentialField | None = None
    expected_outcome: str | None = None

    @model_validator(mode="after")
    def validate_operation_fields(self) -> "RoutePlanStep":
        self.instruction = self.instruction.strip()
        if not self.instruction:
            raise ValueError("Route step instruction cannot be empty.")
        required_by_operation = {
            BrowserExecutionOperation.NAVIGATE_URL: ("url",),
            BrowserExecutionOperation.CLICK: ("target",),
            BrowserExecutionOperation.TYPE_TEXT: ("target", "text"),
            BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL: ("target", "credential_field"),
            BrowserExecutionOperation.PRESS_KEY: ("key",),
            BrowserExecutionOperation.WAIT_FOR_TEXT: ("text",),
        }
        missing = [
            field_name
            for field_name in required_by_operation.get(self.operation, ())
            if getattr(self, field_name) in (None, "")
        ]
        if missing:
            raise ValueError(
                f"Route step operation '{self.operation.value}' is missing required field(s): {', '.join(missing)}"
            )
        return self


class RoutePlanningTaskInput(BaseModel):
    source_name: str
    user_goal: str
    role: str | None = None
    run_timestamp: str | None = None
    current_ontology_yaml: str = ""
    current_page: NavigationPageEvidence | None = None

    @model_validator(mode="after")
    def validate_user_goal(self) -> "RoutePlanningTaskInput":
        self.user_goal = self.user_goal.strip()
        if not self.user_goal:
            raise ValueError("User goal cannot be empty.")
        self.current_ontology_yaml = self.current_ontology_yaml.strip()
        return self


class RoutePlanningTaskOutput(BaseModel):
    subagent_name: str = Field(default="route-planner")
    has_known_route: bool
    summary: str
    route_steps: list[RoutePlanStep] = Field(default_factory=list)
    missing_coverage: list[str] = Field(default_factory=list)
    trace_path: str | None = None


class CachedRouteExecutionTaskInput(BaseModel):
    source_name: str
    user_goal: str
    role: str | None = None
    run_timestamp: str | None = None
    current_page: NavigationPageEvidence | None = None
    include_snapshot: bool = True
    max_steps: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_user_goal(self) -> "CachedRouteExecutionTaskInput":
        self.user_goal = self.user_goal.strip()
        if not self.user_goal:
            raise ValueError("User goal cannot be empty.")
        return self


class CachedRouteStepResult(BaseModel):
    path_description: str
    operation: BrowserExecutionOperation
    instruction: str
    status: NavigationExecutionStatus
    message: str | None = None
    current_page_url: str | None = None
    current_page_title: str | None = None
    trace_path: str | None = None


class CachedRouteExecutionTaskOutput(BaseModel):
    subagent_name: str = Field(default="route-cache")
    status: CachedRouteExecutionStatus
    summary: str
    source_name: str
    run_timestamp: str
    run_folder: str
    ontology_path: str
    matched_paths: list[str] = Field(default_factory=list)
    executed_steps: list[CachedRouteStepResult] = Field(default_factory=list)
    remaining_goal: str | None = None
    current_page: NavigationPageEvidence | None = None
    latest_navigation_result: ClearfactsNavigationResult | None = None
    trace_path: str | None = None


class RecoveryStrategy(str, Enum):
    RETRY_WITH_REFINED_INSTRUCTION = "retry_with_refined_instruction"
    ASK_USER = "ask_user"
    DECLARE_BLOCKED = "declare_blocked"
    MARK_COMPLETED = "mark_completed"


class RecoveryAnalysisTaskInput(BaseModel):
    user_goal: str
    execution: NavigationExecutionEvidence


class RecoveryAnalysisTaskOutput(BaseModel):
    subagent_name: str = Field(default="recovery-analyzer")
    strategy: RecoveryStrategy
    summary: str = Field(description="Short explanation of the recommended recovery move.")
    refined_instruction: str | None = Field(default=None, description="Updated navigation instruction when retrying.")
    question_for_user: str | None = Field(default=None, description="User clarification question when needed.")
    trace_path: str | None = None

    @model_validator(mode="after")
    def validate_strategy_payload(self) -> "RecoveryAnalysisTaskOutput":
        self.summary = self.summary.strip()
        if not self.summary:
            raise ValueError("Recovery summary cannot be empty.")
        if self.refined_instruction is not None:
            self.refined_instruction = self.refined_instruction.strip() or None
        if self.question_for_user is not None:
            self.question_for_user = self.question_for_user.strip() or None
        if self.strategy == RecoveryStrategy.RETRY_WITH_REFINED_INSTRUCTION and not self.refined_instruction:
            raise ValueError("retry_with_refined_instruction requires refined_instruction.")
        if self.strategy == RecoveryStrategy.ASK_USER and not self.question_for_user:
            raise ValueError("ask_user requires question_for_user.")
        return self


class GoalAssessmentStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_MORE_WORK = "needs_more_work"
    NEEDS_USER_INPUT = "needs_user_input"
    BLOCKED = "blocked"


class GoalAssessmentTaskInput(BaseModel):
    user_goal: str
    execution: NavigationExecutionEvidence


class GoalAssessmentTaskOutput(BaseModel):
    subagent_name: str = Field(default="goal-assessor")
    status: GoalAssessmentStatus
    summary: str = Field(description="Assessment summary.")
    confirmed_evidence: list[str] = Field(default_factory=list, description="Observed evidence that supports the assessment.")
    question_for_user: str | None = None
    trace_path: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "GoalAssessmentTaskOutput":
        self.summary = self.summary.strip()
        if not self.summary:
            raise ValueError("Goal assessment summary cannot be empty.")
        if self.question_for_user is not None:
            self.question_for_user = self.question_for_user.strip() or None
        if self.status == GoalAssessmentStatus.NEEDS_USER_INPUT and not self.question_for_user:
            raise ValueError("needs_user_input requires question_for_user.")
        return self


class DeepAgentCoordinatorStructuredResponse(BaseModel):
    status: DeepAgentExecutionStatus
    summary: str
    question_for_user: str | None = None
    latest_page_url: str | None = None
    latest_page_title: str | None = None
    run_timestamp: str | None = None
    run_folder: str | None = None
    ontology_path: str | None = None
    trace_references: list[str] = Field(default_factory=list)


class ClearfactsNavigationDeepAgentResult(BaseModel):
    status: DeepAgentExecutionStatus
    source_name: str
    instruction: str
    role: str | None = None
    message: str
    question_for_user: str | None = None
    run_timestamp: str
    run_folder: str
    ontology_path: str
    current_page: NavigationPageEvidence | None = None
    latest_navigation_result: ClearfactsNavigationResult | None = None
    trace_references: list[DeepAgentTraceReference] = Field(default_factory=list)


class ClearfactsNavigationOntologyUpdateRequest(BaseModel):
    source_name: str = Field(
        default="navigation_agent_clearfacts",
        description="Source identifier that resolves to agents/sources/<source_name>.yaml.",
    )
    run_timestamp: str = Field(description="Existing run timestamp whose evidence should be analyzed.")
    role: str | None = Field(default=None, description="Optional role context for the analysis.")
    instruction: str | None = Field(default=None, description="Optional user-facing description of the update checkpoint.")
    max_events: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum new, ontology-relevant events to analyze in one batch.",
    )


class OntologyBatchAnalysisTaskOutput(BaseModel):
    summary: str = Field(description="Short summary of the grounded ontology updates.")
    ontology_delta: NavigationOntologyDelta = Field(default_factory=NavigationOntologyDelta)
    confidence: str | None = Field(default=None, description="Overall confidence in the proposed updates.")
    open_issues: list[str] = Field(default_factory=list, description="Remaining gaps or uncertain evidence.")


class ClearfactsNavigationOntologyUpdateResult(BaseModel):
    status: str
    summary: str
    source_name: str
    run_timestamp: str
    run_folder: str
    ontology_path: str
    source_ontology_path: str | None = None
    analyzed_event_count: int
    merged_counts: dict[str, int] = Field(default_factory=dict)
    ontology_delta: NavigationOntologyDelta
    open_issues: list[str] = Field(default_factory=list)
    trace_path: str | None = None
    trace_references: list[DeepAgentTraceReference] = Field(default_factory=list)


class ValidationOutcome(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INCONCLUSIVE = "inconclusive"


class ValidationAssessmentTaskInput(BaseModel):
    claim: str
    procedure_instruction: str
    execution: ClearfactsNavigationDeepAgentResult


class ValidationAssessmentTaskOutput(BaseModel):
    subagent_name: str = Field(default="validation-assessor")
    outcome: ValidationOutcome
    summary: str = Field(description="Short evidence-grounded assessment summary.")
    observed_evidence: list[str] = Field(default_factory=list, description="Observed UI facts supporting the assessment.")
    contradictions: list[str] = Field(default_factory=list, description="Observed UI facts that contradict the claim.")
    missing_evidence: list[str] = Field(default_factory=list, description="Important missing evidence or remaining gaps.")
    question_for_user: str | None = None
    trace_path: str | None = None


class ClearfactsNavigationValidationResult(BaseModel):
    outcome: ValidationOutcome
    claim: str
    procedure_instruction: str
    role: str | None = None
    summary: str
    question_for_user: str | None = None
    run_timestamp: str
    run_folder: str
    ontology_path: str
    observed_evidence: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    execution_result: ClearfactsNavigationDeepAgentResult
    trace_references: list[DeepAgentTraceReference] = Field(default_factory=list)
