#!/usr/bin/env python3
"""Orchestrate ontology extraction runs with setup, optional agent execution, and finalize."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from finalize_run import finalize_run
from setup_run import load_source_config, make_timestamp, setup_run, validate_source_config


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Orchestrate an ontology extraction run. "
            "Pass agent command template tokens after '--'."
        )
    )
    parser.add_argument(
        "source_yaml",
        help="Path to source definition YAML, for example agents/sources/support_agent.yaml",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Workspace root where runs are created and managed",
    )
    parser.add_argument(
        "--timestamp",
        help="Optional timestamp override in yyyymmdd_hhmiss format",
    )
    parser.add_argument(
        "--force-setup",
        action="store_true",
        help="Allow setup to overwrite an existing run folder with same timestamp",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip running the agent command",
    )
    parser.add_argument(
        "--skip-finalize",
        action="store_true",
        help="Skip promoting run ontology to baseline",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a baseline backup during finalize (default: disabled)",
    )
    parser.add_argument(
        "--agent-timeout",
        type=int,
        default=3600,
        help="Agent process timeout in seconds",
    )
    parser.add_argument(
        "--manifest-name",
        default="manifest.yaml",
        help="Manifest filename written inside the run folder",
    )

    # Parse known orchestration flags first, then treat remaining tokens as
    # agent command template tokens.
    args, unknown = parser.parse_known_args()
    args.agent_command = unknown
    return args


def write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False, allow_unicode=False)


def build_agent_prompt(
    prompt_path: Path,
    run_ontology: Path,
    source_yaml: Path,
    program_path: Path,
    schema_path: Path,
) -> None:
    prompt_text = (
        "# Ontology Extraction Run\n\n"
        "You are running a controlled ontology extraction task.\n\n"
        "Hard constraints:\n"
        "1. Edit only the run ontology file shown below.\n"
        "2. Do not modify any other file.\n"
        "3. Read and obey source, program, and schema files.\n"
        "4. Use only source-grounded information from the declared source.\n"
        "5. Preserve valid existing ontology content and extend incrementally.\n\n"
        f"run_ontology: {run_ontology}\n"
        f"source_yaml: {source_yaml}\n"
        f"program_file: {program_path}\n"
        f"schema_file: {schema_path}\n"
    )
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")


def normalize_agent_tokens(tokens: list[str]) -> list[str]:
    if tokens and tokens[0] == "--":
        return tokens[1:]
    return tokens


def resolve_agent_command(tokens: list[str], placeholders: dict[str, str]) -> list[str]:
    resolved: list[str] = []
    for token in tokens:
        try:
            resolved.append(token.format(**placeholders))
        except KeyError as exc:
            key = str(exc.args[0])
            supported = ", ".join(sorted(placeholders.keys()))
            raise ValueError(f"Unknown placeholder '{key}' in token '{token}'. Supported: {supported}") from exc
        except ValueError as exc:
            raise ValueError(f"Invalid format token '{token}': {exc}") from exc
    return resolved


def run_agent(command: list[str], logs_dir: Path, timeout_seconds: int) -> tuple[int, Path, Path]:
    stdout_path = logs_dir / "agent_stdout.log"
    stderr_path = logs_dir / "agent_stderr.log"

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")
        return proc.returncode, stdout_path, stderr_path
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        return -1, stdout_path, stderr_path
    except FileNotFoundError as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(exc), encoding="utf-8")
        return -1, stdout_path, stderr_path


def main() -> int:
    args = parse_args()

    source_yaml = Path(args.source_yaml).resolve()
    workspace_dir = Path(args.workspace_dir).resolve()
    timestamp = make_timestamp(args.timestamp)

    extraction_agent_dir = Path(__file__).resolve().parent
    program_path = (extraction_agent_dir / "program.md").resolve()
    schema_path = (extraction_agent_dir / "schema.md").resolve()

    manifest: dict[str, Any] = {
        "run_id": None,
        "source_name": None,
        "source_yaml": str(source_yaml),
        "source_type": None,
        "run_folder": None,
        "run_ontology": None,
        "baseline_ontology": None,
        "logs_dir": None,
        "program_file": str(program_path),
        "schema_file": str(schema_path),
        "status": "initialized",
        "timestamps": {
            "created": utc_now_iso(),
            "selected_timestamp": timestamp,
        },
        "agent_command": None,
        "agent_exit_code": None,
        "finalized": False,
    }

    manifest_path: Path | None = None
    exit_code = 0

    try:
        config = load_source_config(source_yaml)
        validate_source_config(config)

        source_name = str(config["name"]).strip()
        source_type = str(config["type"]).strip()

        source_workspace_dir, run_dir, run_ontology = setup_run(
            source_yaml=source_yaml,
            workspace_dir=workspace_dir,
            timestamp=timestamp,
            force=args.force_setup,
        )

        baseline_ontology = source_workspace_dir / "ontology.md"
        logs_dir = run_dir / "logs"
        prompt_file = logs_dir / "agent_prompt.md"

        manifest.update(
            {
                "run_id": f"{source_name}_{timestamp}",
                "source_name": source_name,
                "source_type": source_type,
                "run_folder": str(run_dir),
                "run_ontology": str(run_ontology),
                "baseline_ontology": str(baseline_ontology),
                "logs_dir": str(logs_dir),
            }
        )

        manifest_path = run_dir / args.manifest_name
        write_manifest(manifest_path, manifest)

        build_agent_prompt(
            prompt_path=prompt_file,
            run_ontology=run_ontology,
            source_yaml=source_yaml,
            program_path=program_path,
            schema_path=schema_path,
        )

        raw_tokens = normalize_agent_tokens(args.agent_command)

        if args.skip_agent:
            manifest["status"] = "agent_succeeded"
            manifest["agent_exit_code"] = 0
            manifest["timestamps"]["agent_started"] = utc_now_iso()
            manifest["timestamps"]["agent_finished"] = utc_now_iso()
            manifest["agent_skipped"] = True
            write_manifest(manifest_path, manifest)
        else:
            if not raw_tokens:
                raise ValueError(
                    "Agent command is required unless --skip-agent is set. "
                    "Pass tokens after '--'."
                )

            placeholders = {
                "prompt_file": str(prompt_file),
                "run_ontology": str(run_ontology),
                "run_dir": str(run_dir),
                "source_yaml": str(source_yaml),
                "program": str(program_path),
                "schema": str(schema_path),
            }

            command = resolve_agent_command(raw_tokens, placeholders)
            manifest["agent_command"] = command
            manifest["status"] = "agent_running"
            manifest["timestamps"]["agent_started"] = utc_now_iso()
            write_manifest(manifest_path, manifest)

            agent_rc, stdout_path, stderr_path = run_agent(
                command=command,
                logs_dir=logs_dir,
                timeout_seconds=args.agent_timeout,
            )
            manifest["agent_exit_code"] = agent_rc
            manifest["agent_stdout_log"] = str(stdout_path)
            manifest["agent_stderr_log"] = str(stderr_path)
            manifest["timestamps"]["agent_finished"] = utc_now_iso()

            if agent_rc == 0:
                manifest["status"] = "agent_succeeded"
            else:
                manifest["status"] = "agent_failed"
                manifest["error"] = f"Agent command failed with exit code {agent_rc}"
                exit_code = 1

            write_manifest(manifest_path, manifest)

        if args.skip_finalize:
            write_manifest(manifest_path, manifest)
            return exit_code

        if manifest["status"] != "agent_succeeded":
            return exit_code

        manifest["timestamps"]["finalize_started"] = utc_now_iso()
        write_manifest(manifest_path, manifest)

        try:
            finalize_result = finalize_run(
                source_yaml=source_yaml,
                workspace_dir=workspace_dir,
                timestamp=timestamp,
                create_backup=args.backup,
                dry_run=False,
            )

            manifest["status"] = "finalized"
            manifest["finalized"] = True
            manifest["content_changed"] = bool(finalize_result.get("changed", False))
            if finalize_result.get("backup_path") is not None:
                manifest["backup_ontology"] = str(finalize_result["backup_path"])

        except Exception as exc:
            manifest["status"] = "finalize_failed"
            manifest["finalized"] = False
            manifest["error"] = str(exc)
            exit_code = 1

        manifest["timestamps"]["finalize_finished"] = utc_now_iso()
        write_manifest(manifest_path, manifest)

    except Exception as exc:
        if manifest_path is not None:
            manifest["error"] = str(exc)
            write_manifest(manifest_path, manifest)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
