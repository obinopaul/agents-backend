"""Coder node package for DS* system.

This package contains:
- node.py: The coder_node implementation (writes code based on plan)
- subagents.py: Researcher subagent for code research
- prompts/: Prompt templates for coder and researcher
"""

from .node import coder_node
from .subagents import get_subagents

__all__ = [
    "coder_node",
    "get_subagents",
]
