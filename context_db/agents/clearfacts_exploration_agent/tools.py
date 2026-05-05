from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from context_db.agents.clearfacts_navigation_agent.tools import (
    REPO_ROOT,
    WORKSPACE_DIR,
    load_manifest,
    load_navigation_source,
    make_run_timestamp,
    utc_now_iso,
    write_manifest,
)

from .schemas import (
    ExplorationEventRecord,
    ExplorationRunContext,
    ExplorationScenarioTask,
    ExplorationTaskStatus,
)


EXPLORATION_RUNS_DIRNAME = "exploration_agent"
SCENARIO_SEEDS_DIR = REPO_ROOT / "agents" / "scenarios"
INDEX_FILENAME = "index.yaml"
TASK_HEADING_RE = re.compile(r"^###\s+(?P<task_id>[A-Za-z0-9_-]+)\s*[-:]\s*(?P<title>.+?)\s*$", re.MULTILINE)
KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(?P<value>.*?)\s*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def list_scenario_seed_paths(source_name: str, *, scenarios_dir: str | Path | None = None) -> list[Path]:
    seed_dir = Path(scenarios_dir) if scenarios_dir is not None else SCENARIO_SEEDS_DIR
    source_seed_dir = seed_dir / source_name
    if not source_seed_dir.exists():
        return []
    return sorted(path.resolve() for path in source_seed_dir.glob("*.md") if path.is_file())


def exploration_runs_dir(source_name: str, *, workspace_dir: str | Path | None = None) -> Path:
    return Path(workspace_dir or WORKSPACE_DIR).resolve() / source_name / EXPLORATION_RUNS_DIRNAME


def exploration_index_path(source_name: str, *, workspace_dir: str | Path | None = None) -> Path:
    return exploration_runs_dir(source_name, workspace_dir=workspace_dir) / INDEX_FILENAME


def resolve_scenario_seed_path(
    source_name: str,
    scenario_seed_path: str | Path | None = None,
    *,
    scenarios_dir: str | Path | None = None,
) -> Path:
    if scenario_seed_path is not None:
        path = Path(scenario_seed_path)
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Scenario seed file not found: {path}")
        return path

    seeds = list_scenario_seed_paths(source_name, scenarios_dir=scenarios_dir)
    if not seeds:
        source_seed_dir = (Path(scenarios_dir) if scenarios_dir is not None else SCENARIO_SEEDS_DIR) / source_name
        raise FileNotFoundError(f"No scenario seed files found under: {source_seed_dir}")
    return seeds[0]


def setup_exploration_run(
    source_name_or_path: str | Path = "navigation_agent_clearfacts",
    *,
    scenario_seed_path: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    timestamp: str | None = None,
    force: bool = False,
) -> ExplorationRunContext:
    source = load_navigation_source(source_name_or_path)
    resolved_timestamp = make_run_timestamp(timestamp)
    source_workspace_dir = Path(workspace_dir or WORKSPACE_DIR).resolve() / source.source_name
    runs_dir = exploration_runs_dir(source.source_name, workspace_dir=workspace_dir)
    run_dir = runs_dir / resolved_timestamp
    seed_path = resolve_scenario_seed_path(source.source_name, scenario_seed_path)

    if run_dir.exists() and not force:
        raise FileExistsError(
            f"Exploration run folder already exists: {run_dir}. Use force=True or choose a different timestamp."
        )
    if run_dir.exists() and force:
        shutil.rmtree(run_dir)

    logs_dir = run_dir / "logs"
    source_workspace_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = run_dir / "scenario.md"
    discoveries_path = run_dir / "discoveries.md"
    events_path = run_dir / "events.jsonl"
    child_navigation_runs_path = run_dir / "child_navigation_runs.yaml"

    shutil.copy2(seed_path, scenario_path)
    discoveries_path.write_text(default_discoveries_text(source.source_name, seed_path), encoding="utf-8")
    events_path.write_text("", encoding="utf-8")
    child_navigation_runs_path.write_text("navigation_runs: []\n", encoding="utf-8")

    run = ExplorationRunContext(
        source_name=source.source_name,
        timestamp=resolved_timestamp,
        source_workspace_dir=source_workspace_dir,
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.yaml",
        scenario_path=scenario_path,
        discoveries_path=discoveries_path,
        events_path=events_path,
        logs_dir=logs_dir,
        child_navigation_runs_path=child_navigation_runs_path,
        scenario_seed_path=seed_path,
        index_path=runs_dir / INDEX_FILENAME,
    )
    write_manifest(run.manifest_path, _manifest_template(run))
    update_exploration_index(run)
    return run


