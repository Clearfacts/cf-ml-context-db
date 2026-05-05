from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from context_db.agents.clearfacts_navigation_agent.schemas import (
    ClearfactsNavigationResult,
    CredentialField,
    ExplorationActionType,
    NavigationActionObservation,
    NavigationEventRecord,
    NavigationExecutionStatus,
    NavigationOntologyDelta,
    NavigationPageEvidence,
    NavigationPathObservation,
    NavigationRouteStep,
    NavigationScreenObservation,
)
from context_db.agents.clearfacts_navigation_agent.tools import (
    ExecutedToolCall,
    append_navigation_event,
    load_manifest,
    load_navigation_ontology,
    merge_navigation_ontology,
    render_navigation_ontology,
    setup_navigation_run,
    update_manifest,
)
from context_db.agents.clearfacts_navigation_deepagent.agents import (
    ClearfactsNavigationDeepAgent,
    ClearfactsNavigationExecutionSubAgent,
    ClearfactsNavigationOntologyBatchAnalyzer,
    ClearfactsNavigationRouteCacheExecutor,
)
from context_db.agents.clearfacts_navigation_deepagent.model_config import (
    NAVIGATION_AGENT_MODEL_PROFILE_ENV,
    available_navigation_agent_model_profiles,
    load_navigation_agent_model_profile,
)
from context_db.agents.clearfacts_navigation_deepagent.runtime_tools import build_navigation_runtime_tools
from context_db.agents.clearfacts_navigation_deepagent.schemas import (
    BrowserExecutionOperation,
    CachedRouteExecutionStatus,
    CachedRouteExecutionTaskInput,
    CachedRouteExecutionTaskOutput,
    ClearfactsNavigationDeepAgentRequest,
    ClearfactsNavigationDeepAgentResult,
    ClearfactsNavigationOntologyUpdateRequest,
    ClearfactsNavigationValidationRequest,
    DeepAgentCoordinatorStructuredResponse,
    DeepAgentTraceReference,
    DeepAgentExecutionStatus,
    GoalAssessmentStatus,
    GoalAssessmentTaskOutput,
    NavigationExecutionTaskInput,
    NavigationExecutionTaskOutput,
    OntologyBatchAnalysisTaskOutput,
    RecoveryAnalysisTaskOutput,
    RecoveryStrategy,
    RoutePlanStep,
    RoutePlanningTaskOutput,
    ValidationAssessmentTaskOutput,
    ValidationOutcome,
)
from context_db.agents.clearfacts_navigation_deepagent.tools import (
    build_trace_references,
    extract_json_object,
    parse_route_planner_task_input,
    parse_subagent_task_input,
    write_trace_artifact,
)


