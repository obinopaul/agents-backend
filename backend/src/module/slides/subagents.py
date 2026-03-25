"""Claude Code module subagents.

Defines the subagents available to this module's agent graph.
Each module can have its own subagents tailored to its specific use case.

The subagents are passed to create_deepagent() which will:
1. If background_tasks enabled: inject ToolCallCounterMiddleware into each subagent
2. Pass them to SubAgentMiddleware for spawning during agent execution
"""
import os
from datetime import datetime
from typing import Any, List, Optional

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger(__name__)

# Initialize Jinja2 environment for subagent prompts
# Points to the 'prompts' subdirectory in this module
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
    """Load and render a subagent prompt template.
    
    Loads a markdown template from the module's prompts directory,
    renders it with Jinja2 (including CURRENT_TIME), and returns
    the rendered string.
    
    Args:
        prompt_name: Name of the prompt file (without .md extension).
            Must match a file in backend/src/module/claude_code/prompts/
        
    Returns:
        The rendered prompt string ready to use as a system prompt.
        
    Raises:
        ValueError: If the template cannot be loaded.
    
    Example:
        >>> prompt = get_subagent_prompt("general_purpose")
        >>> # Returns rendered markdown with current time
    """
    try:
        template = _jinja_env.get_template(f"{prompt_name}.md")
        rendered = template.render(
            CURRENT_TIME=datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        )
        logger.debug(f"Loaded subagent prompt: {prompt_name}")
        return rendered
    except Exception as e:
        logger.error(f"Failed to load subagent prompt '{prompt_name}': {e}")
        # Return a basic fallback prompt
        return f"You are a {prompt_name} subagent. Execute the task diligently."


def get_subagents(
    model: Any = None,
    middleware: Optional[List[Any]] = None,
) -> List[Any]:
    """Get the subagents for the Claude Code module.
    
    Args:
        model: Optional default model for subagents. If not provided,
            SubAgentMiddleware will use its default_model.
        middleware: Optional list of middleware to add to each subagent.
            Note: ToolCallCounterMiddleware will be prepended automatically
            by build_deep_middleware() if background tasks are enabled.
        
    Returns:
        List of SubAgent instances configured for Claude Code tasks.
    """
    if not SUBAGENT_AVAILABLE or SubAgent is None:
        logger.debug("SubAgent not available - returning empty list")
        return []

    # Base middleware for all subagents (can be extended per-subagent)
    base_middleware = middleware if middleware else []
    
    subagents = [
        # 1. General Purpose Assistant
        SubAgent(
            name="general_purpose",
            description="A general purpose assistant for handling various tasks.",
            system_prompt=get_subagent_prompt("general_purpose"),
            middleware=base_middleware.copy(),
            model=model,
        ),
        
        # 2. Research Specialist
        SubAgent(
            name="research",
            description="Specialized in research and information gathering.",
            system_prompt=get_subagent_prompt("research"),
            middleware=base_middleware.copy(),
            model=model,
        ),
    ]
    
    logger.debug(f"Created {len(subagents)} subagent(s) for Claude Code module")
    return subagents
