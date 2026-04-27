"""
Global Token Tracker with Context-Based Automatic Propagation

Provides a global token tracking system that:
- Automatically tracks all LangChain LLM calls when enabled
- Uses contextvars for proper async/thread handling
- Can be configured via environment variables
- Supports automatic database persistence

Usage:
    # At application startup
    from cf_ml_common.llm import init_token_tracking
    init_token_tracking(project="my-project")
    
    # Or via environment variables:
    # CF_LLM_TRACKING_ENABLED=true
    # CF_LLM_TRACKING_PROJECT=my-project
    # CF_LLM_TRACKING_DB_CONFIG=config/database.ini
    # CF_LLM_TRACKING_DB_SECTION=metrics_db
    
    # Then use LangChain normally - tracking happens automatically
    result = chain.invoke({"input": text})
    
    # Get usage summary
    from cf_ml_common.llm import get_usage_summary
    print(get_usage_summary())
"""

import os
import threading
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from .token_usage import TokenUsage, LLMInvocation, build_llm_invocation
from .token_tracker import TokenTracker, AggregatedTokenTracker, _current_context

logger = logging.getLogger(__name__)


@dataclass
class TokenTrackingConfig:
    """
    Configuration for token tracking.
    
    Centralizes all configuration options for token tracking, supporting
    both programmatic configuration and environment variable loading.
    
    Attributes:
        project: Project identifier for grouping metrics
        enabled: Whether tracking is enabled
        persist_to_db: Whether to persist invocations to database
        db_config_file: Path to database config file
        db_section: Database section name (default: "metrics_db")
        batch_size: Number of records to batch before flushing (default: 100)
        flush_interval: Max seconds between flushes (default: 5.0)
        auto_register_callback: Auto-register with LangChain's global callback manager
        on_invocation: Custom callback for each invocation
    """
    project: str = ""
    enabled: bool = True
    persist_to_db: bool = False
    db_config_file: Optional[str] = None
    db_section: str = "metrics_db"
    batch_size: int = 100
    flush_interval: float = 5.0
    auto_register_callback: bool = True
    on_invocation: Optional[Callable[[LLMInvocation], None]] = None
    
    @classmethod
    def from_env(cls) -> "TokenTrackingConfig":
        """
        Load configuration from environment variables.
        
        Environment variables:
            CF_LLM_TRACKING_ENABLED: "true" to enable tracking
            CF_LLM_TRACKING_PROJECT: Project name for grouping
            CF_LLM_TRACKING_DB_CONFIG: Path to database config file
            CF_LLM_TRACKING_DB_SECTION: Database section name
            
        Returns:
            TokenTrackingConfig instance with values from environment
        """
        env_enabled = os.environ.get("CF_LLM_TRACKING_ENABLED", "").lower()
        enabled = env_enabled == "true" if env_enabled else True
        
        return cls(
            project=os.environ.get("CF_LLM_TRACKING_PROJECT", ""),
            enabled=enabled,
            persist_to_db=os.environ.get("CF_LLM_TRACKING_DB_CONFIG") is not None,
            db_config_file=os.environ.get("CF_LLM_TRACKING_DB_CONFIG"),
            db_section=os.environ.get("CF_LLM_TRACKING_DB_SECTION", "metrics_db"),
        )


# Global state
_global_tracker: Optional[AggregatedTokenTracker] = None
_global_lock = threading.Lock()
_initialized = False
_persistence_callback: Optional[Callable[[LLMInvocation], None]] = None
_langchain_hook_registered = False
_langchain_global_handler_var: Optional[Any] = None
_langchain_global_handler: Any = None


