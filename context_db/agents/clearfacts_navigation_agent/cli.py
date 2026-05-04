from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from context_db.agents.clearfacts_navigation_agent.agents import ClearfactsNavigationAgent
from context_db.agents.clearfacts_navigation_agent.schemas import ClearfactsNavigationRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the interactive Clearfacts exploration agent against the Playwright MCP server."
    )
    parser.add_argument("instruction", help="Natural-language exploration goal or navigation instruction.")
    parser.add_argument(
        "--source",
        default="navigation_agent_clearfacts",
        help="Navigation source identifier or YAML path (default: navigation_agent_clearfacts).",
    )
    parser.add_argument(
        "--role",
        help="Optional role to use. Defaults to the source YAML default_role.",
    )
    parser.add_argument(
        "--run-timestamp",
        help="Existing run timestamp to continue. When omitted, a new run is created.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=6,
        help="Upper bound for the exploration loop.",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip persisted page snapshots.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON file path for the full exploration result.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = ClearfactsNavigationRequest(
        source_name=args.source,
        instruction=args.instruction,
        role=args.role,
        run_timestamp=args.run_timestamp,
        max_iterations=args.max_iterations,
        include_snapshot=not args.no_snapshot,
    )
    result = ClearfactsNavigationAgent().invoke(request)
    payload = json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=True)

    if args.output:
        Path(args.output).expanduser().resolve().write_text(f"{payload}\n", encoding="utf-8")

    print(payload)
    return 0 if result.status.value == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
