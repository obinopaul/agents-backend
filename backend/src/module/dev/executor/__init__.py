"""Executor node package for DS* system.

This package contains:
- node.py: The executor_node implementation (executes and tests code)
- subagents.py: Debugger subagent for fixing errors
- prompts/: Prompt templates for executor and debugger
"""

from .node import executor_node
from .subagents import get_subagents

__all__ = [
    "executor_node",
    "get_subagents",
]
