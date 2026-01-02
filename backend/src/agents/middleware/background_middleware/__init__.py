"""Background subagent execution middleware.

This module provides async/background execution for subagent tasks,
allowing the main agent to continue working while subagents run.
"""

from backend.src.agents.middleware.background_middleware.counter import ToolCallCounterMiddleware
from backend.src.agents.middleware.background_middleware.middleware import (
    BackgroundSubagentMiddleware,
    current_background_task_id,
)
from backend.src.agents.middleware.background_middleware.orchestrator import BackgroundSubagentOrchestrator
from backend.src.agents.middleware.background_middleware.registry import BackgroundTask, BackgroundTaskRegistry
from backend.src.agents.middleware.background_middleware.tools import (
    create_background_task_tool,
    create_task_progress_tool,
    create_wait_tool,
)

__all__ = [
    "BackgroundSubagentMiddleware",
    "BackgroundSubagentOrchestrator",
    "BackgroundTask",
    "BackgroundTaskRegistry",
    "ToolCallCounterMiddleware",
    "create_background_task_tool",
    "create_task_progress_tool",
    "create_wait_tool",
    "current_background_task_id",
]
