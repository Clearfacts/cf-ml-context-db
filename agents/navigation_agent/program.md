# Interactive Navigation Agent Program

## Purpose

This document defines the controlled runtime model for the interactive Clearfacts navigation agent.

The navigation agent explores a declared web application source step by step, uses Playwright MCP to inspect and act on the UI, and updates a run-local `ontology.md` so the discovered application view can be reused later for navigation, testing, and documentation.

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

For each user instruction, the agent must:

1. load the declared navigation source
2. create or resume a navigation run
3. read the run-local ontology
4. inspect the current browser state
5. decide the best next step toward the user goal
6. execute the step via Playwright MCP
7. validate the resulting page evidence
8. update the run-local ontology with grounded observations
9. persist events, snapshots, and run metadata
10. stop with an explicit status when the goal is completed, blocked, or needs user input

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
- Prefer incremental ontology updates over full rewrites.
- Persist provenance to snapshots or events whenever possible.
- If the agent is uncertain, it must ask for user input rather than guess.
- If the agent is blocked, it must record the blocking reason explicitly.
