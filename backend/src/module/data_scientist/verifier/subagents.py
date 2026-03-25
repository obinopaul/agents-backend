"""
DS* Verifier Subagents.

This module defines subagents for the verifier node:
- Reviewer: Performs detailed code review
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from backend.src.llms.llm import get_llm

# Try to import SubAgent from deepagents
try:
    from deepagents.middleware.subagents import SubAgent
    SUBAGENT_AVAILABLE = True
except ImportError:
    SUBAGENT_AVAILABLE = False
    SubAgent = None

logger = logging.getLogger(__name__)

# Path to prompts directory
_prompts_dir = Path(__file__).parent / "prompts"


def _load_prompt(prompt_name: str, **kwargs) -> str:
    """Load and render a prompt template from the prompts directory."""
    try:
        env = Environment(loader=FileSystemLoader(str(_prompts_dir)))
        template = env.get_template(f"{prompt_name}.md")
        return template.render(**kwargs)
    except Exception as e:
        logger.warning(f"Failed to load prompt {prompt_name}: {e}")
        return f"You are a {prompt_name} agent."


def get_subagents(
    model=None,
    include_reviewer: bool = True,
) -> List:
    """
    Get the list of subagents for the verifier node.
    
    Args:
        model: The LLM model to use for subagents. Defaults to project LLM.
        include_reviewer: Whether to include the reviewer subagent.
        
    Returns:
        List of SubAgent configurations.
    """
    if not SUBAGENT_AVAILABLE:
        logger.warning("SubAgent not available - deepagents package not installed")
        return []
    
    if model is None:
        model = get_llm()
    
    subagents = []
    
    # Reviewer Subagent - provides detailed code review
    if include_reviewer:
        reviewer_prompt = _load_prompt("reviewer")
        subagents.append(
            SubAgent(
                name="reviewer",
                description=(
                    "A code reviewer that provides detailed analysis of code quality, "
                    "best practices, error handling, and suggestions for improvement. "
                    "Use this to get a thorough code review before making verification decisions."
                ),
                system_prompt=reviewer_prompt,  # Changed from 'prompt' to 'system_prompt'
                model=model,
            )
        )
        logger.debug("Added reviewer subagent for verifier")
    
    # Safe logging - handle both object and dict formats
    subagent_names = []
    for s in subagents:
        if hasattr(s, 'name'):
            subagent_names.append(s.name)
        elif isinstance(s, dict) and 'name' in s:
            subagent_names.append(s['name'])
        else:
            subagent_names.append(str(type(s)))
    logger.info(f"Verifier subagents configured: {subagent_names}")
    
    return subagents


__all__ = [
    "get_subagents",
    "SubAgent",
    "SUBAGENT_AVAILABLE",
]
