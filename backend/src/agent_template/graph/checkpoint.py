# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Checkpoint configuration for the multi-agent template.

Provides utilities to set up checkpointers for graph persistence.
"""

import logging
import os
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


def get_memory_checkpointer() -> BaseCheckpointSaver:
    """
    Get an in-memory checkpointer.
    
    Suitable for development and testing.
    
    Returns:
        MemorySaver instance
    """
    return MemorySaver()


def get_postgres_checkpointer(
    connection_string: Optional[str] = None
) -> Optional[BaseCheckpointSaver]:
    """
    Get a PostgreSQL checkpointer for persistent storage.
    
    Args:
        connection_string: PostgreSQL connection string.
            If None, reads from LANGGRAPH_CHECKPOINT_DB_URL env var.
            
    Returns:
        PostgresSaver instance or None if not configured
    """
    db_url = connection_string or os.getenv("LANGGRAPH_CHECKPOINT_DB_URL")
    
    if not db_url:
        logger.warning("No database URL configured for PostgreSQL checkpointer")
        return None
    
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        
        checkpointer = PostgresSaver.from_conn_string(db_url)
        logger.info("PostgreSQL checkpointer configured")
        return checkpointer
        
    except ImportError:
        logger.warning("langgraph-checkpoint-postgres not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to configure PostgreSQL checkpointer: {e}")
        return None


def get_checkpointer(
    use_postgres: bool = False,
    connection_string: Optional[str] = None,
) -> BaseCheckpointSaver:
    """
    Get the appropriate checkpointer based on configuration.
    
    Args:
        use_postgres: Whether to use PostgreSQL (production)
        connection_string: Optional database connection string
        
    Returns:
        Checkpointer instance
    """
    if use_postgres:
        checkpointer = get_postgres_checkpointer(connection_string)
        if checkpointer:
            return checkpointer
        logger.warning("Falling back to memory checkpointer")
    
    return get_memory_checkpointer()
