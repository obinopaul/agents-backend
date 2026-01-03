# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Centralized LangGraph PostgreSQL Checkpointer and Store.

This module provides production-ready checkpointing AND long-term memory store
for LangGraph using PostgreSQL for persistent storage. PostgreSQL is the 
ONLY supported backend - there is no in-memory fallback.

Features:
- Shared async connection pool (managed by FastAPI lifespan)
- Checkpointer: Persists graph state per thread (conversation history)
- Store: Persists key-value data across threads (long-term memory)
- Automatic table creation (can be disabled in production with Alembic)
- Thread-safe singleton pattern
- Proper connection pool lifecycle management
- TCP keepalive for long-running agent workflows

Usage:
    # In FastAPI lifespan (registrar.py):
    await checkpointer_manager.initialize()
    yield
    await checkpointer_manager.shutdown()
    
    # In agent/chat endpoints:
    async with checkpointer_manager.get_graph_with_checkpointer(graph, thread_id) as g:
        async for event in g.astream_events(...):
            ...
    
    # Store is automatically injected into the graph for middleware access

Configuration (.env):
    LANGGRAPH_CHECKPOINT_ENABLED=true
    LANGGRAPH_CHECKPOINT_DB_URL=postgresql://user:pass@localhost:5432/dbname
    LANGGRAPH_CHECKPOINT_POOL_MIN=2
    LANGGRAPH_CHECKPOINT_POOL_MAX=10
    LANGGRAPH_CHECKPOINT_POOL_TIMEOUT=60

References:
    - LangGraph Checkpointing: https://langchain-ai.github.io/langgraph/reference/checkpoints/
    - LangGraph Store: https://langchain-ai.github.io/langgraph/reference/store/
    - AsyncPostgresSaver: https://langchain-ai.github.io/langgraph/reference/checkpoints/#asyncpostgressaver
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore  # Fallback if PostgreSQL store fails

from backend.core.conf import settings

logger = logging.getLogger(__name__)


class CheckpointerNotConfiguredError(Exception):
    """Raised when PostgreSQL checkpointer is not properly configured."""
    pass


class CheckpointerNotInitializedError(Exception):
    """Raised when checkpointer is accessed before initialization."""
    pass


