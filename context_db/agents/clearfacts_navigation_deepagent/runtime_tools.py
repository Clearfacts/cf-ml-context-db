from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from .schemas import (
    CachedRouteExecutionTaskInput,
    GoalAssessmentTaskInput,
    NavigationExecutionTaskInput,
    RecoveryAnalysisTaskInput,
    RoutePlanningTaskInput,
)


def _truncate(value: str | None, *, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[:limit].rstrip() + f"\n...[truncated {len(value) - limit} chars]"


def _compact_page(
    page: Any | None,
    *,
    text_limit: int = 2500,
    summary_limit: int = 3500,
    affordance_limit: int = 50,
) -> dict[str, Any] | None:
    if page is None:
        return None
    payload = page.model_dump(mode="json", exclude_none=True)
    payload.pop("snapshot", None)
    payload["text_excerpt"] = _truncate(payload.get("text_excerpt"), limit=text_limit)
    payload["page_summary"] = _truncate(payload.get("page_summary"), limit=summary_limit)
    payload["affordances"] = payload.get("affordances", [])[:affordance_limit]
    return payload


def _compact_execution_output(result: Any) -> str:
    payload = result.model_dump(mode="json", exclude_none=True)
    payload.pop("events", None)
    payload["current_page"] = _compact_page(result.current_page)

    raw_result = payload.get("raw_result", {})
    if isinstance(raw_result, dict):
        raw_result.pop("events", None)
        raw_result.pop("tool_inventory", None)
        raw_result["message"] = _truncate(raw_result.get("message"), limit=2000)
        raw_result["current_page"] = _compact_page(result.raw_result.current_page)
    payload["message"] = _truncate(payload.get("message"), limit=2000)
    return json.dumps(payload, ensure_ascii=False)


def _compact_route_cache_output(result: Any) -> str:
    payload = result.model_dump(mode="json", exclude_none=True)
    payload["current_page"] = _compact_page(
        result.current_page,
        text_limit=1200,
        summary_limit=1200,
        affordance_limit=20,
    )
    latest_navigation_result = payload.get("latest_navigation_result", {})
    if result.latest_navigation_result is not None and isinstance(latest_navigation_result, dict):
        latest_navigation_result.pop("events", None)
        latest_navigation_result.pop("tool_inventory", None)
        latest_navigation_result["message"] = _truncate(latest_navigation_result.get("message"), limit=800)
        latest_navigation_result["current_page"] = _compact_page(
            result.latest_navigation_result.current_page,
            text_limit=1200,
            summary_limit=1200,
            affordance_limit=20,
        )
    return json.dumps(payload, ensure_ascii=False)


def build_navigation_runtime_tools(
    *,
    route_cache: Any,
    route_planner: Any,
    execution: Any,
    recovery: Any,
    goal_assessment: Any,
    browser: Any | None = None,
) -> list[BaseTool]:
    """Build typed tools for the navigation coordinator.

    The coordinator sees these as normal LangChain tools with Pydantic argument
    schemas. The underlying implementations can still use LLMs or Playwright,
    but invalid coordinator-to-tool inputs are rejected before execution.
    """

    def execute_cached_route(**kwargs: Any) -> str:
        query = CachedRouteExecutionTaskInput.model_validate(kwargs)
        result = route_cache.invoke(query, browser=browser)
        return _compact_route_cache_output(result)

    def plan_known_route(**kwargs: Any) -> str:
        query = RoutePlanningTaskInput.model_validate(kwargs)
        result = route_planner.invoke(query)
        return result.model_dump_json()

    def execute_browser_operation(**kwargs: Any) -> str:
        query = NavigationExecutionTaskInput.model_validate(kwargs)
        result = execution.invoke(query, browser=browser)
        return _compact_execution_output(result)

    def analyze_recovery(**kwargs: Any) -> str:
        query = RecoveryAnalysisTaskInput.model_validate(kwargs)
        result = recovery.invoke(query)
        return result.model_dump_json()

    def assess_goal_progress(**kwargs: Any) -> str:
        query = GoalAssessmentTaskInput.model_validate(kwargs)
        result = goal_assessment.invoke(query)
        return result.model_dump_json()

    return [
        StructuredTool.from_function(
            func=execute_cached_route,
            name="execute_cached_route",
            description=(
                "Deterministically execute reusable typed route steps from the current ontology cache. "
                "Use this before exploratory navigation for common paths. Returns CachedRouteExecutionTaskOutput as JSON."
            ),
            args_schema=CachedRouteExecutionTaskInput,
        ),
        StructuredTool.from_function(
            func=plan_known_route,
            name="plan_known_route",
            description=(
                "Check whether the current navigation ontology contains a reusable route for the user goal. "
                "Input must match RoutePlanningTaskInput. Returns RoutePlanningTaskOutput as JSON."
            ),
            args_schema=RoutePlanningTaskInput,
        ),
        StructuredTool.from_function(
            func=execute_browser_operation,
            name="execute_browser_operation",
            description=(
                "Execute exactly one typed browser operation through the Playwright MCP adapter. "
                "Input must match NavigationExecutionTaskInput. Returns NavigationExecutionTaskOutput as JSON. "
                "This collects evidence only and does not update the ontology."
            ),
            args_schema=NavigationExecutionTaskInput,
        ),
        StructuredTool.from_function(
            func=analyze_recovery,
            name="analyze_recovery",
            description=(
                "Analyze a blocked or uncertain navigation result and recommend one bounded recovery move. "
                "Input must match RecoveryAnalysisTaskInput. Returns RecoveryAnalysisTaskOutput as JSON."
            ),
            args_schema=RecoveryAnalysisTaskInput,
        ),
        StructuredTool.from_function(
            func=assess_goal_progress,
            name="assess_goal_progress",
            description=(
                "Assess whether the user's navigation goal has been satisfied by the latest execution result. "
                "Input must match GoalAssessmentTaskInput. Returns GoalAssessmentTaskOutput as JSON."
            ),
            args_schema=GoalAssessmentTaskInput,
        ),
    ]
