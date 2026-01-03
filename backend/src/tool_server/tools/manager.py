"""
Tool Manager - Factory functions for sandbox tools.

OPTIMIZATION: All heavy imports are done INSIDE functions (lazy imports).
This means importing this module is fast - the heavy tool classes are only
imported when get_sandbox_tools() is actually called.

/health immediately, and tools are only loaded when needed.
"""
from typing import Dict


def get_common_tools(sandbox):
    """Get common tools that run on the backend (not in sandbox).
    
    These are lightweight tools that don't require heavy imports.
    """
    # Lazy import to avoid loading at module level
    from backend.src.tool_server.interfaces.sandbox import SandboxInterface
    from backend.src.tool_server.tools.dev import RegisterPort
    from backend.src.tool_server.tools.agent.message_user import MessageUserTool
    
    tools = [
        # Sandbox tools
        RegisterPort(sandbox=sandbox),
        MessageUserTool(),
    ]

    return tools


def get_sandbox_tools(workspace_path: str, credential: Dict):
    """Get all sandbox tools with lazy imports.
    
    OPTIMIZATION: All imports happen inside this function, not at module level.
    This allows the MCP server to start immediately and expose /health,
    while tools are only loaded when this function is called.
    
    Args:
        workspace_path: Path to the workspace directory
        credential: Dict with user_api_key and session_id
        
    Returns:
        List of tool instances ready for registration
    """
    # =========================================================================
    # LAZY IMPORTS - Only loaded when this function is called
    # =========================================================================
    
    # Core utilities
    from backend.src.tool_server.core.workspace import WorkspaceManager
    
    # Shell tools
    from backend.src.tool_server.tools.shell import (
        ShellInit,
        ShellRunCommand,
        ShellView,
        ShellStopCommand,
        ShellList,
        TmuxSessionManager,
        ShellWriteToProcessTool,
    )
    
    # File system tools
    from backend.src.tool_server.tools.file_system import (
        ASTGrepTool,
        GrepTool,
        FileReadTool,
        FileWriteTool,
        FileEditTool,
        ApplyPatchTool,
        StrReplaceEditorTool,
    )
    
    # Productivity tools
    from backend.src.tool_server.tools.productivity import TodoReadTool, TodoWriteTool
    
    # Media tools
    from backend.src.tool_server.tools.media import (
        VideoGenerateTool,
        ImageGenerateTool,
    )
    
    # Dev tools
    from backend.src.tool_server.tools.dev import FullStackInitTool, SaveCheckpointTool
    
    # Web tools
    from backend.src.tool_server.tools.web import (
        WebSearchTool,
        WebVisitTool,
        ImageSearchTool,
        WebVisitCompressTool,
        ReadRemoteImageTool,
        WebBatchSearchTool,
    )
    
    # Database tools
    from backend.src.tool_server.tools.dev.database import GetDatabaseConnection
    
    # Slide tools
    from backend.src.tool_server.tools.slide_system.slide_edit_tool import SlideEditTool
    from backend.src.tool_server.tools.slide_system.slide_write_tool import SlideWriteTool
    from backend.src.tool_server.tools.slide_system.slide_patch import SlideApplyPatchTool
    
    # Browser tools
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
    from backend.src.tool_server.browser.browser import Browser
    
    # =========================================================================
    # TOOL INSTANTIATION
    # =========================================================================
    
    terminal_manager = TmuxSessionManager()
    workspace_manager = WorkspaceManager(workspace_path)
    browser = Browser()

    tools = [
        # Shell tools
        ShellInit(terminal_manager, workspace_manager),
        ShellRunCommand(terminal_manager, workspace_manager),
        ShellView(terminal_manager),
        ShellStopCommand(terminal_manager),
        ShellList(terminal_manager),
        ShellWriteToProcessTool(terminal_manager),
        # File system tools
        FileReadTool(workspace_manager),
        FileWriteTool(workspace_manager),
        FileEditTool(workspace_manager),
        ApplyPatchTool(workspace_manager),
        StrReplaceEditorTool(workspace_manager),
        ASTGrepTool(workspace_manager),
        GrepTool(workspace_manager),
        FullStackInitTool(workspace_manager),
        SaveCheckpointTool(workspace_manager),
        # Media tools
        ImageGenerateTool(workspace_manager, credential),
        VideoGenerateTool(workspace_manager, credential),
        # Web tools
        WebSearchTool(credential),
        WebVisitTool(credential),
        WebVisitCompressTool(credential),
        ImageSearchTool(credential),
        ReadRemoteImageTool(),
        WebBatchSearchTool(credential),
        # Database tools
        GetDatabaseConnection(credential),
        # Todo tools
        TodoReadTool(),
        TodoWriteTool(),
        # Slide tools
        SlideWriteTool(workspace_manager),
        SlideEditTool(workspace_manager),
        SlideApplyPatchTool(workspace_manager),
        # Browser tools
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

    return tools


# LangChain Integration - Factory function for LangChain-compatible tools
def get_langchain_tools(workspace_path: str, credential: Dict):
    """Get all sandbox tools as LangChain-compatible tools.
    
    This is the primary entry point for using tools with LangChain agents.
    
    Args:
        workspace_path: Path to the workspace directory in the sandbox
        credential: Credential dictionary for web/media tools
        
    Returns:
        List of LangChain-compatible tools ready for agent use
        
    Example:
        >>> from backend.src.tool_server.tools.manager import get_langchain_tools
        >>> tools = get_langchain_tools("/home/user/workspace", {"TAVILY_API_KEY": "..."})
        >>> from langgraph.prebuilt import create_react_agent
        >>> agent = create_react_agent(llm, tools)
    """
    from backend.src.tool_server.tools.langchain_adapter import adapt_tools_for_langchain
    
    base_tools = get_sandbox_tools(workspace_path, credential)
    return adapt_tools_for_langchain(base_tools)
