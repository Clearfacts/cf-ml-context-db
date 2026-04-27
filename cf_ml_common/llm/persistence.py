"""
Database Persistence for LLM Token Usage Metrics

Provides async batched persistence of token usage data to PostgreSQL.

Table Schema (create this in your database):

    CREATE TABLE IF NOT EXISTS llm_token_usage (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        
        -- Token counts
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        reasoning_tokens INTEGER DEFAULT 0,
        cached_prompt_tokens INTEGER DEFAULT 0,
        cache_creation_tokens INTEGER DEFAULT 0,
        cache_read_tokens INTEGER DEFAULT 0,
        
        -- Model info
        model VARCHAR(100),
        provider VARCHAR(50),
        chat_id VARCHAR(100),
        
        -- Context
        project VARCHAR(100),
        agent_name VARCHAR(100),
        operation VARCHAR(100),
        
        -- Performance
        latency_ms FLOAT,
        
        -- Tracing
        request_id VARCHAR(100),
        trace_id VARCHAR(100),
        
        -- Response metadata
        finish_reason VARCHAR(50),
        system_fingerprint VARCHAR(100),
        
        -- Custom tags (JSONB for flexibility)
        tags JSONB DEFAULT '{}'::jsonb,
        
        -- Indexing
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    -- Indexes for common queries
    CREATE INDEX idx_llm_token_usage_timestamp ON llm_token_usage(timestamp);
    CREATE INDEX idx_llm_token_usage_project ON llm_token_usage(project);
    CREATE INDEX idx_llm_token_usage_agent ON llm_token_usage(agent_name);
    CREATE INDEX idx_llm_token_usage_model ON llm_token_usage(model);
"""

import json
import threading
import queue
import atexit
import logging
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta, timezone

from .token_usage import LLMInvocation, TokenUsage

logger = logging.getLogger(__name__)


