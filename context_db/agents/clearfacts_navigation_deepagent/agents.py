from __future__ import annotations

import json
import logging
from typing import Any

import yaml
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import CompiledSubAgent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from cf_ml_common.llm.token_tracker import tracking_context
from context_db.agents.clearfacts_navigation_agent import ClearfactsNavigationAgent
from context_db.agents.clearfacts_navigation_agent.schemas import ClearfactsNavigationRequest
from context_db.agents.clearfacts_navigation_agent.tools import (
    NavigationRunContext,
    build_prompt_source_context,
    ensure_navigation_run,
    load_navigation_ontology,
    read_recent_navigation_events,
)
from context_db.llm.config import get_azure_llm, init_token_tracking

from .prompts import (
    COORDINATOR_SYSTEM_PROMPT,
    COORDINATOR_USER_PROMPT_TEMPLATE,
    GOAL_ASSESSOR_SYSTEM_PROMPT,
    GOAL_ASSESSOR_USER_PROMPT_TEMPLATE,
    RECOVERY_ANALYZER_SYSTEM_PROMPT,
    RECOVERY_ANALYZER_USER_PROMPT_TEMPLATE,
    VALIDATION_ASSESSOR_SYSTEM_PROMPT,
    VALIDATION_ASSESSOR_USER_PROMPT_TEMPLATE,
)
from .schemas import (
    ClearfactsNavigationDeepAgentRequest,
    ClearfactsNavigationDeepAgentResult,
    ClearfactsNavigationValidationRequest,
    ClearfactsNavigationValidationResult,
    DeepAgentCoordinatorStructuredResponse,
    DeepAgentExecutionStatus,
    GoalAssessmentTaskInput,
    GoalAssessmentTaskOutput,
    NavigationExecutionTaskInput,
    NavigationExecutionTaskOutput,
    RecoveryAnalysisTaskInput,
    RecoveryAnalysisTaskOutput,
    ValidationAssessmentTaskInput,
    ValidationAssessmentTaskOutput,
)
from .tools import (
    build_execution_result_yaml,
    build_trace_references,
    parse_nl_execution_task_input,
    parse_subagent_task_input,
    write_trace_artifact,
)

logger = logging.getLogger(__name__)


class ClearfactsNavigationExecutionSubAgent:
    AGENT_NAME = "clearfacts-navigation-executor-subagent"
    AGENT_OPERATION = "execute-navigation-step-objective"

    def __init__(self, model_name: str = "gpt-5-2025-08-07", max_tokens: int = 4000) -> None:
        self._agent = ClearfactsNavigationAgent(model_name=model_name, max_tokens=max_tokens)

    def invoke(
        self,
        query: NavigationExecutionTaskInput,
        *,
        browser: Any | None = None,
    ) -> NavigationExecutionTaskOutput:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        request = ClearfactsNavigationRequest(
            source_name=query.source_name,
            instruction=query.instruction,
            role=query.role,
            run_timestamp=run.timestamp,
            max_iterations=query.max_iterations,
            include_snapshot=query.include_snapshot,
        )
        input_messages = [HumanMessage(content=request.model_dump_json(indent=2))]
        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            result = self._agent.invoke(request, browser=browser)
        output = NavigationExecutionTaskOutput(
            status=result.status,
            message=result.message,
            question_for_user=result.question_for_user,
            current_page=result.current_page,
            run_timestamp=result.run_timestamp,
            run_folder=result.run_folder,
            ontology_path=result.ontology_path,
            raw_result=result,
        )
        trace_path = write_trace_artifact(
            run=run,
            agent_name=self.AGENT_NAME,
            trace_kind="subagent",
            input_messages=input_messages,
            output_messages=[AIMessage(content=output.model_dump_json(indent=2))],
            structured_input=request,
            structured_output=output,
            metadata={"subagent_name": "navigation-executor"},
        )
        output.trace_path = str(trace_path)
        return output

    def build_compiled_subagent(self, *, browser: Any | None = None) -> CompiledSubAgent:
        def _invoke(state: dict[str, Any]) -> dict[str, Any]:
            content = state["messages"][-1].content
            try:
                task_input = parse_subagent_task_input(content, NavigationExecutionTaskInput)
            except ValueError:
                task_input = parse_nl_execution_task_input(content)
            result = self.invoke(task_input, browser=browser)
            return {
                "messages": [AIMessage(content=result.model_dump_json(indent=2))],
                "structured_response": result,
            }

        return CompiledSubAgent(
            name="navigation-executor",
            description=(
                "Execute one bounded Clearfacts navigation objective using the existing runtime.\n"
                "You MUST call this subagent with a JSON object — do not use natural language. "
                "Required fields: source_name (string), instruction (string). "
                "Optional fields: role (string), run_timestamp (string), max_iterations (integer), include_snapshot (boolean).\n"
                'Example: {"source_name": "navigation_agent_clearfacts", "role": "sme_admin", '
                '"run_timestamp": "20260503_194950", "instruction": "Navigate to the Communication module.", '
                '"max_iterations": 6, "include_snapshot": true}\n'
                "Returns a JSON object with execution status, current page evidence, and a trace path."
            ),
            runnable=RunnableLambda(_invoke),
        )