def load_exploration_run(
    source_name_or_path: str | Path,
    *,
    timestamp: str,
    workspace_dir: str | Path | None = None,
) -> ExplorationRunContext:
    source = load_navigation_source(source_name_or_path)
    source_workspace_dir = Path(workspace_dir or WORKSPACE_DIR).resolve() / source.source_name
    runs_dir = exploration_runs_dir(source.source_name, workspace_dir=workspace_dir)
    run_dir = runs_dir / make_run_timestamp(timestamp)
    if not run_dir.exists():
        raise FileNotFoundError(f"Exploration run folder not found: {run_dir}")
    manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8")) or {}
    seed_path = Path(manifest.get("scenario_seed_path") or "")
    return ExplorationRunContext(
        source_name=source.source_name,
        timestamp=timestamp,
        source_workspace_dir=source_workspace_dir,
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.yaml",
        scenario_path=run_dir / "scenario.md",
        discoveries_path=run_dir / "discoveries.md",
        events_path=run_dir / "events.jsonl",
        logs_dir=run_dir / "logs",
        child_navigation_runs_path=run_dir / "child_navigation_runs.yaml",
        scenario_seed_path=seed_path,
        index_path=runs_dir / INDEX_FILENAME,
    )


def load_exploration_index(source_name_or_path: str | Path, *, workspace_dir: str | Path | None = None) -> dict[str, Any]:
    source = load_navigation_source(source_name_or_path)
    index_path = exploration_index_path(source.source_name, workspace_dir=workspace_dir)
    if not index_path.exists():
        return _empty_index(source.source_name)
    payload = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return _empty_index(source.source_name)
    payload.setdefault("version", 1)
    payload.setdefault("source_name", source.source_name)
    payload.setdefault("scenarios", [])
    return payload


def find_active_exploration_run(
    source_name_or_path: str | Path,
    *,
    scenario_seed_path: str | Path | None = None,
    workspace_dir: str | Path | None = None,
) -> str | None:
    source = load_navigation_source(source_name_or_path)
    seed_path = resolve_scenario_seed_path(source.source_name, scenario_seed_path)
    seed_key = str(seed_path.resolve())
    index = load_exploration_index(source.source_name, workspace_dir=workspace_dir)
    for scenario in index.get("scenarios", []):
        if not isinstance(scenario, dict) or scenario.get("scenario_seed_path") != seed_key:
            continue
        active_run_timestamp = scenario.get("active_run_timestamp")
        return str(active_run_timestamp) if active_run_timestamp else None
    return None


def find_latest_exploration_run(
    source_name_or_path: str | Path,
    *,
    scenario_seed_path: str | Path | None = None,
    workspace_dir: str | Path | None = None,
) -> str | None:
    source = load_navigation_source(source_name_or_path)
    seed_path = resolve_scenario_seed_path(source.source_name, scenario_seed_path)
    seed_key = str(seed_path.resolve())
    index = load_exploration_index(source.source_name, workspace_dir=workspace_dir)
    for scenario in index.get("scenarios", []):
        if not isinstance(scenario, dict) or scenario.get("scenario_seed_path") != seed_key:
            continue
        latest_run_timestamp = scenario.get("latest_run_timestamp")
        return str(latest_run_timestamp) if latest_run_timestamp else None
    return None


