# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Tool loader for the multi-agent template.

Provides functions to load tools from:
- MCP servers (via tool_server)
- Sandbox environments (E2B, Daytona)
- Built-in tools
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool

from backend.src.agent_template.config import ToolConfig

logger = logging.getLogger(__name__)


async def load_mcp_tools(
    mcp_config: Dict[str, Any],
    timeout_seconds: int = 300,
) -> List[BaseTool]:
    """
    Load tools from MCP servers.
    
    Args:
        mcp_config: MCP server configuration dict
        timeout_seconds: Connection timeout
        
    Returns:
        List of LangChain tools from MCP servers
    """
    tools = []
    
    if not mcp_config:
        logger.debug("No MCP config provided")
        return tools
    
    try:
        from langchain_mcp_adapters.tools import load_mcp_tools as _load_mcp_tools
        
        for server_name, server_config in mcp_config.items():
            try:
                transport = server_config.get("transport", "http")
                
                if transport == "http":
                    url = server_config.get("url")
                    if url:
                        server_tools = await _load_mcp_tools(url)
                        tools.extend(server_tools)
                        logger.info(f"Loaded {len(server_tools)} tools from MCP server: {server_name}")
                        
                elif transport == "stdio":
                    command = server_config.get("command")
                    args = server_config.get("args", [])
                    if command:
                        # For stdio transport, need to use subprocess
                        # This is a placeholder - actual implementation would use mcp client
                        logger.info(f"Stdio MCP server: {server_name} (command: {command})")
                        
            except Exception as e:
                logger.warning(f"Failed to load tools from MCP server {server_name}: {e}")
                
    except ImportError:
        logger.warning("langchain-mcp-adapters not installed, skipping MCP tools")
    
    return tools


async def load_sandbox_tools(
    sandbox_url: str,
    enabled_tools: Optional[List[str]] = None,
) -> List[BaseTool]:
    """
    Load tools from a sandbox environment.
    
    Args:
        sandbox_url: Base URL of the sandbox (e.g., http://sandbox.e2b.dev:8080)
        enabled_tools: Optional list of tool names to enable (None = all)
        
    Returns:
        List of LangChain tools from sandbox
    """
    tools = []
    
    if not sandbox_url:
        logger.debug("No sandbox URL provided")
        return tools
    
    try:
        from backend.src.sandbox.agent_infra_sandbox.langchain_tools import create_sandbox_tools
        
        sandbox_tools = create_sandbox_tools(base_url=sandbox_url)
        
        # Filter tools if enabled_tools specified
        if enabled_tools:
            sandbox_tools = [t for t in sandbox_tools if t.name in enabled_tools]
        
        tools.extend(sandbox_tools)
        logger.info(f"Loaded {len(tools)} sandbox tools from {sandbox_url}")
        
    except ImportError:
        logger.warning("Sandbox tools module not available")
    except Exception as e:
        logger.warning(f"Failed to load sandbox tools: {e}")
    
    return tools


async def load_all_tools(
    config: ToolConfig,
    mcp_servers: Optional[Dict[str, Any]] = None,
    sandbox_url: Optional[str] = None,
) -> List[BaseTool]:
    """
    Load all available tools based on configuration.
    
    Args:
        config: Tool configuration
        mcp_servers: MCP server configurations
        sandbox_url: Sandbox URL (if sandbox is enabled)
        
    Returns:
        Combined list of all loaded tools
    """
    tools = []
    
    # Load MCP tools
    if config.enable_mcp and mcp_servers:
        mcp_tools = await load_mcp_tools(
            mcp_config=mcp_servers,
            timeout_seconds=config.mcp_timeout_seconds,
        )
        tools.extend(mcp_tools)
    
    # Load sandbox tools
    if config.enable_sandbox and sandbox_url:
        sandbox_tools = await load_sandbox_tools(
            sandbox_url=sandbox_url,
            enabled_tools=config.allowed_tools if config.allowed_tools else None,
        )
        tools.extend(sandbox_tools)
    
    # Filter out blocked tools
    if config.blocked_tools:
        tools = [t for t in tools if t.name not in config.blocked_tools]
    
    # Filter to only allowed tools (if specified)
    if config.allowed_tools:
        tools = [t for t in tools if t.name in config.allowed_tools]
    
    logger.info(f"Loaded {len(tools)} total tools")
    return tools


def get_built_in_tools() -> List[BaseTool]:
    """
    Get built-in tools that don't require external services.
    
    Returns:
        List of built-in tools
    """
    tools = []
    
    # Add any built-in tools here
    # Example: calculator, datetime, etc.
    
    return tools
