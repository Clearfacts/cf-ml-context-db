# cf-ml-context-db

## Technical debt links
- [Barometer IT](https://wolterskluwer.barometerit.com/b/system/041800002496)
- [SonarQube Project](https://sonarqube.cloud-dev.wolterskluwer.eu/dashboard?id=clearfacts%3Acf-ml-context-db)
- [Black Duck Project](https://wolterskluwer.app.blackduck.com/api/projects/628bca44-133a-45b4-8d0d-9a9fbb6725ca)
- [Checkmarx Project](https://test4tools.cchaxcess.com/CxWebClient/projectscans.aspx?id=18826)

## Overview
`cf-ml-context-db` is the base context system for the ClearFacts AI agent stack. It is intended to hold layered ontology and platform knowledge for the ClearFacts pre-accounting domain, from business concepts down to application, architecture, database, and data-flow details.

## Project layout
- `context_db/`: main Python package
- `context_db/agents/`: LangChain-based agent modules
- `context_db/model/`: model and ontology classes
- `context_db/data/`: ORM repositories
- `context_db/databases/`: database connection helpers
- `context_db/llm/`: model configuration and LLM bootstrap
- `data/`: local database files and generated artifacts
- `config/`: runtime configuration
- `streamlit/`: Streamlit UI entrypoints

## Configuration
- Copy `.env.example` to `.env` and fill in the required values.
- `config/fab_models.yaml` resolves Azure endpoints and API keys from environment variables.
- `config/database.ini` includes a safe local SQLite default for the context database and placeholder sections for related ClearFacts databases.

## Streamlit
- Run `streamlit run streamlit/app.py` to start the Streamlit app.
- The app now includes:
  - an **Explore app** tab for interactive Clearfacts navigation and mapping
  - an **Ontology query** tab for the existing source-level ontology queries
  - the exploration tab uses the **DeepAgents navigation coordinator** with typed browser operations over Playwright MCP
  - the exploration tab uses the navigation source configuration, which now launches Chrome in headed mode by default so you can follow along
  - the exploration tab keeps a live Playwright MCP browser session open for the active run until you explicitly close it or start a different run
  - the exploration tab surfaces persisted DeepAgents trace artifacts alongside the latest execution evidence
  - the exploration tab includes an explicit **Update ontology** action that analyzes collected run evidence in batch

## Clearfacts navigation agent
- The low-level interactive Clearfacts navigation runtime lives in `context_db/agents/clearfacts_navigation_agent/`.
- The DeepAgents orchestration layer lives in `context_db/agents/clearfacts_navigation_deepagent/`.
- The scenario-level exploration orchestrator lives in `context_db/agents/clearfacts_exploration_agent/`.
- Source-driven configuration now lives in `agents/sources/navigation_agent_clearfacts.yaml`.
- Exploration runs are persisted under `workspace/<source_name>/navigation_agent/<timestamp>/`.
- Each run stores:
  - run-local `ontology.md`
  - `manifest.yaml`
  - `events.jsonl`
  - `snapshots/` with a human-readable page summary plus the raw MCP snapshot
  - `logs/`
  - `browser_profile/`
- DeepAgents coordinator and subagent traces are persisted under `logs/deepagent_traces/`.
- The coordinator now has a deterministic `execute_cached_route` tool. It tries high-confidence ontology navigation paths before exploratory browser operations, can execute legacy text route steps or typed route steps, and returns `partial` when only part of a goal is cached.
- Live navigation collects events, snapshots, and affordances only. `update_ontology(...)` merges the batch analyzer delta into both the run-local `ontology.md` and the source-level `workspace/<source_name>/ontology.md`; it does not update after every browser step.
- `ClearfactsNavigationDeepAgent` now exposes both:
  - `invoke(...)` for interactive navigation/exploration
  - `update_ontology(...)` for checkpoint/batch ontology updates from collected run evidence
  - `validate(...)` for validator-driven claim/procedure replay that returns `supports`, `contradicts`, or `inconclusive` with observed evidence
- The ontology remains markdown and is extended with structured sections for:
  - exploration targets
  - screens
  - actions
  - labels
  - navigation paths
  - validation notes
  - open questions
- Longer exploration scenarios can be seeded from `agents/scenarios/<source_name>/NN_exploration_<topic>.md`.
- `ClearfactsExplorationAgent` copies a seed scenario into `workspace/<source_name>/exploration_agent/<timestamp>/scenario.md`, updates that run-local scenario as tasks progress, and records future human-review candidates in `discoveries.md`.
- `workspace/<source_name>/exploration_agent/index.yaml` tracks runs per scenario seed. When `run_timestamp` is omitted, `ClearfactsExplorationAgent` resumes the active run for that seed if it still has `pending` or `in_progress` tasks.
- Example CLI invocation:

```bash
python -m context_db.agents.clearfacts_navigation_agent.cli \
  "Log in and explore where an SME user can upload purchase invoices" \
  --role sme_admin
```