def update_exploration_index(run: ExplorationRunContext) -> None:
    index = _load_index_from_path(run.index_path, source_name=run.source_name)
    scenarios = index.setdefault("scenarios", [])
    seed_path = str(run.scenario_seed_path.resolve()) if run.scenario_seed_path else ""
    seed_sha256 = _safe_sha256(run.scenario_seed_path)
    scenario_entry = _find_scenario_entry(scenarios, seed_path)
    if scenario_entry is None:
        scenario_entry = {
            "scenario_seed_path": seed_path,
            "scenario_seed_sha256": seed_sha256,
            "latest_run_timestamp": None,
            "active_run_timestamp": None,
            "runs": [],
        }
        scenarios.append(scenario_entry)

    scenario_entry["scenario_seed_sha256"] = seed_sha256
    scenario_entry["latest_run_timestamp"] = run.timestamp
    runs = scenario_entry.setdefault("runs", [])
    run_entry = _find_run_entry(runs, run.timestamp)
    if run_entry is None:
        run_entry = {"run_timestamp": run.timestamp}
        runs.append(run_entry)

    manifest = load_manifest(run.manifest_path)
    task_counts = scenario_task_counts(run.scenario_path) if run.scenario_path.exists() else {}
    run_entry.update(
        {
            "run_timestamp": run.timestamp,
            "run_folder": str(run.run_dir),
            "scenario_path": str(run.scenario_path),
            "discoveries_path": str(run.discoveries_path),
            "manifest_path": str(run.manifest_path),
            "status": manifest.get("status") or "unknown",
            "updated_at": utc_now_iso(),
            **task_counts,
        }
    )
    if task_counts.get("active_task_count", 0) > 0:
        scenario_entry["active_run_timestamp"] = run.timestamp
    elif scenario_entry.get("active_run_timestamp") == run.timestamp:
        scenario_entry["active_run_timestamp"] = None

    index["updated_at"] = utc_now_iso()
    run.index_path.parent.mkdir(parents=True, exist_ok=True)
    run.index_path.write_text(yaml.safe_dump(index, sort_keys=False, allow_unicode=False), encoding="utf-8")


def scenario_task_counts(scenario_path: Path) -> dict[str, int]:
    tasks = load_scenario_tasks(scenario_path)
    counts = {
        "task_count": len(tasks),
        "pending_task_count": 0,
        "in_progress_task_count": 0,
        "completed_task_count": 0,
        "blocked_task_count": 0,
        "skipped_task_count": 0,
        "failed_task_count": 0,
        "active_task_count": 0,
    }
    for task in tasks:
        key = f"{task.status.value}_task_count"
        if key in counts:
            counts[key] += 1
        if task.status in {ExplorationTaskStatus.PENDING, ExplorationTaskStatus.IN_PROGRESS}:
            counts["active_task_count"] += 1
    return counts


def parse_scenario_tasks(scenario_text: str) -> list[ExplorationScenarioTask]:
    matches = list(TASK_HEADING_RE.finditer(scenario_text))
    tasks: list[ExplorationScenarioTask] = []
    for index, match in enumerate(matches):
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(scenario_text)
        block = scenario_text[block_start:block_end]
        metadata = _parse_task_metadata(block)
        instruction = str(metadata.get("instruction") or "").strip()
        if not instruction:
            instruction = _first_body_line(block)
        tasks.append(
            ExplorationScenarioTask(
                task_id=match.group("task_id"),
                title=match.group("title"),
                instruction=instruction,
                status=_parse_task_status(metadata.get("status")),
                priority=_optional_str(metadata.get("priority")),
                max_minutes=_parse_int(metadata.get("max_minutes"), default=3),
                role=_optional_str(metadata.get("role")),
                navigation_run_timestamp=_optional_str(metadata.get("navigation_run_timestamp")),
                outcome=_optional_str(metadata.get("outcome")),
            )
        )
    return tasks


