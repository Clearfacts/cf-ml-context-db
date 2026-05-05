from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class CredentialField(str, Enum):
    USERNAME = "username"
    PASSWORD = "password"


class ExplorationActionType(str, Enum):
    NAVIGATE_URL = "navigate_url"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    TYPE_ROLE_CREDENTIAL = "type_role_credential"
    PRESS_KEY = "press_key"
    WAIT_FOR_TEXT = "wait_for_text"
    CAPTURE_SNAPSHOT = "capture_snapshot"


class ExplorationDecisionState(str, Enum):
    CONTINUE = "continue"
    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    BLOCKED = "blocked"


class NavigationExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    BLOCKED = "blocked"
    FAILED = "failed"


class NavigationSourceEntryPoint(BaseModel):
    name: str = Field(description="Human-readable name for a starting point worth exploring.")
    path: str | None = Field(default=None, description="Optional relative path such as /login.")
    purpose: str = Field(description="Why this entry point matters for exploration.")
    hints: list[str] = Field(default_factory=list, description="Optional guidance or known affordances.")


class NavigationSourceUserCredential(BaseModel):
    username: str = Field(description="Username loaded from fixture or source configuration.")
    password: str = Field(description="Password loaded from fixture or source configuration.")


class PlaywrightMcpServerConfig(BaseModel):
    command: str = Field(description="Executable used to start the Playwright MCP server.")
    args: list[str] = Field(default_factory=list, description="Arguments passed to the MCP server command.")
    env: dict[str, str] = Field(default_factory=dict, description="Extra environment variables for the MCP server.")
    headless: bool = Field(default=True, description="Whether the Playwright browser should run headless.")
    step_delay_ms: int = Field(
        default=0,
        ge=0,
        description="Base backoff delay for transient navigation-error retries.",
    )


class NavigationSourceConfig(BaseModel):
    source_name: str = Field(description="Stable source identifier used for workspace folders.")
    description: str = Field(description="Description of the interactive navigation source.")
    source_type: str = Field(description="Declared source type from the source YAML.")
    base_url: str = Field(description="Base URL of the Clearfacts environment to explore.")
    users_file: str | None = Field(default=None, description="Optional path to a JSON fixture containing role credentials.")
    default_role: str | None = Field(default=None, description="Default role to use when the request omits one.")
    available_roles: list[str] = Field(default_factory=list, description="Roles allowed by the source configuration.")
    environment_notes: list[str] = Field(default_factory=list, description="Contextual notes for this environment.")
    entry_points: list[NavigationSourceEntryPoint] = Field(
        default_factory=list,
        description="Initial exploration targets that seed the ontology and guidance.",
    )
    ontology_guidance: str | None = Field(default=None, description="Guidance about what the exploration ontology should capture.")
    context_layer_info: str | None = Field(default=None, description="Optional layering/context guidance for ontology mapping.")
    playwright: PlaywrightMcpServerConfig = Field(description="Playwright MCP runtime configuration.")
    credentials: dict[str, NavigationSourceUserCredential] = Field(
        default_factory=dict,
        description="Resolved credentials keyed by role after users_file loading.",
    )


class NavigationScreenObservation(BaseModel):
    name: str = Field(description="Observed page or screen name.")
    url: str | None = Field(default=None, description="Observed URL if available.")
    title: str | None = Field(default=None, description="Observed page title if available.")
    description: str = Field(description="What the page or screen appears to be used for.")
    user_help_summary: str | None = Field(
        default=None,
        description="Optional user-facing explanation of how this screen is used.",
    )
    labels: list[str] = Field(default_factory=list, description="Important visible labels or headings for this screen.")
    navigation_hints: list[str] = Field(
        default_factory=list,
        description="Reusable hints for navigating to or recognizing this screen.",
    )
    role_scope: list[str] = Field(default_factory=list, description="Roles for which this observation was seen.")
    evidence: list[str] = Field(default_factory=list, description="Provenance references such as event IDs or snapshot files.")


class NavigationActionObservation(BaseModel):
    name: str = Field(description="Observed user action or affordance.")
    description: str = Field(description="What this action appears to do.")
    page_name: str | None = Field(default=None, description="Screen on which this action was observed.")
    target_hint: str | None = Field(default=None, description="Target reference, selector, or label hint if known.")
    role_scope: list[str] = Field(default_factory=list, description="Roles for which this action was seen.")
    evidence: list[str] = Field(default_factory=list, description="Provenance references such as event IDs or snapshot files.")


class NavigationLabelObservation(BaseModel):
    text: str = Field(description="Visible label, heading, or important short text.")
    page_name: str | None = Field(default=None, description="Screen on which this label was observed.")
    label_type: str | None = Field(default=None, description="Optional label type such as heading, button, menu item, or form field.")
    evidence: list[str] = Field(default_factory=list, description="Provenance references such as event IDs or snapshot files.")