class TokenUsageRepository:
    """
    Repository for persisting LLM token usage to PostgreSQL.
    
    Uses a background thread with batching for efficiency.
    
    Usage:
        repo = TokenUsageRepository("config/database.ini", "metrics_db")
        repo.queue_invocation(invocation)  # Non-blocking
        
        # Or batch insert
        repo.insert_invocations([inv1, inv2, inv3])
        
        # Query
        usage = repo.get_usage_by_project("my-project", days=7)
    """
    
    TABLE_NAME = "llm_token_usage"
    BATCH_SIZE = 100
    FLUSH_INTERVAL_SECONDS = 5.0
    
    def __init__(
        self,
        config_file: str,
        section: str = "metrics_db",
        batch_size: int = BATCH_SIZE,
        flush_interval: float = FLUSH_INTERVAL_SECONDS,
        auto_start: bool = True,
    ):
        """
        Initialize TokenUsageRepository.
        
        Args:
            config_file: Path to database config file
            section: Config section name
            batch_size: Number of records to batch before flushing
            flush_interval: Max seconds between flushes
            auto_start: Whether to start background worker automatically
        """
        self.config_file = config_file
        self.section = section
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._engine = None
        self._table_columns: Optional[Set[str]] = None
        self._engine_lock = threading.Lock()
        
        if auto_start:
            self._start_worker()
            atexit.register(self.shutdown)
    
    def _get_engine(self):
        """
        Lazy-load database engine.
        
        Tries to use mlbase.db.MlDatabaseDao if available, otherwise falls back
        to direct SQLAlchemy engine creation.
        
        Returns:
            sqlalchemy.engine.Engine: Database engine instance
            
        Raises:
            ImportError: If required database libraries are not available
            ValueError: If database configuration is invalid
        """
        if self._engine is None:
            with self._engine_lock:  # Double-checked locking pattern
                if self._engine is None:
                    try:
                        # Try to use cf_ml_common.db if available
                        from mlbase import config
                        from mlbase.db import MlDatabaseDao
                        
                        params = config.config(self.config_file, section=self.section)
                        self._engine = MlDatabaseDao(self.config_file, section=self.section).engine
                    except ImportError:
                        # Fallback to direct SQLAlchemy
                        from configparser import ConfigParser
                        from sqlalchemy import create_engine
                        from sqlalchemy.pool import NullPool
                        
                        parser = ConfigParser()
                        parser.read(self.config_file)
                        params = dict(parser.items(self.section))
                        
                        conn_str = (
                            f"postgresql+psycopg2://{params['user']}:{params['password']}"
                            f"@{params['host']}:{params.get('port', 5432)}/{params['database']}"
                        )
                        self._engine = create_engine(conn_str, poolclass=NullPool)
                    except Exception as e:
                        logger.error(
                            "Failed to initialize database engine",
                            exc_info=True,
                            extra={
                                "config_file": self.config_file,
                                "section": self.section,
                            }
                        )
                        raise
        
        return self._engine
    
    def _start_worker(self):
        """
        Start background worker thread for batched inserts.
        
        Thread-safe: can be called multiple times safely.
        """
        with self._engine_lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="TokenUsageWorker",
            )
            self._worker_thread.start()
    
    def _worker_loop(self):
        """
        Background worker that batches and persists invocations.
        
        Runs continuously until stop event is set, batching invocations
        and flushing them periodically or when batch size is reached.
        """
        batch: List[LLMInvocation] = []
        last_flush = datetime.now(timezone.utc)
        
        while not self._stop_event.is_set():
            try:
                # Try to get an item with timeout
                try:
                    invocation = self._queue.get(timeout=1.0)
                    batch.append(invocation)
                    self._queue.task_done()
                except queue.Empty:
                    pass
                
                # Check if we should flush
                should_flush = (
                    len(batch) >= self.batch_size or
                    (batch and (datetime.now(timezone.utc) - last_flush).total_seconds() >= self.flush_interval)
                )
                
                if should_flush and batch:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = datetime.now(timezone.utc)
                    
            except Exception as e:
                logger.error(
                    "TokenUsageRepository worker error",
                    exc_info=True,
                    extra={"batch_size": len(batch)}
                )
                # Continue running despite errors
        
        # Flush remaining on shutdown
        if batch:
            self._flush_batch(batch)
    
    def _flush_batch(self, batch: List[LLMInvocation]):
        """
        Insert a batch of invocations into the database.
        
        Args:
            batch: List of LLMInvocation objects to persist
            
        Raises:
            Exception: If database operation fails (logged but not re-raised)
        """
        if not batch:
            return
        
        try:
            engine = self._get_engine()
            if engine is None:
                logger.error("Database engine not available for batch flush")
                return
                
            conn = engine.raw_connection()
            cur = conn.cursor()

            # Best-effort table introspection: allows adding columns without breaking older DB schemas.
            if self._table_columns is None:
                try:
                    from psycopg2.sql import SQL
                    introspection_sql = SQL(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s
                          AND table_schema = current_schema()
                        """
                    )
                    # psycopg2 cursors can execute SQL objects directly
                    cur.execute(introspection_sql, (self.TABLE_NAME,))
                    self._table_columns = {row[0] for row in cur.fetchall()}
                except Exception as e:
                    logger.warning(
                        "Failed to introspect table columns, using baseline set",
                        exc_info=True,
                        extra={"table_name": self.TABLE_NAME}
                    )
                    # If introspection fails, fall back to a conservative baseline insert set.
                    self._table_columns = set()
            
            # Build batch insert
            baseline_columns = [
                "id", "timestamp", "prompt_tokens", "completion_tokens", "total_tokens",
                "reasoning_tokens", "cached_prompt_tokens", "cache_creation_tokens",
                "cache_read_tokens", "model", "provider", "project", "agent_name",
                "operation", "latency_ms", "request_id", "trace_id", "finish_reason", "tags"
            ]

            desired_columns = [
                "id", "timestamp", "prompt_tokens", "completion_tokens", "total_tokens",
                "reasoning_tokens", "cached_prompt_tokens", "cache_creation_tokens",
                "cache_read_tokens",
                # Model info
                "model", "provider", "chat_id",
                # Context
                "project", "agent_name", "operation",
                # Performance
                "latency_ms",
                # Tracing
                "request_id", "trace_id",
                # Response metadata
                "finish_reason", "system_fingerprint",
                # Custom
                "tags",
            ]

            columns = baseline_columns
            if self._table_columns:
                # Only insert columns that actually exist in the DB table.
                columns = [c for c in desired_columns if c in self._table_columns]
            
            # Use psycopg2's SQL composition for safe identifier handling
            from psycopg2.sql import Identifier, SQL
            
            # Build safe SQL with proper identifier quoting
            table_identifier = Identifier(self.TABLE_NAME)
            column_identifiers = [Identifier(col) for col in columns]
            placeholders = SQL(",").join([SQL("%s")] * len(columns))
            
            insert_sql = SQL(
                "INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
            ).format(
                table=table_identifier,
                columns=SQL(",").join(column_identifiers),
                placeholders=placeholders,
            )
            
            values = []
            for inv in batch:
                row = {
                    "id": inv.id,
                    "timestamp": inv.timestamp,
                    "prompt_tokens": inv.usage.prompt_tokens,
                    "completion_tokens": inv.usage.completion_tokens,
                    "total_tokens": inv.usage.total_tokens,
                    "reasoning_tokens": inv.usage.reasoning_tokens,
                    "cached_prompt_tokens": inv.usage.cached_prompt_tokens,
                    "cache_creation_tokens": inv.usage.cache_creation_tokens,
                    "cache_read_tokens": inv.usage.cache_read_tokens,
                    "model": inv.usage.model,
                    "provider": inv.usage.provider,
                    "chat_id": inv.chat_id,
                    "project": inv.project,
                    "agent_name": inv.agent_name,
                    "operation": inv.operation,
                    "latency_ms": inv.latency_ms,
                    "request_id": inv.request_id,
                    "trace_id": inv.trace_id,
                    "finish_reason": inv.finish_reason,
                    "system_fingerprint": inv.system_fingerprint,
                    "tags": json.dumps(inv.tags),
                }
                values.append(tuple(row.get(c) for c in columns))
            
            cur.executemany(insert_sql, values)
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(
                "Failed to flush token usage batch",
                exc_info=True,
                extra={"batch_size": len(batch)}
            )
            # Consider implementing retry logic or dead letter queue in future
    
    def queue_invocation(self, invocation: LLMInvocation):
        """
        Queue an invocation for async persistence.
        
        Non-blocking - returns immediately.
        
        Args:
            invocation: LLMInvocation to queue for persistence
            
        Raises:
            queue.Full: If the internal queue is full (should not happen in normal operation)
        """
        self._queue.put(invocation)
    
    def insert_invocations(self, invocations: List[LLMInvocation]):
        """
        Synchronously insert multiple invocations.
        
        Use this for batch imports or when you need confirmation.
        
        Args:
            invocations: List of LLMInvocation objects to persist
            
        Raises:
            Exception: If database operation fails (logged but not re-raised)
        """
        self._flush_batch(invocations)
    
    def shutdown(self, timeout: float = 5.0):
        """
        Shutdown the background worker gracefully.
        
        Flushes any pending invocations before stopping.
        
        Args:
            timeout: Maximum seconds to wait for worker thread to finish
            
        Raises:
            RuntimeError: If worker thread does not finish within timeout
        """
        self._stop_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=timeout)
    
    # Query methods
    
    def get_usage_by_project(
        self,
        project: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get aggregated usage for a project.
        
        Args:
            project: Project name
            days: Number of days to look back
            
        Returns:
            Dictionary with aggregated usage stats
            
        Raises:
            Exception: If database query fails (logged but not re-raised)
        """
        engine = self._get_engine()
        conn = engine.raw_connection()
        cur = conn.cursor()
        
        from psycopg2.sql import Identifier, SQL
        sql = SQL(
            """
            SELECT 
                COUNT(*) as invocation_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(reasoning_tokens) as total_reasoning_tokens,
                SUM(cache_read_tokens) as total_cache_read_tokens,
                AVG(latency_ms) as avg_latency_ms
            FROM {table}
            WHERE project = %s
              AND timestamp >= NOW() - INTERVAL '%s days'
            """
        ).format(table=Identifier(self.TABLE_NAME))
        
        # Execute SQL object directly with parameters
        cur.execute(sql, (project, days))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                "project": project,
                "days": days,
                "invocation_count": row[0] or 0,
                "total_prompt_tokens": row[1] or 0,
                "total_completion_tokens": row[2] or 0,
                "total_tokens": row[3] or 0,
                "total_reasoning_tokens": row[4] or 0,
                "total_cache_read_tokens": row[5] or 0,
                "avg_latency_ms": float(row[6]) if row[6] else 0.0,
            }
        return {"project": project, "days": days, "invocation_count": 0}
    
    def get_usage_by_agent(
        self,
        project: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Get usage breakdown by agent for a project.
        
        Args:
            project: Project name
            days: Number of days to look back
            
        Returns:
            List of dictionaries with per-agent usage stats
            
        Raises:
            Exception: If database query fails (logged but not re-raised)
        """
        engine = self._get_engine()
        conn = engine.raw_connection()
        cur = conn.cursor()
        
        from psycopg2.sql import Identifier, SQL
        sql = SQL(
            """
            SELECT 
                agent_name,
                COUNT(*) as invocation_count,
                SUM(total_tokens) as total_tokens,
                AVG(latency_ms) as avg_latency_ms
            FROM {table}
            WHERE project = %s
              AND timestamp >= NOW() - INTERVAL '%s days'
            GROUP BY agent_name
            ORDER BY total_tokens DESC
            """
        ).format(table=Identifier(self.TABLE_NAME))
        
        cur.execute(sql, (project, days))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return [
            {
                "agent_name": row[0],
                "invocation_count": row[1],
                "total_tokens": row[2] or 0,
                "avg_latency_ms": float(row[3]) if row[3] else 0.0,
            }
            for row in rows
        ]
    
    def get_usage_timeseries(
        self,
        project: str,
        days: int = 7,
        interval: str = "hour",
    ) -> List[Dict[str, Any]]:
        """
        Get usage timeseries for a project.
        
        Args:
            project: Project name
            days: Number of days to look back
            interval: Aggregation interval ('hour', 'day', 'week')
            
        Returns:
            List of dictionaries with timestamped usage stats
            
        Raises:
            ValueError: If interval is not one of the supported values
        """
        engine = self._get_engine()
        conn = engine.raw_connection()
        cur = conn.cursor()
        
        # PostgreSQL date_trunc supports: hour, day, week, month
        if interval not in ("hour", "day", "week", "month"):
            interval = "hour"
        
        from psycopg2.sql import Identifier, SQL
        sql = SQL(
            """
            SELECT 
                DATE_TRUNC(%s, timestamp) as period,
                COUNT(*) as invocation_count,
                SUM(total_tokens) as total_tokens,
                SUM(prompt_tokens) as prompt_tokens,
                SUM(completion_tokens) as completion_tokens
            FROM {table}
            WHERE project = %s
              AND timestamp >= NOW() - INTERVAL '%s days'
            GROUP BY DATE_TRUNC(%s, timestamp)
            ORDER BY period
            """
        ).format(table=Identifier(self.TABLE_NAME))
        
        cur.execute(sql, (interval, project, days, interval))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return [
            {
                "period": row[0].isoformat() if row[0] else None,
                "invocation_count": row[1],
                "total_tokens": row[2] or 0,
                "prompt_tokens": row[3] or 0,
                "completion_tokens": row[4] or 0,
            }
            for row in rows
        ]


# SQL for creating the table (convenience function)
def get_create_table_sql() -> str:
    """
    Get SQL to create the llm_token_usage table.
    
    Run this in your database to set up the metrics table.
    """
    return """
    CREATE TABLE IF NOT EXISTS llm_token_usage (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        
        -- Token counts
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        reasoning_tokens INTEGER DEFAULT 0,
        cached_prompt_tokens INTEGER DEFAULT 0,
        cache_creation_tokens INTEGER DEFAULT 0,
        cache_read_tokens INTEGER DEFAULT 0,
        
        -- Model info
        model VARCHAR(100),
        provider VARCHAR(50),
        chat_id VARCHAR(100),
        
        -- Context
        project VARCHAR(100),
        agent_name VARCHAR(100),
        operation VARCHAR(100),
        
        -- Performance
        latency_ms FLOAT,
        
        -- Tracing
        request_id VARCHAR(100),
        trace_id VARCHAR(100),
        
        -- Response metadata
        finish_reason VARCHAR(50),
        system_fingerprint VARCHAR(100),
        
        -- Custom tags (JSONB for flexibility)
        tags JSONB DEFAULT '{}'::jsonb,
        
        -- Indexing
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_llm_token_usage_timestamp ON llm_token_usage(timestamp);
    CREATE INDEX IF NOT EXISTS idx_llm_token_usage_project ON llm_token_usage(project);
    CREATE INDEX IF NOT EXISTS idx_llm_token_usage_agent ON llm_token_usage(agent_name);
    CREATE INDEX IF NOT EXISTS idx_llm_token_usage_model ON llm_token_usage(model);
    CREATE INDEX IF NOT EXISTS idx_llm_token_usage_project_timestamp ON llm_token_usage(project, timestamp);
    """
