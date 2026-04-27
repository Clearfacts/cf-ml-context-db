"""
LLM Token Usage Tracking for LangChain

Model-agnostic token tracking that works with any LangChain-compatible LLM:
- OpenAI / Azure OpenAI (including o1/o3 reasoning tokens)
- Anthropic / Claude (including cache tokens)
- Google / Gemini
- Mistral, Cohere, and others

Features:
- Normalized token counting across providers
- Support for reasoning tokens, cached tokens, audio tokens
- Global tracking with context propagation
- Database persistence for metrics collection
- Minimal integration overhead

Quick Start:

    # Option 1: Global tracking (recommended)
    from cf_ml_common.llm import init_token_tracking, get_tracker, get_usage_summary
    
    # Initialize once at startup
    init_token_tracking(project="my-project")
    
    # Get a tracker for your agent
    tracker = get_tracker("classifier")
    
    # Use with LangChain
    result = chain.invoke({"input": text}, config={"callbacks": [tracker]})
    
    # Check usage
    print(get_usage_summary())

    # Option 2: Manual tracking (more control)
    from cf_ml_common.llm import TokenTracker, AggregatedTokenTracker
    
    tracker = TokenTracker(agent_name="classifier", project="my-project")
    result = chain.invoke({"input": text}, config={"callbacks": [tracker]})
    print(tracker.usage)

    # Option 3: With database persistence
    init_token_tracking(
        project="my-project",
        persist_to_db=True,
        db_config_file="config/database.ini",
        db_section="metrics_db",
    )

Environment Variables:
    CF_LLM_TRACKING_ENABLED: "true" to enable tracking
    CF_LLM_TRACKING_PROJECT: Project name for grouping
    CF_LLM_TRACKING_DB_CONFIG: Path to database config file
    CF_LLM_TRACKING_DB_SECTION: Database section name
"""

from .token_usage import TokenUsage, LLMInvocation
from .token_tracker import TokenTracker, AggregatedTokenTracker, tracking_context
from .global_tracker import (
    init_token_tracking,
    get_global_tracker,
    get_tracker,
    get_token_usage,
    get_token_usage_by_agent,
    get_all_invocations,
    get_usage_summary,
    reset_tracking,
    track_llm_call,
    TokenTrackingConfig,
)
from .persistence import TokenUsageRepository, get_create_table_sql

__all__ = [
    # Core data models
    "TokenUsage",
    "LLMInvocation",
    
    # Callback handlers
    "TokenTracker",
    "AggregatedTokenTracker",
    
    # Global tracking API
    "init_token_tracking",
    "get_global_tracker",
    "get_tracker",
    "get_token_usage",
    "get_token_usage_by_agent",
    "get_all_invocations",
    "get_usage_summary",
    "reset_tracking",
    "tracking_context",
    "track_llm_call",
    "TokenTrackingConfig",
    
    # Persistence
    "TokenUsageRepository",
    "get_create_table_sql",
]
