from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import re
import shlex
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Any

import yaml
from langchain_core.tools import tool

from .route_steps import backfill_typed_route_steps
from .schemas import (
    ClearfactsNavigationResult,
    ExplorationAction,
    ExplorationActionType,
    NavigationActionObservation,
    NavigationEventRecord,
    NavigationExecutionStatus,
    NavigationLabelObservation,
    NavigationOntologyDelta,
    NavigationOntologyDocument,
    NavigationPageAffordance,
    NavigationPageEvidence,
    NavigationPathObservation,
    NavigationRouteStep,
    NavigationScreenObservation,
    NavigationSourceConfig,
    NavigationSourceEntryPoint,
    NavigationSourceUserCredential,
    NavigationValidationNote,
    PlaywrightMcpServerConfig,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCES_DIR = REPO_ROOT / "agents" / "sources"
WORKSPACE_DIR = REPO_ROOT / "workspace"
NAVIGATION_RUNS_DIRNAME = "navigation_agent"
TIMESTAMP_RE = re.compile(r"^\d{8}_\d{6}$")
DEFAULT_PLAYWRIGHT_MCP_COMMAND = "npx"
DEFAULT_PLAYWRIGHT_MCP_ARGS = ["-y", "@playwright/mcp@latest"]
BLANK_PAGE_URLS = {"", "about:blank", "data:,"}
TRANSIENT_NAVIGATION_ERROR_SNIPPETS = (
    "execution context was destroyed",
    "most likely because of a navigation",
    "browserbackend.calltool",
    "target closed",
    "frame was detached",
)

SECTION_ROOTS = {
    "Exploration Targets": "exploration_targets",
    "Screens": "screens",
    "Actions": "actions",
    "Labels": "labels",
    "Navigation Paths": "navigation_paths",
    "Validation Notes": "validation_notes",
    "Open Questions": "open_questions",
}


class NavigationExecutionError(RuntimeError):
    """Raised when a Playwright MCP step cannot be completed."""


class PlaywrightToolExecutionError(RuntimeError):
    """Raised when the Playwright MCP server reports a tool execution error."""

    def __init__(self, tool_name: str, arguments: dict[str, object], message: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.arguments = arguments
        self.message = message


def is_transient_navigation_error(message: str | None) -> bool:
    normalized = (message or "").lower()
    return any(snippet in normalized for snippet in TRANSIENT_NAVIGATION_ERROR_SNIPPETS)


@dataclass
class ExecutedToolCall:
    tool_name: str
    arguments: dict[str, object]
    message: str | None = None


@dataclass
class NavigationRunContext:
    source: NavigationSourceConfig
    source_yaml_path: Path
    timestamp: str
    source_workspace_dir: Path
    run_dir: Path
    run_ontology: Path
    baseline_ontology: Path
    manifest_path: Path
    logs_dir: Path
    snapshots_dir: Path
    events_path: Path
    browser_profile_dir: Path


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def make_run_timestamp(value: str | None = None) -> str:
    if value:
        if not TIMESTAMP_RE.fullmatch(value):
            raise ValueError("Run timestamp must use format yyyymmdd_hhmiss.")
        return value
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize_path(path_value: str | Path, *, base_dir: Path | None = None) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (base_dir or REPO_ROOT) / path
    return path.resolve()


def _parse_boolish(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value '{value}'.")


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"Expected string or list of strings, received: {type(value)!r}")


def _normalize_playwright_args(value: object) -> list[str]:
    if value is None:
        return list(DEFAULT_PLAYWRIGHT_MCP_ARGS)
    if isinstance(value, str):
        return shlex.split(value)
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("Playwright args must be a string or a list.")


def _parse_json_mapping(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(raw_value) for key, raw_value in value.items()}
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("PLAYWRIGHT_MCP_ENV_JSON must be a JSON object.")
        return {str(key): str(raw_value) for key, raw_value in parsed.items()}
    raise ValueError("Playwright env must be a dict or a JSON string.")


def resolve_source_yaml_path(source_name_or_path: str | Path) -> Path:
    candidate = Path(source_name_or_path)
    if candidate.exists():
        return candidate.resolve()

    filename = str(source_name_or_path)
    if not filename.endswith(".yaml"):
        filename = f"{filename}.yaml"
    return (SOURCES_DIR / filename).resolve()


def _load_source_document(source_yaml_path: Path) -> dict[str, Any]:
    if not source_yaml_path.exists():
        raise FileNotFoundError(f"Navigation source YAML not found: {source_yaml_path}")

    with source_yaml_path.open("r", encoding="utf-8") as handle:
        docs = [doc for doc in yaml.safe_load_all(handle) if doc is not None]

    if not docs:
        raise ValueError(f"Navigation source YAML is empty: {source_yaml_path}")

    data = docs[-1]
    if not isinstance(data, dict):
        raise ValueError("Navigation source YAML must contain a top-level mapping/object.")

    return data


def _load_credentials(users_file: Path) -> dict[str, NavigationSourceUserCredential]:
    if not users_file.exists():
        raise FileNotFoundError(
            f"Navigation users file not found: {users_file}. "
            "Update users_file in the navigation source YAML or provide a valid external fixture path."
        )

    payload = json.loads(users_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Navigation users fixture must contain a top-level mapping.")

    credentials: dict[str, NavigationSourceUserCredential] = {}
    for role, value in payload.items():
        if not isinstance(value, dict):
            continue
        username = value.get("username")
        password = value.get("password")
        if not username or not password:
            continue
        credentials[str(role)] = NavigationSourceUserCredential(
            username=str(username),
            password=str(password),
        )
    return credentials


def load_navigation_source(source_name_or_path: str | Path = "navigation_agent_clearfacts") -> NavigationSourceConfig:
    source_yaml_path = resolve_source_yaml_path(source_name_or_path)
    raw = _load_source_document(source_yaml_path)

    if not raw.get("name"):
        raise ValueError("Navigation source YAML must define 'name'.")
    if not raw.get("type"):
        raise ValueError("Navigation source YAML must define 'type'.")
    if not raw.get("url"):
        raise ValueError("Navigation source YAML must define 'url'.")

    source_dir = source_yaml_path.parent
    users_file_value = raw.get("users_file")
    users_file = str(_normalize_path(users_file_value, base_dir=source_dir)) if users_file_value else None
    resolved_credentials = _load_credentials(Path(users_file)) if users_file else {}

    available_roles = _normalize_string_list(raw.get("available_roles"))
    if not available_roles and resolved_credentials:
        available_roles = sorted(resolved_credentials)

    default_role = raw.get("default_role")
    if default_role is not None:
        default_role = str(default_role)
        if available_roles and default_role not in available_roles:
            raise ValueError(f"default_role '{default_role}' is not listed in available_roles.")

    entry_points = [
        NavigationSourceEntryPoint(
            name=str(item["name"]),
            path=str(item["path"]) if item.get("path") else None,
            purpose=str(item["purpose"]),
            hints=_normalize_string_list(item.get("hints")),
        )
        for item in raw.get("entry_points", [])
    ]

    playwright_raw = raw.get("playwright") or {}
    if not isinstance(playwright_raw, dict):
        raise ValueError("playwright section must be a mapping/object.")

    config = NavigationSourceConfig(
        source_name=str(raw["name"]).strip(),
        description=str(raw.get("description", "")).strip(),
        source_type=str(raw["type"]).strip(),
        base_url=str(raw["url"]).rstrip("/"),
        users_file=users_file,
        default_role=default_role,
        available_roles=available_roles,
        environment_notes=_normalize_string_list(raw.get("environment_notes")),
        entry_points=entry_points,
        ontology_guidance=str(raw["ontology_guidance"]).strip() if raw.get("ontology_guidance") else None,
        context_layer_info=str(raw["context_layer_info"]).strip() if raw.get("context_layer_info") else None,
        playwright=PlaywrightMcpServerConfig(
            command=str(playwright_raw.get("command", DEFAULT_PLAYWRIGHT_MCP_COMMAND)),
            args=_normalize_playwright_args(playwright_raw.get("args")),
            env=_parse_json_mapping(playwright_raw.get("env")),
            headless=_parse_boolish(playwright_raw.get("headless"), default=True),
            step_delay_ms=int(playwright_raw.get("step_delay_ms", 0)),
        ),
        credentials=resolved_credentials,
    )
    return config


def load_clearfacts_navigation_config(source_name: str = "navigation_agent_clearfacts") -> NavigationSourceConfig:
    """Backward-compatible helper for notebooks and ad-hoc scripts."""
    return load_navigation_source(source_name)


def build_playwright_mcp_args(raw_args: str | None, *, headless: bool) -> list[str]:
    args = _normalize_playwright_args(raw_args)
    args = [arg for arg in args if arg != "--headless"]
    if headless:
        args.append("--headless")
    return args


def _dump_yaml_block(value: object) -> str:
    rendered = yaml.safe_dump(value, sort_keys=False, allow_unicode=False).strip()
    return rendered if rendered else "[]"


def _extract_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    in_metadata = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "## Metadata":
            in_metadata = True
            continue
        if in_metadata and line.startswith("## "):
            break
        if in_metadata and line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            metadata[key.strip()] = value.strip()

    return metadata


def _extract_yaml_section(text: str, heading: str, root_key: str) -> object:
    pattern = rf"## {re.escape(heading)}\n```yaml\n(.*?)\n```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return []

    parsed = yaml.safe_load(match.group(1)) or {}
    if isinstance(parsed, dict) and root_key in parsed:
        return parsed[root_key] or []
    return parsed


def default_navigation_ontology_text(source: NavigationSourceConfig) -> str:
    targets = [target.model_dump(mode="json") for target in source.entry_points]
    
    return (
        "# Ontology\n\n"
        "## Metadata\n"
        f"- source_name: {source.source_name}\n"
        f"- source_type: {source.source_type}\n"
        f"- base_url: {source.base_url}\n"
        "- status: initialized\n\n"
        "## Notes\n"
        "- This ontology is maintained by the interactive navigation_agent runtime.\n"
        "- Update it incrementally with source-grounded observations discovered through Playwright exploration.\n\n"
        "## Exploration Targets\n"
        f"```yaml\nexploration_targets:\n{yaml.safe_dump(targets, sort_keys=False, allow_unicode=False).rstrip() if targets else '  []'}\n```\n\n"
        "## Screens\n"
        "```yaml\nscreens: []\n```\n\n"
        "## Actions\n"
        "```yaml\nactions: []\n```\n\n"
        "## Labels\n"
        "```yaml\nlabels: []\n```\n\n"
        "## Navigation Paths\n"
        "```yaml\nnavigation_paths: []\n```\n\n"
        "## Validation Notes\n"
        "```yaml\nvalidation_notes: []\n```\n\n"
        "## Open Questions\n"
        "```yaml\nopen_questions: []\n```\n"
    )


def load_navigation_ontology(path: Path) -> NavigationOntologyDocument:
    text = path.read_text(encoding="utf-8")
    metadata = _extract_metadata(text)
    return NavigationOntologyDocument(
        source_name=metadata.get("source_name", path.parent.name),
        base_url=metadata.get("base_url", ""),
        entry_points=[
            NavigationSourceEntryPoint.model_validate(item)
            for item in (_extract_yaml_section(text, "Exploration Targets", "exploration_targets") or [])
        ],
        screens=[
            NavigationScreenObservation.model_validate(item)
            for item in (_extract_yaml_section(text, "Screens", "screens") or [])
        ],
        actions=[
            NavigationActionObservation.model_validate(item)
            for item in (_extract_yaml_section(text, "Actions", "actions") or [])
        ],
        labels=[
            NavigationLabelObservation.model_validate(item)
            for item in (_extract_yaml_section(text, "Labels", "labels") or [])
        ],
        navigation_paths=[
            NavigationPathObservation.model_validate(item)
            for item in (_extract_yaml_section(text, "Navigation Paths", "navigation_paths") or [])
        ],
        validation_notes=[
            NavigationValidationNote.model_validate(item)
            for item in (_extract_yaml_section(text, "Validation Notes", "validation_notes") or [])
        ],
        open_questions=[str(item) for item in (_extract_yaml_section(text, "Open Questions", "open_questions") or [])],
    )


def render_navigation_ontology(document: NavigationOntologyDocument, *, status: str = "in_progress") -> str:
    return (
        "# Ontology\n\n"
        "## Metadata\n"
        f"- source_name: {document.source_name}\n"
        "- source_type: website\n"
        f"- base_url: {document.base_url}\n"
        f"- status: {status}\n\n"
        "## Notes\n"
        "- This ontology is maintained by the interactive navigation_agent runtime.\n"
        "- Sections below are structured so exploration findings can later support navigation, tests, and user help.\n\n"
        "## Exploration Targets\n"
        f"```yaml\nexploration_targets:\n{yaml.safe_dump([item.model_dump(mode='json') for item in document.entry_points], sort_keys=False, allow_unicode=False).rstrip() if document.entry_points else '  []'}\n```\n\n"
        "## Screens\n"
        f"```yaml\nscreens:\n{yaml.safe_dump([item.model_dump(mode='json') for item in document.screens], sort_keys=False, allow_unicode=False).rstrip() if document.screens else '  []'}\n```\n\n"
        "## Actions\n"
        f"```yaml\nactions:\n{yaml.safe_dump([item.model_dump(mode='json') for item in document.actions], sort_keys=False, allow_unicode=False).rstrip() if document.actions else '  []'}\n```\n\n"
        "## Labels\n"
        f"```yaml\nlabels:\n{yaml.safe_dump([item.model_dump(mode='json') for item in document.labels], sort_keys=False, allow_unicode=False).rstrip() if document.labels else '  []'}\n```\n\n"
        "## Navigation Paths\n"
        f"```yaml\nnavigation_paths:\n{yaml.safe_dump([item.model_dump(mode='json') for item in document.navigation_paths], sort_keys=False, allow_unicode=False).rstrip() if document.navigation_paths else '  []'}\n```\n\n"
        "## Validation Notes\n"
        f"```yaml\nvalidation_notes:\n{yaml.safe_dump([item.model_dump(mode='json') for item in document.validation_notes], sort_keys=False, allow_unicode=False).rstrip() if document.validation_notes else '  []'}\n```\n\n"
        "## Open Questions\n"
        f"```yaml\nopen_questions:\n{yaml.safe_dump(document.open_questions, sort_keys=False, allow_unicode=False).rstrip() if document.open_questions else '  []'}\n```\n"
    )


def _merge_unique_strings(existing: list[str], new_values: list[str]) -> list[str]:
    merged = list(existing)
    for value in new_values:
        if value not in merged:
            merged.append(value)
    return merged


def _route_step_key(step: NavigationRouteStep) -> str:
    return "|".join(
        str(part or "").strip().lower()
        for part in [
            step.operation.value,
            step.instruction,
            step.target,
            step.url,
            step.text,
            step.key,
            step.credential_field.value if step.credential_field else None,
        ]
    )


def _merge_route_steps(existing: list[NavigationRouteStep], new_values: list[NavigationRouteStep]) -> list[NavigationRouteStep]:
    merged = list(existing)
    seen = {_route_step_key(step) for step in merged}
    for step in new_values:
        key = _route_step_key(step)
        if key not in seen:
            merged.append(step)
            seen.add(key)
    return merged


def _screen_key(item: NavigationScreenObservation) -> str:
    return (item.url or item.title or item.name).strip().lower()


def _action_key(item: NavigationActionObservation) -> str:
    return "|".join(
        part.strip().lower()
        for part in [item.page_name or "", item.name, item.target_hint or ""]
        if part is not None
    )


def _label_key(item: NavigationLabelObservation) -> str:
    return "|".join(part.strip().lower() for part in [item.page_name or "", item.text])


def _path_key(item: NavigationPathObservation) -> str:
    return "|".join(part.strip().lower() for part in [item.from_screen or "", item.to_screen or "", item.description])


def _validation_key(item: NavigationValidationNote) -> str:
    return f"{item.severity}|{item.note.strip().lower()}"


def _merge_model_items(
    existing: list[Any],
    new_values: list[Any],
    key_fn,
    merge_fn,
) -> list[Any]:
    by_key = {key_fn(item): item for item in existing}
    ordered_keys = [key_fn(item) for item in existing]

    for item in new_values:
        key = key_fn(item)
        if key in by_key:
            by_key[key] = merge_fn(by_key[key], item)
        else:
            by_key[key] = item
            ordered_keys.append(key)

    return [by_key[key] for key in ordered_keys]


def _merge_screen(existing: NavigationScreenObservation, new_item: NavigationScreenObservation) -> NavigationScreenObservation:
    return NavigationScreenObservation(
        name=new_item.name or existing.name,
        url=new_item.url or existing.url,
        title=new_item.title or existing.title,
        description=new_item.description or existing.description,
        user_help_summary=new_item.user_help_summary or existing.user_help_summary,
        labels=_merge_unique_strings(existing.labels, new_item.labels),
        navigation_hints=_merge_unique_strings(existing.navigation_hints, new_item.navigation_hints),
        role_scope=_merge_unique_strings(existing.role_scope, new_item.role_scope),
        evidence=_merge_unique_strings(existing.evidence, new_item.evidence),
    )


def _merge_action(existing: NavigationActionObservation, new_item: NavigationActionObservation) -> NavigationActionObservation:
    return NavigationActionObservation(
        name=new_item.name or existing.name,
        description=new_item.description or existing.description,
        page_name=new_item.page_name or existing.page_name,
        target_hint=new_item.target_hint or existing.target_hint,
        role_scope=_merge_unique_strings(existing.role_scope, new_item.role_scope),
        evidence=_merge_unique_strings(existing.evidence, new_item.evidence),
    )


def _merge_label(existing: NavigationLabelObservation, new_item: NavigationLabelObservation) -> NavigationLabelObservation:
    return NavigationLabelObservation(
        text=new_item.text or existing.text,
        page_name=new_item.page_name or existing.page_name,
        label_type=new_item.label_type or existing.label_type,
        evidence=_merge_unique_strings(existing.evidence, new_item.evidence),
    )


def _merge_path(existing: NavigationPathObservation, new_item: NavigationPathObservation) -> NavigationPathObservation:
    return NavigationPathObservation(
        description=new_item.description or existing.description,
        from_screen=new_item.from_screen or existing.from_screen,
        to_screen=new_item.to_screen or existing.to_screen,
        action_summary=new_item.action_summary or existing.action_summary,
        route_steps=_merge_unique_strings(existing.route_steps, new_item.route_steps),
        typed_route_steps=_merge_route_steps(existing.typed_route_steps, new_item.typed_route_steps),
        success_criteria=_merge_unique_strings(existing.success_criteria, new_item.success_criteria),
        confidence=new_item.confidence or existing.confidence,
        evidence=_merge_unique_strings(existing.evidence, new_item.evidence),
    )


def _merge_validation(existing: NavigationValidationNote, new_item: NavigationValidationNote) -> NavigationValidationNote:
    return NavigationValidationNote(
        note=new_item.note or existing.note,
        severity=new_item.severity or existing.severity,
        evidence=_merge_unique_strings(existing.evidence, new_item.evidence),
    )


def merge_navigation_ontology(
    path: Path,
    delta: NavigationOntologyDelta,
    *,
    source_base_url: str | None = None,
) -> NavigationOntologyDocument:
    document = load_navigation_ontology(path)
    document.screens = _merge_model_items(document.screens, delta.screens, _screen_key, _merge_screen)
    document.actions = _merge_model_items(document.actions, delta.actions, _action_key, _merge_action)
    document.labels = _merge_model_items(document.labels, delta.labels, _label_key, _merge_label)
    document.navigation_paths = _merge_model_items(document.navigation_paths, delta.navigation_paths, _path_key, _merge_path)
    document.validation_notes = _merge_model_items(
        document.validation_notes,
        delta.validation_notes,
        _validation_key,
        _merge_validation,
    )
    document.open_questions = _merge_unique_strings(document.open_questions, delta.open_questions)
    backfill_typed_route_steps(document, source_base_url=source_base_url)
    path.write_text(render_navigation_ontology(document), encoding="utf-8")
    return document


def backfill_navigation_ontology_file(path: Path, *, source_base_url: str | None = None) -> int:
    document = load_navigation_ontology(path)
    added_count = backfill_typed_route_steps(document, source_base_url=source_base_url)
    if added_count:
        path.write_text(render_navigation_ontology(document), encoding="utf-8")
    return added_count


def _document_to_delta(document: NavigationOntologyDocument) -> NavigationOntologyDelta:
    return NavigationOntologyDelta(
        screens=document.screens,
        actions=document.actions,
        labels=document.labels,
        navigation_paths=document.navigation_paths,
        validation_notes=document.validation_notes,
        open_questions=document.open_questions,
    )


def _source_workspace_dir(source_name: str, workspace_dir: str | Path | None = None) -> Path:
    return _normalize_path(workspace_dir or WORKSPACE_DIR) / source_name


def _runs_workspace_dir(source_name: str, workspace_dir: str | Path | None = None) -> Path:
    return _source_workspace_dir(source_name, workspace_dir) / NAVIGATION_RUNS_DIRNAME


def _manifest_template(run: NavigationRunContext) -> dict[str, Any]:
    return {
        "run_id": f"{run.source.source_name}_{run.timestamp}",
        "source_name": run.source.source_name,
        "source_yaml": str(run.source_yaml_path),
        "base_url": run.source.base_url,
        "run_folder": str(run.run_dir),
        "run_ontology": str(run.run_ontology),
        "baseline_ontology": str(run.baseline_ontology),
        "snapshots_dir": str(run.snapshots_dir),
        "logs_dir": str(run.logs_dir),
        "events_file": str(run.events_path),
        "browser_profile_dir": str(run.browser_profile_dir),
        "status": "initialized",
        "timestamps": {
            "created": utc_now_iso(),
            "selected_timestamp": run.timestamp,
        },
        "last_role": None,
        "last_instruction": None,
        "last_observed_url": None,
        "last_observed_title": None,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False, allow_unicode=False)


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def update_manifest(path: Path, **updates: Any) -> dict[str, Any]:
    manifest = load_manifest(path)
    manifest.update(updates)
    timestamps = manifest.setdefault("timestamps", {})
    if not timestamps.get("updated"):
        timestamps["updated"] = utc_now_iso()
    else:
        timestamps["updated"] = utc_now_iso()
    write_manifest(path, manifest)
    return manifest


def _build_run_context(
    source: NavigationSourceConfig,
    source_yaml_path: Path,
    workspace_dir: str | Path | None,
    timestamp: str,
) -> NavigationRunContext:
    source_workspace_dir = _source_workspace_dir(source.source_name, workspace_dir)
    run_dir = _runs_workspace_dir(source.source_name, workspace_dir) / timestamp
    return NavigationRunContext(
        source=source,
        source_yaml_path=source_yaml_path,
        timestamp=timestamp,
        source_workspace_dir=source_workspace_dir,
        run_dir=run_dir,
        run_ontology=run_dir / "ontology.md",
        baseline_ontology=source_workspace_dir / "ontology.md",
        manifest_path=run_dir / "manifest.yaml",
        logs_dir=run_dir / "logs",
        snapshots_dir=run_dir / "snapshots",
        events_path=run_dir / "events.jsonl",
        browser_profile_dir=run_dir / "browser_profile",
    )


def setup_navigation_run(
    source_name_or_path: str | Path = "navigation_agent_clearfacts",
    *,
    workspace_dir: str | Path | None = None,
    timestamp: str | None = None,
    force: bool = False,
) -> NavigationRunContext:
    source_yaml_path = resolve_source_yaml_path(source_name_or_path)
    source = load_navigation_source(source_yaml_path)
    resolved_timestamp = make_run_timestamp(timestamp)
    run = _build_run_context(source, source_yaml_path, workspace_dir, resolved_timestamp)

    run.source_workspace_dir.mkdir(parents=True, exist_ok=True)
    _runs_workspace_dir(source.source_name, workspace_dir).mkdir(parents=True, exist_ok=True)

    if not run.baseline_ontology.exists():
        run.baseline_ontology.write_text(default_navigation_ontology_text(source), encoding="utf-8")

    if run.run_dir.exists() and not force:
        raise FileExistsError(
            f"Navigation run folder already exists: {run.run_dir}. "
            "Use force=True or choose a different timestamp."
        )

    run.run_dir.mkdir(parents=True, exist_ok=True)
    run.logs_dir.mkdir(parents=True, exist_ok=True)
    run.snapshots_dir.mkdir(parents=True, exist_ok=True)
    run.browser_profile_dir.mkdir(parents=True, exist_ok=True)

    if run.run_ontology.exists() and force:
        run.run_ontology.unlink()

    if not run.run_ontology.exists():
        shutil.copy2(run.baseline_ontology, run.run_ontology)

    write_manifest(run.manifest_path, _manifest_template(run))
    if not run.events_path.exists():
        run.events_path.write_text("", encoding="utf-8")
    return run


def load_navigation_run(
    source_name_or_path: str | Path,
    *,
    timestamp: str,
    workspace_dir: str | Path | None = None,
) -> NavigationRunContext:
    source_yaml_path = resolve_source_yaml_path(source_name_or_path)
    source = load_navigation_source(source_yaml_path)
    resolved_timestamp = make_run_timestamp(timestamp)
    run = _build_run_context(source, source_yaml_path, workspace_dir, resolved_timestamp)
    if not run.run_dir.exists():
        raise FileNotFoundError(f"Navigation run folder not found: {run.run_dir}")
    return run


def ensure_navigation_run(
    source_name_or_path: str | Path,
    *,
    timestamp: str | None = None,
    workspace_dir: str | Path | None = None,
) -> NavigationRunContext:
    if timestamp:
        return load_navigation_run(source_name_or_path, timestamp=timestamp, workspace_dir=workspace_dir)
    return setup_navigation_run(source_name_or_path, workspace_dir=workspace_dir, timestamp=timestamp, force=False)


def finalize_navigation_run(
    source_name_or_path: str | Path,
    *,
    timestamp: str,
    workspace_dir: str | Path | None = None,
    create_backup: bool = False,
) -> dict[str, Any]:
    run = load_navigation_run(source_name_or_path, timestamp=timestamp, workspace_dir=workspace_dir)
    if not run.run_ontology.exists():
        raise FileNotFoundError(f"Run ontology not found: {run.run_ontology}")

    backup_path: Path | None = None
    if create_backup and run.baseline_ontology.exists():
        backup_path = run.source_workspace_dir / f"ontology.backup.{make_run_timestamp()}.md"
        shutil.copy2(run.baseline_ontology, backup_path)

    if run.baseline_ontology.exists():
        run_delta = _document_to_delta(load_navigation_ontology(run.run_ontology))
        merge_navigation_ontology(run.baseline_ontology, run_delta, source_base_url=run.source.base_url)
    else:
        shutil.copy2(run.run_ontology, run.baseline_ontology)
        backfill_navigation_ontology_file(run.baseline_ontology, source_base_url=run.source.base_url)
    update_manifest(run.manifest_path, status="finalized", finalized=True)
    return {
        "run_folder": run.run_dir,
        "run_ontology": run.run_ontology,
        "baseline_ontology": run.baseline_ontology,
        "backup_path": backup_path,
    }


def append_navigation_event(run: NavigationRunContext, event: NavigationEventRecord) -> None:
    run.events_path.parent.mkdir(parents=True, exist_ok=True)
    with run.events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")


def read_recent_navigation_events(run: NavigationRunContext, limit: int = 6) -> list[NavigationEventRecord]:
    if not run.events_path.exists():
        return []

    lines = [line for line in run.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    recent: list[NavigationEventRecord] = []
    for line in lines[-limit:]:
        recent.append(NavigationEventRecord.model_validate(json.loads(line)))
    return recent


def read_navigation_events(run: NavigationRunContext) -> list[NavigationEventRecord]:
    if not run.events_path.exists():
        return []

    events: list[NavigationEventRecord] = []
    for line in run.events_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(NavigationEventRecord.model_validate(json.loads(line)))
    return events


def next_navigation_step_index(run: NavigationRunContext) -> int:
    return len(read_navigation_events(run)) + 1


def save_snapshot(
    run: NavigationRunContext,
    *,
    step_index: int,
    phase: str,
    page: NavigationPageEvidence,
) -> Path | None:
    if not page.snapshot and not page.text_excerpt and not page.page_summary:
        return None

    path = run.snapshots_dir / f"step_{step_index:02d}_{phase}.md"
    payload = [
        f"# Snapshot step {step_index} ({phase})",
        "",
        f"- url: {page.url or ''}",
        f"- title: {page.title or ''}",
        "",
    ]
    if page.page_summary:
        payload.extend(["## Human summary", "", page.page_summary[:12000], ""])
    if page.text_excerpt:
        payload.extend(["## Text excerpt", "```", page.text_excerpt[:12000], "```", ""])
    if page.snapshot:
        payload.extend(["## Raw snapshot", "```", page.snapshot[:24000], "```", ""])
    path.write_text("\n".join(payload), encoding="utf-8")
    return path


def _truncate_lines(values: list[str], limit: int = 8) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        compact = " ".join(part for part in value.split())
        if compact and compact not in cleaned:
            cleaned.append(compact)
        if len(cleaned) >= limit:
            break
    return cleaned


def build_human_readable_page_summary(page_data: dict[str, Any]) -> str | None:
    sections: list[str] = []

    if page_data.get("title"):
        sections.append(f"**Page title:** {page_data['title']}")
    if page_data.get("url"):
        sections.append(f"**URL:** {page_data['url']}")

    headings = _truncate_lines(page_data.get("headings") or [], limit=10)
    if headings:
        sections.append("**Headings**\n" + "\n".join(f"- {value}" for value in headings))

    buttons = _truncate_lines(page_data.get("buttons") or [], limit=12)
    if buttons:
        sections.append("**Buttons and clickable actions**\n" + "\n".join(f"- {value}" for value in buttons))

    links = _truncate_lines(page_data.get("links") or [], limit=12)
    if links:
        sections.append("**Links**\n" + "\n".join(f"- {value}" for value in links))

    inputs = _truncate_lines(page_data.get("inputs") or [], limit=12)
    if inputs:
        sections.append("**Inputs and form fields**\n" + "\n".join(f"- {value}" for value in inputs))

    affordances = page_data.get("affordances") or []
    if affordances:
        affordance_lines: list[str] = []
        for affordance in affordances[:12]:
            label = affordance.get("label") or affordance.get("description") or affordance.get("key")
            selector = affordance.get("selector")
            href = affordance.get("href")
            parts = [str(label)]
            if selector:
                parts.append(f"selector={selector}")
            elif href:
                parts.append(f"href={href}")
            affordance_lines.append(" | ".join(parts))
        if affordance_lines:
            sections.append("**Structured affordances**\n" + "\n".join(f"- {value}" for value in affordance_lines))

    text_excerpt = page_data.get("text_excerpt")
    if isinstance(text_excerpt, str) and text_excerpt.strip():
        sections.append(f"**Visible text excerpt:**\n{text_excerpt.strip()[:2000]}")

    if not sections:
        return None
    return "\n\n".join(sections)


def _slugify_affordance_value(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "item"


def _extract_ref_value(target: str | None) -> str | None:
    if not target:
        return None
    normalized = target.strip()
    if normalized.startswith("[ref=") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if normalized.startswith("[ref:") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if normalized.startswith("ref="):
        normalized = normalized.split("=", 1)[1].strip()
    if normalized.startswith("ref:"):
        normalized = normalized.split(":", 1)[1].strip()
    return normalized or None


def _snapshot_line_for_ref(snapshot: str | None, ref_target: str | None) -> str | None:
    ref_value = _extract_ref_value(ref_target)
    if not snapshot or not ref_value:
        return None
    marker = f"[ref={ref_value}]"
    for raw_line in snapshot.splitlines():
        if marker in raw_line:
            return raw_line
    return None


def _snapshot_line_descriptor(snapshot_line: str | None) -> str | None:
    if not snapshot_line:
        return None
    descriptor = snapshot_line.strip()
    descriptor = descriptor.lstrip("- ").rstrip(":")
    descriptor = re.sub(r"\s+\[[^\]]+\]", "", descriptor)
    descriptor = " ".join(descriptor.split())
    return descriptor or None


def remap_snapshot_ref_target(
    target: str | None,
    *,
    previous_snapshot: str | None,
    fresh_snapshot: str | None,
) -> str | None:
    previous_line = _snapshot_line_for_ref(previous_snapshot, target)
    descriptor = _snapshot_line_descriptor(previous_line)
    if not descriptor or not fresh_snapshot:
        return None

    exact_match: str | None = None
    fallback_match: str | None = None
    for raw_line in fresh_snapshot.splitlines():
        current_descriptor = _snapshot_line_descriptor(raw_line)
        if not current_descriptor:
            continue
        ref_match = re.search(r"\[ref=([^\]]+)\]", raw_line)
        if ref_match is None:
            continue
        candidate_ref = ref_match.group(1)
        if current_descriptor == descriptor:
            exact_match = candidate_ref
            break
        if fallback_match is None and descriptor in current_descriptor:
            fallback_match = candidate_ref
    matched_ref = exact_match or fallback_match
    if matched_ref is None:
        return None
    return f"ref={matched_ref}" if str(target or "").strip().startswith(("ref=", "[ref=")) else matched_ref


def extract_json_payload_from_tool_message(message: str | None) -> dict[str, Any] | None:
    if not message:
        return None

    candidates: list[str] = [message.strip()]
    result_match = re.search(r"### Result\s*(.*?)\s*(?:### |\Z)", message, flags=re.DOTALL)
    if result_match:
        candidates.insert(0, result_match.group(1).strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                nested = json.loads(parsed)
                if isinstance(nested, dict):
                    return nested
        except json.JSONDecodeError:
            continue
    return None


def build_prompt_source_context(source: NavigationSourceConfig, role: str | None) -> dict[str, object]:
    return {
        "source_name": source.source_name,
        "description": source.description,
        "base_url": source.base_url,
        "default_role": source.default_role,
        "active_role": role,
        "available_roles": source.available_roles,
        "environment_notes": source.environment_notes,
        "entry_points": [item.model_dump(mode="json", exclude_none=True) for item in source.entry_points],
        "ontology_guidance": source.ontology_guidance,
        "context_layer_info": source.context_layer_info,
    }


@tool("describe_navigation_source")
def describe_navigation_source_tool(source_name: str = "navigation_agent_clearfacts") -> str:
    """Describe the configured navigation source without exposing raw secrets."""
    source = load_navigation_source(source_name)
    payload = build_prompt_source_context(source, role=source.default_role)
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


class PlaywrightMcpBrowser:
    def __init__(self, config: PlaywrightMcpServerConfig) -> None:
        self._config = config
        self._session: Any | None = None
        self._tools: dict[str, Any] = {}
        self._stdio_context: Any | None = None
        self._session_context: Any | None = None


    async def __aenter__(self) -> "PlaywrightMcpBrowser":
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env={**os.environ, **self._config.env},
        )
        self._stdio_context = stdio_client(server_params)
        read, write = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(read, write)
        self._session = await self._session_context.__aenter__()
        await self._session.initialize()

        tool_result = await self._session.list_tools()
        self._tools = {tool.name: tool for tool in tool_result.tools}
        logger.info("Playwright MCP tools discovered: %s", ", ".join(sorted(self._tools)))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session_context is not None:
            await self._session_context.__aexit__(exc_type, exc, tb)
        if self._stdio_context is not None:
            await self._stdio_context.__aexit__(exc_type, exc, tb)

    def tool_inventory(self) -> list[str]:
        return sorted(self._tools)

    def _resolve_tool_name(
        self,
        *,
        exact_names: tuple[str, ...],
        contains_names: tuple[str, ...],
        purpose: str,
    ) -> str:
        for exact_name in exact_names:
            if exact_name in self._tools:
                return exact_name

        for tool_name in sorted(self._tools):
            normalized = tool_name.lower()
            if any(fragment in normalized for fragment in contains_names):
                return tool_name

        raise NavigationExecutionError(
            f"The Playwright MCP server does not expose a tool for '{purpose}'. "
            f"Available tools: {', '.join(sorted(self._tools))}"
        )

    def _tool_schema(self, tool_name: str) -> dict[str, Any]:
        tool_definition = self._tools[tool_name]
        schema = getattr(tool_definition, "inputSchema", None)
        if schema is None:
            schema = getattr(tool_definition, "input_schema", None)
        return schema or {}

    def _tool_accepts_any(self, tool_name: str, field_names: tuple[str, ...]) -> bool:
        properties = self._tool_schema(tool_name).get("properties", {})
        return any(field_name in properties for field_name in field_names)

    def _prepare_arguments(
        self,
        tool_name: str,
        candidates: list[tuple[tuple[str, ...], object | None]],
    ) -> dict[str, object]:
        properties = self._tool_schema(tool_name).get("properties", {})
        accepted_names = set(properties)
        arguments: dict[str, object] = {}

        for aliases, value in candidates:
            if value is None:
                continue
            for alias in aliases:
                if not accepted_names or alias in accepted_names:
                    arguments[alias] = value
                    break
        return arguments

    @staticmethod
    def _normalize_call_result(result: Any) -> tuple[str | None, object | None]:
        blocks: list[str] = []
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text is not None:
                blocks.append(text)
            elif hasattr(block, "model_dump"):
                blocks.append(json.dumps(block.model_dump(mode="json"), ensure_ascii=True))
            else:
                blocks.append(str(block))

        structured = getattr(result, "structured_content", None)
        if structured is None:
            structured = getattr(result, "structuredContent", None)

        combined_text = "\n".join(part for part in blocks if part).strip()
        return combined_text or None, structured

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> tuple[ExecutedToolCall, str | None, object | None]:
        logger.debug("Calling MCP tool %s with args=%s", tool_name, arguments)
        try:
            result = await self._session.call_tool(tool_name, arguments=arguments)
        except Exception as exc:
            raise PlaywrightToolExecutionError(
                tool_name=tool_name,
                arguments=arguments,
                message=f"{type(exc).__name__}: {exc}",
            ) from exc
        text, structured = self._normalize_call_result(result)
        if text and (text.lstrip().startswith("### Error") or is_transient_navigation_error(text)):
            raise PlaywrightToolExecutionError(tool_name=tool_name, arguments=arguments, message=text)
        return ExecutedToolCall(tool_name=tool_name, arguments=arguments, message=text), text, structured

    async def _with_transient_navigation_retry(
        self,
        operation,
        *,
        purpose: str,
        attempts: int = 3,
        suppress_exhausted: bool = False,
    ) -> Any | None:
        delay_seconds = max(self._config.step_delay_ms / 1000, 0.4)
        last_error: PlaywrightToolExecutionError | None = None
        for attempt_index in range(attempts):
            try:
                if attempt_index > 0:
                    await asyncio.sleep(delay_seconds * attempt_index)
                return await operation()
            except PlaywrightToolExecutionError as exc:
                if not is_transient_navigation_error(exc.message):
                    raise
                last_error = exc
                logger.debug(
                    "Transient navigation error while %s (attempt %s/%s): %s",
                    purpose,
                    attempt_index + 1,
                    attempts,
                    exc.message,
                )
        if suppress_exhausted:
            logger.debug("Suppressing exhausted transient navigation error while %s: %s", purpose, last_error)
            return None
        assert last_error is not None
        raise last_error

    async def navigate(self, url: str) -> ExecutedToolCall:
        tool_name = self._resolve_tool_name(
            exact_names=("browser_navigate", "navigate"),
            contains_names=("navigate", "goto"),
            purpose="navigation",
        )
        arguments = self._prepare_arguments(tool_name, [(("url", "uri"), url)])
        execution, _, _ = await self._call_tool(tool_name, arguments)
        return execution

    async def click(self, target: str) -> ExecutedToolCall:
        tool_name = self._resolve_tool_name(
            exact_names=("browser_click", "click"),
            contains_names=("click",),
            purpose="clicking an element",
        )
        arguments = self._prepare_arguments(tool_name, [(("target", "selector", "element", "ref"), target)])
        execution, _, _ = await self._call_tool(tool_name, arguments)
        return execution

    async def type_text(self, target: str, text: str, *, slowly: bool = False) -> ExecutedToolCall:
        tool_name = self._resolve_tool_name(
            exact_names=("browser_type", "browser_fill", "type", "fill"),
            contains_names=("type", "fill"),
            purpose="typing into an element",
        )
        arguments = self._prepare_arguments(
            tool_name,
            [
                (("target", "selector", "element", "ref"), target),
                (("text", "value"), text),
                (("slowly",), slowly if slowly else None),
            ],
        )
        execution, _, _ = await self._call_tool(tool_name, arguments)
        return execution

    async def press(self, key: str, target: str | None = None) -> ExecutedToolCall:
        tool_name = self._resolve_tool_name(
            exact_names=("browser_press_key", "browser_press", "press_key", "press"),
            contains_names=("press", "keyboard"),
            purpose="pressing a key",
        )
        arguments = self._prepare_arguments(
            tool_name,
            [
                (("target", "selector", "element", "ref"), target),
                (("key", "text"), key),
            ],
        )
        execution, _, _ = await self._call_tool(tool_name, arguments)
        return execution

    async def capture_snapshot(self, target: str | None = None) -> ExecutedToolCall:
        tool_name = self._resolve_tool_name(
            exact_names=("browser_snapshot", "snapshot", "browser_screenshot", "screenshot"),
            contains_names=("snapshot", "screenshot"),
            purpose="capturing page evidence",
        )
        arguments = self._prepare_arguments(tool_name, [(("target", "selector", "element", "ref"), target)])
        execution, _, _ = await self._call_tool(tool_name, arguments)
        return execution

    async def evaluate(self, function_text: str, target: str | None = None) -> ExecutedToolCall:
        tool_name = self._resolve_tool_name(
            exact_names=("browser_evaluate", "evaluate"),
            contains_names=("evaluate", "script"),
            purpose="running page evaluation code",
        )
        arguments = self._prepare_arguments(
            tool_name,
            [
                (("target", "selector", "element", "ref"), target),
                (("function", "expression", "script", "javascript", "code"), function_text),
            ],
        )
        execution, _, _ = await self._call_tool(tool_name, arguments)
        return execution

    async def inspect_page(self, include_snapshot: bool) -> NavigationPageEvidence:
        page = NavigationPageEvidence()

        # Phase 1: page-stability snapshot.
        # browser_snapshot waits for Playwright to settle any pending navigation
        # (e.g. form submit → server-side redirect) before evaluate() reads the DOM.
        # We discard these refs — a second snapshot is taken after evaluate() to
        # produce refs that are valid for the next action.
        if include_snapshot:
            try:
                await self._with_transient_navigation_retry(
                    lambda: self.capture_snapshot(),
                    purpose="capturing page-stability snapshot",
                    suppress_exhausted=True,
                )
            except (NavigationExecutionError, PlaywrightToolExecutionError):
                logger.debug("No snapshot tool exposed by the Playwright MCP server (stability pass).")

        try:
            execution = await self._with_transient_navigation_retry(
                lambda: self.evaluate(
                    """() => {
                    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                    const slugify = (value) => normalize(value).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'item';
                    const visible = (element) => {
                        if (!element) return false;
                        const style = window.getComputedStyle(element);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        const rect = element.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    };
                    const take = (items, limit = 12) => items.filter(Boolean).slice(0, limit);
                    const textFrom = (element) => normalize(element.innerText || element.textContent || '');
                    const inputLabel = (element) => {
                        const id = element.id || '';
                        const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                        const labelText = normalize(label ? label.innerText || label.textContent || '' : '');
                        const placeholder = normalize(element.getAttribute('placeholder') || '');
                        const name = normalize(element.getAttribute('name') || '');
                        const type = normalize(element.getAttribute('type') || element.tagName.toLowerCase());
                        return [labelText, placeholder, name, type].filter(Boolean).join(' | ');
                    };
                    const bestSelector = (element, labelText) => {
                        const tag = element.tagName.toLowerCase();
                        const id = normalize(element.id || '');
                        if (id) return `#${id}`;
                        const href = normalize(element.getAttribute('href') || '');
                        if (tag === 'a' && href) return `a[href="${href}"]`;
                        const name = normalize(element.getAttribute('name') || '');
                        if (name && ['input', 'textarea', 'select'].includes(tag)) {
                            return `${tag}[name="${name}"]`;
                        }
                        const type = normalize(element.getAttribute('type') || '');
                        if (tag === 'button' && type) return `button[type="${type}"]`;
                        if (tag === 'input' && type) return `input[type="${type}"]`;
                        const aria = normalize(element.getAttribute('aria-label') || '');
                        if (aria) return `${tag}[aria-label="${aria}"]`;
                        if (labelText && ['button', 'a'].includes(tag)) return `${tag}:has-text(${JSON.stringify(labelText)})`;
                        return null;
                    };
                    const affordanceKey = (element, labelText) => {
                        const tag = element.tagName.toLowerCase();
                        const id = normalize(element.id || '');
                        if (id) return `${tag}:id:${id}`;
                        const href = normalize(element.getAttribute('href') || '');
                        if (tag === 'a' && href) return `link:href:${href}`;
                        const name = normalize(element.getAttribute('name') || '');
                        if (name) return `${tag}:name:${name}`;
                        if (labelText) return `${tag}:text:${slugify(labelText)}`;
                        return `${tag}:anonymous`;
                    };
                    const affordances = [];
                    const seenAffordances = new Set();
                    for (const element of Array.from(document.querySelectorAll('a, button, input, textarea, select, [role="button"]'))) {
                        if (!visible(element)) continue;
                        const tag = element.tagName.toLowerCase();
                        const role = normalize(element.getAttribute('role') || '');
                        const href = normalize(element.getAttribute('href') || '');
                        const labelText = tag === 'a'
                            ? normalize(element.innerText || element.textContent || '') || href
                            : (tag === 'input' || tag === 'textarea' || tag === 'select')
                                ? inputLabel(element)
                                : normalize(element.innerText || element.textContent || '') || normalize(element.getAttribute('aria-label') || '');
                        const selector = bestSelector(element, labelText);
                        const key = affordanceKey(element, labelText);
                        const signature = `${key}|${selector || ''}|${href || ''}`;
                        if (seenAffordances.has(signature)) continue;
                        seenAffordances.add(signature);
                        affordances.push({
                            key,
                            kind: role === 'button' ? 'button' : tag,
                            label: labelText || null,
                            selector,
                            href: href || null,
                            id_attribute: normalize(element.id || '') || null,
                            name_attribute: normalize(element.getAttribute('name') || '') || null,
                            input_type: normalize(element.getAttribute('type') || '') || null,
                            description: tag === 'a'
                                ? `Link to ${href || labelText || 'target'}`
                                : tag === 'button'
                                    ? `Button ${labelText || key}`
                                    : ['input', 'textarea', 'select'].includes(tag)
                                        ? `Form field ${labelText || key}`
                                        : `${tag} ${labelText || key}`,
                        });
                        if (affordances.length >= 40) break;
                    }

                    return JSON.stringify({
                        title: document.title || null,
                        url: window.location.href || null,
                        text_excerpt: document.body && document.body.innerText ? document.body.innerText.slice(0, 4000) : null,
                        headings: take(Array.from(document.querySelectorAll('h1, h2, h3')).filter(visible).map(textFrom), 10),
                        buttons: take(
                            Array.from(document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]'))
                                .filter(visible)
                                .map((element) => textFrom(element) || normalize(element.getAttribute('value') || '') || normalize(element.getAttribute('aria-label') || '')),
                            12
                        ),
                        links: take(
                            Array.from(document.querySelectorAll('a'))
                                .filter(visible)
                                .map((element) => {
                                    const text = textFrom(element);
                                    const href = normalize(element.getAttribute('href') || '');
                                    return [text, href].filter(Boolean).join(' -> ');
                                }),
                            12
                        ),
                        inputs: take(
                            Array.from(document.querySelectorAll('input, textarea, select'))
                                .filter(visible)
                                .map(inputLabel),
                            12
                        ),
                        affordances,
                    });
                }"""
                ),
                purpose="evaluating page evidence",
                suppress_exhausted=True,
            )
            if execution is not None and execution.message:
                parsed = extract_json_payload_from_tool_message(execution.message)
                if isinstance(parsed, dict):
                    parsed_affordances = parsed.get("affordances") or []
                    page = NavigationPageEvidence(
                        url=parsed.get("url"),
                        title=parsed.get("title"),
                        text_excerpt=parsed.get("text_excerpt"),
                        page_summary=build_human_readable_page_summary(parsed),
                        affordances=[
                            NavigationPageAffordance.model_validate(item)
                            for item in parsed_affordances
                            if isinstance(item, dict)
                        ],
                    )
                else:
                    logger.debug("Could not parse page evaluation payload: %s", execution.message)
        except (NavigationExecutionError, PlaywrightToolExecutionError):
            logger.debug("No evaluation tool exposed by the Playwright MCP server.")

        # Phase 2: ref-generating snapshot.
        # This must be the LAST browser tool call before returning so that Playwright MCP
        # treats these refs as valid for the next action. Any tool call after browser_snapshot
        # (including browser_evaluate) causes the MCP server to mark previous refs as stale.
        if include_snapshot:
            try:
                snapshot = await self._with_transient_navigation_retry(
                    lambda: self.capture_snapshot(),
                    purpose="capturing ref-generating snapshot",
                    suppress_exhausted=True,
                )
                if snapshot is not None:
                    page.snapshot = snapshot.message
                    if page.text_excerpt is None and snapshot.message:
                        page.text_excerpt = snapshot.message[:4000]
                    if page.page_summary is None and page.text_excerpt:
                        page.page_summary = f"**Visible text excerpt:**\n{page.text_excerpt[:2000]}"
            except (NavigationExecutionError, PlaywrightToolExecutionError):
                logger.debug("No snapshot tool exposed by the Playwright MCP server (ref pass).")
        return page

    async def wait_for_text(self, text: str, timeout_seconds: int = 15) -> ExecutedToolCall:
        escaped_text = json.dumps(text)
        try:
            execution = await self.evaluate(
                f"""async () => {{
                const expected = {escaped_text};
                const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                const visibleText = () => normalize(document.body ? document.body.innerText || document.body.textContent || '' : '');
                const deadline = Date.now() + {int(timeout_seconds * 1000)};
                while (Date.now() <= deadline) {{
                    if (visibleText().includes(expected)) {{
                        return JSON.stringify({{
                            visible: true,
                            text: expected,
                            url: window.location.href || null,
                            title: document.title || null
                        }});
                    }}
                    await new Promise((resolve) => setTimeout(resolve, 250));
                }}
                return JSON.stringify({{
                    visible: false,
                    text: expected,
                    url: window.location.href || null,
                    title: document.title || null
                }});
            }}"""
            )
        except (NavigationExecutionError, PlaywrightToolExecutionError):
            logger.debug("Evaluate-based text wait unavailable; falling back to page evidence polling.")
        else:
            parsed = extract_json_payload_from_tool_message(execution.message)
            if parsed and parsed.get("visible") is True:
                return ExecutedToolCall(
                    tool_name=execution.tool_name,
                    arguments=execution.arguments,
                    message=f"Observed text '{text}' in page evidence.",
                )
            raise NavigationExecutionError(f"Timed out while waiting for text '{text}'.")

        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            page = await self.inspect_page(include_snapshot=True)
            haystacks = [page.text_excerpt or "", page.snapshot or "", page.title or ""]
            if any(text in haystack for haystack in haystacks):
                return ExecutedToolCall(
                    tool_name="snapshot-poll",
                    arguments={"text": text, "timeout_seconds": timeout_seconds},
                    message=f"Observed text '{text}' in page evidence.",
                )
            await asyncio.sleep(0.25)

        raise NavigationExecutionError(f"Timed out while waiting for text '{text}'.")


class PersistentPlaywrightBrowserSession:
    def __init__(self, config: PlaywrightMcpServerConfig) -> None:
        self._config = config
        self._browser: PlaywrightMcpBrowser | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._ready_event = threading.Event()
        self._shutdown_future: asyncio.Future[None] | None = None
        self._startup_error: Exception | None = None

    def start(self, timeout_seconds: int = 60) -> None:
        with self._lock:
            if self.is_active():
                return
            self._ready_event = threading.Event()
            self._startup_error = None
            self._thread = threading.Thread(target=self._thread_main, daemon=True)
            self._thread.start()

        if not self._ready_event.wait(timeout_seconds):
            raise TimeoutError("Timed out while starting the persistent Playwright MCP session.")
        if self._startup_error is not None:
            raise RuntimeError("Could not start the persistent Playwright MCP session.") from self._startup_error

    def stop(self, timeout_seconds: int = 15) -> None:
        with self._lock:
            loop = self._loop
            shutdown_future = self._shutdown_future
            thread = self._thread

        if loop is not None and shutdown_future is not None and not shutdown_future.done():
            loop.call_soon_threadsafe(shutdown_future.set_result, None)

        if thread is not None:
            thread.join(timeout_seconds)

        with self._lock:
            self._browser = None
            self._loop = None
            self._thread = None
            self._shutdown_future = None
            self._startup_error = None

    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._browser is not None and self._loop is not None

    def tool_inventory(self) -> list[str]:
        self.start()
        assert self._browser is not None
        return self._browser.tool_inventory()

    async def _run_on_session(self, operation):
        self.start()
        loop = self._loop
        browser = self._browser
        if loop is None or browser is None:
            raise RuntimeError("Persistent Playwright session is not active.")
        future = asyncio.run_coroutine_threadsafe(operation(browser), loop)
        return await asyncio.wrap_future(future)

    async def navigate(self, url: str) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.navigate(url))

    async def click(self, target: str) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.click(target))

    async def type_text(self, target: str, text: str, *, slowly: bool = False) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.type_text(target, text, slowly=slowly))

    async def press(self, key: str, target: str | None = None) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.press(key, target=target))

    async def capture_snapshot(self, target: str | None = None) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.capture_snapshot(target))

    async def evaluate(self, function_text: str, target: str | None = None) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.evaluate(function_text, target=target))

    async def inspect_page(self, include_snapshot: bool) -> NavigationPageEvidence:
        return await self._run_on_session(lambda browser: browser.inspect_page(include_snapshot))

    async def wait_for_text(self, text: str, timeout_seconds: int = 15) -> ExecutedToolCall:
        return await self._run_on_session(lambda browser: browser.wait_for_text(text, timeout_seconds=timeout_seconds))

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._shutdown_future = loop.create_future()

        async def _runner() -> None:
            browser = PlaywrightMcpBrowser(self._config)
            try:
                await browser.__aenter__()
                self._browser = browser
            except Exception as exc:  # pragma: no cover - depends on local environment
                self._startup_error = exc
                self._ready_event.set()
                return

            self._ready_event.set()
            try:
                await self._shutdown_future
            finally:
                try:
                    await browser.__aexit__(None, None, None)
                finally:
                    self._browser = None

        try:
            loop.run_until_complete(_runner())
        finally:
            self._loop = None
            self._shutdown_future = None
            loop.close()