class ClearfactsNavigationRecoverySubAgent:
    AGENT_NAME = "clearfacts-navigation-recovery-subagent"
    AGENT_OPERATION = "analyze-navigation-recovery"

    def __init__(self, model_name: str = "gpt-5-2025-08-07", max_tokens: int = 4000) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens)
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

    def build_compiled_subagent(self) -> CompiledSubAgent:
        def _invoke(state: dict[str, Any]) -> dict[str, Any]:
            task_input = parse_subagent_task_input(state["messages"][-1].content, RecoveryAnalysisTaskInput)
            result = self.invoke(task_input)
            return {
                "messages": [AIMessage(content=result.model_dump_json(indent=2))],
                "structured_response": result,
            }

        return CompiledSubAgent(
            name="recovery-analyzer",
            description=(
                "Analyze a blocked or uncertain navigation result and recommend one bounded recovery move. "
                "Pass JSON with user_goal and execution. Returns JSON with strategy, summary, and optional refined_instruction."
            ),
            runnable=RunnableLambda(_invoke),
        )

    def build_general_purpose_compiled_subagent(self) -> CompiledSubAgent:
        def _invoke(state: dict[str, Any]) -> dict[str, Any]:
            task_input = parse_subagent_task_input(state["messages"][-1].content, RecoveryAnalysisTaskInput)
            result = self.invoke(task_input)
            return {
                "messages": [AIMessage(content=result.model_dump_json(indent=2))],
                "structured_response": result,
            }

        return CompiledSubAgent(
            name="general-purpose",
            description=(
                "General-purpose reasoning over existing Clearfacts navigation results only. "
                "Do not use for browser execution. Pass the same JSON contract as recovery-analyzer."
            ),
            runnable=RunnableLambda(_invoke),
        )


class ClearfactsNavigationGoalAssessmentSubAgent:
    AGENT_NAME = "clearfacts-navigation-goal-assessor-subagent"
    AGENT_OPERATION = "assess-navigation-goal-progress"

    def __init__(self, model_name: str = "gpt-5-2025-08-07", max_tokens: int = 4000) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens)
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

    def build_compiled_subagent(self) -> CompiledSubAgent:
        def _invoke(state: dict[str, Any]) -> dict[str, Any]:
            task_input = parse_subagent_task_input(state["messages"][-1].content, GoalAssessmentTaskInput)
            result = self.invoke(task_input)
            return {
                "messages": [AIMessage(content=result.model_dump_json(indent=2))],
                "structured_response": result,
            }

        return CompiledSubAgent(
            name="goal-assessor",
            description=(
                "Assess whether the user's Clearfacts navigation goal has been satisfied. "
                "Pass JSON with user_goal and execution. Returns JSON with completion status and evidence."
            ),
            runnable=RunnableLambda(_invoke),
        )


class ClearfactsNavigationValidationSubAgent:
    AGENT_NAME = "clearfacts-navigation-validation-subagent"
    AGENT_OPERATION = "assess-navigation-validation-claim"

    def __init__(self, model_name: str = "gpt-5-2025-08-07", max_tokens: int = 4000) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens)
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


