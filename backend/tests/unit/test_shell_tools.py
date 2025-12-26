"""
Unit tests for Shell tools.

Tests ShellRunCommand, ShellInit, ShellView, and other shell-related tools
with mocked terminal manager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockCommandOutput:
    """Mock output from shell command."""
    def __init__(self, clean_output="", ansi_output=""):
        self.clean_output = clean_output
        self.ansi_output = ansi_output


class TestShellRunCommand:
    """Test ShellRunCommand tool."""

    @pytest.fixture
    def mock_terminal_manager(self):
        """Create a mock terminal manager."""
        manager = MagicMock()
        manager.get_all_sessions.return_value = ["main"]
        manager.run_command.return_value = MockCommandOutput(
            clean_output="command output",
            ansi_output="\x1b[32mcommand output\x1b[0m"
        )
        manager.get_session_output.return_value = MockCommandOutput(
            clean_output="session output",
            ansi_output="session output"
        )
        return manager

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        return manager

    @pytest.mark.asyncio
    async def test_shell_run_command_success(self, mock_terminal_manager, mock_workspace_manager):
        """Test successful command execution."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "echo 'hello'",
            "description": "Prints hello"
        })
        
        assert result.llm_content == "command output"
        assert result.is_error is False
        mock_terminal_manager.run_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_shell_run_command_with_timeout(self, mock_terminal_manager, mock_workspace_manager):
        """Test command execution with custom timeout."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "sleep 5",
            "description": "Sleeps for 5 seconds",
            "timeout": 120
        })
        
        mock_terminal_manager.run_command.assert_called_with(
            "main", "sleep 5", timeout=120, wait_for_output=True
        )

    @pytest.mark.asyncio
    async def test_shell_run_command_timeout_exceeded(self, mock_terminal_manager, mock_workspace_manager):
        """Test that exceeding max timeout returns error."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand, MAX_TIMEOUT
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "long_command",
            "description": "Long running",
            "timeout": MAX_TIMEOUT + 100
        })
        
        assert result.is_error is True
        assert "Timeout must be less than" in result.llm_content

    @pytest.mark.asyncio
    async def test_shell_run_command_timeout_error(self, mock_terminal_manager, mock_workspace_manager):
        """Test handling of ShellCommandTimeoutError."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        from backend.src.tool_server.tools.shell.terminal_manager import ShellCommandTimeoutError
        
        mock_terminal_manager.run_command.side_effect = ShellCommandTimeoutError()
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "slow_command",
            "description": "Slow command"
        })
        
        assert result.is_error is True
        assert "timed out" in result.llm_content.lower()

    @pytest.mark.asyncio
    async def test_shell_run_command_busy_error(self, mock_terminal_manager, mock_workspace_manager):
        """Test handling of ShellBusyError."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        from backend.src.tool_server.tools.shell.terminal_manager import ShellBusyError
        
        mock_terminal_manager.run_command.side_effect = ShellBusyError()
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "echo test",
            "description": "Test command"
        })
        
        assert result.is_error is True
        assert "not finished" in result.llm_content.lower()

    @pytest.mark.asyncio
    async def test_shell_run_creates_session_if_not_exists(self, mock_terminal_manager, mock_workspace_manager):
        """Test that missing session is auto-created."""
        mock_terminal_manager.get_all_sessions.return_value = []  # No sessions
        
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        await tool.execute({
            "session_name": "new_session",
            "command": "echo test",
            "description": "Test"
        })
        
        mock_terminal_manager.create_session.assert_called_once_with(
            "new_session", "/workspace"
        )

    @pytest.mark.asyncio
    async def test_shell_run_command_empty_command_error(self, mock_terminal_manager, mock_workspace_manager):
        """Test that empty command returns error."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "",
            "description": "Empty"
        })
        
        assert result.is_error is True
        assert "required" in result.llm_content.lower()

    def test_shell_run_should_confirm_execute(self, mock_terminal_manager, mock_workspace_manager):
        """Test should_confirm_execute returns confirmation details."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = tool.should_confirm_execute({
            "command": "rm -rf /tmp/test",
            "description": "Delete temp files"
        })
        
        assert result is not False
        assert result.type == "bash"
        assert "rm -rf" in result.message

    @pytest.mark.asyncio
    async def test_execute_mcp_wrapper(self, mock_terminal_manager, mock_workspace_manager):
        """Test the MCP wrapper method."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute_mcp_wrapper(
            session_name="main",
            command="echo hello",
            description="Prints hello"
        )
        
        # MCP wrapper should return FastMCPToolResult format
        assert result is not None


class TestShellInit:
    """Test ShellInit tool."""

    @pytest.fixture
    def mock_terminal_manager(self):
        """Create a mock terminal manager."""
        manager = MagicMock()
        manager.get_all_sessions.return_value = []
        return manager

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock workspace manager."""
        manager = MagicMock()
        manager.get_workspace_path.return_value = "/workspace"
        return manager

    @pytest.mark.asyncio
    async def test_shell_init_creates_session(self, mock_terminal_manager, mock_workspace_manager):
        """Test that ShellInit creates a new session."""
        from backend.src.tool_server.tools.shell.shell_init import ShellInit
        
        tool = ShellInit(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "new_session"
        })
        
        mock_terminal_manager.create_session.assert_called_once()
        assert result.is_error is False or result.is_error is None


