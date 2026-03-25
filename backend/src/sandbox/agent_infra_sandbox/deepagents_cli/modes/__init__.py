"""Modes module for pre-configured skill sets.

Modes are collections of skills that can be dynamically injected into a session.
Think of them as "personas" or "roles" for the agent - a data scientist mode
would include EDA and ML skills, while a software developer mode would include
code review and testing skills.

Usage:
    /mode list              - Show available modes
    /mode data_scientist    - Activate data scientist mode
"""

from deepagents_cli.modes.manager import ModeManager
from deepagents_cli.modes.commands import execute_mode_command, setup_mode_parser

__all__ = [
    "ModeManager",
    "execute_mode_command",
    "setup_mode_parser",
]
