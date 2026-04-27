#!/usr/bin/env python3
"""Create a timestamped ontology extraction run from a source YAML definition."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

import yaml


AGENT_RUNS_DIRNAME = "extraction_agent"
SUPPORTED_TYPES = {"local source code", "website"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Set up a new ontology extraction run under "
            "workspace/<source_name>/extraction_agent/<timestamp>/ "
            "from a source YAML file."
        )
    )
    parser.add_argument(
        "source_yaml",
        help="Path to a source definition YAML (e.g., agents/sources/support_agent.yaml)",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Workspace root folder where runs are created (default: workspace)",
    )
    parser.add_argument(
        "--timestamp",
        help="Optional timestamp override in format yyyymmdd_hhmiss",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing run folder if the same timestamp already exists",
    )
    return parser.parse_args()


def load_source_config(source_yaml_path: Path) -> dict:
    if not source_yaml_path.exists():
        raise FileNotFoundError(f"Source YAML not found: {source_yaml_path}")

    with source_yaml_path.open("r", encoding="utf-8") as handle:
        docs = [doc for doc in yaml.safe_load_all(handle) if doc is not None]

    if not docs:
        return {}

    # Support markdown-like front matter patterns where doc 1 contains metadata
    # (e.g., title) and doc 2 contains the actual source definition payload.
    data = docs[-1]

    if not isinstance(data, dict):
        raise ValueError("Source YAML must contain a top-level mapping/object")

    return data


def validate_source_config(config: dict) -> None:
    missing = [key for key in ("name", "type") if not config.get(key)]
    if missing:
        raise ValueError(f"Missing required source YAML field(s): {', '.join(missing)}")

    source_type = str(config["type"]).strip()
    if source_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(f"Unsupported source type '{source_type}'. Supported types: {supported}")

    if source_type == "local source code" and not config.get("folder"):
        raise ValueError("Field 'folder' is required for source type 'local source code'")

    if source_type == "website" and not config.get("url"):
        raise ValueError("Field 'url' is required for source type 'website'")


def make_timestamp(value: str | None) -> str:
    if value:
        try:
            dt.datetime.strptime(value, "%Y%m%d_%H%M%S")
        except ValueError as exc:
            raise ValueError("--timestamp must use format yyyymmdd_hhmiss") from exc
        return value

    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def default_ontology_text(source_name: str, source_type: str) -> str:
    return (
        "# Ontology\n\n"
        "## Metadata\n"
        f"- source_name: {source_name}\n"
        f"- source_type: {source_type}\n"
        "- status: initialized\n\n"
        "## Notes\n"
        "- This baseline ontology file was initialized by agents/extraction_agent/setup_run.py.\n"
        "- Extend this file during each run using agents/extraction_agent/schema.md and agents/extraction_agent/program.md.\n"
    )


def get_runs_workspace_dir(source_workspace_dir: Path) -> Path:
    return source_workspace_dir / AGENT_RUNS_DIRNAME


def setup_run(source_yaml: Path, workspace_dir: Path, timestamp: str, force: bool) -> tuple[Path, Path, Path]:
    config = load_source_config(source_yaml)
    validate_source_config(config)

    source_name = str(config["name"]).strip()
    source_type = str(config["type"]).strip()

    source_workspace_dir = workspace_dir / source_name
    runs_workspace_dir = get_runs_workspace_dir(source_workspace_dir)
    parent_ontology = source_workspace_dir / "ontology.md"

    run_dir = runs_workspace_dir / timestamp
    run_ontology = run_dir / "ontology.md"
    logs_dir = run_dir / "logs"

    source_workspace_dir.mkdir(parents=True, exist_ok=True)
    runs_workspace_dir.mkdir(parents=True, exist_ok=True)

    if not parent_ontology.exists():
        parent_ontology.write_text(default_ontology_text(source_name, source_type), encoding="utf-8")

    if run_dir.exists() and not force:
        raise FileExistsError(
            f"Run folder already exists: {run_dir}. Use --force or provide a different timestamp."
        )

    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if run_ontology.exists() and force:
        run_ontology.unlink()

    shutil.copy2(parent_ontology, run_ontology)

    return source_workspace_dir, run_dir, run_ontology


def main() -> int:
    args = parse_args()

    try:
        source_yaml = Path(args.source_yaml).resolve()
        workspace_dir = Path(args.workspace_dir).resolve()
        timestamp = make_timestamp(args.timestamp)

        source_workspace_dir, run_dir, run_ontology = setup_run(
            source_yaml=source_yaml,
            workspace_dir=workspace_dir,
            timestamp=timestamp,
            force=args.force,
        )
    except Exception as exc:  # pragma: no cover - simple CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Run setup complete")
    print(f"source_workspace: {source_workspace_dir}")
    print(f"run_folder: {run_dir}")
    print(f"run_ontology: {run_ontology}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
