"""Executor subagents.

Defines the subagents available to the Executor node.
The debugger is a subagent that helps fix errors during execution.
"""
import os
from datetime import datetime
from typing import Any, List, Optional

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger(__name__)

# Initialize Jinja2 environment for subagent prompts
_prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
_jinja_env = Environment(
    loader=FileSystemLoader(_prompts_dir),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Try to import SubAgent from deepagents package
try:
    from deepagents.middleware.subagents import SubAgent
    SUBAGENT_AVAILABLE = True
except ImportError:
    SubAgent = None
    SUBAGENT_AVAILABLE = False
    logger.warning("deepagents package not found. Subagents will not be available.")


def get_subagent_prompt(prompt_name: str) -> str:
    """Load and render a subagent prompt template."""
    try:
        template = _jinja_env.get_template(f"{prompt_name}.md")
        rendered = template.render(
            CURRENT_TIME=datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        )
        logger.debug(f"Loaded subagent prompt: {prompt_name}")
        return rendered
    except Exception as e:
        logger.error(f"Failed to load subagent prompt '{prompt_name}': {e}")
        return f"You are a {prompt_name} subagent. Execute the task diligently."


def get_subagents(
    model: Any = None,
    middleware: Optional[List[Any]] = None,
) -> List[Any]:
    """Get the subagents for Executor node.
    
    Args:
        model: Optional default model for subagents.
        middleware: Optional list of middleware to add to each subagent.
        
    Returns:
        List of SubAgent instances configured for Executor tasks.
    """
    if not SUBAGENT_AVAILABLE or SubAgent is None:
        logger.debug("SubAgent not available - returning empty list")
        return []

    base_middleware = middleware if middleware else []
    
    subagents = [
        # Debugger Subagent - fixes errors during execution
        SubAgent(
            name="debugger",
            description="Debugs and fixes errors in code. Use when execution fails or tests don't pass. Has access to all files, error logs, and can modify code to fix issues.",
            system_prompt=get_subagent_prompt("debugger"),
            middleware=base_middleware.copy(),
            model=model,
        ),
    ]
    
    logger.debug(f"Created {len(subagents)} subagent(s)")
    return subagents
