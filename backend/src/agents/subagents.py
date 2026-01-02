"""Subagent configuration and factory.

This module defines the subagents available to the system and handles their configuration,
including dependency injection for middleware like ToolCallCounterMiddleware.
"""

from typing import Any, List, Optional
import structlog

from backend.src.agents.middleware.background_middleware import (
    ToolCallCounterMiddleware,
    BackgroundTaskRegistry,
)

logger = structlog.get_logger(__name__)

# Try to import SubAgent from deepagents package
try:
    from deepagents.middleware.subagents import SubAgent
except ImportError:
    SubAgent = None
    logger.warning("deepagents package not found. Subagents will not be available.")


def create_default_subagents(
    registry: Optional[BackgroundTaskRegistry] = None,
    model: Any = None,
) -> List[Any]:
    """Create default subagents with optional tool call tracking.
    
    Args:
        registry: Optional BackgroundTaskRegistry. If provided, ToolCallCounterMiddleware
            will be created and injected into subagents to track their tool usage.
        model: Optional default model to use for subagents.

    Returns:
        List of configured SubAgent instances.
    """
    if SubAgent is None:
        return []

    # Create middleware list for subagents
    middleware = []
    
    # If registry is provided, inject ToolCallCounterMiddleware
    # This is what allows 'task_progress' to show tool call counts!
    if registry:
        counter = ToolCallCounterMiddleware(registry)
        middleware.append(counter)
        logger.debug("Injected ToolCallCounterMiddleware into subagents")

    # Define subagents
    # 1. General Assistant: Robust placeholder/default
    general_subagent = SubAgent(
        name="general_purpose",
        description="A general purpose assistant for handling various tasks.",
        system_prompt=(
            "You are a helpful general assistant subagent. "
            "Execute the task provided in the description diligently. "
            "Use available tools to complete the work."
        ),
        # Pass the middleware list (includes counter if registry provided)
        middleware=middleware, 
        model=model, 
    )
    
    # 2. Researcher: Specialized for information gathering (example)
    researcher_subagent = SubAgent(
        name="research",
        description="Specialized in research and information gathering.",
        system_prompt=(
            "You are a research specialist. "
            "Focus on gathering accurate information, citing sources, "
            "and synthesizing findings."
        ),
        middleware=middleware,
        model=model,
    )

    return [general_subagent, researcher_subagent]
