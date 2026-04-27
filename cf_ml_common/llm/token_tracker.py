"""
LangChain Callback Handler for Token Tracking

Model-agnostic callback that extracts and normalizes token usage
from any LangChain-compatible LLM provider.
"""

from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from contextvars import ContextVar
import threading
import time
import logging

from .token_usage import TokenUsage, LLMInvocation, build_llm_invocation

# Lazy import to avoid hard dependency on langchain
if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# Context variable for request/operation scoping
# Used by both TokenTracker and global tracking system
_current_context: ContextVar[Dict[str, Any]] = ContextVar("llm_tracking_context", default={})


def _get_base_callback_handler():
    """Lazy import of BaseCallbackHandler"""
    try:
        from langchain_core.callbacks import BaseCallbackHandler
        return BaseCallbackHandler
    except ImportError:
        # Fallback for older langchain versions
        try:
            from langchain.callbacks.base import BaseCallbackHandler
            return BaseCallbackHandler
        except ImportError:
            raise ImportError(
                "langchain-core is required for token tracking. "
                "Install with: pip install langchain-core"
            )


class TokenTracker(_get_base_callback_handler()):
    """
    LangChain callback handler for tracking token usage.
    
    Extracts and normalizes token usage from any LLM provider response.
    
    Usage:
        tracker = TokenTracker(agent_name="classifier")
        result = chain.invoke({"input": text}, config={"callbacks": [tracker]})
        print(tracker.usage)
        print(tracker.invocations)
    """
    
    def __init__(
        self,
        agent_name: str = "",
        project: str = "",
        operation: str = "",
        tags: Optional[Dict[str, str]] = None,
        trace_id: Optional[str] = None,
        on_invocation: Optional[Callable[[LLMInvocation], None]] = None,
    ):
        """
        Initialize TokenTracker.
        
        Args:
            agent_name: Name of the agent/component using this tracker
            project: Project identifier for grouping metrics
            operation: Operation type (e.g., "classify", "analyze")
            tags: Custom tags for filtering/grouping
            trace_id: Optional trace ID for request tracing (also checked from context if available)
            on_invocation: Optional callback called after each invocation
                           Signature: (invocation: LLMInvocation) -> None
        """
        super().__init__()
        self.agent_name = agent_name
        self.project = project
        self.operation = operation
        self.tags = tags or {}
        self.trace_id = trace_id
        self.on_invocation = on_invocation
        
        self._usage = TokenUsage()
        self._invocations: List[LLMInvocation] = []
        self._start_time: Optional[float] = None
        self._lock = threading.Lock()
        self._invocation_count = 0
    
    @property
    def usage(self) -> TokenUsage:
        """Get aggregated token usage"""
        return self._usage
    
    @property
    def invocations(self) -> List[LLMInvocation]:
        """Get list of individual invocation records"""
        return self._invocations.copy()
    
    @property
    def invocation_count(self) -> int:
        """Get total number of invocations"""
        return self._invocation_count
    
    def reset(self):
        """
        Reset all tracked usage.
        
        Thread-safe operation that clears all invocations and usage statistics.
        """
        with self._lock:
            self._usage = TokenUsage()
            self._invocations = []
            self._invocation_count = 0
    
    def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """
        Called when LLM starts processing.
        
        Args:
            serialized: Serialized LLM configuration
            prompts: List of input prompts
            **kwargs: Additional arguments from LangChain
        """
        self._start_time = time.time()
    
    def on_llm_end(
        self, 
        response: Any,  # LLMResult type from langchain
        **kwargs: Any
    ) -> None:
        """
        Called when LLM completes - extract token usage.
        
        Args:
            response: LLMResult from LangChain
            **kwargs: Additional arguments from LangChain
            
        Raises:
            Exception: If token extraction fails (logged but not re-raised)
        """
        latency_ms = (time.time() - self._start_time) * 1000 if self._start_time else 0
        
        invocation_usage = self._extract_usage(response)
        metadata = self._extract_metadata(response)
        
        # Get context values (if tracking context is active)
        trace_id = self.trace_id
        operation = self.operation
        tags = dict(self.tags)  # Copy to avoid mutating instance tags
        
        # Check context for dynamic values
        context = _current_context.get()
        if context:
            # Merge trace_id: context takes precedence
            trace_id = context.get("trace_id") or trace_id
            # Use context operation if available, otherwise fall back to instance
            context_operation = context.get("operation")
            if context_operation:
                operation = context_operation
            # Merge tags: context tags first, then instance tags (instance tags override context)
            context_tags = context.get("tags", {})
            if context_tags:
                tags = {**context_tags, **tags}
        
        invocation = build_llm_invocation(
            usage=invocation_usage,
            project=self.project,
            agent_name=self.agent_name,
            operation=operation,
            latency_ms=latency_ms,
            trace_id=trace_id,
            tags=tags,
            metadata=metadata,
        )
        
        with self._lock:
            self._usage += invocation_usage
            self._invocations.append(invocation)
            self._invocation_count += 1
        
        # Call optional callback
        if self.on_invocation:
            try:
                self.on_invocation(invocation)
            except Exception as e:
                logger.error(
                    "Error in on_invocation callback",
                    exc_info=True,
                    extra={
                        "agent_name": self.agent_name,
                        "invocation_id": invocation.id,
                        "project": self.project,
                    }
                )
                # Don't let callback errors affect main flow
    
    def _extract_usage(self, response: Any) -> TokenUsage:
        """
        Extract token usage from LLMResult - handles multiple providers.
        
        Args:
            response: LLMResult from LangChain
            
        Returns:
            TokenUsage object with extracted token counts
            
        Raises:
            Exception: If extraction fails (logged and returns empty usage)
        """
        usage = TokenUsage()
        
        try:
            # Try llm_output first (standard location)
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage", {})
            
            # Also check response metadata from generations
            response_metadata = {}
            generations = getattr(response, "generations", None)
            if generations and generations[0]:
                gen = generations[0][0]
                if hasattr(gen, "message") and hasattr(gen.message, "response_metadata"):
                    response_metadata = gen.message.response_metadata or {}
                # Also check generation_info
                if hasattr(gen, "generation_info") and gen.generation_info:
                    response_metadata.update(gen.generation_info)
            
            # Merge sources (response_metadata takes precedence)
            combined = {**token_usage, **response_metadata}
            
            # Also check for nested "usage" key (Anthropic format)
            if "usage" in combined and isinstance(combined["usage"], dict):
                combined.update(combined["usage"])
            
            # Extract model info
            usage.model = (
                llm_output.get("model_name") or 
                response_metadata.get("model") or
                response_metadata.get("model_name", "")
            )
            
            # Detect provider
            usage.provider = self._detect_provider(usage.model, combined)
            
            # Extract tokens based on provider patterns
            usage = self._normalize_tokens(usage, combined)
            
        except Exception as e:
            logger.warning(
                "Failed to extract token usage from response",
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "response_type": type(response).__name__,
                }
            )
            # Return empty usage rather than crashing
            return TokenUsage()
        
        return usage
    
    def _detect_provider(self, model: str, data: Dict[str, Any]) -> str:
        """
        Detect the LLM provider from model name or response structure.
        
        Args:
            model: Model name string
            data: Response data dictionary
            
        Returns:
            Provider name string (e.g., "openai", "anthropic", "google")
        """
        model_lower = model.lower()
        
        if any(x in model_lower for x in ["gpt", "o1", "o3", "davinci", "turbo"]):
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        elif "gemini" in model_lower:
            return "google"
        elif any(x in model_lower for x in ["mistral", "mixtral"]):
            return "mistral"
        elif "llama" in model_lower:
            return "meta"
        elif "command" in model_lower:
            return "cohere"
        
        # Detect from response structure
        if "input_tokens" in data:
            return "anthropic"
        if "prompt_tokens_details" in data:
            return "openai"
        if "promptTokenCount" in data or "prompt_token_count" in data:
            return "google"
        
        return "unknown"
    
    def _normalize_tokens(self, usage: TokenUsage, data: Dict[str, Any]) -> TokenUsage:
        """
        Normalize token counts across different provider response formats.
        
        Args:
            usage: TokenUsage object to populate
            data: Response data dictionary with provider-specific token fields
            
        Returns:
            TokenUsage object with normalized token counts
        """
        
        # OpenAI / Azure OpenAI format
        if "prompt_tokens" in data:
            usage.prompt_tokens = data.get("prompt_tokens", 0)
            usage.completion_tokens = data.get("completion_tokens", 0)
            usage.total_tokens = data.get("total_tokens", 0)
            
            # OpenAI detailed breakdown (GPT-4 Turbo, o1, o3)
            prompt_details = data.get("prompt_tokens_details", {})
            if prompt_details:
                usage.cached_prompt_tokens = prompt_details.get("cached_tokens", 0)
                usage.cache_read_tokens = prompt_details.get("cached_tokens", 0)
                usage.audio_prompt_tokens = prompt_details.get("audio_tokens", 0)
            
            completion_details = data.get("completion_tokens_details", {})
            if completion_details:
                usage.reasoning_tokens = completion_details.get("reasoning_tokens", 0)
                usage.audio_completion_tokens = completion_details.get("audio_tokens", 0)
        
        # Anthropic format
        elif "input_tokens" in data:
            usage.prompt_tokens = data.get("input_tokens", 0)
            usage.completion_tokens = data.get("output_tokens", 0)
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            
            # Anthropic cache tokens
            usage.cache_creation_tokens = data.get("cache_creation_input_tokens", 0)
            usage.cache_read_tokens = data.get("cache_read_input_tokens", 0)
            usage.cached_prompt_tokens = usage.cache_read_tokens
        
        # Google/Gemini format
        elif "promptTokenCount" in data or "prompt_token_count" in data:
            usage.prompt_tokens = data.get("promptTokenCount") or data.get("prompt_token_count", 0)
            usage.completion_tokens = data.get("candidatesTokenCount") or data.get("candidates_token_count", 0)
            usage.total_tokens = data.get("totalTokenCount") or data.get("total_token_count", 0)
            
            # Gemini cached content
            usage.cached_prompt_tokens = data.get("cachedContentTokenCount") or data.get("cached_content_token_count", 0)
            usage.cache_read_tokens = usage.cached_prompt_tokens
        
        # Ensure total is calculated if not provided
        if usage.total_tokens == 0 and (usage.prompt_tokens or usage.completion_tokens):
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        
        return usage
    
    def _extract_metadata(self, response: Any) -> Dict[str, Any]:
        """
        Extract additional metadata from response.
        
        Args:
            response: LLMResult from LangChain
            
        Returns:
            Dictionary with extracted metadata (chat_id, finish_reason, etc.)
        """
        metadata = {}
        
        llm_output = getattr(response, "llm_output", None) or {}
        if llm_output:
            metadata["system_fingerprint"] = llm_output.get("system_fingerprint")
            metadata["chat_id"] = (
                llm_output.get("id")
                or llm_output.get("response_id")
                or llm_output.get("completion_id")
            )
        
        generations = getattr(response, "generations", None)
        if generations and generations[0]:
            gen = generations[0][0]
            if hasattr(gen, "message") and hasattr(gen.message, "response_metadata"):
                rm = gen.message.response_metadata or {}
                metadata["finish_reason"] = rm.get("finish_reason") or rm.get("stop_reason")
                metadata["chat_id"] = metadata.get("chat_id") or rm.get("id") or rm.get("response_id") or rm.get("completion_id")
                if not metadata.get("system_fingerprint"):
                    metadata["system_fingerprint"] = rm.get("system_fingerprint")
            if hasattr(gen, "generation_info") and gen.generation_info:
                gi = gen.generation_info or {}
                metadata["finish_reason"] = metadata.get("finish_reason") or gi.get("finish_reason") or gi.get("stop_reason")
                metadata["chat_id"] = metadata.get("chat_id") or gi.get("id") or gi.get("response_id") or gi.get("completion_id")
                if not metadata.get("system_fingerprint"):
                    metadata["system_fingerprint"] = gi.get("system_fingerprint")
        
        return {k: v for k, v in metadata.items() if v is not None}
    
    def summary(self) -> str:
        """Generate human-readable usage summary"""
        u = self._usage
        lines = [
            f"TokenTracker: {self.agent_name or 'unnamed'}",
            f"  Invocations: {self._invocation_count}",
            f"  Total tokens: {u.total_tokens:,}",
            f"    Prompt: {u.prompt_tokens:,}",
            f"    Completion: {u.completion_tokens:,}",
        ]
        
        if u.reasoning_tokens:
            lines.append(f"    Reasoning: {u.reasoning_tokens:,}")
        
        if u.cache_read_tokens:
            lines.append(f"    Cached: {u.cache_read_tokens:,}")
            lines.append(f"    Effective prompt: {u.effective_prompt_tokens:,}")
        
        if u.model:
            lines.append(f"  Model: {u.model}")
        
        return "\n".join(lines)