class PostgresCheckpointerManager:
    """
    Manages a shared PostgreSQL connection pool for LangGraph checkpointing.
    
    This class implements the singleton pattern and manages the lifecycle
    of the async connection pool. It provides context managers for safely
    acquiring checkpointers for graph execution.
    
    PostgreSQL is REQUIRED - there is no in-memory fallback. This ensures
    that agent state is always persisted and survives restarts.
    
    Attributes:
        _pool: The shared AsyncConnectionPool instance
        _checkpointer: The shared AsyncPostgresSaver instance
        _store: The shared PostgreSQL store for cross-thread long-term memory
        _initialized: Whether the manager has been initialized
    """
    
    def __init__(self):
        self._pool: Optional[Any] = None  # AsyncConnectionPool
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._store: Optional[BaseStore] = None  # Initialized to PostgreSQL store
        self._initialized: bool = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if PostgreSQL checkpointing is enabled and configured."""
        return (
            settings.LANGGRAPH_CHECKPOINT_ENABLED 
            and bool(settings.LANGGRAPH_CHECKPOINT_DB_URL)
            and settings.LANGGRAPH_CHECKPOINT_DB_URL.startswith("postgresql://")
        )
    
    @property
    def is_initialized(self) -> bool:
        """Check if the manager has been initialized."""
        return self._initialized
    
    @property
    def store(self) -> BaseStore:
        """Get the shared memory store for cross-thread data.
        
        Returns the PostgreSQL-backed store for persistent long-term memory.
        Falls back to InMemoryStore if not initialized.
        """
        if self._store is None:
            logger.warning("Store accessed before initialization, using InMemoryStore fallback")
            return InMemoryStore()
        return self._store
    
    def _validate_configuration(self) -> None:
        """Validate that PostgreSQL is properly configured."""
        if not settings.LANGGRAPH_CHECKPOINT_ENABLED:
            raise CheckpointerNotConfiguredError(
                "PostgreSQL checkpointing is required but not enabled. "
                "Set LANGGRAPH_CHECKPOINT_ENABLED=true in your .env file."
            )
        
        if not settings.LANGGRAPH_CHECKPOINT_DB_URL:
            raise CheckpointerNotConfiguredError(
                "PostgreSQL checkpointing is enabled but no database URL provided. "
                "Set LANGGRAPH_CHECKPOINT_DB_URL=postgresql://user:pass@host:port/dbname in your .env file."
            )
        
        if not settings.LANGGRAPH_CHECKPOINT_DB_URL.startswith("postgresql://"):
            raise CheckpointerNotConfiguredError(
                f"Invalid database URL scheme. Expected 'postgresql://', got: "
                f"'{settings.LANGGRAPH_CHECKPOINT_DB_URL[:20]}...'. "
                "Only PostgreSQL is supported for checkpointing."
            )

    async def _setup_checkpoint_tables(self) -> None:
        """
        Create LangGraph checkpoint tables if they don't exist.
        
        This is a custom implementation that works with Supabase connection poolers
        by avoiding CREATE INDEX CONCURRENTLY (which requires a direct connection)
        and executing statements one at a time (required for pgbouncer).
        
        Tables created:
        - checkpoint_migrations: Tracks applied migrations
        - checkpoints: Main checkpoint storage
        - checkpoint_blobs: Binary data storage
        - checkpoint_writes: Write-ahead log
        """
        # SQL statements - must be executed one at a time for pgbouncer compatibility
        statements = [
            # Migration tracking table
            """CREATE TABLE IF NOT EXISTS checkpoint_migrations (
                v INTEGER PRIMARY KEY
            )""",
            
            # Main checkpoints table
            """CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}',
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            )""",
            
            # Checkpoint blobs table
            """CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                blob BYTEA,
                PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
            )""",
            
            # Checkpoint writes table
            """CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                blob BYTEA NOT NULL,
                task_path TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            )""",
            
            # Indexes (without CONCURRENTLY for connection pooler compatibility)
            "CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id)",
            "CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id)",
            "CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id)",
        ]
        
        # Migration version inserts - must be done one at a time
        migration_inserts = [
            "INSERT INTO checkpoint_migrations (v) VALUES (1) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (2) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (3) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (4) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (5) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (6) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (7) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (8) ON CONFLICT (v) DO NOTHING",
            "INSERT INTO checkpoint_migrations (v) VALUES (9) ON CONFLICT (v) DO NOTHING",
        ]
        
        try:
            async with self._pool.connection() as conn:
                # Disable prepared statements for pgbouncer/Supabase compatibility
                conn.prepare_threshold = None
                
                async with conn.cursor() as cur:
                    # Execute each statement separately (required for pgbouncer)
                    for stmt in statements:
                        try:
                            await cur.execute(stmt)
                        except Exception as e:
                            # Only ignore "already exists" errors
                            if "already exists" in str(e).lower():
                                logger.debug(f"Table/Index already exists: {e}")
                            else:
                                logger.error(f"Failed to execute creation statement: {stmt[:50]}... Error: {e}")
                                raise e
                    
                    # Insert migration versions
                    for insert in migration_inserts:
                        try:
                            await cur.execute(insert)
                        except Exception:
                            pass  # Ignore conflicts
                            
            logger.info("✅ LangGraph checkpoint tables created/verified")
        except Exception as e:
            logger.error(f"Failed to setup checkpoint tables: {e}")
            raise

    async def _setup_store_tables(self) -> None:
        """
        Create LangGraph store tables if they don't exist.
        
        This creates the necessary tables for persistent key-value storage
        that works across threads and survives server restarts.
        
        Tables created:
        - store: Key-value storage with namespace prefix for long-term memory
        """
        statements = [
            # Store table for key-value pairs with namespace
            """CREATE TABLE IF NOT EXISTS store (
                prefix TEXT NOT NULL,
                key TEXT NOT NULL,
                value JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (prefix, key)
            )""",
            
            # Index for efficient namespace queries
            "CREATE INDEX IF NOT EXISTS store_prefix_idx ON store(prefix)",
        ]
        
        try:
            async with self._pool.connection() as conn:
                # Disable prepared statements for pgbouncer/Supabase compatibility
                conn.prepare_threshold = None
                
                async with conn.cursor() as cur:
                    for stmt in statements:
                        try:
                            await cur.execute(stmt)
                        except Exception as e:
                            if "already exists" in str(e).lower():
                                logger.debug(f"Store table/index already exists: {e}")
                            else:
                                logger.error(f"Failed to execute store statement: {stmt[:50]}... Error: {e}")
                                raise
                                
            logger.info("✅ LangGraph store tables created/verified")
        except Exception as e:
            logger.error(f"Failed to setup store tables: {e}")
            raise

    async def initialize(self) -> None:
        """
        Initialize the PostgreSQL connection pool and checkpointer.
        
        This should be called during FastAPI application startup (lifespan).
        
        Raises:
            CheckpointerNotConfiguredError: If PostgreSQL is not properly configured
            Exception: If connection to PostgreSQL fails
        """
        if self._initialized:
            logger.debug("Checkpointer already initialized")
            return
        
        # Validate configuration - PostgreSQL is mandatory
        self._validate_configuration()
        
        try:
            # Import here to provide clear error if psycopg is not installed
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            
            db_url = settings.LANGGRAPH_CHECKPOINT_DB_URL
            
            # Connection pool configuration optimized for long-running agent workflows
            # TCP keepalive settings help maintain connection health during extended operations
            connection_kwargs = {
                "autocommit": True,
                # TCP keepalive settings to prevent idle disconnects
                "keepalives": 1,
                "keepalives_idle": 30,      # seconds before starting keepalives
                "keepalives_interval": 10,  # seconds between keepalives
                "keepalives_count": 5,      # number of lost keepalives before disconnect
            }
            
            # Configure callback to disable prepared statements on each connection
            # This is REQUIRED for Supabase/pgbouncer connection poolers
            async def configure_connection(conn):
                conn.prepare_threshold = None
            
            # Pool settings from configuration
            pool_min_size = settings.LANGGRAPH_CHECKPOINT_POOL_MIN
            pool_max_size = settings.LANGGRAPH_CHECKPOINT_POOL_MAX
            pool_timeout = settings.LANGGRAPH_CHECKPOINT_POOL_TIMEOUT
            
            logger.info(
                f"Initializing PostgreSQL checkpointer pool: "
                f"min={pool_min_size}, max={pool_max_size}, timeout={pool_timeout}s"
            )
            
            # Create the connection pool with configure callback
            self._pool = AsyncConnectionPool(
                db_url,
                min_size=pool_min_size,
                max_size=pool_max_size,
                timeout=pool_timeout,
                kwargs=connection_kwargs,
                configure=configure_connection,  # Disable prepared statements on each connection
                open=False,  # Don't open yet, we'll do it explicitly
            )
            
            # Open the pool and test the connection
            await self._pool.open()
            await self._pool.check()
            
            # Create the checkpointer
            self._checkpointer = AsyncPostgresSaver(self._pool)
            
            # Always setup tables using our custom method that works with connection poolers
            # This is idempotent (safe to run multiple times) and handles Supabase pooler limitations
            logger.info("Setting up LangGraph checkpoint tables...")
            await self._setup_checkpoint_tables()
            
            # Create and initialize the PostgreSQL store for long-term memory
            # Uses the same connection pool as the checkpointer
            try:
                from langgraph.store.postgres.aio import AsyncPostgresStore
                self._store = AsyncPostgresStore(self._pool)
                await self._setup_store_tables()
                logger.info("✅ PostgreSQL store initialized successfully")
            except ImportError:
                logger.warning(
                    "langgraph.store.postgres not available, using InMemoryStore. "
                    "Long-term memory will not persist across restarts. "
                    "Install with: pip install langgraph-checkpoint-postgres"
                )
                self._store = InMemoryStore()
            except Exception as store_error:
                logger.warning(
                    f"Failed to initialize PostgreSQL store, using InMemoryStore: {store_error}. "
                    "Long-term memory will not persist across restarts."
                )
                self._store = InMemoryStore()
            
            self._initialized = True
            logger.info("✅ PostgreSQL checkpointer initialized successfully")

            
        except ImportError as e:
            raise CheckpointerNotConfiguredError(
                f"Required package not installed: {e}. "
                "Install with: pip install langgraph-checkpoint-postgres psycopg-pool"
            ) from e
        except Exception as e:
            # Cleanup any partial initialization
            if self._pool is not None:
                try:
                    await self._pool.close()
                except Exception:
                    pass
                self._pool = None
            
            self._checkpointer = None
            
            logger.exception(f"Failed to initialize PostgreSQL checkpointer: {e}")
            raise CheckpointerNotConfiguredError(
                f"Failed to connect to PostgreSQL: {e}. "
                "Check your LANGGRAPH_CHECKPOINT_DB_URL and ensure PostgreSQL is running."
            ) from e
    
    async def shutdown(self) -> None:
        """
        Shutdown the connection pool and cleanup resources.
        
        This should be called during FastAPI application shutdown (lifespan).
        """
        if not self._initialized:
            return
        
        if self._pool is not None:
            try:
                logger.info("Closing PostgreSQL checkpointer connection pool...")
                await self._pool.close()
                logger.info("PostgreSQL checkpointer connection pool closed")
            except Exception as e:
                logger.error(f"Error closing checkpointer pool: {e}")
            finally:
                self._pool = None
                self._checkpointer = None
                self._store = None
        
        self._initialized = False
    
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        Get the PostgreSQL checkpointer instance.
        
        Returns:
            The AsyncPostgresSaver instance
            
        Raises:
            CheckpointerNotInitializedError: If not initialized
        """
        if not self._initialized:
            raise CheckpointerNotInitializedError(
                "Checkpointer accessed before initialization. "
                "Ensure checkpointer_manager.initialize() is called at startup."
            )
        
        if self._checkpointer is None:
            raise CheckpointerNotInitializedError(
                "Checkpointer is None after initialization. This should not happen."
            )
        
        return self._checkpointer
    
    @asynccontextmanager
    async def get_graph_with_checkpointer(
        self, 
        graph: CompiledStateGraph,
        thread_id: Optional[str] = None,
    ):
        """
        Context manager that configures a graph with the PostgreSQL checkpointer.
        
        This method safely assigns the checkpointer and store to the graph
        for the duration of the context. The graph's original checkpointer
        is restored after the context exits.
        
        Args:
            graph: The compiled LangGraph state graph
            thread_id: Optional thread ID for logging
            
        Yields:
            The configured graph with PostgreSQL checkpointer
            
        Raises:
            CheckpointerNotInitializedError: If checkpointer is not initialized
            
        Example:
            async with checkpointer_manager.get_graph_with_checkpointer(graph, thread_id) as g:
                async for event in g.astream_events(input, config):
                    yield event
        """
        if not self._initialized:
            await self.initialize()
        
        checkpointer = self.get_checkpointer()
        
        # Store original values
        original_checkpointer = graph.checkpointer
        original_store = graph.store
        
        try:
            # Configure the graph with PostgreSQL checkpointer
            graph.checkpointer = checkpointer
            graph.store = self._store
            
            logger.debug(f"[{thread_id or 'unknown'}] Using PostgreSQL checkpointer")
            
            yield graph
            
        except Exception as e:
            # Log PostgreSQL connection errors
            try:
                import psycopg
                if isinstance(e, psycopg.OperationalError):
                    logger.exception(
                        f"[{thread_id or 'unknown'}] PostgreSQL connection error during graph execution"
                    )
            except ImportError:
                pass
            raise
            
        finally:
            # Restore original configuration
            graph.checkpointer = original_checkpointer
            graph.store = original_store
    
    async def health_check(self) -> dict:
        """
        Check the health of the PostgreSQL checkpointer, store, and connection pool.
        
        Returns:
            dict with status information including pool statistics and store type
        """
        # Determine store type
        store_type = "not_initialized"
        if self._store is not None:
            store_type = type(self._store).__name__
        
        result = {
            "enabled": self.is_enabled,
            "initialized": self._initialized,
            "type": "postgresql",
            "status": "healthy" if self._initialized and self._checkpointer else "unhealthy",
            "pool_status": None,
            "store_type": store_type,
            "store_persistent": store_type == "AsyncPostgresStore",
        }
        
        if self._pool is not None:
            try:
                stats = self._pool.get_stats()
                result["pool_status"] = {
                    "pool_min": stats.get("pool_min", 0),
                    "pool_max": stats.get("pool_max", 0),
                    "pool_size": stats.get("pool_size", 0),
                    "pool_available": stats.get("pool_available", 0),
                    "requests_waiting": stats.get("requests_waiting", 0),
                }
            except Exception as e:
                result["pool_status"] = {"error": str(e)}
                result["status"] = "degraded"
        
        return result


# Global singleton instance
checkpointer_manager = PostgresCheckpointerManager()


# =============================================================================
# Convenience Functions
# =============================================================================

async def initialize_checkpointer() -> None:
    """Initialize the global checkpointer manager."""
    await checkpointer_manager.initialize()


async def shutdown_checkpointer() -> None:
    """Shutdown the global checkpointer manager."""
    await checkpointer_manager.shutdown()


def get_checkpointer() -> BaseCheckpointSaver:
    """Get the PostgreSQL checkpointer instance."""
    return checkpointer_manager.get_checkpointer()


def get_store() -> BaseStore:
    """Get the shared memory store."""
    return checkpointer_manager.store
