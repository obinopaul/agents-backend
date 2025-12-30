# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Checkpoint configuration for the multi-agent template.

This module re-exports the centralized PostgreSQL checkpointer
for use by the agent template.

PostgreSQL is the ONLY supported backend - there is no in-memory fallback.
"""

from backend.src.graph.checkpointer import (
    checkpointer_manager,
    get_checkpointer,
    get_store,
    initialize_checkpointer,
    shutdown_checkpointer,
    CheckpointerNotConfiguredError,
    CheckpointerNotInitializedError,
)

__all__ = [
    "checkpointer_manager",
    "get_checkpointer",
    "get_store",
    "initialize_checkpointer",
    "shutdown_checkpointer",
    "CheckpointerNotConfiguredError",
    "CheckpointerNotInitializedError",
]
