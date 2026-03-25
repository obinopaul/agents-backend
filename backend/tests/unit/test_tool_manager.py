"""
Unit tests for Tool Manager.

Tests get_sandbox_tools, get_common_tools, and tool instantiation.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestGetSandboxTools:
    """Test get_sandbox_tools function."""

    def test_get_sandbox_tools_returns_list(self):
        """Test that get_sandbox_tools returns a list of tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_sandbox_tools_includes_shell_tools(self):
        """Test that get_sandbox_tools includes shell tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        from backend.src.tool_server.tools.shell import ShellRunCommand, ShellInit
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        tool_types = [type(t) for t in tools]
        
        assert ShellRunCommand in tool_types or any(
            t.__class__.__name__ == "ShellRunCommand" for t in tools
        )

    def test_get_sandbox_tools_includes_file_tools(self):
        """Test that get_sandbox_tools includes file system tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        tool_names = [t.name for t in tools]
        
        # Should have file read/write/edit tools
        assert any("file" in name.lower() or "read" in name.lower() for name in tool_names)

    def test_get_sandbox_tools_includes_web_tools(self):
        """Test that get_sandbox_tools includes web tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        tool_names = [t.name for t in tools]
        
        # Should have web search tool
        assert any("search" in name.lower() or "web" in name.lower() for name in tool_names)

    def test_get_sandbox_tools_includes_browser_tools(self):
        """Test that get_sandbox_tools includes browser tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        tool_names = [t.name for t in tools]
        
        # Should have browser tools
        assert any("browser" in name.lower() or "click" in name.lower() for name in tool_names)

    def test_get_sandbox_tools_all_have_required_attributes(self):
        """Test that all tools have required attributes."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        for tool in tools:
            assert hasattr(tool, 'name'), f"Tool missing 'name' attribute"
            assert hasattr(tool, 'description'), f"Tool {tool.name} missing 'description'"
            assert hasattr(tool, 'input_schema'), f"Tool {tool.name} missing 'input_schema'"
            assert hasattr(tool, 'execute'), f"Tool {tool.name} missing 'execute' method"

    def test_get_sandbox_tools_all_have_unique_names(self):
        """Test that all tools have unique names."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tools = get_sandbox_tools(
            workspace_path="/tmp/workspace",
            credential=credential
        )
        
        tool_names = [t.name for t in tools]
        
        assert len(tool_names) == len(set(tool_names)), "Tool names must be unique"


class TestGetCommonTools:
    """Test get_common_tools function."""

    def test_get_common_tools_returns_list(self):
        """Test that get_common_tools returns a list."""
        from backend.src.tool_server.tools.manager import get_common_tools
        from backend.src.tool_server.interfaces.sandbox import SandboxInterface
        
        # Create a mock sandbox
        mock_sandbox = MagicMock(spec=SandboxInterface)
        
        tools = get_common_tools(sandbox=mock_sandbox)
        
        assert isinstance(tools, list)

    def test_get_common_tools_includes_register_port(self):
        """Test that get_common_tools includes RegisterPort."""
        from backend.src.tool_server.tools.manager import get_common_tools
        from backend.src.tool_server.interfaces.sandbox import SandboxInterface
        
        mock_sandbox = MagicMock(spec=SandboxInterface)
        
        tools = get_common_tools(sandbox=mock_sandbox)
        
        tool_types = [type(t).__name__ for t in tools]
        
        assert "RegisterPort" in tool_types

    def test_get_common_tools_includes_message_user(self):
        """Test that get_common_tools includes MessageUserTool."""
        from backend.src.tool_server.tools.manager import get_common_tools
        from backend.src.tool_server.interfaces.sandbox import SandboxInterface
        
        mock_sandbox = MagicMock(spec=SandboxInterface)
        
        tools = get_common_tools(sandbox=mock_sandbox)
        
        tool_types = [type(t).__name__ for t in tools]
        
        assert "MessageUserTool" in tool_types


class TestToolCategories:
    """Test that tools are properly categorized."""

    def test_shell_tools_count(self):
        """Test the number of shell tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {"user_api_key": "test", "session_id": "test"}
        tools = get_sandbox_tools("/tmp", credential)
        
        shell_tools = [t for t in tools if "bash" in t.name.lower() or "shell" in t.name.lower()]
        
        # Should have multiple shell tools (init, run, view, stop, list, write)
        assert len(shell_tools) >= 3

    def test_browser_tools_count(self):
        """Test the number of browser tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {"user_api_key": "test", "session_id": "test"}
        tools = get_sandbox_tools("/tmp", credential)
        
        browser_tools = [t for t in tools if "browser" in t.name.lower()]
        
        # Should have multiple browser tools
        assert len(browser_tools) >= 5

    def test_file_tools_count(self):
        """Test the number of file system tools."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {"user_api_key": "test", "session_id": "test"}
        tools = get_sandbox_tools("/tmp", credential)
        
        # File tools might have various names
        file_tool_keywords = ["file", "read", "write", "edit", "grep", "patch"]
        file_tools = [
            t for t in tools 
            if any(kw in t.name.lower() for kw in file_tool_keywords)
        ]
        
        assert len(file_tools) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
