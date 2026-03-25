"""Tests for PTC (Programmatic Tool Calling) tools.

Tests cover:
- Tool factory functions
- Tool imports and structure
- get_all_tools function
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestPTCToolImports:
    """Tests for PTC tool imports."""

    def test_import_ptc_tools_package(self):
        """Test that PTC tools package can be imported."""
        from backend.src.ptc.tools import (
            create_execute_bash_tool,
            create_filesystem_tools,
            create_glob_tool,
            create_grep_tool,
            create_execute_code_tool,
            get_all_tools,
        )
        
        assert callable(create_execute_bash_tool)
        assert callable(create_filesystem_tools)
        assert callable(create_glob_tool)
        assert callable(create_grep_tool)
        assert callable(create_execute_code_tool)
        assert callable(get_all_tools)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from backend.src.ptc.tools import __all__
        
        expected = [
            "create_execute_bash_tool",
            "create_execute_code_tool",
            "create_filesystem_tools",
            "create_glob_tool",
            "create_grep_tool",
            "get_all_tools",
        ]
        
        for item in expected:
            assert item in __all__, f"{item} not in __all__"


class TestToolFactories:
    """Tests for tool factory functions."""

    def test_create_filesystem_tools_returns_tuple(self):
        """Test that create_filesystem_tools returns 3 tools."""
        from backend.src.ptc.tools import create_filesystem_tools
        
        mock_sandbox = MagicMock()
        mock_sandbox.normalize_path = MagicMock(side_effect=lambda x: x)
        
        tools = create_filesystem_tools(mock_sandbox)
        
        assert isinstance(tools, tuple)
        assert len(tools) == 3
        
        read_file, write_file, edit_file = tools
        assert read_file.name == "read_file"
        assert write_file.name == "write_file"
        assert edit_file.name == "edit_file"

    def test_create_bash_tool(self):
        """Test that create_execute_bash_tool creates a tool."""
        from backend.src.ptc.tools import create_execute_bash_tool
        
        mock_sandbox = MagicMock()
        tool = create_execute_bash_tool(mock_sandbox)
        
        assert tool is not None
        assert hasattr(tool, 'name')

    def test_create_glob_tool(self):
        """Test that create_glob_tool creates a tool."""
        from backend.src.ptc.tools import create_glob_tool
        
        mock_sandbox = MagicMock()
        tool = create_glob_tool(mock_sandbox)
        
        assert tool is not None
        assert hasattr(tool, 'name')

    def test_create_grep_tool(self):
        """Test that create_grep_tool creates a tool."""
        from backend.src.ptc.tools import create_grep_tool
        
        mock_sandbox = MagicMock()
        tool = create_grep_tool(mock_sandbox)
        
        assert tool is not None
        assert hasattr(tool, 'name')


class TestGetAllTools:
    """Tests for get_all_tools function."""

    def test_get_all_tools_returns_list(self):
        """Test that get_all_tools returns a list of tools."""
        from backend.src.ptc.tools import get_all_tools
        
        mock_sandbox = MagicMock()
        mock_sandbox.normalize_path = MagicMock(side_effect=lambda x: x)
        mock_mcp_registry = MagicMock()
        
        tools = get_all_tools(mock_sandbox, mock_mcp_registry)
        
        assert isinstance(tools, list)
        assert len(tools) >= 7  # At least 7 tools

    def test_get_all_tools_contains_expected_tools(self):
        """Test that get_all_tools includes expected tool types."""
        from backend.src.ptc.tools import get_all_tools
        
        mock_sandbox = MagicMock()
        mock_sandbox.normalize_path = MagicMock(side_effect=lambda x: x)
        mock_mcp_registry = MagicMock()
        
        tools = get_all_tools(mock_sandbox, mock_mcp_registry)
        tool_names = [t.name for t in tools]
        
        # Check for expected tool names
        expected_tools = ["read_file", "write_file", "edit_file"]
        for expected in expected_tools:
            assert expected in tool_names, f"{expected} not in tools"


class TestStorageModule:
    """Tests for PTC storage module."""

    def test_import_storage_module(self):
        """Test that storage module can be imported."""
        from backend.src.ptc.utils.storage import (
            is_storage_enabled,
            get_public_url,
            upload_bytes,
        )
        
        assert callable(is_storage_enabled)
        assert callable(get_public_url)
        assert callable(upload_bytes)

    def test_is_storage_enabled_returns_bool(self):
        """Test that is_storage_enabled returns a boolean."""
        from backend.src.ptc.utils.storage import is_storage_enabled
        
        result = is_storage_enabled()
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
