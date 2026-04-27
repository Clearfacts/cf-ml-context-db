# Copilot instructions for cf-ml-context-db

This repository contains Python services, data/ontology code, and LangChain-based agents.

When working on agent-related code:

- Follow the LangChain agent conventions in `.github/instructions/langchain-agents.instructions.md`.
- Prefer the existing project structure and utilities over introducing new patterns.
- Keep business rules in code and schemas, not only in prompts.
- Preserve observability and token tracking for all agent execution paths.

When the task is not agent-related:

- Follow the surrounding module structure and naming already used in the repository.
- Keep changes focused and consistent with existing code.
