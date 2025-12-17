"""Background subagent execution middleware.

This module provides async/background execution for subagent tasks,
allowing the main agent to continue working while subagents run.
"""

from backend.src.agents.middleware.background.counter import ToolCallCounterMiddleware
from backend.src.agents.middleware.background.middleware import (
    BackgroundSubagentMiddleware,
    current_background_task_id,
)
from backend.src.agents.middleware.background.orchestrator import BackgroundSubagentOrchestrator
from backend.src.agents.middleware.background.registry import BackgroundTask, BackgroundTaskRegistry
from backend.src.agents.middleware.background.tools import (
    create_task_progress_tool,
    create_wait_tool,
)

__all__ = [
    "BackgroundSubagentMiddleware",
    "BackgroundSubagentOrchestrator",
    "BackgroundTask",
    "BackgroundTaskRegistry",
    "ToolCallCounterMiddleware",
    "create_task_progress_tool",
    "create_wait_tool",
    "current_background_task_id",
]
