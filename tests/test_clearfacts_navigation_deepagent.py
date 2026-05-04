from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from context_db.agents.clearfacts_navigation_agent.schemas import (
    ClearfactsNavigationResult,
    NavigationExecutionStatus,
    NavigationPageEvidence,
)
from context_db.agents.clearfacts_navigation_agent.tools import setup_navigation_run
from context_db.agents.clearfacts_navigation_deepagent.agents import (
    ClearfactsNavigationDeepAgent,
    ClearfactsNavigationExecutionSubAgent,
)
from context_db.agents.clearfacts_navigation_deepagent.schemas import (
    ClearfactsNavigationDeepAgentRequest,
    ClearfactsNavigationDeepAgentResult,
    ClearfactsNavigationValidationRequest,
    DeepAgentCoordinatorStructuredResponse,
    DeepAgentTraceReference,
    DeepAgentExecutionStatus,
    NavigationExecutionTaskInput,
    NavigationExecutionTaskOutput,
    ValidationAssessmentTaskOutput,
    ValidationOutcome,
)
from context_db.agents.clearfacts_navigation_deepagent.tools import (
    build_trace_references,
    extract_json_object,
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

    def test_validation_request_trims_claim_and_optional_instruction(self) -> None:
        request = ClearfactsNavigationValidationRequest(
            claim="  SME can upload a purchase invoice from the purchase inbox.  ",
            procedure_instruction="  Go to the purchase inbox and upload an invoice.  ",
        )
        self.assertEqual(request.claim, "SME can upload a purchase invoice from the purchase inbox.")
        self.assertEqual(request.procedure_instruction, "Go to the purchase inbox and upload an invoice.")

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

    def test_execution_subagent_compiled_wrapper_returns_messages_and_structured_response(self) -> None:
        fake_result = ClearfactsNavigationResult(
            status=NavigationExecutionStatus.COMPLETED,
            source_name="navigation_agent_clearfacts",
            run_timestamp="20260503_160501",
            run_folder="/tmp/run",
            ontology_path="/tmp/run/ontology.md",
            instruction="open purchase inbox",
            role="sme_admin",
            message="Reached the purchase inbox.",
            current_page=NavigationPageEvidence(url="https://example.test/inbox", title="Inbox"),
        )
        subagent = ClearfactsNavigationExecutionSubAgent.__new__(ClearfactsNavigationExecutionSubAgent)
        subagent._agent = type("FakeNavigationAgent", (), {"invoke": lambda self, request, browser=None: fake_result})()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "context_db.agents.clearfacts_navigation_deepagent.agents.ensure_navigation_run",
                side_effect=lambda source_name, timestamp=None: setup_navigation_run(
                    source_name,
                    workspace_dir=tmp_dir,
                    timestamp=timestamp or "20260503_160501",
                ),
            ):
                compiled = subagent.build_compiled_subagent(browser=None)
                state = compiled["runnable"].invoke(
                    {
                        "messages": [
                            HumanMessage(
                                content=(
                                    '{"source_name":"navigation_agent_clearfacts","instruction":"open purchase inbox",'
                                    '"run_timestamp":"20260503_160501","role":"sme_admin","max_iterations":3,"include_snapshot":true}'
                                )
                            )
                        ]
                    }
                )
                self.assertIn("messages", state)
                self.assertIn("structured_response", state)
                self.assertEqual(state["structured_response"].status, NavigationExecutionStatus.COMPLETED)

    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.create_deep_agent")
    @patch("context_db.agents.clearfacts_navigation_deepagent.agents.get_azure_llm")
    def test_coordinator_returns_structured_result_and_latest_navigation_output(
        self,
        mock_get_azure_llm,
        mock_create_deep_agent,
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
        mock_create_deep_agent.return_value = fake_compiled_agent

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