class NavigationRouteStep(BaseModel):
    operation: ExplorationActionType = Field(description="Typed browser operation for deterministic route execution.")
    instruction: str = Field(description="Short instruction explaining this route step.")
    target: str | None = Field(default=None, description="Selector, affordance key, label, or current snapshot ref.")
    url: str | None = Field(default=None, description="URL for navigate_url operations.")
    text: str | None = Field(default=None, description="Text for type_text or wait_for_text operations.")
    key: str | None = Field(default=None, description="Keyboard key for press_key operations.")
    credential_field: CredentialField | None = Field(default=None, description="Credential field for type_role_credential.")
    expected_outcome: str | None = Field(default=None, description="Expected observable result after the step.")

    @model_validator(mode="after")
    def validate_operation_fields(self) -> "NavigationRouteStep":
        self.instruction = self.instruction.strip()
        if not self.instruction:
            raise ValueError("Route step instruction cannot be empty.")
        required_by_operation = {
            ExplorationActionType.NAVIGATE_URL: ("url",),
            ExplorationActionType.CLICK: ("target",),
            ExplorationActionType.TYPE_TEXT: ("target", "text"),
            ExplorationActionType.TYPE_ROLE_CREDENTIAL: ("target", "credential_field"),
            ExplorationActionType.PRESS_KEY: ("key",),
            ExplorationActionType.WAIT_FOR_TEXT: ("text",),
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


class NavigationPathObservation(BaseModel):
    description: str = Field(description="Summary of a discovered path through the UI.")
    from_screen: str | None = Field(default=None, description="Origin screen if known.")
    to_screen: str | None = Field(default=None, description="Destination screen if known.")
    action_summary: str = Field(description="Action summary for how the path was traversed.")
    route_steps: list[str] = Field(
        default_factory=list,
        description="Reusable high-level route steps for faster future navigation.",
    )
    typed_route_steps: list[NavigationRouteStep] = Field(
        default_factory=list,
        description="Executable typed route steps for deterministic navigation cache execution.",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Observable facts that indicate this path reached the intended destination.",
    )
    confidence: str | None = Field(default=None, description="Confidence level such as low, medium, or high.")
    evidence: list[str] = Field(default_factory=list, description="Provenance references such as event IDs or snapshot files.")


class NavigationValidationNote(BaseModel):
    note: str = Field(description="Validation note, uncertainty, or follow-up detail discovered during exploration.")
    severity: str = Field(default="info", description="Severity such as info, warning, or blocked.")
    evidence: list[str] = Field(default_factory=list, description="Provenance references such as event IDs or snapshot files.")


class NavigationOntologyDelta(BaseModel):
    screens: list[NavigationScreenObservation] = Field(default_factory=list)
    actions: list[NavigationActionObservation] = Field(default_factory=list)
    labels: list[NavigationLabelObservation] = Field(default_factory=list)
    navigation_paths: list[NavigationPathObservation] = Field(default_factory=list)
    validation_notes: list[NavigationValidationNote] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class NavigationOntologyDocument(BaseModel):
    source_name: str
    base_url: str
    entry_points: list[NavigationSourceEntryPoint] = Field(default_factory=list)
    screens: list[NavigationScreenObservation] = Field(default_factory=list)
    actions: list[NavigationActionObservation] = Field(default_factory=list)
    labels: list[NavigationLabelObservation] = Field(default_factory=list)
    navigation_paths: list[NavigationPathObservation] = Field(default_factory=list)
    validation_notes: list[NavigationValidationNote] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class NavigationPageAffordance(BaseModel):
    key: str = Field(description="Stable affordance key used by the planner and runtime resolver.")
    kind: str = Field(description="Affordance kind such as link, button, input, select, or textarea.")
    label: str | None = Field(default=None, description="Primary user-facing label or visible text.")
    selector: str | None = Field(default=None, description="Preferred stable selector for direct execution when available.")
    href: str | None = Field(default=None, description="Href for link affordances when available.")
    id_attribute: str | None = Field(default=None, description="DOM id attribute when available.")
    name_attribute: str | None = Field(default=None, description="DOM name attribute when available.")
    input_type: str | None = Field(default=None, description="Input type for form controls when available.")
    description: str | None = Field(default=None, description="Short human-readable description of the affordance.")


class NavigationPageEvidence(BaseModel):
    url: str | None = Field(default=None, description="Detected page URL when available.")
    title: str | None = Field(default=None, description="Detected page title when available.")
    text_excerpt: str | None = Field(default=None, description="Detected visible text excerpt when available.")
    page_summary: str | None = Field(default=None, description="Human-readable summary of the current page.")
    affordances: list[NavigationPageAffordance] = Field(
        default_factory=list,
        description="Structured current-page affordances that can be resolved at execution time.",
    )
    snapshot: str | None = Field(default=None, description="Raw snapshot or inspection output when available.")


class ExplorationAction(BaseModel):
    action_type: ExplorationActionType = Field(description="Next Playwright-backed action the agent should take.")
    summary: str = Field(description="Short explanation of why this is the next best step.")
    url: str | None = Field(default=None, description="Absolute URL for navigate_url actions.")
    target: str | None = Field(
        default=None,
        description="Semantic affordance key preferred; may also be a stable selector, href, or last-resort current-snapshot ref.",
    )
    text: str | None = Field(default=None, description="Text payload for type_text or wait_for_text actions.")
    key: str | None = Field(default=None, description="Keyboard key for press_key actions.")
    role: str | None = Field(default=None, description="Role whose credentials should be used for type_role_credential actions.")
    credential_field: CredentialField | None = Field(default=None, description="Credential field for type_role_credential actions.")
    expected_outcome: str | None = Field(default=None, description="What the agent expects to see after taking the action.")

    @model_validator(mode="after")
    def validate_required_fields(self) -> "ExplorationAction":
        required_by_action = {
            ExplorationActionType.NAVIGATE_URL: ("url",),
            ExplorationActionType.CLICK: ("target",),
            ExplorationActionType.TYPE_TEXT: ("target", "text"),
            ExplorationActionType.TYPE_ROLE_CREDENTIAL: ("target", "role", "credential_field"),
            ExplorationActionType.PRESS_KEY: ("key",),
            ExplorationActionType.WAIT_FOR_TEXT: ("text",),
        }
        required_fields = required_by_action.get(self.action_type, ())
        missing = [field_name for field_name in required_fields if getattr(self, field_name) in (None, "")]
        if missing:
            raise ValueError(
                f"Action '{self.action_type.value}' is missing required field(s): {', '.join(missing)}"
            )
        return self


class ExplorationDecision(BaseModel):
    state: ExplorationDecisionState = Field(description="Whether to continue, complete, block, or ask for user input.")
    summary: str = Field(description="Short explanation of the current exploration assessment.")
    next_action: ExplorationAction | None = Field(
        default=None,
        description="Single next action to execute when the state is continue.",
    )
    ontology_update: NavigationOntologyDelta = Field(
        default_factory=NavigationOntologyDelta,
        description="Ontology additions inferred from the latest page evidence and recent actions.",
    )
    user_question: str | None = Field(
        default=None,
        description="Question to surface when the agent needs clarification or guidance.",
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> "ExplorationDecision":
        if self.state == ExplorationDecisionState.CONTINUE and self.next_action is None:
            raise ValueError("A continue decision must include next_action.")
        if self.state == ExplorationDecisionState.NEEDS_USER_INPUT and not self.user_question:
            raise ValueError("A needs_user_input decision must include user_question.")
        return self


class ClearfactsNavigationRequest(BaseModel):
    source_name: str = Field(
        default="navigation_agent_clearfacts",
        description="Source identifier that resolves to agents/sources/<source_name>.yaml.",
    )
    instruction: str = Field(description="Natural-language exploration goal or navigation instruction.")
    role: str | None = Field(default=None, description="Optional role to use; defaults from the source configuration.")
    run_timestamp: str | None = Field(
        default=None,
        description="Existing run timestamp to continue; when omitted a new run is created.",
    )
    max_iterations: int = Field(default=6, ge=1, le=20, description="Upper bound for the exploration loop.")
    include_snapshot: bool = Field(default=True, description="Whether to capture and persist page snapshots.")

    @model_validator(mode="after")
    def validate_instruction(self) -> "ClearfactsNavigationRequest":
        self.instruction = self.instruction.strip()
        if not self.instruction:
            raise ValueError("Instruction cannot be empty.")
        return self


class NavigationEventRecord(BaseModel):
    event_id: str = Field(description="Unique event identifier for the run.")
    step_index: int = Field(description="1-based exploration step index.")
    phase: str = Field(description="Phase such as observation, decision, action, ontology, or result.")
    status: str = Field(description="Status for this event.")
    message: str | None = Field(default=None, description="Human-readable detail for the event.")
    tool_name: str | None = Field(default=None, description="Underlying Playwright MCP tool, if relevant.")
    arguments: dict[str, object] = Field(default_factory=dict, description="Arguments passed to the tool, if relevant.")
    snapshot_path: str | None = Field(default=None, description="Path to a persisted snapshot file, if any.")
    page_url: str | None = Field(default=None, description="Observed page URL for this event, if any.")
    page_title: str | None = Field(default=None, description="Observed page title for this event, if any.")


class ClearfactsNavigationResult(BaseModel):
    status: NavigationExecutionStatus = Field(description="Overall execution status.")
    source_name: str = Field(description="Source identifier used for the run.")
    run_timestamp: str = Field(description="Run timestamp folder used for persistence.")
    run_folder: str = Field(description="Absolute path to the run folder.")
    ontology_path: str = Field(description="Absolute path to the run-local ontology.")
    instruction: str = Field(description="Instruction that drove this exploration run.")
    role: str | None = Field(default=None, description="Role used for the run, if any.")
    message: str | None = Field(default=None, description="High-level result message.")
    question_for_user: str | None = Field(default=None, description="Follow-up question when more guidance is needed.")
    events: list[NavigationEventRecord] = Field(default_factory=list, description="Ordered exploration events.")
    current_page: NavigationPageEvidence | None = Field(default=None, description="Latest observed page evidence.")
    tool_inventory: list[str] = Field(default_factory=list, description="Playwright MCP tool names available for the run.")