def init_token_tracking(
    project: str = "",
    enabled: bool = True,
    persist_to_db: bool = False,
    db_config_file: Optional[str] = None,
    db_section: Optional[str] = None,
    on_invocation: Optional[Callable[[LLMInvocation], None]] = None,
    auto_register_callback: bool = True,
    config: Optional[TokenTrackingConfig] = None,
) -> Optional[AggregatedTokenTracker]:
    """
    Initialize global token tracking.
    
    Call this once at application startup. Can also be configured via environment variables
    or by passing a TokenTrackingConfig instance.
    
    Args:
        project: Project identifier for grouping metrics (overridden by config)
        enabled: Whether tracking is enabled (overridden by config)
        persist_to_db: Whether to persist invocations to database (overridden by config)
        db_config_file: Path to database config file (overridden by config)
        db_section: Database section name (overridden by config)
        on_invocation: Custom callback for each invocation (overridden by config)
        auto_register_callback: Auto-register with LangChain's global callback manager (overridden by config)
        config: TokenTrackingConfig instance (takes precedence over individual parameters)
        
    Returns:
        AggregatedTokenTracker instance if enabled, None otherwise
        
    Raises:
        ValueError: If database configuration is invalid when persist_to_db is True
    """
    global _global_tracker, _initialized, _persistence_callback
    
    # Use config if provided, otherwise create from parameters/env
    if config is None:
        config = TokenTrackingConfig.from_env()
        # Override with explicit parameters if provided
        if project:
            config.project = project
        if enabled is not None:
            config.enabled = enabled
        if persist_to_db:
            config.persist_to_db = persist_to_db
        if db_config_file:
            config.db_config_file = db_config_file
        if db_section:
            config.db_section = db_section
        if on_invocation:
            config.on_invocation = on_invocation
        if auto_register_callback is not None:
            config.auto_register_callback = auto_register_callback
    
    if not config.enabled:
        _initialized = True
        return None
    
    project = config.project
    db_config_file = config.db_config_file
    db_section = config.db_section
    
    # Set up persistence if configured
    if config.persist_to_db and config.db_config_file:
        _persistence_callback = _create_db_persistence_callback(
            config.db_config_file, 
            config.db_section,
            batch_size=config.batch_size,
            flush_interval=config.flush_interval,
        )
    
    # Combine callbacks
    def combined_callback(invocation: LLMInvocation):
        if config.on_invocation:
            config.on_invocation(invocation)
        if _persistence_callback:
            _persistence_callback(invocation)
    
    with _global_lock:
        _global_tracker = AggregatedTokenTracker(
            project=project,
            on_invocation=combined_callback if (config.on_invocation or _persistence_callback) else None,
        )
        _initialized = True
    
    # Auto-register with LangChain global callback manager
    if config.auto_register_callback:
        _register_global_callback()
    
    return _global_tracker


def _create_db_persistence_callback(
    config_file: str,
    section: str,
    batch_size: int = 100,
    flush_interval: float = 5.0,
) -> Callable[[LLMInvocation], None]:
    """
    Create a callback that persists invocations to database.
    
    Uses a background thread with batching for efficiency.
    
    Args:
        config_file: Path to database config file
        section: Database section name
        batch_size: Number of records to batch before flushing
        flush_interval: Max seconds between flushes
        
    Returns:
        Callback function that queues invocations for persistence
        
    Raises:
        ValueError: If database configuration is invalid
    """
    from .persistence import TokenUsageRepository
    
    repo = TokenUsageRepository(
        config_file, 
        section,
        batch_size=batch_size,
        flush_interval=flush_interval,
    )
    
    def callback(invocation: LLMInvocation):
        # Queue for async persistence
        repo.queue_invocation(invocation)
    
    return callback


def _register_global_callback():
    """
    Register a global callback with LangChain's callback manager.

    Notes:
        LangChain does not expose a single "global callback manager" instance.
        Instead, callback managers are *configured* per-run via
        `CallbackManager.configure(...)`. LangChain provides a supported hook
        mechanism (`register_configure_hook`) that allows injecting a handler
        into every configured callback manager.

        This function uses that hook so token tracking works without explicitly
        passing callbacks in `config={"callbacks": [...]}`.
    """
    try:
        # LangChain's supported hook API (used by tracing_v2_enabled, collect_runs, etc.)
        from contextvars import ContextVar

        from langchain_core.tracers.context import register_configure_hook

        global _langchain_hook_registered, _langchain_global_handler_var, _langchain_global_handler

        if _langchain_hook_registered:
            # Idempotent: we only want to register the hook once per process.
            return

        class _GlobalTokenTrackingHandler(TokenTracker):
            """
            A global callback handler that forwards invocations into the global aggregator.

            Important:
                This handler is meant for "automatic tracking" mode where users do NOT
                pass explicit TokenTracker callbacks. If you also pass explicit trackers,
                you may double-count usage (once via explicit tracker, once via this global handler).
            """

            def __init__(self):
                # TokenTracker is only used here for its extraction/parsing logic.
                super().__init__(agent_name="", project="", operation="", tags={})
                self._start_times: Dict[str, float] = {}

            def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
                run_id = kwargs.get("run_id")
                if run_id is not None:
                    self._start_times[str(run_id)] = datetime.now(timezone.utc).timestamp()

            def on_llm_end(self, response, **kwargs):
                
                # If global tracking is disabled/uninitialized, do nothing.
                if _global_tracker is None:
                    return

                # Derive latency from the stored run_id start timestamp (best-effort).
                latency_ms = 0.0
                run_id = kwargs.get("run_id")
                if run_id is not None:
                    start_ts = self._start_times.pop(str(run_id), None)
                    if start_ts is not None:
                        latency_ms = (datetime.now(timezone.utc).timestamp() - start_ts) * 1000.0

                # Pull dynamic context (tags, trace_id, and optional agent attribution)
                context = _current_context.get() or {}
                agent_name = context.get("agent_name") or "global"
                operation = context.get("operation") or ""
                tags = context.get("tags", {}) or {}
                trace_id = context.get("trace_id")

                # Extract normalized usage + metadata
                invocation_usage = self._extract_usage(response)
                metadata = self._extract_metadata(response)

                invocation = build_llm_invocation(
                    usage=invocation_usage,
                    project=_global_tracker.project,
                    agent_name=agent_name,
                    operation=operation,
                    latency_ms=latency_ms,
                    trace_id=trace_id,
                    tags=tags,
                    metadata=metadata,
                )

                # Ensure an agent tracker exists, then update it atomically.
                tracker = _global_tracker.get_tracker(agent_name)
                if tracker is None:
                    tracker = _global_tracker.create_tracker(agent_name, operation=operation, tags=None)

                with tracker._lock:  # noqa: SLF001 (internal aggregation)
                    tracker._usage += invocation_usage  # noqa: SLF001
                    tracker._invocations.append(invocation)  # noqa: SLF001
                    tracker._invocation_count += 1  # noqa: SLF001

                # Call global "on_invocation" callback (e.g., DB persistence), if configured.
                if _global_tracker.on_invocation:
                    try:
                        _global_tracker.on_invocation(invocation)
                    except Exception as e:
                        logger.error(
                            "Error in global on_invocation callback",
                            exc_info=True,
                            extra={
                                "agent_name": agent_name,
                                "invocation_id": invocation.id,
                                "project": _global_tracker.project,
                            }
                        )
                        # Don't let callback errors affect main flow

        _langchain_global_handler_var = ContextVar("cf_llm_global_token_tracking_handler", default=None)
        register_configure_hook(_langchain_global_handler_var, inheritable=True)

        _langchain_global_handler = _GlobalTokenTrackingHandler()
        _langchain_global_handler_var.set(_langchain_global_handler)
        _langchain_hook_registered = True

    except ImportError:
        pass  # LangChain not available, skip auto-registration


