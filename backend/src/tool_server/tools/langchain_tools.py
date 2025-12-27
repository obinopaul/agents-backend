"""
LangChain Tools Registry

This module provides a centralized registry of all LangChain-compatible tools
for the agents-backend. It wraps all 44+ BaseTool implementations using the
LangChainToolAdapter for seamless integration with LangChain agents.

Usage:
    from backend.src.tool_server.tools.langchain_tools import (
        get_langchain_browser_tools,
        get_langchain_shell_tools,
        get_langchain_file_tools,
        get_all_langchain_tools,
    )
    
    # Get specific category of tools
    browser_tools = get_langchain_browser_tools(browser)
    
    # Get all tools for a sandbox session
    all_tools = get_all_langchain_tools(
        workspace_path="/workspace",
        credential={"session_id": "xxx", "user_api_key": "yyy"},
        sandbox=sandbox_instance,
        browser=browser_instance,
    )
    
    # Use with LangChain agent
    from langgraph.prebuilt import create_react_agent
    agent = create_react_agent(llm, all_tools)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
import logging

if TYPE_CHECKING:
    from backend.src.tool_server.browser.browser import Browser
    from backend.src.sandbox.interfaces.sandbox_interface import SandboxInterface
    from backend.src.tool_server.tools.shell.terminal_manager import BaseShellManager
    from langchain_core.tools import BaseTool as LangChainBaseTool

logger = logging.getLogger(__name__)


# =============================================================================
# Browser Tools (15)
# =============================================================================

def get_langchain_browser_tools(browser: "Browser") -> List["LangChainBaseTool"]:
    """
    Get all browser-related LangChain tools.
    
    Args:
        browser: Browser instance for page interactions
        
    Returns:
        List of 15 browser tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.browser import (
        BrowserClickTool,
        BrowserWaitTool,
        BrowserViewTool,
        BrowserScrollDownTool,
        BrowserScrollUpTool,
        BrowserSwitchTabTool,
        BrowserOpenNewTabTool,
        BrowserGetSelectOptionsTool,
        BrowserSelectDropdownOptionTool,
        BrowserNavigationTool,
        BrowserRestartTool,
        BrowserEnterTextTool,
        BrowserPressKeyTool,
        BrowserDragTool,
        BrowserEnterMultipleTextsTool,
    )
    
    tools = [
        BrowserClickTool(browser),
        BrowserWaitTool(browser),
        BrowserViewTool(browser),
        BrowserScrollDownTool(browser),
        BrowserScrollUpTool(browser),
        BrowserSwitchTabTool(browser),
        BrowserOpenNewTabTool(browser),
        BrowserGetSelectOptionsTool(browser),
        BrowserSelectDropdownOptionTool(browser),
        BrowserNavigationTool(browser),
        BrowserRestartTool(browser),
        BrowserEnterTextTool(browser),
        BrowserPressKeyTool(browser),
        BrowserDragTool(browser),
        BrowserEnterMultipleTextsTool(browser),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Shell Tools (6)
# =============================================================================

def get_langchain_shell_tools(
    shell_manager: "BaseShellManager",
    workspace_manager: Optional[Any] = None,
) -> List["LangChainBaseTool"]:
    """
    Get all shell-related LangChain tools.
    
    Args:
        shell_manager: BaseShellManager for command execution (e.g., TmuxSessionManager, LocalShellManager)
        workspace_manager: WorkspaceManager context (optional, created if None)
        
    Returns:
        List of 6 shell tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.shell import (
        ShellInit,
        ShellRunCommand,
        ShellView,
        ShellStopCommand,
        ShellList,
        ShellWriteToProcessTool,
    )
    
    # Create workspace manager if not provided (needed for ShellInit)
    if not workspace_manager:
        from backend.src.tool_server.core.workspace import WorkspaceManager
        workspace_manager = WorkspaceManager("/workspace")

    # Shell tools require BaseShellManager + WorkspaceManager
    tools = [
        ShellInit(shell_manager, workspace_manager),
        ShellRunCommand(shell_manager, workspace_manager),
        ShellView(shell_manager),
        ShellStopCommand(shell_manager),
        ShellList(shell_manager),
        ShellWriteToProcessTool(shell_manager),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# File System Tools (9)
# =============================================================================

def get_langchain_file_tools(
    sandbox: "SandboxInterface",
    workspace_manager: Optional[Any] = None,
) -> List["LangChainBaseTool"]:
    """
    Get all file system-related LangChain tools.
    
    Args:
        sandbox: SandboxInterface for file operations
        workspace_manager: Optional WorkspaceManager for workspace operations
        
    Returns:
        List of file system tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.file_system import (
        FileReadTool,
        FileWriteTool,
        FileEditTool,
        ApplyPatchTool,
        StrReplaceEditorTool,
        ASTGrepTool,
        GrepTool,
    )
    
    tools = [
        FileReadTool(workspace_manager),
        FileWriteTool(workspace_manager),
        FileEditTool(workspace_manager),
        ApplyPatchTool(workspace_manager),
        StrReplaceEditorTool(workspace_manager),
        ASTGrepTool(sandbox),
        GrepTool(sandbox),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Web Tools (6)
# =============================================================================

def get_langchain_web_tools(credential: Dict[str, Any]) -> List["LangChainBaseTool"]:
    """
    Get all web-related LangChain tools.
    
    Args:
        credential: Dictionary with authentication credentials
        
    Returns:
        List of web tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.web import (
        WebSearchTool,
        WebVisitTool,
        WebVisitCompressTool,
        ImageSearchTool,
        ReadRemoteImageTool,
        WebBatchSearchTool,
    )
    
    tools = [
        WebSearchTool(credential),
        WebVisitTool(credential),
        WebVisitCompressTool(credential),
        ImageSearchTool(credential),
        ReadRemoteImageTool(),
        WebBatchSearchTool(credential),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Media Tools (2)
# =============================================================================

def get_langchain_media_tools(credential: Dict[str, Any]) -> List["LangChainBaseTool"]:
    """
    Get all media-related LangChain tools.
    
    Args:
        credential: Dictionary with authentication credentials
        
    Returns:
        List of media tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.media import (
        ImageGenerateTool,
        VideoGenerateTool,
    )
    
    tools = [
        ImageGenerateTool(credential),
        VideoGenerateTool(credential),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Productivity Tools (Todo, Slide)
# =============================================================================

def get_langchain_productivity_tools(
    sandbox: "SandboxInterface",
) -> List["LangChainBaseTool"]:
    """
    Get productivity tools (Todo, Slides).
    
    Args:
        sandbox: SandboxInterface for file operations
        
    Returns:
        List of productivity tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.productivity import (
        TodoReadTool,
        TodoWriteTool,
    )
    from backend.src.tool_server.tools.slide_system import (
        SlideWriteTool,
        SlideEditTool,
        SlideApplyPatchTool,
    )
    
    tools = [
        TodoReadTool(sandbox),
        TodoWriteTool(sandbox),
        SlideWriteTool(sandbox),
        SlideEditTool(sandbox),
        SlideApplyPatchTool(sandbox),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Dev Tools (checkpoint, init, register_port)
# =============================================================================

def get_langchain_dev_tools(
    sandbox: "SandboxInterface",
    workspace_manager: Optional[Any] = None,
    credential: Optional[Dict[str, Any]] = None,
) -> List["LangChainBaseTool"]:
    """
    Get development tools.
    
    Args:
        sandbox: SandboxInterface 
        workspace_manager: Optional WorkspaceManager
        credential: Optional credentials
        
    Returns:
        List of dev tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.dev import (
        SaveCheckpointTool,
        FullStackInitTool,
    )
    
    tools = []
    
    if workspace_manager:
        tools.append(FullStackInitTool(sandbox, workspace_manager))
    
    tools.append(SaveCheckpointTool(sandbox))
    
    # Add database connection tool if credentials provided
    if credential:
        from backend.src.tool_server.tools.dev import GetDatabaseConnection
        tools.append(GetDatabaseConnection(credential))
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Agent Tools (message_user)
# =============================================================================

def get_langchain_agent_tools() -> List["LangChainBaseTool"]:
    """
    Get agent communication tools.
    
    Returns:
        List of agent tools wrapped for LangChain
    """
    from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
    from backend.src.tool_server.tools.agent import MessageUserTool
    
    tools = [
        MessageUserTool(),
    ]
    
    return [LangChainToolAdapter.from_base_tool(tool) for tool in tools]


# =============================================================================
# Master Function: Get All Tools
# =============================================================================

def get_all_langchain_tools(
    workspace_path: str,
    credential: Dict[str, Any],
    sandbox: Optional["SandboxInterface"] = None,
    browser: Optional["Browser"] = None,
    workspace_manager: Optional[Any] = None,
    shell_manager: Optional["BaseShellManager"] = None,
    include_browser: bool = True,
    include_shell: bool = True,
    include_file: bool = True,
    include_web: bool = True,
    include_media: bool = True,
    include_productivity: bool = True,
    include_dev: bool = True,
    include_agent: bool = True,
) -> List["LangChainBaseTool"]:
    """
    Get all LangChain-compatible tools for a sandbox session.
    
    This is the primary function for setting up an agent with all available tools.
    
    Args:
        workspace_path: Path to the workspace directory
        credential: Authentication credentials dict
        sandbox: SandboxInterface instance (required for file/productivity/dev tools)
        browser: Browser instance (required for browser tools)
        workspace_manager: Optional WorkspaceManager
        shell_manager: BaseShellManager instance (required for shell tools)
        include_*: Flags to include/exclude tool categories
        
    Returns:
        List of all LangChain-compatible tools
        
    Example:
        >>> tools = get_all_langchain_tools(
        ...     workspace_path="/workspace",
        ...     credential={"session_id": "xxx", "user_api_key": "yyy"},
        ...     shell_manager=shell_manager_instance,
        ...     browser=browser_instance,
        ... )
        >>> agent = create_react_agent(llm, tools)
    """
    all_tools = []
    
    if include_browser and browser:
        all_tools.extend(get_langchain_browser_tools(browser))
        logger.info(f"Added {len(all_tools)} browser tools")
    
    if include_shell and shell_manager:
        # Create workspace manager if not provided (needed for ShellInit)
        if not workspace_manager:
            from backend.src.tool_server.core.workspace import WorkspaceManager
            # Use provided path or default
            path = workspace_path or "/workspace"
            workspace_manager = WorkspaceManager(path)
            
        shell_tools = get_langchain_shell_tools(shell_manager, workspace_manager)
        all_tools.extend(shell_tools)
        logger.info(f"Added {len(shell_tools)} shell tools")
    
    if include_file and sandbox:
        # Create workspace manager if not provided (needed for file tools)
        if not workspace_manager:
            from backend.src.tool_server.core.workspace import WorkspaceManager
            # Use provided path or default
            path = workspace_path or "/workspace"
            workspace_manager = WorkspaceManager(path)
            
        file_tools = get_langchain_file_tools(sandbox, workspace_manager)
        all_tools.extend(file_tools)
        logger.info(f"Added {len(file_tools)} file tools")
    
    if include_web and credential:
        web_tools = get_langchain_web_tools(credential)
        all_tools.extend(web_tools)
        logger.info(f"Added {len(web_tools)} web tools")
    
    if include_media and credential:
        media_tools = get_langchain_media_tools(credential)
        all_tools.extend(media_tools)
        logger.info(f"Added {len(media_tools)} media tools")
    
    if include_productivity and sandbox:
        prod_tools = get_langchain_productivity_tools(sandbox)
        all_tools.extend(prod_tools)
        logger.info(f"Added {len(prod_tools)} productivity tools")
    
    if include_dev and sandbox:
        dev_tools = get_langchain_dev_tools(sandbox, workspace_manager, credential)
        all_tools.extend(dev_tools)
        logger.info(f"Added {len(dev_tools)} dev tools")
    
    if include_agent:
        agent_tools = get_langchain_agent_tools()
        all_tools.extend(agent_tools)
        logger.info(f"Added {len(agent_tools)} agent tools")
    
    logger.info(f"Total LangChain tools: {len(all_tools)}")
    return all_tools


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Category-specific functions
    "get_langchain_browser_tools",
    "get_langchain_shell_tools",
    "get_langchain_file_tools",
    "get_langchain_web_tools",
    "get_langchain_media_tools",
    "get_langchain_productivity_tools",
    "get_langchain_dev_tools",
    "get_langchain_agent_tools",
    # Master function
    "get_all_langchain_tools",
]
