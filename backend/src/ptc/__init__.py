"""PTC Module - Programmatic Tool Calling Core Infrastructure.

An implementation of Programmatic Tool Calling (PTC) with MCP,
where agents generate executable Python code to interact with MCP servers.

This package provides the core infrastructure:
- PTCSandbox: Daytona sandbox management
- MCPRegistry: MCP server connections and tool discovery
- ToolFunctionGenerator: Convert MCP schemas to Python functions
- Session/SessionManager: Session lifecycle management
- Config: Configuration loading from YAML or programmatic

For agent implementations, see your LangGraph/LangChain agent code.
Import this module to add PTC capabilities to any agent.

Usage (Programmatic):
    from langchain_anthropic import ChatAnthropic
    from backend.src.ptc import PTCSandbox, MCPRegistry, Session
    from backend.src.ptc.config import AgentConfig

    llm = ChatAnthropic(model="claude-sonnet-4-20250514")
    config = AgentConfig.create(llm=llm)
    
    # Use core config with PTCSandbox
    core_config = config.to_core_config()
    sandbox = PTCSandbox(core_config)
    registry = MCPRegistry(core_config)
    
Usage (File-based):
    from backend.src.ptc.config import load_from_files
    
    config = await load_from_files()  # Reads config.yaml
    core_config = config.to_core_config()
"""

__version__ = "0.1.0"

# Core config from main config module
from backend.src.config.core import CoreConfig

# Core PTC classes
from .mcp_registry import MCPRegistry, MCPToolInfo
from .sandbox import ChartData, ExecutionResult, PTCSandbox
from .session import Session, SessionManager
from .tool_generator import ToolFunctionGenerator

# Config submodule exports for convenience
from .config import AgentConfig, LLMConfig, LLMDefinition

__all__ = [
    # Core PTC classes
    "ChartData",
    "CoreConfig",
    "ExecutionResult",
    "MCPRegistry",
    "MCPToolInfo",
    "PTCSandbox",
    "Session",
    "SessionManager",
    "ToolFunctionGenerator",
    # Config classes
    "AgentConfig",
    "LLMConfig",
    "LLMDefinition",
]

