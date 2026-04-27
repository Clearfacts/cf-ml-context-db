# Ontology Builder Program

## Purpose

This document defines what an ontology extraction agent can and cannot do during a run.

The agent receives:
- A path to this program file
- A path to one source input YAML file under `agents/sources/`

The agent must analyze the declared source and update the ontology for that source.

## Runtime Layout

Runs are created by `agents/extraction_agent/setup_run.py` and follow this structure:

```text
workspace/<source_name>/
	ontology.md
	extraction_agent/
		<yyyymmdd_hhmiss>/
			ontology.md
			logs/
```

Meaning:
- `workspace/<source_name>/ontology.md` is the current baseline ontology.
- `workspace/<source_name>/extraction_agent/<yyyymmdd_hhmiss>/ontology.md` is the run-local working copy.
- `workspace/<source_name>/extraction_agent/<yyyymmdd_hhmiss>/logs/` is reserved for runtime traces.

At setup time, the run-local `ontology.md` is copied from the baseline `ontology.md`.
At run completion, orchestration can copy run-local ontology back to baseline.

## Input Sources Supported

Supported source types:
- `local source code`
- `website`

If a source YAML declares any other `type`, the agent must stop and report that the input type is unsupported.

## Allowed Inputs

The agent may read:
- This program file
- `agents/extraction_agent/schema.md`
- The provided source YAML file in `agents/sources/`
- The run-local `ontology.md`
- The actual source content referenced by the source YAML (source code path or website URLs)

## Allowed Writes

The agent may only write to:
- `workspace/<source_name>/extraction_agent/<yyyymmdd_hhmiss>/ontology.md`

No other file may be modified by the ontology extraction agent.

## Forbidden Writes

The agent must not modify:
- `agents/extraction_agent/program.md`
- `agents/extraction_agent/schema.md`
- Any file in `agents/sources/`
- `workspace/<source_name>/ontology.md` (baseline)
- Source code files in analyzed repositories
- Files under `logs/`
- Any other workspace file

## Schema Requirement

Ontology updates must follow `agents/extraction_agent/schema.md`:
- Use core structures for entities, relationships, associations, categories, and memberships
- Keep extraction provenance (`source`, `extracted_from`) whenever possible
- Include confidence and uncertainty when applicable
- Keep output merge-friendly for later multi-agent consolidation

## Agent Task

For each run, the agent must:
1. Read the source YAML and determine source type and location.
2. Read run-local `ontology.md` as the starting point.
3. Analyze only the declared source.
4. Extend and refine run-local ontology using the schema.
5. Record ambiguity and conflicts explicitly instead of hiding them.

## Source YAML Contract

Expected fields in source input YAML:
- `name`: source identifier used as workspace folder name
- `description`: natural language description of the source
- `type`: `local source code` or `website`
- `folder`: required for `local source code`
- `urls`: required for `website` (single URL or list)
- `entry_points`: optional list of high-value files/pages
- `context_layer_info`: optional guidance on expected ontology layers

## Operational Rules

- Do not fabricate facts; only add source-grounded information.
- Prefer incremental updates over full rewrites of ontology content.
- If evidence is weak, mark low confidence and add validation notes.
- Keep existing valid ontology content unless replaced by better-structured, source-backed content.

## Completion Criteria

A run is complete when:
1. Source YAML was parsed and source was analyzed.
2. Run-local ontology was updated in schema-aligned form.
3. No forbidden file writes occurred.
4. Ambiguities and unresolved conflicts are explicitly captured.

## Short Summary

Read:
- Program
- Schema
- Source YAML
- Declared source
- Run-local ontology

Write:
- Only run-local ontology

Supported source types:
- Local source code
- website

Primary goal:
- Extend ontology in a consistent, merge-ready format.