class ClearfactsNavigationDeepAgentTest(unittest.TestCase):
    class _FakeLLM:
        def with_structured_output(self, schema):
            class _FakeStructuredLLM:
                def invoke(self, _messages):
                    raise AssertionError("Structured LLM should not be invoked in this unit test.")

            return _FakeStructuredLLM()

    @staticmethod
    def _write_model_profile_config(path: Path) -> None:
        path.write_text(
            """
default_profile: balanced
profiles:
  balanced:
    coordinator:
      model_name: gpt-5-mini-2025-08-07
      max_tokens: 4000
    route_planner:
      model_name: gpt-5-mini-2025-08-07
      max_tokens: 3000
    goal_assessor:
      model_name: gpt-5-nano-2025-08-07
      max_tokens: 1500
    recovery:
      model_name: gpt-5-mini-2025-08-07
      max_tokens: 3000
    validation:
      model_name: gpt-5-mini-2025-08-07
      max_tokens: 3000
    ontology_batch_analyzer:
      model_name: gpt-5-mini-2025-08-07
      max_tokens: 4000
      reasoning:
        effort: low
  quality:
    coordinator:
      model_name: gpt-5-2025-08-07
      max_tokens: 4000
    route_planner:
      model_name: gpt-5-2025-08-07
      max_tokens: 4000
    goal_assessor:
      model_name: gpt-5-mini-2025-08-07
      max_tokens: 2000
    recovery:
      model_name: gpt-5-2025-08-07
      max_tokens: 4000
    validation:
      model_name: gpt-5-2025-08-07
      max_tokens: 4000
    ontology_batch_analyzer:
      model_name: gpt-5-2025-08-07
      max_tokens: 4000
      reasoning:
        effort: low
""".lstrip(),
            encoding="utf-8",
        )

    def test_navigation_model_profile_loader_uses_default_and_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "navigation_agent_models.yaml"
            self._write_model_profile_config(config_path)

            default_profile = load_navigation_agent_model_profile(config_path=config_path)
            with patch.dict("os.environ", {NAVIGATION_AGENT_MODEL_PROFILE_ENV: "quality"}):
                env_profile = load_navigation_agent_model_profile(config_path=config_path)
            available_profiles = available_navigation_agent_model_profiles(config_path=config_path)

        self.assertEqual(default_profile.name, "balanced")
        self.assertEqual(default_profile.goal_assessor.model_name, "gpt-5-nano-2025-08-07")
        self.assertEqual(env_profile.name, "quality")
        self.assertEqual(env_profile.goal_assessor.model_name, "gpt-5-mini-2025-08-07")
        self.assertEqual(available_profiles, ["balanced", "quality"])

    def test_navigation_model_profile_loader_rejects_unknown_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "navigation_agent_models.yaml"
            self._write_model_profile_config(config_path)

            with self.assertRaisesRegex(ValueError, "Valid profiles: balanced, quality"):
                load_navigation_agent_model_profile("missing", config_path=config_path)

    def test_extract_json_object_reads_json_code_block(self) -> None:
        payload = extract_json_object(
            """
            Use this payload:
            ```json
            {"instruction":"open purchase inbox","max_iterations":4}
            ```
            """
        )
        self.assertEqual(payload["instruction"], "open purchase inbox")
        self.assertEqual(payload["max_iterations"], 4)

    def test_parse_subagent_task_input_validates_model(self) -> None:
        parsed = parse_subagent_task_input(
            '{"source_name":"navigation_agent_clearfacts","instruction":"login","max_iterations":3,"include_snapshot":true}',
            NavigationExecutionTaskInput,
        )
        self.assertEqual(parsed.source_name, "navigation_agent_clearfacts")
        self.assertEqual(parsed.max_iterations, 3)

    def test_route_planner_parses_labeled_prose_payload(self) -> None:
        payload = """
        Check if there is a known reusable route in the current ontology to accomplish the user goal.

        Inputs:

        source_name: navigation_agent_clearfacts
        user_goal: "go to the archive"
        role: null (no active role specified; use ontology knowledge only)
        run_timestamp: 20260504_182509
        current_ontology_yaml: |
          source_name: navigation_agent_clearfacts
          base_url: https://staging.acc.clearfacts.be
          screens: []
          navigation_paths: []
        current_page: null

        Output:

        has_known_route: boolean
        """
        parsed = parse_route_planner_task_input(payload)
        self.assertEqual(parsed.source_name, "navigation_agent_clearfacts")
        self.assertEqual(parsed.user_goal, "go to the archive")
        self.assertIsNone(parsed.role)
        self.assertEqual(parsed.run_timestamp, "20260504_182509")
        self.assertIn("navigation_paths", parsed.current_ontology_yaml)

    def test_route_planner_accepts_goal_and_run_timestamp_aliases(self) -> None:
        parsed = parse_route_planner_task_input(
            """
            Check whether the ontology has a route.
            Source: navigation_agent_clearfacts
            Goal: go to the archive
            Run timestamp: 20260504_182509
            """,
        )
        self.assertEqual(parsed.source_name, "navigation_agent_clearfacts")
        self.assertEqual(parsed.user_goal, "go to the archive")
        self.assertEqual(parsed.run_timestamp, "20260504_182509")

    def test_route_planner_uses_active_run_defaults_for_omitted_safe_fields(self) -> None:
        parsed = parse_route_planner_task_input(
            "Goal: go to the archive",
            default_source_name="navigation_agent_clearfacts",
            default_run_timestamp="20260504_182509",
        )
        self.assertEqual(parsed.source_name, "navigation_agent_clearfacts")
        self.assertEqual(parsed.user_goal, "go to the archive")
        self.assertEqual(parsed.run_timestamp, "20260504_182509")

    def test_route_planner_runtime_tool_accepts_structured_payload(self) -> None:
        class FakeRoutePlanner:
            def invoke(self, query):
                return RoutePlanningTaskOutput(
                    has_known_route=False,
                    summary=f"No known route for {query.user_goal}.",
                    missing_coverage=["archive"],
                )

        tools = build_navigation_runtime_tools(
            route_cache=object(),
            route_planner=FakeRoutePlanner(),
            execution=object(),
            recovery=object(),
            goal_assessment=object(),
        )
        tool_by_name = {tool.name: tool for tool in tools}
        payload = tool_by_name["plan_known_route"].invoke(
            {
                "source_name": "navigation_agent_clearfacts",
                "user_goal": "go to the archive",
                "role": None,
                "run_timestamp": "20260504_182509",
                "current_ontology_yaml": "navigation_paths: []",
                "current_page": None,
            }
        )
        result = RoutePlanningTaskOutput.model_validate_json(payload)
        self.assertFalse(result.has_known_route)
        self.assertEqual(result.missing_coverage, ["archive"])

    def test_runtime_tool_rejects_invalid_browser_operation_before_execution(self) -> None:
        class FailingExecution:
            def invoke(self, _query, *, browser=None):
                raise AssertionError("Invalid tool input should not reach execution.")

        tools = build_navigation_runtime_tools(
            route_cache=object(),
            route_planner=object(),
            execution=FailingExecution(),
            recovery=object(),
            goal_assessment=object(),
        )
        tool_by_name = {tool.name: tool for tool in tools}
        with self.assertRaises(Exception):
            tool_by_name["execute_browser_operation"].invoke(
                {
                    "source_name": "navigation_agent_clearfacts",
                    "instruction": "Click archive.",
                    "operation": "click",
                    "run_timestamp": "20260504_182509",
                }
            )

    def test_route_cache_executes_parseable_legacy_route_and_reports_partial_goal(self) -> None:
        class FakeExecution:
            def __init__(self):
                self.queries = []

            def invoke(self, query, *, browser=None):
                self.queries.append(query)
                current_page = NavigationPageEvidence(
                    url="https://example.test/current",
                    title="Current page",
                    page_summary=query.expected_outcome,
                )
                if query.operation == BrowserExecutionOperation.WAIT_FOR_TEXT and query.text:
                    current_page.page_summary = f"{query.text} is visible."
                return NavigationExecutionTaskOutput(
                    operation=query.operation,
                    status=NavigationExecutionStatus.COMPLETED,
                    message=query.expected_outcome or query.instruction,
                    current_page=current_page,
                    run_timestamp=query.run_timestamp,
                    run_folder="/tmp/run",
                    ontology_path="/tmp/run/ontology.md",
                    raw_result=ClearfactsNavigationResult(
                        status=NavigationExecutionStatus.COMPLETED,
                        source_name=query.source_name,
                        run_timestamp=query.run_timestamp,
                        run_folder="/tmp/run",
                        ontology_path="/tmp/run/ontology.md",
                        instruction=query.instruction,
                        role=query.role,
                        message=query.expected_outcome or query.instruction,
                        current_page=current_page,
                    ),
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160507",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Authenticate from the Login page to reach the role-specific Dashboard.",
                            from_screen="Login page",
                            to_screen="Dashboard (VDL Accountant)",
                            action_summary="Fill credentials and submit.",
                            route_steps=[
                                "Navigate to https://staging.acc.clearfacts.be/login",
                                "Type username into #username",
                                "Type password into #password",
                                "Click #_submit",
                            ],
                            success_criteria=["Dashboard headings visible (e.g., Bedrijfsresultaat per boekperiode)"],
                            confidence="high",
                        ),
                        NavigationPathObservation(
                            description="Navigate from the Dashboard to the Sales inbox.",
                            from_screen="Dashboard (VDL Accountant)",
                            to_screen="Sales inbox",
                            action_summary="Click the Verkoop link.",
                            route_steps=['On Dashboard, click a[href="/test-dossier-vdl/inbox/sale"]'],
                            success_criteria=["Sales inbox heading 'Digitale postbus: Verkoop Scan Upload' is visible"],
                            confidence="high",
                        ),
                    ]
                ),
            )
            fake_execution = FakeExecution()
            route_cache = ClearfactsNavigationRouteCacheExecutor(execution=fake_execution)

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160507",
                    force=False,
                )
                if timestamp != "20260503_160507"
                else run,
            ):
                result = route_cache.invoke(
                    CachedRouteExecutionTaskInput(
                        source_name="navigation_agent_clearfacts",
                        user_goal="move to sale inbox then go to purchase inbox",
                        role="sme_admin",
                        run_timestamp="20260503_160507",
                    )
                )

        self.assertEqual(result.status, CachedRouteExecutionStatus.PARTIAL)
        self.assertEqual(result.remaining_goal, "go to Purchase inbox")
        self.assertEqual(
            [query.operation for query in fake_execution.queries],
            [
                BrowserExecutionOperation.NAVIGATE_URL,
                BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL,
                BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL,
                BrowserExecutionOperation.CLICK,
                BrowserExecutionOperation.WAIT_FOR_TEXT,
                BrowserExecutionOperation.CLICK,
                BrowserExecutionOperation.WAIT_FOR_TEXT,
            ],
        )
        self.assertEqual(fake_execution.queries[1].credential_field, CredentialField.USERNAME)
        self.assertEqual(fake_execution.queries[2].credential_field, CredentialField.PASSWORD)

    def test_route_cache_executes_known_prefix_for_unknown_action_target(self) -> None:
        class FakeExecution:
            def __init__(self):
                self.queries = []

            def invoke(self, query, *, browser=None):
                self.queries.append(query)
                current_page = NavigationPageEvidence(
                    url="https://staging.acc.clearfacts.be/test-dossier-vdl/dashboard",
                    title="Dashboard",
                    page_summary=query.expected_outcome,
                )
                return NavigationExecutionTaskOutput(
                    operation=query.operation,
                    status=NavigationExecutionStatus.COMPLETED,
                    message=query.expected_outcome or query.instruction,
                    current_page=current_page,
                    run_timestamp=query.run_timestamp,
                    run_folder="/tmp/run",
                    ontology_path="/tmp/run/ontology.md",
                    raw_result=ClearfactsNavigationResult(
                        status=NavigationExecutionStatus.COMPLETED,
                        source_name=query.source_name,
                        run_timestamp=query.run_timestamp,
                        run_folder="/tmp/run",
                        ontology_path="/tmp/run/ontology.md",
                        instruction=query.instruction,
                        role=query.role,
                        message=query.expected_outcome or query.instruction,
                        current_page=current_page,
                    ),
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160509",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    actions=[
                        NavigationActionObservation(
                            name="Navigeer naar 'Betalingen' (Payments)",
                            description="Open the Payments module from the dashboard navigation.",
                            page_name="Dashboard (VDL Accountant)",
                            target_hint='a[href="/test-dossier-vdl/payments"]',
                        )
                    ],
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Authenticate from the Login page to reach the role-specific Dashboard.",
                            from_screen="Login page",
                            to_screen="Dashboard (VDL Accountant)",
                            action_summary="Fill credentials and submit.",
                            route_steps=[
                                "Navigate to https://staging.acc.clearfacts.be/login",
                                "Type username into #username",
                                "Type password into #password",
                                "Click #_submit",
                            ],
                            success_criteria=["Dashboard headings visible (e.g., Bedrijfsresultaat per boekperiode)"],
                            confidence="high",
                        )
                    ],
                ),
            )
            fake_execution = FakeExecution()
            route_cache = ClearfactsNavigationRouteCacheExecutor(execution=fake_execution)

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                return_value=run,
            ):
                result = route_cache.invoke(
                    CachedRouteExecutionTaskInput(
                        source_name="navigation_agent_clearfacts",
                        user_goal="go to payments",
                        role="sme_admin",
                        run_timestamp="20260503_160509",
                    )
                )

        self.assertEqual(result.status, CachedRouteExecutionStatus.PARTIAL)
        self.assertEqual(result.remaining_goal, "go to Payments")
        self.assertEqual(result.matched_paths, ["Authenticate from the Login page to reach the role-specific Dashboard."])
        self.assertEqual(
            [query.operation for query in fake_execution.queries],
            [
                BrowserExecutionOperation.NAVIGATE_URL,
                BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL,
                BrowserExecutionOperation.TYPE_ROLE_CREDENTIAL,
                BrowserExecutionOperation.CLICK,
                BrowserExecutionOperation.WAIT_FOR_TEXT,
            ],
        )

    def test_route_cache_fast_path_batches_steps_without_executor_subagent(self) -> None:
        class FakeExecution:
            def __init__(self):
                self.queries = []

            def invoke(self, query, *, browser=None):
                self.queries.append(query)
                raise AssertionError("Fast route cache should not invoke the executor subagent.")

        class FakeBrowser:
            def __init__(self):
                self.calls = []

            def tool_inventory(self):
                return ["browser_navigate", "browser_type", "browser_click", "browser_evaluate"]

            async def navigate(self, url):
                self.calls.append(("navigate", url))
                return ExecutedToolCall(tool_name="browser_navigate", arguments={"url": url}, message="navigated")

            async def type_text(self, target, text, *, slowly=False):
                self.calls.append(("type_text", target, text, slowly))
                return ExecutedToolCall(
                    tool_name="browser_type",
                    arguments={"target": target, "text": text, "slowly": slowly},
                    message="typed",
                )

            async def click(self, target):
                self.calls.append(("click", target))
                return ExecutedToolCall(tool_name="browser_click", arguments={"target": target}, message="clicked")

            async def wait_for_text(self, text):
                self.calls.append(("wait_for_text", text))
                return ExecutedToolCall(tool_name="browser_evaluate", arguments={"text": text}, message="observed")

            async def inspect_page(self, include_snapshot):
                self.calls.append(("inspect_page", include_snapshot))
                return NavigationPageEvidence(
                    url="https://staging.acc.clearfacts.be/test-dossier-vdl/dashboard",
                    title="Clearfacts voor VDL Accountant",
                    page_summary="Dashboard is visible.",
                    snapshot="- heading \"Bedrijfsresultaat per boekperiode\" [ref=e1]" if include_snapshot else None,
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160510",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Authenticate from the Login page to reach the role-specific Dashboard.",
                            from_screen="Login page",
                            to_screen="Dashboard (VDL Accountant)",
                            action_summary="Fill credentials and submit.",
                            route_steps=[
                                "Navigate to https://staging.acc.clearfacts.be/login",
                                "Type username into #username",
                                "Type password into #password",
                                "Click #_submit",
                            ],
                            success_criteria=["Dashboard headings visible (e.g., Bedrijfsresultaat per boekperiode)"],
                            confidence="high",
                        )
                    ]
                ),
            )
            fake_execution = FakeExecution()
            fake_browser = FakeBrowser()
            route_cache = ClearfactsNavigationRouteCacheExecutor(execution=fake_execution)

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                return_value=run,
            ):
                result = route_cache.invoke(
                    CachedRouteExecutionTaskInput(
                        source_name="navigation_agent_clearfacts",
                        user_goal="go to dashboard",
                        role="sme_admin",
                        run_timestamp="20260503_160510",
                        include_snapshot=True,
                    ),
                    browser=fake_browser,
                )

            events = [
                json.loads(line)
                for line in run.events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(result.status, CachedRouteExecutionStatus.COMPLETED)
        self.assertFalse(fake_execution.queries)
        self.assertEqual(
            [call[0] for call in fake_browser.calls],
            ["navigate", "type_text", "type_text", "click", "wait_for_text", "inspect_page"],
        )
        self.assertTrue(fake_browser.calls[1][3])
        self.assertTrue(fake_browser.calls[2][3])
        self.assertEqual([event["phase"] for event in events], ["action", "action", "action", "action", "action", "observation"])
        self.assertEqual(events[1]["arguments"]["text"], "<redacted>")
        self.assertEqual(events[2]["arguments"]["text"], "<redacted>")

    def test_route_cache_fast_path_marks_completed_when_truncated_after_target_reached(self) -> None:
        class FakeExecution:
            def invoke(self, query, *, browser=None):
                raise AssertionError("Fast route cache should not invoke the executor subagent.")

        class FakeBrowser:
            def __init__(self):
                self.calls = []

            def tool_inventory(self):
                return ["browser_navigate", "browser_type", "browser_click", "browser_evaluate"]

            async def navigate(self, url):
                self.calls.append(("navigate", url))
                return ExecutedToolCall(tool_name="browser_navigate", arguments={"url": url}, message="navigated")

            async def type_text(self, target, text, *, slowly=False):
                self.calls.append(("type_text", target, text, slowly))
                return ExecutedToolCall(tool_name="browser_type", arguments={"target": target, "text": text}, message="typed")

            async def click(self, target):
                self.calls.append(("click", target))
                return ExecutedToolCall(tool_name="browser_click", arguments={"target": target}, message="clicked")

            async def wait_for_text(self, text):
                self.calls.append(("wait_for_text", text))
                return ExecutedToolCall(tool_name="browser_evaluate", arguments={"text": text}, message="observed")

            async def inspect_page(self, include_snapshot):
                self.calls.append(("inspect_page", include_snapshot))
                return NavigationPageEvidence(
                    url="https://staging.acc.clearfacts.be/test-dossier-vdl/payments",
                    title="Clearfacts voor VDL Accountant",
                    text_excerpt="Betalingen Betaalmand Uitgevoerde betalingen Filteren",
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160511",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Authenticate from the Login page to reach the role-specific Dashboard.",
                            from_screen="Login page",
                            to_screen="Dashboard (VDL Accountant)",
                            action_summary="Fill credentials and submit.",
                            typed_route_steps=[
                                NavigationRouteStep(
                                    operation=ExplorationActionType.NAVIGATE_URL,
                                    instruction="Navigate to login.",
                                    url="https://staging.acc.clearfacts.be/login",
                                ),
                                NavigationRouteStep(
                                    operation=ExplorationActionType.TYPE_ROLE_CREDENTIAL,
                                    instruction="Type username.",
                                    target="#username",
                                    credential_field=CredentialField.USERNAME,
                                ),
                                NavigationRouteStep(
                                    operation=ExplorationActionType.TYPE_ROLE_CREDENTIAL,
                                    instruction="Type password.",
                                    target="#password",
                                    credential_field=CredentialField.PASSWORD,
                                ),
                                NavigationRouteStep(
                                    operation=ExplorationActionType.CLICK,
                                    instruction="Submit login.",
                                    target="#_submit",
                                ),
                                NavigationRouteStep(
                                    operation=ExplorationActionType.WAIT_FOR_TEXT,
                                    instruction="Wait for dashboard.",
                                    text="Bedrijfsresultaat per boekperiode",
                                ),
                            ],
                            confidence="high",
                        ),
                        NavigationPathObservation(
                            description="Navigate from the Dashboard to the Payments module.",
                            from_screen="Dashboard (VDL Accountant)",
                            to_screen="Payments page",
                            action_summary="Click the Betalingen link.",
                            typed_route_steps=[
                                NavigationRouteStep(
                                    operation=ExplorationActionType.CLICK,
                                    instruction="Click Payments.",
                                    target='a[href="/test-dossier-vdl/payments"]',
                                ),
                                NavigationRouteStep(
                                    operation=ExplorationActionType.WAIT_FOR_TEXT,
                                    instruction="Wait for payments filters.",
                                    text="Filteren",
                                ),
                            ],
                            confidence="high",
                        ),
                    ]
                ),
            )
            route_cache = ClearfactsNavigationRouteCacheExecutor(execution=FakeExecution())

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                return_value=run,
            ):
                result = route_cache.invoke(
                    CachedRouteExecutionTaskInput(
                        source_name="navigation_agent_clearfacts",
                        user_goal="go to payments",
                        role="sme_admin",
                        run_timestamp="20260503_160511",
                        max_steps=6,
                    ),
                    browser=FakeBrowser(),
                )

        self.assertEqual(result.status, CachedRouteExecutionStatus.COMPLETED)
        self.assertIsNone(result.remaining_goal)
        self.assertEqual(len(result.executed_steps), 6)
        self.assertEqual(result.current_page.url, "https://staging.acc.clearfacts.be/test-dossier-vdl/payments")

    def test_route_cache_wait_text_skips_page_title_success_criteria(self) -> None:
        steps = ClearfactsNavigationRouteCacheExecutor._steps_for_chain(
            [
                NavigationPathObservation(
                    description="Authenticate from the Login page to reach the role-specific Dashboard.",
                    from_screen="Login page",
                    to_screen="Dashboard (VDL Accountant)",
                    action_summary="Fill credentials and submit.",
                    route_steps=[
                        "Navigate to https://staging.acc.clearfacts.be/login",
                        "Type username into #username",
                        "Type password into #password",
                        "Click #_submit",
                    ],
                    success_criteria=[
                        "Browser loads a dossier dashboard URL containing /dashboard",
                        "Page title shows 'Clearfacts voor VDL Accountant'",
                        "Dashboard headings visible (e.g., Bedrijfsresultaat per boekperiode)",
                    ],
                    confidence="high",
                )
            ],
            source_base_url="https://staging.acc.clearfacts.be",
        )

        wait_steps = [step for _path, step in steps if step.operation == ExplorationActionType.WAIT_FOR_TEXT]
        self.assertEqual(len(wait_steps), 1)
        self.assertEqual(wait_steps[0].text, "Bedrijfsresultaat per boekperiode")

    def test_route_cache_does_not_wait_for_title_only_success_criteria(self) -> None:
        steps = ClearfactsNavigationRouteCacheExecutor._steps_for_chain(
            [
                NavigationPathObservation(
                    description="Authenticate from the Login page to reach the role-specific Dashboard.",
                    from_screen="Login page",
                    to_screen="Dashboard (VDL Accountant)",
                    action_summary="Fill credentials and submit.",
                    route_steps=[
                        "Navigate to https://staging.acc.clearfacts.be/login",
                        "Type username into #username",
                        "Type password into #password",
                        "Click #_submit",
                    ],
                    success_criteria=[
                        "Browser loads a dossier dashboard URL containing /dashboard",
                        "Page title shows 'Clearfacts voor VDL Accountant'",
                    ],
                    confidence="high",
                )
            ],
            source_base_url="https://staging.acc.clearfacts.be",
        )

        self.assertFalse(any(step.operation == ExplorationActionType.WAIT_FOR_TEXT for _path, step in steps))

    def test_typed_route_steps_round_trip_through_ontology_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160508",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Navigate from the Dashboard to the Archive.",
                            from_screen="Dashboard (VDL Accountant)",
                            to_screen="Archive",
                            action_summary="Click the archive menu link.",
                            route_steps=["Click the Archief link."],
                            typed_route_steps=[
                                NavigationRouteStep(
                                    operation=ExplorationActionType.CLICK,
                                    instruction="Open the Archive module.",
                                    target='a[href="/test-dossier-vdl/archive"]',
                                    expected_outcome="Archive page is visible.",
                                )
                            ],
                            success_criteria=["Archive page is visible."],
                            confidence="high",
                        )
                    ]
                ),
            )

            ontology = load_navigation_ontology(run.run_ontology)

        self.assertEqual(len(ontology.navigation_paths), 1)
        self.assertEqual(len(ontology.navigation_paths[0].typed_route_steps), 1)
        self.assertEqual(ontology.navigation_paths[0].typed_route_steps[0].operation, ExplorationActionType.CLICK)
        self.assertEqual(ontology.navigation_paths[0].typed_route_steps[0].target, 'a[href="/test-dossier-vdl/archive"]')

    def test_validation_request_trims_claim_and_optional_instruction(self) -> None:
        request = ClearfactsNavigationValidationRequest(
            claim="  SME can upload a purchase invoice from the purchase inbox.  ",
            procedure_instruction="  Go to the purchase inbox and upload an invoice.  ",
        )
        self.assertEqual(request.claim, "SME can upload a purchase invoice from the purchase inbox.")
        self.assertEqual(request.procedure_instruction, "Go to the purchase inbox and upload an invoice.")

    def test_route_plan_step_validates_operation_specific_fields(self) -> None:
        with self.assertRaises(ValueError):
            RoutePlanStep(
                operation=BrowserExecutionOperation.CLICK,
                instruction="Click the archive menu item.",
            )

    def test_recovery_output_requires_strategy_payload(self) -> None:
        with self.assertRaises(ValueError):
            RecoveryAnalysisTaskOutput(
                strategy=RecoveryStrategy.ASK_USER,
                summary="The target area is ambiguous.",
            )

    def test_goal_assessment_requires_question_for_user_input(self) -> None:
        with self.assertRaises(ValueError):
            GoalAssessmentTaskOutput(
                status=GoalAssessmentStatus.NEEDS_USER_INPUT,
                summary="The user must choose an entity first.",
            )

    def test_write_trace_artifact_persists_message_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160500",
            )
            path = write_trace_artifact(
                run=run,
                agent_name="coordinator",
                trace_kind="coordinator",
                input_messages=[HumanMessage(content="hello")],
                output_messages=[AIMessage(content="world")],
                structured_input={"step": 1},
                structured_output={"status": "completed"},
            )
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["input_messages"][0]["content"], "hello")
            references = build_trace_references(run)
            self.assertTrue(any(reference.path == str(path) for reference in references))

    def test_execution_runtime_tool_returns_json_output(self) -> None:
        class FakeBrowser:
            def tool_inventory(self):
                return ["browser_snapshot", "browser_evaluate"]

            async def inspect_page(self, include_snapshot: bool):
                return NavigationPageEvidence(
                    url="https://example.test/inbox",
                    title="Inbox",
                    page_summary="Purchase inbox is visible.",
                    snapshot="- heading \"Inbox\" [ref=e1]" if include_snapshot else None,
                )

        subagent = ClearfactsNavigationExecutionSubAgent(model_name="gpt-5-2025-08-07")

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs = {}

            def ensure_run(source_name, timestamp=None):
                resolved_timestamp = timestamp or "20260503_160501"
                if resolved_timestamp not in runs:
                    runs[resolved_timestamp] = setup_navigation_run(
                        source_name,
                        workspace_dir=tmp_dir,
                        timestamp=resolved_timestamp,
                    )
                return runs[resolved_timestamp]

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=ensure_run,
            ):
                tools = build_navigation_runtime_tools(
                    route_cache=object(),
                    route_planner=object(),
                    execution=subagent,
                    recovery=object(),
                    goal_assessment=object(),
                    browser=FakeBrowser(),
                )
                tool_by_name = {tool.name: tool for tool in tools}
                payload = tool_by_name["execute_browser_operation"].invoke(
                    {
                        "source_name": "navigation_agent_clearfacts",
                        "instruction": "open purchase inbox",
                        "operation": "inspect",
                        "run_timestamp": "20260503_160501",
                        "role": "sme_admin",
                        "max_iterations": 3,
                        "include_snapshot": True,
                    }
                )
                result = NavigationExecutionTaskOutput.model_validate_json(payload)
                self.assertEqual(result.status, NavigationExecutionStatus.COMPLETED)
            self.assertIsNotNone(result.current_page)
            self.assertIsNone(result.current_page.snapshot)
            self.assertNotIn("events", json.loads(payload))

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_deepagent_model_profile_wires_models_per_agent_role(self, mock_get_azure_llm) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        deepagent = ClearfactsNavigationDeepAgent(model_profile="balanced")

        calls = [
            (
                call.kwargs["model_name"],
                call.kwargs["max_tokens"],
                call.kwargs.get("reasoning"),
            )
            for call in mock_get_azure_llm.call_args_list
        ]
        self.assertEqual(deepagent._model_profile.name, "balanced")
        self.assertEqual(
            calls,
            [
                ("gpt-5-mini-2025-08-07", 4000, None),
                ("gpt-5-mini-2025-08-07", 3000, None),
                ("gpt-5-mini-2025-08-07", 3000, None),
                ("gpt-5-nano-2025-08-07", 1500, None),
                ("gpt-5-mini-2025-08-07", 3000, None),
                ("gpt-5-mini-2025-08-07", 4000, {"effort": "low"}),
            ],
        )

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_deepagent_explicit_model_name_keeps_single_model_compatibility(self, mock_get_azure_llm) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07", max_tokens=1234)

        calls = [
            (
                call.kwargs["model_name"],
                call.kwargs["max_tokens"],
                call.kwargs.get("reasoning"),
            )
            for call in mock_get_azure_llm.call_args_list
        ]
        self.assertEqual(deepagent._model_profile.name, "single-model")
        self.assertEqual(
            calls,
            [
                ("gpt-5-2025-08-07", 1234, None),
                ("gpt-5-2025-08-07", 1234, None),
                ("gpt-5-2025-08-07", 1234, None),
                ("gpt-5-2025-08-07", 1234, None),
                ("gpt-5-2025-08-07", 1234, None),
                ("gpt-5-2025-08-07", 1234, {"effort": "low"}),
            ],
        )

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_deepagent_short_circuits_completed_deterministic_route_cache(
        self,
        mock_get_azure_llm,
        mock_create_agent,
    ) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        class FakeBrowser:
            def __init__(self):
                self.calls = []

            def tool_inventory(self):
                return ["browser_navigate", "browser_type", "browser_click", "browser_evaluate"]

            async def navigate(self, url):
                self.calls.append(("navigate", url))
                return ExecutedToolCall(tool_name="browser_navigate", arguments={"url": url}, message="navigated")

            async def type_text(self, target, text, *, slowly=False):
                self.calls.append(("type_text", target, text, slowly))
                return ExecutedToolCall(tool_name="browser_type", arguments={"target": target, "text": text}, message="typed")

            async def click(self, target):
                self.calls.append(("click", target))
                return ExecutedToolCall(tool_name="browser_click", arguments={"target": target}, message="clicked")

            async def wait_for_text(self, text):
                self.calls.append(("wait_for_text", text))
                return ExecutedToolCall(tool_name="browser_evaluate", arguments={"text": text}, message="observed")

            async def inspect_page(self, include_snapshot):
                self.calls.append(("inspect_page", include_snapshot))
                return NavigationPageEvidence(
                    url="https://staging.acc.clearfacts.be/test-dossier-vdl/dashboard",
                    title="Clearfacts voor VDL Accountant",
                    text_excerpt="Dashboard Bedrijfsresultaat per boekperiode",
                )

        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07")
        fake_browser = FakeBrowser()
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_160512",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Authenticate from the Login page to reach the role-specific Dashboard.",
                            from_screen="Login page",
                            to_screen="Dashboard (VDL Accountant)",
                            action_summary="Fill credentials and submit.",
                            route_steps=[
                                "Navigate to https://staging.acc.clearfacts.be/login",
                                "Type username into #username",
                                "Type password into #password",
                                "Click #_submit",
                            ],
                            success_criteria=["Dashboard heading Bedrijfsresultaat per boekperiode is visible"],
                            confidence="high",
                        )
                    ]
                ),
            )

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                return_value=run,
            ):
                result = deepagent.invoke(
                    ClearfactsNavigationDeepAgentRequest(
                        instruction="go to dashboard",
                        role="sme_admin",
                        run_timestamp="20260503_160512",
                    ),
                    browser=fake_browser,
                )

        self.assertEqual(result.status, DeepAgentExecutionStatus.COMPLETED)
        self.assertIsNotNone(result.latest_navigation_result)
        self.assertEqual(result.latest_navigation_result.current_page.url, "https://staging.acc.clearfacts.be/test-dossier-vdl/dashboard")
        self.assertEqual([call[0] for call in fake_browser.calls], ["navigate", "type_text", "type_text", "click", "inspect_page"])
        mock_create_agent.assert_not_called()

    def test_latest_navigation_result_from_messages_reads_cached_route_tool(self) -> None:
        latest_navigation = ClearfactsNavigationResult(
            status=NavigationExecutionStatus.COMPLETED,
            source_name="navigation_agent_clearfacts",
            run_timestamp="20260503_160513",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            instruction="go to payments",
            role="sme_admin",
            message="Reached payments.",
            current_page=NavigationPageEvidence(
                url="https://staging.acc.clearfacts.be/test-dossier-vdl/payments",
                title="Payments",
            ),
        )
        route_payload = CachedRouteExecutionTaskOutput(
            status=CachedRouteExecutionStatus.COMPLETED,
            summary="Fast-executed the matching deterministic route cache path(s).",
            source_name="navigation_agent_clearfacts",
            run_timestamp="20260503_160513",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            latest_navigation_result=latest_navigation,
        )

        parsed = ClearfactsNavigationDeepAgent._latest_navigation_result_from_messages(
            [
                ToolMessage(
                    content=route_payload.model_dump_json(),
                    tool_call_id="call-1",
                    name="execute_cached_route",
                )
            ]
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.current_page.url, "https://staging.acc.clearfacts.be/test-dossier-vdl/payments")

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_coordinator_returns_structured_result_and_latest_navigation_output(
        self,
        mock_get_azure_llm,
        mock_create_agent,
    ) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07")
        navigation_tool_payload = NavigationExecutionTaskOutput(
            status=NavigationExecutionStatus.COMPLETED,
            message="Reached the purchase inbox.",
            current_page=NavigationPageEvidence(url="https://example.test/inbox", title="Purchase inbox"),
            run_timestamp="20260503_160502",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            raw_result=ClearfactsNavigationResult(
                status=NavigationExecutionStatus.COMPLETED,
                source_name="navigation_agent_clearfacts",
                run_timestamp="20260503_160502",
                run_folder="/tmp/run",
                ontology_path="/tmp/run/ontology.md",
                instruction="open purchase inbox",
                role="sme_admin",
                message="Reached the purchase inbox.",
                current_page=NavigationPageEvidence(url="https://example.test/inbox", title="Purchase inbox"),
            ),
        )

        fake_compiled_agent = type(
            "FakeCompiledAgent",
            (),
            {
                "invoke": lambda self, payload: {
                    "messages": [
                        HumanMessage(content="user"),
                        ToolMessage(content=navigation_tool_payload.model_dump_json(), tool_call_id="call-1"),
                    ],
                    "structured_response": DeepAgentCoordinatorStructuredResponse(
                        status=DeepAgentExecutionStatus.COMPLETED,
                        summary="Purchase inbox reached.",
                        run_timestamp="20260503_160502",
                        run_folder="/tmp/run",
                        ontology_path="/tmp/run/ontology.md",
                    ),
                }
            },
        )()
        mock_create_agent.return_value = fake_compiled_agent

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160502",
                ),
            ):
                result = deepagent.invoke(
                    ClearfactsNavigationDeepAgentRequest(
                        instruction="Open the purchase inbox",
                        role="sme_admin",
                        run_timestamp="20260503_160502",
                    )
                )

        self.assertEqual(result.status, DeepAgentExecutionStatus.COMPLETED)
        self.assertEqual(result.message, "Purchase inbox reached.")
        self.assertIsNotNone(result.latest_navigation_result)
        self.assertEqual(result.latest_navigation_result.current_page.title, "Purchase inbox")
        self.assertTrue(result.trace_references)
        mock_create_agent.assert_called_once()
        self.assertEqual(
            mock_create_agent.call_args.kwargs["response_format"],
            DeepAgentCoordinatorStructuredResponse,
        )
        self.assertEqual(
            {tool.name for tool in mock_create_agent.call_args.kwargs["tools"]},
            {
                "execute_cached_route",
                "plan_known_route",
                "execute_browser_operation",
                "analyze_recovery",
                "assess_goal_progress",
            },
        )

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_coordinator_missing_structured_response_fails_when_latest_page_does_not_match_goal(
        self,
        mock_get_azure_llm,
        mock_create_agent,
    ) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07")
        navigation_tool_payload = NavigationExecutionTaskOutput(
            status=NavigationExecutionStatus.COMPLETED,
            message="Reached the purchase inbox.",
            current_page=NavigationPageEvidence(url="https://example.test/inbox", title="Purchase inbox"),
            run_timestamp="20260503_160503",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            raw_result=ClearfactsNavigationResult(
                status=NavigationExecutionStatus.COMPLETED,
                source_name="navigation_agent_clearfacts",
                run_timestamp="20260503_160503",
                run_folder="/tmp/run",
                ontology_path="/tmp/run/ontology.md",
                instruction="open purchase inbox",
                role="sme_admin",
                message="Reached the purchase inbox.",
                current_page=NavigationPageEvidence(url="https://example.test/inbox", title="Purchase inbox"),
            ),
        )
        fake_compiled_agent = type(
            "FakeCompiledAgent",
            (),
            {
                "invoke": lambda self, payload: {
                    "messages": [
                        HumanMessage(content="user"),
                        ToolMessage(content=navigation_tool_payload.model_dump_json(), tool_call_id="call-1"),
                    ],
                }
            },
        )()
        mock_create_agent.return_value = fake_compiled_agent

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160503",
                ),
            ):
                result = deepagent.invoke(
                    ClearfactsNavigationDeepAgentRequest(
                        instruction="Open the archive",
                        role="sme_admin",
                        run_timestamp="20260503_160503",
                    )
                )

        self.assertEqual(result.status, DeepAgentExecutionStatus.FAILED)
        self.assertIn("without a structured response", result.message)
        self.assertIsNotNone(result.latest_navigation_result)
        self.assertEqual(result.latest_navigation_result.current_page.title, "Purchase inbox")

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_coordinator_missing_structured_response_completes_when_latest_page_matches_goal(
        self,
        mock_get_azure_llm,
        mock_create_agent,
    ) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07")
        navigation_tool_payload = NavigationExecutionTaskOutput(
            status=NavigationExecutionStatus.COMPLETED,
            message="Reached the archive.",
            current_page=NavigationPageEvidence(
                url="https://example.test/test-dossier/archive",
                title="Archive",
                page_summary="Archive filters and results are visible.",
            ),
            run_timestamp="20260503_160505",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            raw_result=ClearfactsNavigationResult(
                status=NavigationExecutionStatus.COMPLETED,
                source_name="navigation_agent_clearfacts",
                run_timestamp="20260503_160505",
                run_folder="/tmp/run",
                ontology_path="/tmp/run/ontology.md",
                instruction="open archive",
                role="sme_admin",
                message="Reached the archive.",
                current_page=NavigationPageEvidence(
                    url="https://example.test/test-dossier/archive",
                    title="Archive",
                    page_summary="Archive filters and results are visible.",
                ),
            ),
        )
        fake_compiled_agent = type(
            "FakeCompiledAgent",
            (),
            {
                "invoke": lambda self, payload: {
                    "messages": [
                        HumanMessage(content="user"),
                        ToolMessage(content=navigation_tool_payload.model_dump_json(), tool_call_id="call-1"),
                    ],
                }
            },
        )()
        mock_create_agent.return_value = fake_compiled_agent

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160505",
                ),
            ):
                result = deepagent.invoke(
                    ClearfactsNavigationDeepAgentRequest(
                        instruction="Open the archive",
                        role="sme_admin",
                        run_timestamp="20260503_160505",
                    )
                )

        self.assertEqual(result.status, DeepAgentExecutionStatus.COMPLETED)
        self.assertIn("without a structured response", result.message)
        self.assertEqual(result.current_page.url, "https://example.test/test-dossier/archive")

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_coordinator_ignores_goal_assessor_payload_with_wrong_subagent_name(
        self,
        mock_get_azure_llm,
        mock_create_agent,
    ) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07")
        navigation_tool_payload = NavigationExecutionTaskOutput(
            status=NavigationExecutionStatus.COMPLETED,
            message="Reached the archive.",
            current_page=NavigationPageEvidence(
                url="https://example.test/test-dossier/archive",
                title="Archive",
                page_summary="Archive filters and results are visible.",
            ),
            run_timestamp="20260503_160506",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            raw_result=ClearfactsNavigationResult(
                status=NavigationExecutionStatus.COMPLETED,
                source_name="navigation_agent_clearfacts",
                run_timestamp="20260503_160506",
                run_folder="/tmp/run",
                ontology_path="/tmp/run/ontology.md",
                instruction="open archive",
                role="sme_admin",
                message="Reached the archive.",
                current_page=NavigationPageEvidence(
                    url="https://example.test/test-dossier/archive",
                    title="Archive",
                    page_summary="Archive filters and results are visible.",
                ),
            ),
        )
        bad_goal_payload = {
            "subagent_name": "navigation-executor",
            "status": "needs_more_work",
            "summary": "The goal assessor reused the executor subagent name by mistake.",
            "confirmed_evidence": ["Archive page is visible."],
            "trace_path": "/tmp/goal-assessor.json",
        }
        fake_compiled_agent = type(
            "FakeCompiledAgent",
            (),
            {
                "invoke": lambda self, payload: {
                    "messages": [
                        HumanMessage(content="user"),
                        ToolMessage(
                            content=navigation_tool_payload.model_dump_json(),
                            name="execute_browser_operation",
                            tool_call_id="call-1",
                        ),
                        ToolMessage(
                            content=json.dumps(bad_goal_payload),
                            name="assess_goal_progress",
                            tool_call_id="call-2",
                        ),
                    ],
                }
            },
        )()
        mock_create_agent.return_value = fake_compiled_agent

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160506",
                ),
            ):
                result = deepagent.invoke(
                    ClearfactsNavigationDeepAgentRequest(
                        instruction="Open the archive",
                        role="sme_admin",
                        run_timestamp="20260503_160506",
                    )
                )

        self.assertEqual(result.status, DeepAgentExecutionStatus.COMPLETED)
        self.assertIsNotNone(result.latest_navigation_result)
        self.assertEqual(result.latest_navigation_result.current_page.title, "Archive")

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_coordinator_exception_returns_failed_result(
        self,
        mock_get_azure_llm,
        mock_create_agent,
    ) -> None:
        mock_get_azure_llm.return_value = self._FakeLLM()

        class FailingAgent:
            def invoke(self, _payload):
                raise ValueError("Tool input validation failed.")

        mock_create_agent.return_value = FailingAgent()
        deepagent = ClearfactsNavigationDeepAgent(model_name="gpt-5-2025-08-07")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160504",
                ),
            ):
                result = deepagent.invoke(
                    ClearfactsNavigationDeepAgentRequest(
                        instruction="Open the purchase inbox",
                        role="sme_admin",
                        run_timestamp="20260503_160504",
                    )
                )

        self.assertEqual(result.status, DeepAgentExecutionStatus.FAILED)
        self.assertIn("Tool input validation failed", result.message)
        self.assertTrue(result.trace_references)

    def test_validate_returns_structured_validation_result(self) -> None:
        deepagent = ClearfactsNavigationDeepAgent.__new__(ClearfactsNavigationDeepAgent)
        deepagent.invoke = lambda request, browser=None: ClearfactsNavigationDeepAgentResult(
            status=DeepAgentExecutionStatus.COMPLETED,
            source_name="navigation_agent_clearfacts",
            instruction=request.instruction,
            role=request.role,
            message="Reached purchase inbox and upload affordance is visible.",
            run_timestamp="20260503_190000",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            current_page=NavigationPageEvidence(
                url="https://example.test/inbox/purchase",
                title="Purchase inbox",
                page_summary="Upload invoice action is visible in the purchase inbox.",
            ),
            latest_navigation_result=ClearfactsNavigationResult(
                status=NavigationExecutionStatus.COMPLETED,
                source_name="navigation_agent_clearfacts",
                run_timestamp="20260503_190000",
                run_folder="/tmp/run",
                ontology_path="/tmp/run/ontology.md",
                instruction=request.instruction,
                role=request.role,
                message="Reached purchase inbox and upload affordance is visible.",
                current_page=NavigationPageEvidence(
                    url="https://example.test/inbox/purchase",
                    title="Purchase inbox",
                    page_summary="Upload invoice action is visible in the purchase inbox.",
                ),
            ),
            trace_references=[
                DeepAgentTraceReference(
                    agent_name="clearfacts-navigation-deepagent",
                    trace_kind="coordinator",
                    path="/tmp/run/logs/deepagent_traces/coordinator.json",
                )
            ],
        )
        deepagent._validation_subagent = type(
            "FakeValidationSubAgent",
            (),
            {
                "invoke": lambda self, query: ValidationAssessmentTaskOutput(
                    outcome=ValidationOutcome.SUPPORTS,
                    summary="The observed purchase inbox shows the upload affordance described by the claim.",
                    observed_evidence=["Purchase inbox page is open.", "Upload invoice action is visible."],
                    missing_evidence=[],
                    contradictions=[],
                )
            },
        )()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_190000",
                ),
            ):
                result = deepagent.validate(
                    ClearfactsNavigationValidationRequest(
                        claim="SME can upload a purchase invoice from the purchase inbox.",
                        procedure_instruction="Open the purchase inbox and verify that invoice upload is available.",
                        role="sme_admin",
                        run_timestamp="20260503_190000",
                    )
                )

        self.assertEqual(result.outcome, ValidationOutcome.SUPPORTS)
        self.assertEqual(result.execution_result.current_page.title, "Purchase inbox")
        self.assertTrue(result.trace_references)
        self.assertIn("Upload invoice action is visible.", result.observed_evidence)

    def test_ontology_batch_analyzer_compacts_incremental_evidence(self) -> None:
        analyzer = ClearfactsNavigationOntologyBatchAnalyzer.__new__(ClearfactsNavigationOntologyBatchAnalyzer)

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_195000",
            )
            pre_snapshot = run.snapshots_dir / "step_01_pre_action.md"
            pre_snapshot.write_text(
                "# Snapshot step 1 (pre_action)\n\n"
                "- url: https://example.test/dashboard\n"
                "- title: Dashboard\n\n"
                "## Human summary\n\nDashboard is visible.\n",
                encoding="utf-8",
            )
            post_snapshot = run.snapshots_dir / "step_02_post_action.md"
            raw_lines = "\n".join(f'- button "Archive action {index}" [ref=e{index}]' for index in range(200))
            post_snapshot.write_text(
                "# Snapshot step 2 (post_action)\n\n"
                "- url: https://example.test/archive\n"
                "- title: Archive\n\n"
                "## Human summary\n\nThe archive page is open with filters and results.\n\n"
                "## Text excerpt\n```\nArchive\nFilters\nResults\n" + ("Repeated archive text\n" * 200) + "```\n\n"
                "## Raw snapshot\n```\n" + raw_lines + "\n```\n",
                encoding="utf-8",
            )
            pre_event = NavigationEventRecord(
                event_id="01-observation-pre",
                step_index=1,
                phase="observation",
                status="captured",
                message="Captured page evidence before executing the browser operation.",
                snapshot_path=str(pre_snapshot),
                page_url="https://example.test/dashboard",
                page_title="Dashboard",
            )
            action_event = NavigationEventRecord(
                event_id="02-action",
                step_index=2,
                phase="action",
                status="completed",
                message="Clicked the archive navigation link.",
                tool_name="browser_click",
                arguments={"target": "Archive", "large": "x" * 5000},
                page_url="https://example.test/dashboard",
                page_title="Dashboard",
            )
            post_event = NavigationEventRecord(
                event_id="03-observation-post",
                step_index=2,
                phase="observation",
                status="captured",
                message="The Archive page loads at /archive with archive filters or results visible.",
                snapshot_path=str(post_snapshot),
                page_url="https://example.test/archive",
                page_title="Archive",
            )
            duplicate_event = NavigationEventRecord(
                event_id="04-observation-duplicate",
                step_index=3,
                phase="observation",
                status="captured",
                message="Captured current browser evidence.",
                snapshot_path=str(post_snapshot),
                page_url="https://example.test/archive",
                page_title="Archive",
            )
            append_navigation_event(run, pre_event)
            append_navigation_event(run, action_event)
            append_navigation_event(run, post_event)
            append_navigation_event(run, duplicate_event)
            update_manifest(
                run.manifest_path,
                last_ontology_update_event_count=1,
                last_ontology_update_event_id=pre_event.event_id,
            )

            batch = analyzer.prepare_evidence_batch(
                run,
                ClearfactsNavigationOntologyUpdateRequest(
                    run_timestamp="20260503_195000",
                    instruction="Checkpoint update.",
                ),
            )

        self.assertEqual(batch.selected_event_ids, ["02-action", "03-observation-post"])
        self.assertEqual(batch.processed_event_id, "04-observation-duplicate")
        self.assertLess(batch.payload_chars, 7000)
        self.assertNotIn("snapshot_excerpt", json.dumps(batch.payloads))
        self.assertIn("snapshot_ref", batch.payloads[1])
        self.assertIn("summary_facts", batch.payloads[1]["snapshot_evidence"])
        self.assertNotIn("raw_snapshot_key_lines", batch.payloads[1]["snapshot_evidence"])
        self.assertNotIn("visible_text_excerpt", batch.payloads[1]["snapshot_evidence"])

    def test_update_ontology_noops_when_no_new_events_since_last_update(self) -> None:
        deepagent = ClearfactsNavigationDeepAgent.__new__(ClearfactsNavigationDeepAgent)
        deepagent._ontology_batch_analyzer = ClearfactsNavigationOntologyBatchAnalyzer.__new__(
            ClearfactsNavigationOntologyBatchAnalyzer
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_195500",
            )
            event = NavigationEventRecord(
                event_id="01-action",
                step_index=1,
                phase="action",
                status="completed",
                message="Opened the archive.",
                page_url="https://example.test/archive",
                page_title="Archive",
            )
            append_navigation_event(run, event)
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Navigate from the Dashboard to the Archive.",
                            from_screen="Dashboard",
                            to_screen="Archive",
                            action_summary="Click the archive menu link.",
                            route_steps=['On Dashboard, click a[href="/test-dossier-vdl/archive"]'],
                            success_criteria=["Archive filters are visible (e.g., Filters)."],
                        )
                    ]
                ),
            )
            # Simulate a legacy ontology created before typed_route_steps existed.
            ontology = load_navigation_ontology(run.run_ontology)
            ontology.navigation_paths[0].typed_route_steps = []
            run.run_ontology.write_text(render_navigation_ontology(ontology), encoding="utf-8")
            source_ontology = load_navigation_ontology(run.baseline_ontology)
            source_ontology.navigation_paths = ontology.navigation_paths
            run.baseline_ontology.write_text(render_navigation_ontology(source_ontology), encoding="utf-8")
            update_manifest(
                run.manifest_path,
                last_ontology_update_event_count=1,
                last_ontology_update_event_id=event.event_id,
            )

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                return_value=run,
            ):
                result = deepagent.update_ontology(
                    ClearfactsNavigationOntologyUpdateRequest(
                        run_timestamp="20260503_195500",
                        instruction="Checkpoint update.",
                    )
                )

            manifest = load_manifest(run.manifest_path)
            ontology = load_navigation_ontology(run.run_ontology)
            source_ontology = load_navigation_ontology(run.baseline_ontology)

        self.assertEqual(result.status, "no_new_events")
        self.assertEqual(result.analyzed_event_count, 0)
        self.assertEqual(manifest["status"], "ontology_noop")
        self.assertEqual(manifest["last_ontology_update_event_count"], 1)
        self.assertEqual(manifest["last_ontology_update_event_id"], "01-action")
        self.assertEqual(len(ontology.navigation_paths[0].typed_route_steps), 2)
        self.assertEqual(len(source_ontology.navigation_paths[0].typed_route_steps), 2)

    def test_ontology_batch_analyzer_writes_failure_trace(self) -> None:
        class FailingStructuredLLM:
            def invoke(self, _messages):
                raise RuntimeError("Could not parse response content as the length limit was reached.")

        analyzer = ClearfactsNavigationOntologyBatchAnalyzer.__new__(ClearfactsNavigationOntologyBatchAnalyzer)
        analyzer._llm = FailingStructuredLLM()

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260503_195600",
            )
            append_navigation_event(
                run,
                NavigationEventRecord(
                    event_id="01-action",
                    step_index=1,
                    phase="action",
                    status="completed",
                    message="Opened the archive.",
                    page_url="https://example.test/archive",
                    page_title="Archive",
                ),
            )
            request = ClearfactsNavigationOntologyUpdateRequest(
                run_timestamp="20260503_195600",
                instruction="Checkpoint update.",
            )
            batch = analyzer.prepare_evidence_batch(run, request)

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                return_value=run,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    analyzer.invoke(request, evidence_batch=batch)

            trace_paths = sorted((run.logs_dir / "deepagent_traces").glob("*ontology_batch_failed.json"))
            payload = json.loads(trace_paths[-1].read_text(encoding="utf-8"))

        self.assertIn("length limit", str(caught.exception))
        self.assertTrue(trace_paths)
        self.assertEqual(payload["metadata"]["selected_event_ids"], ["01-action"])
        self.assertGreater(payload["metadata"]["prompt_chars"], 0)
        self.assertEqual(payload["structured_output"]["status"], "failed")

    def test_update_ontology_merges_batch_delta(self) -> None:
        class FakeOntologyBatchAnalyzer:
            def prepare_evidence_batch(self, run, query):
                analyzer = ClearfactsNavigationOntologyBatchAnalyzer.__new__(
                    ClearfactsNavigationOntologyBatchAnalyzer
                )
                return analyzer.prepare_evidence_batch(run, query)

            def invoke(self, query, *, evidence_batch=None):
                if evidence_batch is None or not evidence_batch.selected_events:
                    raise AssertionError("Expected compact evidence batch to be prepared before analysis.")
                return (
                    OntologyBatchAnalysisTaskOutput(
                        summary="Merged purchase inbox evidence.",
                        ontology_delta=NavigationOntologyDelta(
                            screens=[
                                NavigationScreenObservation(
                                    name="Purchase inbox",
                                    url="https://example.test/inbox/purchase",
                                    title="Purchase inbox",
                                    description="Screen for purchase invoice intake.",
                                    user_help_summary="Users can review and upload purchase invoices here.",
                                    evidence=["01-observation-test"],
                                )
                            ]
                        ),
                        open_issues=["Confirm whether archive access differs by role."],
                    ),
                    "/tmp/ontology_batch_trace.json",
                )

        deepagent = ClearfactsNavigationDeepAgent.__new__(ClearfactsNavigationDeepAgent)
        deepagent._ontology_batch_analyzer = FakeOntologyBatchAnalyzer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs = {}

            def ensure_run(source_name, timestamp=None):
                resolved_timestamp = timestamp or "20260503_200000"
                if resolved_timestamp not in runs:
                    runs[resolved_timestamp] = setup_navigation_run(
                        source_name,
                        workspace_dir=tmp_dir,
                        timestamp=resolved_timestamp,
                    )
                    append_navigation_event(
                        runs[resolved_timestamp],
                        NavigationEventRecord(
                            event_id="01-observation-test",
                            step_index=1,
                            phase="observation",
                            status="captured",
                            message="Purchase inbox page is visible.",
                            page_url="https://example.test/inbox/purchase",
                            page_title="Purchase inbox",
                        ),
                    )
                return runs[resolved_timestamp]

            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=ensure_run,
            ):
                result = deepagent.update_ontology(
                    ClearfactsNavigationOntologyUpdateRequest(
                        run_timestamp="20260503_200000",
                        instruction="Checkpoint update.",
                    )
                )

            ontology = load_navigation_ontology(Path(result.ontology_path))
            source_ontology = load_navigation_ontology(Path(result.source_ontology_path))
            manifest = load_manifest(runs["20260503_200000"].manifest_path)
            self.assertEqual(result.status, "updated")
            self.assertEqual(result.merged_counts["screens"], 1)
            self.assertEqual(ontology.screens[0].name, "Purchase inbox")
            self.assertEqual(source_ontology.screens[0].name, "Purchase inbox")
            self.assertEqual(result.open_issues, ["Confirm whether archive access differs by role."])
            self.assertIn("Confirm whether archive access differs by role.", ontology.open_questions)
            self.assertIn("Confirm whether archive access differs by role.", source_ontology.open_questions)
            self.assertEqual(manifest["last_ontology_update_open_issues"], result.open_issues)
            self.assertEqual(manifest["last_ontology_update_source_ontology"], result.source_ontology_path)
            self.assertEqual(manifest["status"], "ontology_updated")
