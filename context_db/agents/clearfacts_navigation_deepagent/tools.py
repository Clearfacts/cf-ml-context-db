from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import BaseMessage

from context_db.agents.clearfacts_navigation_agent.schemas import ClearfactsNavigationResult
from context_db.agents.clearfacts_navigation_agent.tools import NavigationRunContext

from .schemas import DeepAgentTraceReference, NavigationExecutionTaskOutput, RoutePlanningTaskInput


TRACE_DIRNAME = "deepagent_traces"


def ensure_trace_dir(run: NavigationRunContext) -> Path:
    path = run.logs_dir / TRACE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(raw_value) for key, raw_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    return str(value)


def serialize_message(message: BaseMessage) -> dict[str, Any]:
    payload = {
        "type": type(message).__name__,
        "content": _json_safe(message.content),
    }
    for attr_name in ("name", "tool_call_id", "tool_calls", "response_metadata", "usage_metadata", "additional_kwargs"):
        attr_value = getattr(message, attr_name, None)
        if attr_value:
            payload[attr_name] = _json_safe(attr_value)
    return payload


def write_trace_artifact(
    *,
    run: NavigationRunContext,
    agent_name: str,
    trace_kind: str,
    input_messages: list[BaseMessage] | None = None,
    output_messages: list[BaseMessage] | None = None,
    structured_input: Any | None = None,
    structured_output: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    trace_dir = ensure_trace_dir(run)
    path = trace_dir / f"{_timestamp()}_{agent_name}_{trace_kind}.json"
    payload = {
        "agent_name": agent_name,
        "trace_kind": trace_kind,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "structured_input": _json_safe(structured_input),
        "structured_output": _json_safe(structured_output),
        "input_messages": [serialize_message(message) for message in input_messages or []],
        "output_messages": [serialize_message(message) for message in output_messages or []],
        "metadata": _json_safe(metadata or {}),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def build_trace_references(run: NavigationRunContext) -> list[DeepAgentTraceReference]:
    trace_dir = ensure_trace_dir(run)
    references: list[DeepAgentTraceReference] = []
    for trace_path in sorted(trace_dir.glob("*.json")):
        agent_name = "unknown"
        trace_kind = "trace"
        try:
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            agent_name = str(payload.get("agent_name") or agent_name)
            trace_kind = str(payload.get("trace_kind") or trace_kind)
        except (OSError, json.JSONDecodeError):
            logger_name = trace_path.stem.split("_", 3)[-1] if "_" in trace_path.stem else trace_path.stem
            agent_name = logger_name or agent_name
        references.append(
            DeepAgentTraceReference(
                agent_name=agent_name,
                trace_kind=trace_kind,
                path=str(trace_path),
            )
        )
    return references


def extract_json_object(text: str) -> dict[str, Any]:
    normalized = text.strip()
    if not normalized:
        raise ValueError("Expected a JSON payload but received an empty task description.")

    code_block_match = re.search(r"```json\s*(.*?)\s*```", normalized, flags=re.DOTALL)
    if code_block_match:
        normalized = code_block_match.group(1).strip()

    decoder = json.JSONDecoder()
    if normalized.startswith("{"):
        obj, end_index = decoder.raw_decode(normalized)
        if isinstance(obj, dict) and normalized[end_index:].strip() == "":
            return obj

    for index, char in enumerate(normalized):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(normalized[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    raise ValueError(f"Could not extract a JSON object from subagent task description: {text}")


def parse_subagent_task_input(text: str, schema: type[Any]) -> Any:
    return schema.model_validate(extract_json_object(text))


def _unquote_label_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized[0:1] in {"'", '"'}:
        quote = normalized[0]
        end_index = normalized.find(quote, 1)
        if end_index > 0:
            normalized = normalized[1:end_index]
    return normalized.strip() or None


def _extract_labeled_value(text: str, *labels: str) -> str | None:
    for label in labels:
        label_pattern = re.escape(label).replace(r"\ ", r"[\s_-]+")
        match = re.search(rf"(?im)^\s*(?:[-*]\s*)?{label_pattern}\s*:\s*(.+?)\s*$", text)
        if match:
            return _unquote_label_value(match.group(1))
    return None


def _extract_run_timestamp(text: str) -> str | None:
    labeled = _extract_labeled_value(text, "run_timestamp", "run timestamp", "timestamp", "run id", "run_id")
    if labeled:
        match = re.search(r"\b\d{8}_\d{6}\b", labeled)
        return match.group(0) if match else labeled
    match = re.search(r"\b\d{8}_\d{6}\b", text)
    return match.group(0) if match else None


def parse_route_planner_task_input(
    text: str,
    *,
    default_source_name: str | None = None,
    default_run_timestamp: str | None = None,
    default_user_goal: str | None = None,
) -> RoutePlanningTaskInput:
    try:
        return parse_subagent_task_input(text, RoutePlanningTaskInput)
    except ValueError:
        pass

    source_name = _extract_labeled_value(text, "source_name", "source name", "source") or default_source_name
    user_goal = _extract_labeled_value(
        text,
        "user_goal",
        "user goal",
        "goal",
        "objective",
        "user request",
        "request",
    ) or default_user_goal
    run_timestamp = _extract_run_timestamp(text) or default_run_timestamp
    role = _extract_labeled_value(text, "role", "active role")
    if role is not None and role.lower().startswith(("null", "none")):
        role = None

    ontology_match = re.search(
        r"(?is)current_ontology_yaml\s*:\s*\|?\s*(.*?)(?=\n\s*current_page\s*:|\n\s*output\s*:|\Z)",
        text,
    )
    current_ontology_yaml = ontology_match.group(1).strip() if ontology_match else ""

    missing = [
        field_name
        for field_name, value in {
            "source_name": source_name,
            "user_goal": user_goal,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            "Route planner task must be JSON or include labeled fields: "
            f"{', '.join(missing)} missing."
        )

    return RoutePlanningTaskInput(
        source_name=source_name,
        user_goal=user_goal,
        role=role,
        run_timestamp=run_timestamp,
        current_ontology_yaml=current_ontology_yaml,
        current_page=None,
    )


def build_execution_result_yaml(result: NavigationExecutionTaskOutput | ClearfactsNavigationResult) -> str:
    if hasattr(result, "model_dump"):
        payload = result.model_dump(mode="json", exclude_none=True)
    else:
        payload = result
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
