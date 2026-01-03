"""Skills module for agent middleware.

Public API:
- SkillsMiddleware: Middleware for integrating skills into agent execution (local filesystem)
- SandboxSkillsMiddleware: Middleware for loading skills from sandbox environment (remote)
- list_skills_from_sandbox: Async function to load skills from sandbox
- format_skills_for_prompt: Format skills metadata for system prompt injection

CLI commands (optional, requires deepagents_cli):
- execute_skills_command: Execute skills subcommands (list/create/info)
- setup_skills_parser: Setup argparse configuration for skills commands

All other components are internal implementation details.
"""

from backend.src.agents.middleware.skills_middleware.middleware import (
    SkillsMiddleware,
    SandboxSkillsMiddleware,
)
from backend.src.agents.middleware.skills_middleware.sandbox_load import (
    list_skills_from_sandbox,
    format_skills_for_prompt,
)

# CLI commands are optional - requires deepagents_cli package
try:
    from backend.src.agents.middleware.skills_middleware.commands import (
        execute_skills_command,
        setup_skills_parser,
    )
    _CLI_AVAILABLE = True
except ImportError:
    execute_skills_command = None
    setup_skills_parser = None
    _CLI_AVAILABLE = False

__all__ = [
    "SkillsMiddleware",
    "SandboxSkillsMiddleware",
    "list_skills_from_sandbox",
    "format_skills_for_prompt",
    "execute_skills_command",
    "setup_skills_parser",
]


