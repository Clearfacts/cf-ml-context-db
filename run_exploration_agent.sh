

python - <<'PY'
from context_db.agents.clearfacts_exploration_agent import ClearfactsExplorationAgent
from context_db.agents.clearfacts_exploration_agent.schemas import ClearfactsExplorationRequest

result = ClearfactsExplorationAgent().invoke(
    ClearfactsExplorationRequest(
        source_name="navigation_agent_clearfacts",
        scenario_seed_path="agents/scenarios/navigation_agent_clearfacts/01_exploration_core_navigation.md",
        max_tasks=3,
        retry_blocked=True,
        navigation_execution_max_iterations=6,
    )
)

print(result.model_dump_json(indent=2))
PY