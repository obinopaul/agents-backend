# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import dataclasses
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from langgraph.prebuilt.chat_agent_executor import AgentState

from backend.src.config.configuration import Configuration

# Base directory for this module (backend/src/module/dev)
MODULE_DIR = Path(__file__).parent

# Node folders that contain prompts
NODE_FOLDERS = ["analyzer", "planner", "coder", "executor", "verifier"]


def _get_template_path(prompt_name: str) -> tuple[Path, str]:
    """
    Find the template path for a given prompt name.
    
    Searches in each node's prompts/ subfolder for the template.
    E.g., 'analyzer' -> analyzer/prompts/analyzer.md
          'planner_subagent' -> analyzer/prompts/planner_subagent.md (if found there)
    
    Args:
        prompt_name: Name of the prompt template file (without .md extension)
    
    Returns:
        Tuple of (directory_path, filename) for the template
    
    Raises:
        FileNotFoundError if template not found in any node folder
    """
    template_filename = f"{prompt_name}.md"
    
    # First, check if the prompt_name matches a node folder name directly
    # e.g., "analyzer" -> analyzer/prompts/analyzer.md
    for node in NODE_FOLDERS:
        if prompt_name == node or prompt_name.startswith(f"{node}_"):
            prompts_dir = MODULE_DIR / node / "prompts"
            template_path = prompts_dir / template_filename
            if template_path.exists():
                return prompts_dir, template_filename
    
    # Search through all node prompts folders
    for node in NODE_FOLDERS:
        prompts_dir = MODULE_DIR / node / "prompts"
        template_path = prompts_dir / template_filename
        if template_path.exists():
            return prompts_dir, template_filename
    
    # Not found - raise helpful error
    searched_paths = [str(MODULE_DIR / node / "prompts" / template_filename) for node in NODE_FOLDERS]
    raise FileNotFoundError(
        f"Template '{prompt_name}.md' not found in any node prompts folder. "
        f"Searched: {searched_paths}"
    )


def get_prompt_template(prompt_name: str) -> str:
    """
    Load and return a prompt template using Jinja2.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)

    Returns:
        The template string with proper variable substitution syntax
    """
    try:
        prompts_dir, template_filename = _get_template_path(prompt_name)
        
        # Create a Jinja2 environment for this specific prompts directory
        env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        template = env.get_template(template_filename)
        return template.render()
    except FileNotFoundError as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")


def apply_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute
        configurable: Configuration object with additional variables

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }

    # Add configurable variables
    if configurable:
        state_vars.update(dataclasses.asdict(configurable))

    try:
        prompts_dir, template_filename = _get_template_path(prompt_name)
        
        # Create a Jinja2 environment for this specific prompts directory
        env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        template = env.get_template(template_filename)
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except FileNotFoundError as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")

