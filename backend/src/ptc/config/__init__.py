"""Unified configuration package for PTC Module.

This package consolidates all configuration-related code:
- backend.src.config.core: Core infrastructure configs (Daytona, MCP, Filesystem, Security, Logging)
- agent.py: Agent-specific configs (AgentConfig, LLMConfig, LLMDefinition)
- loaders.py: File-based configuration loading
- utils.py: Shared utilities for config parsing

Usage:
    # Programmatic configuration (recommended)
    from langchain_anthropic import ChatAnthropic
    from backend.src.ptc.config import AgentConfig

    llm = ChatAnthropic(model="claude-sonnet-4-20250514")
    config = AgentConfig.create(llm=llm)

    # File-based configuration (for CLI, etc.)
    from backend.src.ptc.config import load_from_files
    config = await load_from_files()

    # Core config only (for SessionManager)
    from backend.src.ptc.config import load_core_from_files
    core_config = await load_core_from_files()
"""

# Core data classes from main config module
from backend.src.config.core import (
    CoreConfig,
    DaytonaConfig,
    FilesystemConfig,
    LoggingConfig,
    MCPConfig,
    MCPServerConfig,
    SecurityConfig,
)

# Agent data classes
from backend.src.ptc.config.agent import (
    AgentConfig,
    LLMConfig,
    LLMDefinition,
)

# File-based loading
from backend.src.ptc.config.loaders import (
    # Context enum
    ConfigContext,
    ensure_config_dir,
    find_config_file,
    find_project_root,
    # Template generation
    generate_config_template,
    get_config_search_paths,
    # Config path utilities
    get_default_config_dir,
    load_core_from_files,
    load_from_dict,
    # Config loading
    load_from_files,
    load_llm_catalog,
)

# Utilities
from backend.src.ptc.config.utils import configure_logging

__all__ = [
    # Agent data classes
    "AgentConfig",
    # Context enum
    "ConfigContext",
    # Core data classes
    "CoreConfig",
    "DaytonaConfig",
    "FilesystemConfig",
    "LLMConfig",
    "LLMDefinition",
    "LoggingConfig",
    "MCPConfig",
    "MCPServerConfig",
    "SecurityConfig",
    # Utilities
    "configure_logging",
    "ensure_config_dir",
    "find_config_file",
    "find_project_root",
    # Template generation
    "generate_config_template",
    "get_config_search_paths",
    # Config path utilities
    "get_default_config_dir",
    "load_core_from_files",
    "load_from_dict",
    # Config loading
    "load_from_files",
    "load_llm_catalog",
]
