from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from context_db.agents.clearfacts_navigation_agent.schemas import (
    ClearfactsNavigationResult,
    NavigationExecutionStatus,
    NavigationPageEvidence,
)


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


class NavigationExecutionTaskInput(BaseModel):
    source_name: str
    instruction: str
    role: str | None = None
    run_timestamp: str | None = None
    include_snapshot: bool = True
    max_iterations: int = Field(default=6, ge=1, le=20)


class NavigationExecutionTaskOutput(BaseModel):
    subagent_name: str = Field(default="navigation-executor")
    status: NavigationExecutionStatus
    message: str | None = None
    question_for_user: str | None = None
    current_page: NavigationPageEvidence | None = None
    run_timestamp: str
    run_folder: str
    ontology_path: str
    trace_path: str | None = None
    raw_result: ClearfactsNavigationResult


class RecoveryStrategy(str, Enum):
    RETRY_WITH_REFINED_INSTRUCTION = "retry_with_refined_instruction"
    ASK_USER = "ask_user"
    DECLARE_BLOCKED = "declare_blocked"
    MARK_COMPLETED = "mark_completed"


class RecoveryAnalysisTaskInput(BaseModel):
    user_goal: str
    execution: NavigationExecutionTaskOutput


class RecoveryAnalysisTaskOutput(BaseModel):
    subagent_name: str = Field(default="recovery-analyzer")
    strategy: RecoveryStrategy
    summary: str = Field(description="Short explanation of the recommended recovery move.")
    refined_instruction: str | None = Field(default=None, description="Updated navigation instruction when retrying.")
    question_for_user: str | None = Field(default=None, description="User clarification question when needed.")
    trace_path: str | None = None


class GoalAssessmentStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_MORE_WORK = "needs_more_work"
    NEEDS_USER_INPUT = "needs_user_input"
    BLOCKED = "blocked"


class GoalAssessmentTaskInput(BaseModel):
    user_goal: str
    execution: NavigationExecutionTaskOutput


class GoalAssessmentTaskOutput(BaseModel):
    subagent_name: str = Field(default="goal-assessor")
    status: GoalAssessmentStatus
    summary: str = Field(description="Assessment summary.")
    confirmed_evidence: list[str] = Field(default_factory=list, description="Observed evidence that supports the assessment.")
    question_for_user: str | None = None
    trace_path: str | None = None


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
