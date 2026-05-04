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

from .schemas import DeepAgentTraceReference, NavigationExecutionTaskInput, NavigationExecutionTaskOutput


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
        parts = trace_path.stem.split("_", 3)
        trace_kind = parts[-1] if parts else "trace"
        agent_name = parts[-2] if len(parts) >= 2 else "unknown"
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


import logging as _logging

_logger = _logging.getLogger(__name__)


def parse_nl_execution_task_input(text: str) -> NavigationExecutionTaskInput:
    """Fallback: extract NavigationExecutionTaskInput from natural-language coordinator output.

    The coordinator sometimes produces a prose description instead of a JSON payload.
    This parser handles the expected natural-language field labels so the subagent can
    proceed without losing the run context.
    """
    source_match = re.search(r"Source:\s*([^\s(]+)", text)
    role_match = re.search(r"(?:Default role|role):\s*([^\s(,]+)", text, re.IGNORECASE)
    timestamp_match = re.search(r"Run timestamp:\s*(\S+)", text, re.IGNORECASE)
    goal_match = re.search(
        r"Goal:\s*(.*?)(?=\n\s*\n|\nInstructions\s+to\s+execute|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    source_name = source_match.group(1).strip() if source_match else "navigation_agent_clearfacts"
    role = role_match.group(1).strip() if role_match else None
    run_timestamp = timestamp_match.group(1).strip() if timestamp_match else None
    instruction = goal_match.group(1).strip() if goal_match else text.strip()

    _logger.warning(
        "navigation-executor received natural-language task description instead of JSON; "
        "extracted source=%s role=%s timestamp=%s instruction=%.120s",
        source_name,
        role,
        run_timestamp,
        instruction,
    )
    return NavigationExecutionTaskInput(
        source_name=source_name,
        role=role,
        run_timestamp=run_timestamp,
        instruction=instruction,
    )

def build_execution_result_yaml(result: NavigationExecutionTaskOutput | ClearfactsNavigationResult) -> str:
    if hasattr(result, "model_dump"):
        payload = result.model_dump(mode="json", exclude_none=True)
    else:
        payload = result
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
