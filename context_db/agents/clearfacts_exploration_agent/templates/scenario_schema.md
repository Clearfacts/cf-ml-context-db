# Exploration Scenario Schema

Seed scenarios are human-authored markdown files stored under `agents/scenarios/<source_name>/`.
Each exploration run copies one seed into its run folder as mutable `scenario.md`.

## Frontmatter

```yaml
---
scenario_id: cf-nav-01-core-navigation
source_name: navigation_agent_clearfacts
title: Core navigation coverage
default_role: sme_admin
---
```

## Task Blocks

Tasks are parsed from `### <task_id> - <title>` headings.

Required fields:
- `status`: one of `pending`, `in_progress`, `completed`, `blocked`, `skipped`, `failed`
- `instruction`: focused navigation objective to send to the Clearfacts navigation agent

Optional fields:
- `priority`: human scheduling hint
- `max_minutes`: expected time budget for the task
- `role`: role override for this task
- `navigation_run_timestamp`: populated by the exploration agent
- `outcome`: populated by the exploration agent

Example:

```md
### T001 - Payments overview
status: pending
priority: high
instruction: Go to Payments and identify visible tabs, filters, and actions.
max_minutes: 3
role: sme_admin
```