class AggregatedTokenTracker:
    """
    Aggregates token usage across multiple agents/components.
    
    Usage:
        aggregator = AggregatedTokenTracker(project="support-agent")
        
        tracker1 = aggregator.create_tracker("content_analyzer")
        result1 = chain1.invoke(..., config={"callbacks": [tracker1]})
        
        tracker2 = aggregator.create_tracker("classifier")
        result2 = chain2.invoke(..., config={"callbacks": [tracker2]})
        
        print(aggregator.summary())
    """
    
    def __init__(
        self,
        project: str = "",
        on_invocation: Optional[Callable[[LLMInvocation], None]] = None,
    ):
        """
        Initialize AggregatedTokenTracker.
        
        Args:
            project: Project identifier applied to all trackers
            on_invocation: Callback called after each invocation across all trackers
        """
        self.project = project
        self.on_invocation = on_invocation
        self._trackers: Dict[str, TokenTracker] = {}
        self._lock = threading.Lock()
    
    def create_tracker(
        self,
        agent_name: str,
        operation: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> TokenTracker:
        """
        Create a new tracker for an agent.
        
        Args:
            agent_name: Name of the agent/component
            operation: Operation type
            tags: Custom tags
            
        Returns:
            TokenTracker instance
        """
        tracker = TokenTracker(
            agent_name=agent_name,
            project=self.project,
            operation=operation,
            tags=tags,
            on_invocation=self.on_invocation,
        )
        
        with self._lock:
            self._trackers[agent_name] = tracker
        
        return tracker
    
    def get_tracker(self, agent_name: str) -> Optional[TokenTracker]:
        """Get tracker for a specific agent"""
        return self._trackers.get(agent_name)
    
    @property
    def total_usage(self) -> TokenUsage:
        """Get total aggregated usage across all agents"""
        total = TokenUsage()
        for tracker in self._trackers.values():
            total += tracker.usage
        return total
    
    @property
    def usage_by_agent(self) -> Dict[str, TokenUsage]:
        """Get usage breakdown by agent"""
        return {name: tracker.usage for name, tracker in self._trackers.items()}
    
    @property
    def all_invocations(self) -> List[LLMInvocation]:
        """Get all invocations across all agents, sorted by timestamp"""
        invocations = []
        for tracker in self._trackers.values():
            invocations.extend(tracker.invocations)
        return sorted(invocations, key=lambda x: x.timestamp)
    
    @property
    def total_invocations(self) -> int:
        """Get total invocation count across all trackers"""
        return sum(t.invocation_count for t in self._trackers.values())
    
    def reset(self):
        """Reset all trackers"""
        with self._lock:
            for tracker in self._trackers.values():
                tracker.reset()
    
    def to_dict(self) -> Dict[str, Any]:
        """Export all tracking data as dictionary"""
        return {
            "project": self.project,
            "total": self.total_usage.to_dict(),
            "by_agent": {name: usage.to_dict() for name, usage in self.usage_by_agent.items()},
            "invocation_count": self.total_invocations,
        }
    
    def summary(self) -> str:
        """Generate a human-readable summary"""
        total = self.total_usage
        lines = [
            "=" * 50,
            f"Token Usage Summary: {self.project or 'unnamed project'}",
            "=" * 50,
            f"Total tokens: {total.total_tokens:,}",
            f"  Prompt: {total.prompt_tokens:,}",
            f"  Completion: {total.completion_tokens:,}",
        ]
        
        if total.reasoning_tokens:
            lines.append(f"  Reasoning: {total.reasoning_tokens:,}")
        
        if total.cache_read_tokens:
            lines.append(f"  Cached: {total.cache_read_tokens:,}")
            lines.append(f"  Effective prompt: {total.effective_prompt_tokens:,}")
        
        lines.append(f"\nTotal invocations: {self.total_invocations}")
        
        if len(self._trackers) > 1:
            lines.append("\nBy Agent:")
            for name, tracker in sorted(self._trackers.items()):
                u = tracker.usage
                lines.append(f"  {name}: {u.total_tokens:,} tokens ({tracker.invocation_count} calls)")
        
        lines.append("=" * 50)
        return "\n".join(lines)


class tracking_context:
    """
    Context manager for scoped token tracking.
    
    Use this to add context (tags, trace_id, operation, agent_name) to all invocations within a scope.
    Works with both global tracking and direct TokenTracker usage.
    
    Usage:
        with tracking_context(trace_id="request-123", tags={"user": "john"}):
            # All LLM calls within this block get the context
            result = chain.invoke(...)
    """
    
    def __init__(
        self,
        trace_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        agent_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        self.trace_id = trace_id
        self.tags = tags or {}
        self.agent_name = agent_name
        self.operation = operation
        self.tags.update(kwargs)  # Allow tags as keyword args
        self._token = None
        self._previous_context = None
    
    def __enter__(self):
        self._previous_context = _current_context.get()
        
        # Merge with existing context
        new_context = {
            "trace_id": self.trace_id or self._previous_context.get("trace_id"),
            "agent_name": self.agent_name or self._previous_context.get("agent_name"),
            "operation": self.operation or self._previous_context.get("operation"),
            "tags": {**self._previous_context.get("tags", {}), **self.tags},
        }
        
        self._token = _current_context.set(new_context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token is not None:
            _current_context.reset(self._token)
        return False
