"""
Token Usage Data Models

Model-agnostic token usage tracking that normalizes across providers:
- OpenAI / Azure OpenAI
- Anthropic / Claude
- Google / Gemini
- Mistral, Cohere, etc.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid


@dataclass
class TokenUsage:
    """
    Normalized token usage across LLM providers.
    
    Supports standard tokens, reasoning tokens (o1/o3, Claude thinking),
    cached tokens, and audio tokens for multimodal models.
    """
    
    # Standard tokens
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Reasoning tokens (o1/o3 models, Claude extended thinking)
    reasoning_tokens: int = 0
    
    # Cached tokens (prompt caching)
    cached_prompt_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    
    # Audio tokens (multimodal)
    audio_prompt_tokens: int = 0
    audio_completion_tokens: int = 0
    
    # Metadata
    model: str = ""
    provider: str = ""
    
    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage objects together"""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cached_prompt_tokens=self.cached_prompt_tokens + other.cached_prompt_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            audio_prompt_tokens=self.audio_prompt_tokens + other.audio_prompt_tokens,
            audio_completion_tokens=self.audio_completion_tokens + other.audio_completion_tokens,
            model=other.model or self.model,
            provider=other.provider or self.provider,
        )
    
    def __iadd__(self, other: "TokenUsage") -> "TokenUsage":
        """In-place addition"""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.cached_prompt_tokens += other.cached_prompt_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.audio_prompt_tokens += other.audio_prompt_tokens
        self.audio_completion_tokens += other.audio_completion_tokens
        self.model = other.model or self.model
        self.provider = other.provider or self.provider
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_prompt_tokens": self.cached_prompt_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "audio_prompt_tokens": self.audio_prompt_tokens,
            "audio_completion_tokens": self.audio_completion_tokens,
            "model": self.model,
            "provider": self.provider,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenUsage":
        """Create from dictionary"""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            reasoning_tokens=data.get("reasoning_tokens", 0),
            cached_prompt_tokens=data.get("cached_prompt_tokens", 0),
            cache_creation_tokens=data.get("cache_creation_tokens", 0),
            cache_read_tokens=data.get("cache_read_tokens", 0),
            audio_prompt_tokens=data.get("audio_prompt_tokens", 0),
            audio_completion_tokens=data.get("audio_completion_tokens", 0),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
        )
    
    @property
    def effective_prompt_tokens(self) -> int:
        """Tokens actually processed (excluding cache reads)"""
        return self.prompt_tokens - self.cache_read_tokens
    
    @property
    def billable_tokens(self) -> int:
        """
        Estimated billable tokens (provider-dependent).
        
        This is an approximation - actual billing varies by provider.
        Cached tokens are typically billed at reduced rates.
        """
        # Full price tokens
        full_price = self.effective_prompt_tokens + self.completion_tokens
        # Cached tokens at ~10% (typical discount)
        cached = self.cache_read_tokens * 0.1
        return int(full_price + cached)
    
    def __repr__(self) -> str:
        parts = [f"prompt={self.prompt_tokens}", f"completion={self.completion_tokens}"]
        if self.reasoning_tokens:
            parts.append(f"reasoning={self.reasoning_tokens}")
        if self.cache_read_tokens:
            parts.append(f"cached={self.cache_read_tokens}")
        return f"TokenUsage({', '.join(parts)}, total={self.total_tokens})"


@dataclass
class LLMInvocation:
    """
    Record of a single LLM invocation with full context.
    
    Used for detailed tracking and persistence.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Token usage
    usage: TokenUsage = field(default_factory=TokenUsage)

    # Model metadata (duplicated for convenience; canonical values still live in `usage`)
    model_provider: str = ""
    model_name: str = ""
    chat_id: Optional[str] = None
    
    # Context
    project: str = ""
    agent_name: str = ""
    operation: str = ""
    
    # Performance
    latency_ms: float = 0
    
    # Request metadata
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    # Response metadata
    finish_reason: Optional[str] = None
    system_fingerprint: Optional[str] = None
    
    # Custom tags for filtering/grouping
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization/persistence"""
        model_provider = self.model_provider or self.usage.provider
        model_name = self.model_name or self.usage.model
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "usage": self.usage.to_dict(),
            "project": self.project,
            "agent_name": self.agent_name,
            "operation": self.operation,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "finish_reason": self.finish_reason,
            "system_fingerprint": self.system_fingerprint,
            "model_provider": model_provider,
            "model_name": model_name,
            "chat_id": self.chat_id,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        """
        Human-readable multi-line representation.
        
        Focuses on the most important fields instead of dumping the full dict.
        """
        # Shorten ID for readability
        short_id = self.id[:8] if self.id else ""
        usage = self.usage
        lines = [
            f"LLMInvocation(id={short_id!r}, project={self.project!r}, agent={self.agent_name!r})",
            f"  model={self.model_provider or usage.provider!r}/{self.model_name or usage.model!r}",
            f"  tokens: total={usage.total_tokens}, prompt={usage.prompt_tokens}, completion={usage.completion_tokens}",
            f"  latency_ms={self.latency_ms:.1f}, operation={self.operation!r}, trace_id={self.trace_id!r}",
        ]
        if self.finish_reason:
            lines.append(f"  finish_reason={self.finish_reason!r}")
        if self.system_fingerprint:
            lines.append(f"  system_fingerprint={self.system_fingerprint!r}")
        if self.tags:
            lines.append(f"  tags={self.tags}")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMInvocation":
        """Create from dictionary"""
        usage = TokenUsage.from_dict(data.get("usage", {}))
        model_block = data.get("model", {}) if isinstance(data.get("model", {}), dict) else {}
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
            usage=usage,
            model_provider=(
                data.get("model_provider")
                or model_block.get("provider")
                or usage.provider
                or ""
            ),
            model_name=(
                data.get("model_name")
                or model_block.get("name")
                or usage.model
                or ""
            ),
            chat_id=data.get("chat_id") or data.get("model_id") or model_block.get("id"),
            project=data.get("project", ""),
            agent_name=data.get("agent_name", ""),
            operation=data.get("operation", ""),
            latency_ms=data.get("latency_ms", 0),
            request_id=data.get("request_id"),
            trace_id=data.get("trace_id"),
            finish_reason=data.get("finish_reason"),
            system_fingerprint=data.get("system_fingerprint"),
            tags=data.get("tags", {}),
        )


def build_llm_invocation(
    *,
    usage: TokenUsage,
    project: str,
    agent_name: str,
    operation: str,
    latency_ms: float,
    trace_id: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LLMInvocation:
    """
    Helper to construct a fully-populated LLMInvocation from usage + context.
    
    Centralizes how we map metadata fields (finish_reason, system_fingerprint, chat_id, etc.)
    so TokenTracker and the global handler stay in sync.
    """
    metadata = metadata or {}
    tags = tags or {}
    
    return LLMInvocation(
        timestamp=datetime.now(timezone.utc),
        usage=usage,
        model_provider=usage.provider,
        model_name=usage.model,
        chat_id=metadata.get("chat_id"),
        project=project,
        agent_name=agent_name,
        operation=operation,
        latency_ms=latency_ms,
        request_id=None,
        trace_id=trace_id,
        finish_reason=metadata.get("finish_reason"),
        system_fingerprint=metadata.get("system_fingerprint"),
        tags=dict(tags),
    )
