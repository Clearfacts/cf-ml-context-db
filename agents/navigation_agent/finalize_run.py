#!/usr/bin/env python3
"""Promote a navigation run ontology to baseline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from context_db.agents.clearfacts_navigation_agent.tools import finalize_navigation_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a navigation run by copying "
            "workspace/<source_name>/navigation_agent/<timestamp>/ontology.md "
            "to workspace/<source_name>/ontology.md"
        )
    )
    parser.add_argument(
        "source_yaml",
        help="Path to a navigation source YAML file (e.g., agents/sources/navigation_agent_clearfacts.yaml)",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Workspace root folder where runs are stored (default: workspace)",
    )
    parser.add_argument(
        "--timestamp",
        required=True,
        help="Run timestamp folder to finalize, format yyyymmdd_hhmiss",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup copy of baseline ontology before overwrite",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        result = finalize_navigation_run(
            args.source_yaml,
            timestamp=args.timestamp,
            workspace_dir=Path(args.workspace_dir).resolve(),
            create_backup=args.backup,
        )
    except Exception as exc:  # pragma: no cover - simple CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Finalize complete")
    print(f"run_folder: {result['run_folder']}")
    print(f"run_ontology: {result['run_ontology']}")
    print(f"baseline_ontology: {result['baseline_ontology']}")
    if result["backup_path"] is not None:
        print(f"backup_ontology: {result['backup_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
