#!/usr/bin/env python3
"""Create a timestamped navigation exploration run from a source YAML definition."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from context_db.agents.clearfacts_navigation_agent.tools import setup_navigation_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Set up a new navigation run under "
            "workspace/<source_name>/navigation_agent/<timestamp>/ "
            "from a navigation source YAML file."
        )
    )
    parser.add_argument(
        "source_yaml",
        help="Path to a navigation source YAML file (e.g., agents/sources/navigation_agent_clearfacts.yaml)",
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


def main() -> int:
    args = parse_args()

    try:
        run = setup_navigation_run(
            args.source_yaml,
            workspace_dir=Path(args.workspace_dir).resolve(),
            timestamp=args.timestamp,
            force=args.force,
        )
    except Exception as exc:  # pragma: no cover - simple CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Run setup complete")
    print(f"source_workspace: {run.source_workspace_dir}")
    print(f"run_folder: {run.run_dir}")
    print(f"run_ontology: {run.run_ontology}")
    print(f"manifest: {run.manifest_path}")
    print(f"events: {run.events_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
