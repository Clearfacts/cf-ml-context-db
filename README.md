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
- Run `streamlit run streamlit/app.py` to start the source ontology query UI.
