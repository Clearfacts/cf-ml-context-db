#!/usr/bin/env python3
"""Finalize an ontology extraction run by promoting run ontology to baseline."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

import yaml

from setup_run import AGENT_RUNS_DIRNAME, get_runs_workspace_dir


TIMESTAMP_RE = re.compile(r"^\d{8}_\d{6}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a run by copying "
            "workspace/<source_name>/extraction_agent/<timestamp>/ontology.md "
            "to workspace/<source_name>/ontology.md"
        )
    )
    parser.add_argument(
        "source_yaml",
        help="Path to a source definition YAML (e.g., agents/sources/support_agent.yaml)",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Workspace root folder where runs are stored (default: workspace)",
    )
    parser.add_argument(
        "--timestamp",
        help=(
            "Run timestamp folder to finalize, format yyyymmdd_hhmiss. "
            "If omitted, the latest run folder is selected automatically."
        ),
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup copy of baseline ontology before overwrite (default: disabled)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print what would happen without changing files",
    )
    return parser.parse_args()


def load_source_config(source_yaml_path: Path) -> dict:
    if not source_yaml_path.exists():
        raise FileNotFoundError(f"Source YAML not found: {source_yaml_path}")

    with source_yaml_path.open("r", encoding="utf-8") as handle:
        docs = [doc for doc in yaml.safe_load_all(handle) if doc is not None]

    if not docs:
        raise ValueError("Source YAML is empty")

    data = docs[-1]
    if not isinstance(data, dict):
        raise ValueError("Source YAML must contain a top-level mapping/object")

    if not data.get("name"):
        raise ValueError("Source YAML must include field 'name'")

    return data


def validate_timestamp(value: str) -> str:
    if not TIMESTAMP_RE.fullmatch(value):
        raise ValueError("--timestamp must use format yyyymmdd_hhmiss")
    return value


def list_run_dirs(runs_workspace: Path) -> list[Path]:
    if not runs_workspace.exists():
        return []

    run_dirs: list[Path] = []
    for child in runs_workspace.iterdir():
        if child.is_dir() and TIMESTAMP_RE.fullmatch(child.name):
            run_dirs.append(child)

    return sorted(run_dirs, key=lambda p: p.name)


def pick_run_dir(source_workspace: Path, timestamp: str | None) -> Path:
    runs_workspace = get_runs_workspace_dir(source_workspace)

    if timestamp:
        validate_timestamp(timestamp)
        run_dir = runs_workspace / timestamp
        if not run_dir.exists() or not run_dir.is_dir():
            raise FileNotFoundError(f"Run folder not found: {run_dir}")
        return run_dir

    runs = list_run_dirs(runs_workspace)
    if not runs:
        raise FileNotFoundError(
            f"No run folders found in {runs_workspace}. "
            "Create one first with agents/extraction_agent/setup_run.py."
        )

    return runs[-1]


def finalize_run(
    source_yaml: Path,
    workspace_dir: Path,
    timestamp: str | None,
    create_backup: bool,
    dry_run: bool,
) -> dict:
    config = load_source_config(source_yaml)
    source_name = str(config["name"]).strip()

    source_workspace = workspace_dir / source_name
    runs_workspace = get_runs_workspace_dir(source_workspace)
    baseline_ontology = source_workspace / "ontology.md"

    run_dir = pick_run_dir(source_workspace, timestamp)
    run_ontology = run_dir / "ontology.md"

    if not run_ontology.exists():
        raise FileNotFoundError(f"Run ontology not found: {run_ontology}")

    if not baseline_ontology.exists():
        raise FileNotFoundError(
            f"Baseline ontology not found: {baseline_ontology}. "
            "Run agents/extraction_agent/setup_run.py first to initialize the source workspace."
        )

    baseline_text = baseline_ontology.read_text(encoding="utf-8")
    run_text = run_ontology.read_text(encoding="utf-8")
    content_changed = baseline_text != run_text

    backup_path: Path | None = None
    if create_backup:
        backup_stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = source_workspace / f"ontology.backup.{backup_stamp}.md"

    if dry_run:
        return {
            "source_workspace": source_workspace,
            "runs_workspace": runs_workspace,
            "run_folder": run_dir,
            "run_ontology": run_ontology,
            "baseline_ontology": baseline_ontology,
            "backup_path": backup_path,
            "changed": content_changed,
            "dry_run": True,
        }

    if backup_path is not None:
        shutil.copy2(baseline_ontology, backup_path)

    shutil.copy2(run_ontology, baseline_ontology)

    return {
        "source_workspace": source_workspace,
        "runs_workspace": runs_workspace,
        "run_folder": run_dir,
        "run_ontology": run_ontology,
        "baseline_ontology": baseline_ontology,
        "backup_path": backup_path,
        "changed": content_changed,
        "dry_run": False,
    }


def main() -> int:
    args = parse_args()

    try:
        result = finalize_run(
            source_yaml=Path(args.source_yaml).resolve(),
            workspace_dir=Path(args.workspace_dir).resolve(),
            timestamp=args.timestamp,
            create_backup=args.backup,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # pragma: no cover - simple CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result["dry_run"]:
        print("Finalize dry-run complete")
    else:
        print("Finalize complete")

    print(f"source_workspace: {result['source_workspace']}")
    print(f"run_folder: {result['run_folder']}")
    print(f"run_ontology: {result['run_ontology']}")
    print(f"baseline_ontology: {result['baseline_ontology']}")

    if result["backup_path"] is not None:
        print(f"backup_ontology: {result['backup_path']}")

    print(f"content_changed: {result['changed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
