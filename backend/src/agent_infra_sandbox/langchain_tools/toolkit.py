"""Sandbox LangChain Toolkit - Factory for creating all sandbox tools."""

from typing import List, Optional, Any
from langchain_core.tools import BaseTool

from langchain_tools.client import SandboxClient
from langchain_tools.tools.file_tools import create_file_tools
from langchain_tools.tools.shell_tools import create_shell_tools
from langchain_tools.tools.code_tools import create_code_tools
from langchain_tools.tools.browser_tools import create_browser_tools
from langchain_tools.tools.mcp_tools import create_mcp_tools
from langchain_tools.tools.grep_tool import create_grep_tool
from langchain_tools.tools.sandbox_tools import create_sandbox_tools as create_sandbox_info_tools


class SandboxToolkit:
    """Toolkit for creating LangChain tools bound to an AIO Sandbox.
    
    Provides factory methods for creating tools either individually by category
    or all at once. All tools are async-first with sync wrappers available.
    
    Args:
        base_url: Base URL of the sandbox (default: http://localhost:8080)
        timeout: Request timeout in seconds (default: 60)
        
    Example:
        >>> toolkit = SandboxToolkit(base_url="http://localhost:8080")
        >>> all_tools = toolkit.get_tools()
        >>> file_tools = toolkit.get_file_tools()
    """
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8080",
        timeout: float = 60.0,
    ):
        self.client = SandboxClient(base_url=base_url, timeout=timeout)
        
    def get_tools(self) -> List[BaseTool]:
        """Get all available sandbox tools.
        
        Returns:
            List of all LangChain tools for sandbox operations
        """
        tools = []
        tools.extend(self.get_file_tools())
        tools.extend(self.get_shell_tools())
        tools.extend(self.get_code_tools())
        tools.extend(self.get_browser_tools())
        tools.extend(self.get_mcp_tools())
        tools.append(self.get_grep_tool())
        tools.extend(self.get_sandbox_info_tools())
        return tools
    
    def get_file_tools(self) -> List[BaseTool]:
        """Get file system operation tools.
        
        Includes: file_read, file_write, file_edit, file_list, 
                  file_find, file_search, file_upload, file_download
        """
        return create_file_tools(self.client)
    
    def get_shell_tools(self) -> List[BaseTool]:
        """Get shell/terminal operation tools.
        
        Includes: shell_exec, shell_view, shell_write, 
                  shell_wait, shell_kill, shell_sessions
        """
        return create_shell_tools(self.client)
    
    def get_code_tools(self) -> List[BaseTool]:
        """Get code execution tools.
        
        Includes: jupyter_execute, nodejs_execute, code_execute
        """
        return create_code_tools(self.client)
    
    def get_browser_tools(self) -> List[BaseTool]:
        """Get browser automation tools.
        
        Includes: browser_info, browser_screenshot, browser_action, browser_config
        """
        return create_browser_tools(self.client)
    
    def get_mcp_tools(self) -> List[BaseTool]:
        """Get MCP server integration tools.
        
        Includes: mcp_list_servers, mcp_list_tools, mcp_execute
        """
        return create_mcp_tools(self.client)
    
    def get_grep_tool(self) -> BaseTool:
        """Get the grep content search tool."""
        return create_grep_tool(self.client)
    
    def get_sandbox_info_tools(self) -> List[BaseTool]:
        """Get sandbox info/utility tools.
        
        Includes: sandbox_context, sandbox_packages
        """
        return create_sandbox_info_tools(self.client)


def create_sandbox_tools(
    base_url: str = "http://localhost:8080",
    timeout: float = 60.0,
) -> List[BaseTool]:
    """Factory function to create all sandbox tools.
    
    Convenience function that creates a SandboxToolkit and returns all tools.
    
    Args:
        base_url: Base URL of the sandbox (default: http://localhost:8080)
        timeout: Request timeout in seconds (default: 60)
        
    Returns:
        List of all LangChain tools for sandbox operations
        
    Example:
        >>> tools = create_sandbox_tools(base_url="http://localhost:8080")
        >>> agent = create_react_agent(llm, tools)
    """
    toolkit = SandboxToolkit(base_url=base_url, timeout=timeout)
    return toolkit.get_tools()