def _run_async_blocking(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result_queue: Queue[tuple[str, Any]] = Queue(maxsize=1)

    def _target() -> None:
        try:
            result_queue.put(("result", asyncio.run(coroutine)))
        except Exception as exc:  # pragma: no cover - exercised via caller-side assertion
            result_queue.put(("error", exc))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    outcome, payload = result_queue.get()
    if outcome == "error":
        raise payload
    return payload


def prepare_playwright_run_config(source: NavigationSourceConfig, run: NavigationRunContext) -> PlaywrightMcpServerConfig:
    args = [arg for arg in source.playwright.args if arg != "--headless"]
    if source.playwright.headless:
        args.append("--headless")

    if "--user-data-dir" not in args:
        args.extend(["--user-data-dir", str(run.browser_profile_dir)])
    if "--output-dir" not in args:
        args.extend(["--output-dir", str(run.run_dir / ".playwright-mcp")])
    if "--output-mode" not in args:
        args.extend(["--output-mode", "file"])
    if "--save-session" not in args:
        args.append("--save-session")

    return PlaywrightMcpServerConfig(
        command=source.playwright.command,
        args=args,
        env=source.playwright.env,
        headless=source.playwright.headless,
        step_delay_ms=source.playwright.step_delay_ms,
    )


def resolve_role(source: NavigationSourceConfig, requested_role: str | None) -> str | None:
    role = requested_role or source.default_role
    if role is None:
        return None
    if source.available_roles and role not in source.available_roles:
        raise ValueError(
            f"Unknown role '{role}' for source '{source.source_name}'. "
            f"Available roles: {', '.join(source.available_roles)}"
        )
    return role


def resolve_role_credential(source: NavigationSourceConfig, role: str, field_name: str) -> str:
    credentials = source.credentials.get(role)
    if credentials is None:
        raise ValueError(f"No credentials configured for role '{role}'.")
    if field_name == "username":
        return credentials.username
    if field_name == "password":
        return credentials.password
    raise ValueError(f"Unsupported credential field '{field_name}'.")


def normalize_navigation_target(target: str | None) -> str | None:
    if target is None:
        return None
    normalized = target.strip()
    if normalized.startswith("[ref=") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if normalized.startswith("[ref:") and normalized.endswith("]"):
        normalized = "ref=" + normalized[5:-1]
    if normalized.startswith("ref="):
        return normalized
    if normalized.startswith("ref:"):
        ref_value = normalized.split(":", 1)[1].strip()
        return f"ref={ref_value}" if ref_value else None
    return normalized


def is_snapshot_ref_target(target: str | None) -> bool:
    if target is None:
        return False
    return re.fullmatch(r"(?:ref=)?(?:[a-z]\d+)*e\d+", target) is not None


def is_direct_execution_target(target: str | None) -> bool:
    if target is None:
        return False
    return (
        target.startswith(("#", ".", "a[", "button", "input", "textarea", "select", "["))
        or ":has-text(" in target
        or is_snapshot_ref_target(target)
    )


def resolve_affordance_target(target: str | None, *, current_page: NavigationPageEvidence | None) -> str | None:
    if target is None or is_direct_execution_target(target) or current_page is None:
        return target

    affordances = current_page.affordances
    if not affordances:
        return target

    for affordance in affordances:
        if affordance.key == target:
            return affordance.selector or (f'a[href="{affordance.href}"]' if affordance.href else None) or target

    lowered_target = target.lower()
    for affordance in affordances:
        label = (affordance.label or "").lower()
        if lowered_target == label or lowered_target in label:
            return affordance.selector or (f'a[href="{affordance.href}"]' if affordance.href else None) or affordance.key

    return target


def login_selector_target(action: ExplorationAction, *, current_page: NavigationPageEvidence | None) -> str | None:
    current_url = (current_page.url or "").lower() if current_page else ""
    snapshot = current_page.snapshot or "" if current_page else ""
    if "/login" not in current_url and "Aanmelden op Clearfacts" not in snapshot:
        return None

    if action.action_type == ExplorationActionType.TYPE_ROLE_CREDENTIAL and action.credential_field is not None:
        if action.credential_field.value == "username":
            return "#username"
        if action.credential_field.value == "password":
            return "#password"
    if action.action_type == ExplorationActionType.CLICK:
        target = action.target or ""
        summary_text = " ".join(filter(None, [action.summary, action.expected_outcome, target]))
        if "Aanmelden" in summary_text or "_submit" in target:
            return "#_submit"
    return None


def prepare_navigation_action_target(
    action: ExplorationAction,
    *,
    current_page: NavigationPageEvidence | None,
) -> ExplorationAction:
    prepared_action = action.model_copy(deep=True)
    prepared_action.target = normalize_navigation_target(prepared_action.target)

    login_target = login_selector_target(prepared_action, current_page=current_page)
    if login_target is not None:
        prepared_action.target = login_target
        return prepared_action

    resolved_target = resolve_affordance_target(prepared_action.target, current_page=current_page)
    if resolved_target is not None:
        prepared_action.target = resolved_target
    return prepared_action


def should_type_slowly(action: ExplorationAction) -> bool:
    target = action.target or ""
    return target in {"#username", "#password"} or target.startswith("input:")


def should_retry_stale_ref(*, action: ExplorationAction, error: PlaywrightToolExecutionError) -> bool:
    if action.target is None or not is_snapshot_ref_target(action.target):
        return False
    if action.action_type not in {
        ExplorationActionType.CLICK,
        ExplorationActionType.TYPE_TEXT,
        ExplorationActionType.TYPE_ROLE_CREDENTIAL,
        ExplorationActionType.PRESS_KEY,
    }:
        return False
    normalized = error.message.lower()
    return "ref " in normalized and "not found" in normalized


def event_record(
    *,
    step_index: int,
    phase: str,
    status: str,
    message: str | None = None,
    tool_name: str | None = None,
    arguments: dict[str, object] | None = None,
    snapshot_path: Path | None = None,
    page: NavigationPageEvidence | None = None,
) -> NavigationEventRecord:
    return NavigationEventRecord(
        event_id=f"{step_index:02d}-{phase}-{dt.datetime.now().strftime('%H%M%S%f')}",
        step_index=step_index,
        phase=phase,
        status=status,
        message=message,
        tool_name=tool_name,
        arguments=arguments or {},
        snapshot_path=str(snapshot_path) if snapshot_path else None,
        page_url=page.url if page else None,
        page_title=page.title if page else None,
    )


def build_result(
    *,
    status: NavigationExecutionStatus,
    run: NavigationRunContext,
    instruction: str,
    role: str | None,
    events: list[NavigationEventRecord],
    current_page: NavigationPageEvidence | None,
    tool_inventory: list[str],
    message: str | None,
    question_for_user: str | None = None,
) -> ClearfactsNavigationResult:
    return ClearfactsNavigationResult(
        status=status,
        source_name=run.source.source_name,
        run_timestamp=run.timestamp,
        run_folder=str(run.run_dir),
        ontology_path=str(run.run_ontology),
        instruction=instruction,
        role=role,
        message=message,
        question_for_user=question_for_user,
        events=events,
        current_page=current_page,
        tool_inventory=tool_inventory,
    )
