# Interactive Navigation Agent Program

## Purpose

This document defines the controlled runtime model for the interactive Clearfacts navigation agent.

The navigation agent explores a declared web application source through typed Playwright MCP-backed browser operations. Live navigation collects events, snapshots, and page affordances; a separate batch/checkpoint analyzer updates run-local `ontology.md` so the discovered application view can be reused later for navigation, testing, and documentation.

## Runtime Layout

Runs are created under:

```text
workspace/<source_name>/
    ontology.md
    navigation_agent/
        <yyyymmdd_hhmiss>/
            ontology.md
            manifest.yaml
            events.jsonl
            browser_profile/
            snapshots/
            logs/
```

Meaning:
- `workspace/<source_name>/ontology.md` is the baseline exploration ontology
- `workspace/<source_name>/navigation_agent/<timestamp>/ontology.md` is the run-local working copy
- `manifest.yaml` stores run metadata
- `events.jsonl` stores ordered exploration events
- `browser_profile/` stores browser session state for run continuation
- `snapshots/` stores page evidence
- `logs/` stores prompts, decisions, and runtime traces

## Source Contract

The navigation source YAML is expected to define:
- `name`
- `description`
- `type`
- `url`
- optional `users_file`
- optional `default_role`
- optional `available_roles`
- optional `playwright`
- optional `environment_notes`
- optional `entry_points`
- optional `ontology_guidance`
- optional `context_layer_info`

## Agent Task

For each user instruction, the live navigation runtime must:

1. load the declared navigation source
2. create or resume a navigation run
3. read the run-local ontology
4. inspect the current browser state
5. try the deterministic ontology route cache when coverage exists
6. switch to exploratory typed browser operations when the cache is missing, partial, or failed
7. validate the resulting page evidence
8. persist events, snapshots, affordances, and run metadata
9. stop with an explicit status when the goal is completed, blocked, or needs user input

For an ontology update checkpoint, the batch analyzer must:

1. read the run-local ontology and collected run evidence
2. produce additive, evidence-referenced ontology deltas
3. merge the deltas into run-local `ontology.md`
4. preserve unresolved uncertainty as validation notes or open questions

## Ontology Expectations

The run-local `ontology.md` should remain human-readable and structured enough to support later:
- guided navigation
- exploratory mapping
- user help/documentation
- future agentic tests

The ontology should capture:
- exploration targets
- screens/pages
- visible labels
- user actions and affordances
- navigation paths
- validation notes and uncertainty
- open questions for future exploration

## Operational Rules

- Do not fabricate UI facts.
- Prefer checkpoint/batch ontology updates over per-step ontology mutation.
- Persist provenance to snapshots or events whenever possible.
- If the agent is uncertain, it must ask for user input rather than guess.
- If the agent is blocked, it must record the blocking reason explicitly.