class TestShellView:
    """Test ShellView tool."""

    @pytest.fixture
    def mock_terminal_manager(self):
        """Create a mock terminal manager."""
        manager = MagicMock()
        manager.get_all_sessions.return_value = ["main"]
        manager.get_session_output.return_value = MockCommandOutput(
            clean_output="$ echo hello\nhello\n$",
            ansi_output="$ echo hello\nhello\n$"
        )
        return manager

    @pytest.mark.asyncio
    async def test_shell_view_returns_output(self, mock_terminal_manager):
        """Test that ShellView returns session output."""
        from backend.src.tool_server.tools.shell.shell_view import ShellView
        
        tool = ShellView(mock_terminal_manager)
        
        result = await tool.execute({
            "session_name": "main"
        })
        
        mock_terminal_manager.get_session_output.assert_called_once_with("main")
        assert "echo hello" in result.llm_content


class TestShellList:
    """Test ShellList tool."""

    @pytest.fixture
    def mock_terminal_manager(self):
        """Create a mock terminal manager."""
        manager = MagicMock()
        manager.get_all_sessions.return_value = ["main", "dev", "test"]
        return manager

    @pytest.mark.asyncio
    async def test_shell_list_returns_sessions(self, mock_terminal_manager):
        """Test that ShellList returns all sessions."""
        from backend.src.tool_server.tools.shell.shell_list import ShellList
        
        tool = ShellList(mock_terminal_manager)
        
        result = await tool.execute({})
        
        assert "main" in result.llm_content
        assert "dev" in result.llm_content
        assert "test" in result.llm_content


class TestShellStopCommand:
    """Test ShellStopCommand tool."""

    @pytest.fixture
    def mock_terminal_manager(self):
        """Create a mock terminal manager."""
        manager = MagicMock()
        manager.get_all_sessions.return_value = ["main"]
        manager.stop_current_command.return_value = MockCommandOutput(
            clean_output="Command stopped",
            ansi_output="Command stopped"
        )
        return manager

    @pytest.mark.asyncio
    async def test_shell_stop_command(self, mock_terminal_manager):
        """Test stopping a running command."""
        from backend.src.tool_server.tools.shell.shell_stop_command import ShellStopCommand
        
        tool = ShellStopCommand(mock_terminal_manager)
        
        result = await tool.execute({
            "session_name": "main"
        })
        
        mock_terminal_manager.stop_current_command.assert_called_once_with("main")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