class ClearfactsNavigationDeepAgent:
    AGENT_NAME = "clearfacts-navigation-deepagent"
    AGENT_OPERATION = "orchestrate-clearfacts-navigation"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
    ) -> None:
        init_token_tracking()
        self._model_name = model_name
        self._max_tokens = max_tokens
        self._coordinator_model = get_azure_llm(model_name=model_name, max_tokens=max_tokens)
        self._execution_subagent = ClearfactsNavigationExecutionSubAgent(model_name=model_name, max_tokens=max_tokens)
        self._recovery_subagent = ClearfactsNavigationRecoverySubAgent(model_name=model_name, max_tokens=max_tokens)
        self._goal_assessment_subagent = ClearfactsNavigationGoalAssessmentSubAgent(
            model_name=model_name,
            max_tokens=max_tokens,
        )
        self._validation_subagent = ClearfactsNavigationValidationSubAgent(
            model_name=model_name,
            max_tokens=max_tokens,
        )

    def invoke(
        self,
        query: ClearfactsNavigationDeepAgentRequest,
        browser: Any | None = None,
    ) -> ClearfactsNavigationDeepAgentResult:
        run = ensure_navigation_run(query.source_name, timestamp=query.run_timestamp)
        coordinator = self._build_agent(run=run, browser=browser)
        prompt = self._build_user_prompt(query=query, run=run)
        input_messages: list[BaseMessage] = [HumanMessage(content=prompt)]

        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            result = coordinator.invoke({"messages": [{"role": "user", "content": prompt}]})

        structured_response = self._coordinator_structured_response(result, run=run)
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
        subagents: list[CompiledSubAgent] = [
            self._recovery_subagent.build_general_purpose_compiled_subagent(),
            self._execution_subagent.build_compiled_subagent(browser=browser),
            self._recovery_subagent.build_compiled_subagent(),
            self._goal_assessment_subagent.build_compiled_subagent(),
        ]
        return create_deep_agent(
            model=self._coordinator_model,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            subagents=subagents,
            response_format=AutoStrategy(DeepAgentCoordinatorStructuredResponse),
            backend=FilesystemBackend(root_dir=run.run_dir, virtual_mode=True),
            name=self.AGENT_NAME,
        )

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
    def _coordinator_structured_response(result: dict[str, Any], *, run: NavigationRunContext) -> DeepAgentCoordinatorStructuredResponse:
        structured = result.get("structured_response")
        if isinstance(structured, DeepAgentCoordinatorStructuredResponse):
            return structured
        if isinstance(structured, dict):
            return DeepAgentCoordinatorStructuredResponse.model_validate(structured)

        latest_navigation = ClearfactsNavigationDeepAgent._latest_navigation_result_from_messages(result.get("messages", []))
        if latest_navigation is None:
            return DeepAgentCoordinatorStructuredResponse(
                status=DeepAgentExecutionStatus.FAILED,
                summary="The DeepAgents coordinator finished without a structured response or navigation execution result.",
                run_timestamp=run.timestamp,
                run_folder=str(run.run_dir),
                ontology_path=str(run.run_ontology),
            )

        status_mapping = {
            "completed": DeepAgentExecutionStatus.COMPLETED,
            "needs_user_input": DeepAgentExecutionStatus.NEEDS_USER_INPUT,
            "blocked": DeepAgentExecutionStatus.BLOCKED,
            "failed": DeepAgentExecutionStatus.FAILED,
        }
        return DeepAgentCoordinatorStructuredResponse(
            status=status_mapping[latest_navigation.status.value],
            summary=latest_navigation.message or "Navigation execution completed.",
            question_for_user=latest_navigation.question_for_user,
            latest_page_url=latest_navigation.current_page.url if latest_navigation.current_page else None,
            latest_page_title=latest_navigation.current_page.title if latest_navigation.current_page else None,
            run_timestamp=latest_navigation.run_timestamp,
            run_folder=latest_navigation.run_folder,
            ontology_path=latest_navigation.ontology_path,
        )

    @staticmethod
    def _latest_navigation_result_from_messages(messages: list[BaseMessage]) -> Any | None:
        latest: Any | None = None
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            payload = None
            if isinstance(message.content, str):
                try:
                    payload = json.loads(message.content)
                except json.JSONDecodeError:
                    payload = None
            if not isinstance(payload, dict):
                continue
            if payload.get("subagent_name") != "navigation-executor":
                continue
            latest = NavigationExecutionTaskOutput.model_validate(payload).raw_result
        return latest