def parse_scenario_metadata(scenario_text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(scenario_text)
    if not match:
        return {}
    payload = yaml.safe_load(match.group("body")) or {}
    return payload if isinstance(payload, dict) else {}


def load_scenario_metadata(scenario_path: Path) -> dict[str, Any]:
    return parse_scenario_metadata(scenario_path.read_text(encoding="utf-8"))


def load_scenario_tasks(scenario_path: Path) -> list[ExplorationScenarioTask]:
    return parse_scenario_tasks(scenario_path.read_text(encoding="utf-8"))


def update_scenario_task(
    scenario_path: Path,
    *,
    task_id: str,
    status: ExplorationTaskStatus,
    outcome: str,
    navigation_run_timestamp: str | None = None,
    evidence: list[str] | None = None,
) -> None:
    text = scenario_path.read_text(encoding="utf-8")
    matches = list(TASK_HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group("task_id") != task_id:
            continue
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[block_start:block_end]
        block = _upsert_metadata(block, "status", status.value)
        block = _upsert_metadata(block, "last_update", utc_now_iso())
        block = _upsert_metadata(block, "outcome", _single_line(outcome))
        if navigation_run_timestamp:
            block = _upsert_metadata(block, "navigation_run_timestamp", navigation_run_timestamp)
        block = _append_progress_note(
            block,
            status=status,
            outcome=outcome,
            evidence=evidence or [],
        )
        scenario_path.write_text(text[:block_start] + block + text[block_end:], encoding="utf-8")
        return
    raise ValueError(f"Scenario task not found: {task_id}")


def append_discovery(
    discoveries_path: Path,
    *,
    task_id: str,
    message: str,
    evidence: list[str] | None = None,
) -> None:
    evidence_text = ", ".join(evidence or [])
    suffix = f" Evidence: {evidence_text}" if evidence_text else ""
    with discoveries_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {utc_now_iso()} [{task_id}] {message}{suffix}\n")


def append_exploration_event(run: ExplorationRunContext, event: ExplorationEventRecord) -> None:
    with run.events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")


def record_child_navigation_run(
    run: ExplorationRunContext,
    *,
    task_id: str,
    status: str,
    run_timestamp: str,
    run_folder: str,
    instruction: str,
) -> None:
    payload = yaml.safe_load(run.child_navigation_runs_path.read_text(encoding="utf-8")) or {}
    navigation_runs = payload.setdefault("navigation_runs", [])
    navigation_runs.append(
        {
            "task_id": task_id,
            "status": status,
            "run_timestamp": run_timestamp,
            "run_folder": run_folder,
            "instruction": instruction,
            "recorded_at": utc_now_iso(),
        }
    )
    run.child_navigation_runs_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def default_discoveries_text(source_name: str, seed_path: Path) -> str:
    return (
        "# Exploration Discoveries\n\n"
        "Human-reviewed candidates for future scenario seeds. The exploration agent should append here instead of silently expanding scope.\n\n"
        f"- source_name: {source_name}\n"
        f"- scenario_seed: {seed_path}\n\n"
        "## Candidates\n"
    )


def _manifest_template(run: ExplorationRunContext) -> dict[str, Any]:
    return {
        "run_id": f"{run.source_name}_exploration_{run.timestamp}",
        "source_name": run.source_name,
        "run_folder": str(run.run_dir),
        "scenario_path": str(run.scenario_path),
        "discoveries_path": str(run.discoveries_path),
        "events_file": str(run.events_path),
        "logs_dir": str(run.logs_dir),
        "child_navigation_runs": str(run.child_navigation_runs_path),
        "scenario_seed_path": str(run.scenario_seed_path),
        "scenario_seed_sha256": _sha256(run.scenario_seed_path),
        "status": "initialized",
        "timestamps": {
            "created": utc_now_iso(),
            "selected_timestamp": run.timestamp,
        },
        "attempted_task_count": 0,
        "completed_task_count": 0,
        "blocked_task_count": 0,
        "skipped_task_count": 0,
        "failed_task_count": 0,
    }


def _empty_index(source_name: str) -> dict[str, Any]:
    return {
        "version": 1,
        "source_name": source_name,
        "updated_at": utc_now_iso(),
        "scenarios": [],
    }


def _load_index_from_path(index_path: Path, *, source_name: str) -> dict[str, Any]:
    if not index_path.exists():
        return _empty_index(source_name)
    payload = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return _empty_index(source_name)
    payload.setdefault("version", 1)
    payload.setdefault("source_name", source_name)
    payload.setdefault("scenarios", [])
    return payload


def _find_scenario_entry(scenarios: list[Any], seed_path: str) -> dict[str, Any] | None:
    for scenario in scenarios:
        if isinstance(scenario, dict) and scenario.get("scenario_seed_path") == seed_path:
            return scenario
    return None


def _find_run_entry(runs: list[Any], timestamp: str) -> dict[str, Any] | None:
    for run in runs:
        if isinstance(run, dict) and run.get("run_timestamp") == timestamp:
            return run
    return None


def _parse_task_metadata(block: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    lines = block.splitlines()
    line_index = 0
    while line_index < len(lines):
        raw_line = lines[line_index]
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("- "):
            line_index += 1
            continue
        match = KEY_VALUE_RE.match(line)
        if match:
            key = match.group("key")
            value = match.group("value").strip()
            if value in {"|", ">"}:
                block_lines: list[str] = []
                line_index += 1
                while line_index < len(lines):
                    next_raw_line = lines[line_index]
                    next_line = next_raw_line.strip()
                    if next_line and not next_raw_line.startswith((" ", "\t")):
                        break
                    if not next_line:
                        block_lines.append("")
                    elif next_raw_line.startswith((" ", "\t")):
                        block_lines.append(next_raw_line.strip())
                    else:
                        block_lines.append(next_line)
                    line_index += 1
                if value == ">":
                    metadata[key] = " ".join(line for line in block_lines if line).strip()
                else:
                    metadata[key] = "\n".join(block_lines).strip()
                continue
            metadata[key] = value.strip('"')
        line_index += 1
    return metadata


def _first_body_line(block: str) -> str:
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if line and not KEY_VALUE_RE.match(line) and not line.startswith("#") and not line.startswith("- "):
            return line
    return ""


def _parse_task_status(value: str | None) -> ExplorationTaskStatus:
    if not value:
        return ExplorationTaskStatus.PENDING
    try:
        return ExplorationTaskStatus(value.strip().lower())
    except ValueError:
        return ExplorationTaskStatus.PENDING


def _parse_int(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _upsert_metadata(block: str, key: str, value: str) -> str:
    lines = block.splitlines()
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*:")
    replacement = f"{key}: {value}"
    for index, line in enumerate(lines):
        if key_re.match(line):
            lines[index] = replacement
            return "\n" + "\n".join(lines).strip("\n") + "\n\n"
    insert_index = 0
    while insert_index < len(lines) and not lines[insert_index].strip():
        insert_index += 1
    lines.insert(insert_index, replacement)
    return "\n" + "\n".join(lines).strip("\n") + "\n\n"


def _append_progress_note(
    block: str,
    *,
    status: ExplorationTaskStatus,
    outcome: str,
    evidence: list[str],
) -> str:
    evidence_suffix = f" Evidence: {', '.join(evidence)}" if evidence else ""
    note = f"- {utc_now_iso()} [{status.value}] {_single_line(outcome)}{evidence_suffix}"
    stripped = block.rstrip()
    if "#### Progress Notes" not in stripped:
        return stripped + "\n\n#### Progress Notes\n" + note + "\n\n"
    return stripped + "\n" + note + "\n\n"


def _single_line(value: str) -> str:
    return " ".join((value or "").split())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_sha256(path: Path) -> str | None:
    if not path or not path.is_file():
        return None
    return _sha256(path)