def get_global_tracker() -> Optional[AggregatedTokenTracker]:
    """
    Get the global token tracker instance.
    
    Returns:
        AggregatedTokenTracker if initialized and enabled, None otherwise
    """
    return _global_tracker


def get_tracker(agent_name: str, operation: str = "", tags: Optional[Dict[str, str]] = None) -> TokenTracker:
    """
    Get or create a tracker for a specific agent.
    
    This is the main way to get trackers when using global tracking.
    
    Args:
        agent_name: Name of the agent/component
        operation: Operation type
        tags: Custom tags
        
    Returns:
        TokenTracker instance
        
    Raises:
        RuntimeError: If global tracker initialization fails
        
    Example:
        tracker = get_tracker("classifier")
        result = chain.invoke({"input": text}, config={"callbacks": [tracker]})
    """
    global _global_tracker
    
    if _global_tracker is None:
        # Auto-initialize with defaults if not already initialized
        if not _initialized:
            init_token_tracking()
        
        if _global_tracker is None:
            # Tracking disabled, return a no-op tracker
            return TokenTracker(agent_name=agent_name)
    
    # Merge with context tags
    context = _current_context.get()
    merged_tags = {**context.get("tags", {}), **(tags or {})}
    
    return _global_tracker.create_tracker(
        agent_name=agent_name,
        operation=operation,
        tags=merged_tags,
    )


def get_token_usage() -> TokenUsage:
    """
    Get total token usage from the global tracker.
    
    Returns:
        TokenUsage with aggregated totals
    """
    if _global_tracker is None:
        return TokenUsage()
    return _global_tracker.total_usage


def get_token_usage_by_agent() -> Dict[str, TokenUsage]:
    """
    Get token usage breakdown by agent.
    
    Returns:
        Dictionary mapping agent names to TokenUsage
    """
    if _global_tracker is None:
        return {}
    return _global_tracker.usage_by_agent


def get_all_invocations() -> List[LLMInvocation]:
    """
    Get all recorded invocations.
    
    Returns:
        List of LLMInvocation records sorted by timestamp
    """
    if _global_tracker is None:
        return []
    return _global_tracker.all_invocations


def get_usage_summary() -> str:
    """
    Get human-readable usage summary.
    
    Returns:
        Formatted summary string
    """
    if _global_tracker is None:
        return "Token tracking not initialized or disabled"
    return _global_tracker.summary()


def reset_tracking():
    """Reset all tracked usage (useful between test runs or batches)"""
    if _global_tracker is not None:
        _global_tracker.reset()


# Convenience function for getting a pre-configured tracker in common patterns
def track_llm_call(
    agent_name: str = "default",
    operation: str = "",
) -> TokenTracker:
    """
    Convenience function to get a tracker for a single LLM call.
    
    Usage:
        with track_llm_call("summarizer") as tracker:
            result = chain.invoke({"input": text}, config={"callbacks": [tracker]})
        print(tracker.usage)
    """
    return get_tracker(agent_name, operation)
