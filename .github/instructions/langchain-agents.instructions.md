# LangChain agent guidelines

Apply these instructions when creating or updating LangChain-based agents, subagents, prompts, tools, and structured-output flows in this repository.

## Architecture

- Do not use LCEL pipelines for agent orchestration. Prefer consistent `invoke(...)` or `stream(...)` calls from well-defined agent objects.
- Use explicit typed input and output models at agent boundaries.
- Keep business rules in code, schemas, validators, and tools. Do not rely on prompt text alone for behavior that must be enforced.

### Typed tool boundaries, subagents, and structured output

- Use structured output for model response shape. This does not enforce the shape of coordinator-to-subagent delegation text.
- For schema-critical orchestration paths, prefer typed LangChain tools with Pydantic `args_schema` wrappers around the underlying service or analyzer.
- Use DeepAgents `CompiledSubAgent` only when natural-language delegation is acceptable or when the subagent has its own robust input validation/fallback policy.
- Give each tool or subagent a stable name and a precise description of:
  - what input it accepts
  - any size limits or batching rules
  - what output shape it returns

Example typed tool wrapper:

```python
from langchain_core.tools import StructuredTool


def classify_batch(**kwargs: object) -> str:
    query = GPCBatchTaxonomyRequest.model_validate(kwargs)
    result = self.gpc_batch_agent.invoke(query)
    return result.model_dump_json()


classify_batch_tool = StructuredTool.from_function(
    func=classify_batch,
    name="classify_gpc_batch",
    description="Classify a batch of similar invoice lines. Input must match GPCBatchTaxonomyRequest.",
    args_schema=GPCBatchTaxonomyRequest,
)
```

Example DeepAgents subagent for non-critical delegation:

```python
AGENT_NAME = "gpc_batch_taxonomy_agent"
subagent_graph = create_agent(
      model=self.llm,
      tools=[
          get_gpc_segments, get_gpc_families, get_gpc_classes,
          get_gpc_bricks, get_gpc_brick_details, search_gpc_by_title,
          get_gpc_navigation_options,
      ],
      system_prompt=GPC_BATCH_TAXONOMY_PROMPT,
      response_format=GPCBatchTaxonomyResult,
      name=AGENT_NAME,
  )

self.gpc_batch_subagent = CompiledSubAgent(
    name=AGENT_NAME,
    description=(
        "Classifies a batch of similar invoice lines (maximum 8 lines per call) "
        "against the GPC taxonomy. "
        "Pass a JSON list of lines (each with a line_index field) and the GPC segments context. "
        "Returns a raw JSON object with a 'results' list containing one classification per line."
    ),
    runnable=subagent_graph,
)
```

## Module structure

- For each main agent, create a dedicated submodule under the main source module's `agents` package.
- Preferred layout: `<main_src_module>/agents/<agent_name>/`

Use this structure inside that folder:

- `agents.py`
  - Define one class per main agent or subagent.
  - Every agent class must define `AGENT_NAME` and `AGENT_OPERATION`.
  - All agent execution must use token tracking.
- `prompts.py`
  - Store all prompts here.
  - Use `textwrap.dedent(...)` to keep prompt definitions readable in Python files.
  - Use `.format(...)` for dynamic prompt injection.
- `schemas.py`
  - Store structured output models and related schema definitions here.
- `tools.py`
  - Prefer `@tool` annotations.
  - When tools call subagents, log the full message trace, including reasoning blocks when available.

## Model setup and Token tracking

always initialize the Azure LLM with token tracking enabled when implementing agents:

```python 
from context_db.llm.config import get_azure_llm, init_token_tracking

init_token_tracking()    
llm = get_azure_llm()
```

Wrap every agent or subagent execution path with the shared tracking context:

```python
from cf_ml_common.llm.token_tracker import tracking_context

with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
    response = agent.invoke(...)
```

The same rule applies to streaming flows.

## Prompts

- Keep prompts deterministic and domain-specific.
- When injecting data, prefer XML-style tags to create boundaries and YAML to represent structured data points.
- Use prompt structure that makes source data and instructions clearly separable.
- Do not embed business rules only in prompt text if they belong in code.

## Observability

- Log all agent and subagent calls.
- Capture full message traces for debugging and review.
- Include reasoning blocks in logs when the underlying model/runtime exposes them.
- Preserve observability for tool-triggered subagent execution as well as direct agent calls.

## Implementation preferences

- Prefer small, composable agent classes over large multi-purpose agent modules.
- Keep prompts, schemas, tools, and agent orchestration in separate files using the structure above.
- Reuse shared utilities from `cf_ml_common` where available instead of introducing parallel tracking or logging mechanisms.
