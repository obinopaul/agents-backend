"""
Tool Server Tools Package

This module provides tool classes and utilities for the tool server.
Imports are lazy to avoid loading all 44 tools on every package import.
"""

# Only export base classes that are lightweight
from backend.src.tool_server.tools.base import (
    BaseTool,
    ToolResult,
    ToolParam,
    TextContent,
    ImageContent,
    FileURLContent,
    ToolConfirmationDetails,
)

__all__ = [
    # Base tool classes (always available)
    "BaseTool",
    "ToolResult",
    "ToolParam",
    "TextContent",
    "ImageContent",
    "FileURLContent",
    "ToolConfirmationDetails",
    # Lazy imports (use functions below to access)
    "get_sandbox_tools",
    "get_common_tools",
    "get_langchain_tools",
    "LangChainToolAdapter",
    "AuthenticationContext",
    "adapt_tools_for_langchain",
    "json_schema_to_pydantic_model",
]


def __getattr__(name: str):
    """Lazy loading for heavy imports (manager.py, langchain_adapter.py)."""
    
    # Manager functions (loads all 44 tools)
    if name in ("get_sandbox_tools", "get_common_tools"):
        from backend.src.tool_server.tools.manager import get_sandbox_tools, get_common_tools
        return get_sandbox_tools if name == "get_sandbox_tools" else get_common_tools
    
    if name == "get_langchain_tools":
        from backend.src.tool_server.tools.manager import get_langchain_tools
        return get_langchain_tools
    
    # LangChain adapter classes
    if name == "LangChainToolAdapter":
        from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
        return LangChainToolAdapter
    
    if name == "AuthenticationContext":
        from backend.src.tool_server.tools.langchain_adapter import AuthenticationContext
        return AuthenticationContext
    
    if name == "adapt_tools_for_langchain":
        from backend.src.tool_server.tools.langchain_adapter import adapt_tools_for_langchain
        return adapt_tools_for_langchain
    
    if name == "json_schema_to_pydantic_model":
        from backend.src.tool_server.tools.langchain_adapter import json_schema_to_pydantic_model
        return json_schema_to_pydantic_model
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
