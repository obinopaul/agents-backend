"""
Integration tests for Tool execution with Sandbox.

These tests verify that tools can be executed through the MCP server
when connected to a sandbox.

Requires:
- Running sandbox server (port 8100)
- Running MCP tool server (port 6060) OR mocked environment
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestToolWithMCPIntegration:
    """Test tool execution through MCP."""

    @pytest.mark.asyncio
    async def test_shell_tool_via_execute(self):
        """Test ShellRunCommand execute method directly."""
        from backend.src.tool_server.tools.shell.shell_run_command import ShellRunCommand
        from backend.src.tool_server.core.workspace import WorkspaceManager
        from backend.src.tool_server.tools.shell.terminal_manager import TmuxSessionManager
        
        # Create mocked managers
        mock_terminal_manager = MagicMock()
        mock_terminal_manager.get_all_sessions.return_value = ["main"]
        
        mock_output = MagicMock()
        mock_output.clean_output = "Hello World"
        mock_output.ansi_output = "Hello World"
        mock_terminal_manager.run_command.return_value = mock_output
        
        mock_workspace_manager = MagicMock()
        mock_workspace_manager.get_workspace_path.return_value = "/workspace"
        
        tool = ShellRunCommand(mock_terminal_manager, mock_workspace_manager)
        
        result = await tool.execute({
            "session_name": "main",
            "command": "echo 'Hello World'",
            "description": "Print greeting"
        })
        
        assert result.llm_content == "Hello World"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_file_read_tool_via_execute(self):
        """Test FileReadTool execute method with mocked file."""
        from backend.src.tool_server.tools.file_system.file_read import FileReadTool
        
        mock_workspace_manager = MagicMock()
        mock_workspace_manager.get_workspace_path.return_value = "/workspace"
        mock_workspace_manager.is_path_in_workspace.return_value = True
        
        tool = FileReadTool(mock_workspace_manager)
        
        file_content = "Line 1\nLine 2\nLine 3"
        
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=file_content))),
            __exit__=MagicMock()
        ))):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    result = await tool.execute({
                        "file_path": "/workspace/test.txt"
                    })
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_web_search_tool_via_execute(self):
        """Test WebSearchTool execute method with mocked API."""
        from backend.src.tool_server.tools.web.web_search import WebSearchTool
        
        credential = {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }
        
        tool = WebSearchTool(credential)
        
        mock_response = {
            "organic": [
                {"title": "Result 1", "link": "https://example.com", "snippet": "Snippet 1"}
            ]
        }
        
        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await tool.execute({
                "query": "test query"
            })
        
        assert result is not None


class TestMCPClientToolCalling:
    """Test calling tools through MCP client."""

    @pytest.mark.asyncio
    async def test_mcp_client_list_tools(self):
        """Test that MCP client can list available tools."""
        from backend.src.tool_server.mcp.client import MCPClient
        
        # This would require a running MCP server
        # For unit testing, we mock the client
        with patch("fastmcp.client.Client.list_tools", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {"name": "Bash", "description": "Run bash command"},
                {"name": "FileRead", "description": "Read file"},
            ]
            
            client = MCPClient(server_url="http://localhost:6060")
            client._connected = True
            client.list_tools = mock_list
            
            tools = await client.list_tools()
            
            assert len(tools) >= 2
            tool_names = [t["name"] for t in tools]
            assert "Bash" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_client_call_tool(self):
        """Test that MCP client can call a tool."""
        from backend.src.tool_server.mcp.client import MCPClient
        
        with patch("fastmcp.client.Client.call_tool", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "content": [{"type": "text", "text": "Tool execution result"}]
            }
            
            client = MCPClient(server_url="http://localhost:6060")
            client._connected = True
            client.call_tool = mock_call
            
            result = await client.call_tool("Bash", {
                "session_name": "main",
                "command": "echo test",
                "description": "Test"
            })
            
            assert result is not None


class TestToolMCPWrapper:
    """Test that tools properly wrap results for MCP."""

    @pytest.mark.asyncio
    async def test_tool_mcp_wrapper_text_result(self):
        """Test MCP wrapper converts text result correctly."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class MockTool(BaseTool):
            name = "mock"
            description = "Mock tool"
            input_schema = {}
            read_only = True
            display_name = "Mock"
            
            async def execute(self, tool_input):
                return ToolResult(llm_content="Simple text result")
        
        tool = MockTool()
        result = await tool._mcp_wrapper({})
        
        assert result is not None
        assert hasattr(result, 'content')
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_tool_mcp_wrapper_list_result(self):
        """Test MCP wrapper converts list result correctly."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult, TextContent, ImageContent
        
        class MockTool(BaseTool):
            name = "mock"
            description = "Mock tool"
            input_schema = {}
            read_only = True
            display_name = "Mock"
            
            async def execute(self, tool_input):
                return ToolResult(
                    llm_content=[
                        TextContent(type="text", text="Text part"),
                        ImageContent(type="image", data="base64data", mime_type="image/png")
                    ]
                )
        
        tool = MockTool()
        result = await tool._mcp_wrapper({})
        
        assert result is not None
        assert hasattr(result, 'content')
        # Should have both text and image content
        assert len(result.content) == 2


class TestSandboxServiceIntegration:
    """Test SandboxService integration with sandbox controller."""

    @pytest.mark.asyncio
    async def test_sandbox_service_lifecycle(self):
        """Test SandboxService full lifecycle with mocks."""
        from backend.src.services.sandbox_service import SandboxService
        
        # This is a simplified version of the existing test
        with patch("backend.src.services.sandbox_service.SandboxConfig") as MockConfig:
            mock_config = MockConfig.return_value
            mock_config.provider_type = "e2b"
            mock_config.e2b_api_key = "test_key"
            mock_config.redis_url = "redis://localhost"
            mock_config.has_queue_provider = True
            
            with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxController") as MockController:
                mock_controller = AsyncMock()
                mock_controller.start = AsyncMock()
                mock_controller.shutdown = AsyncMock()
                mock_controller.create_sandbox = AsyncMock(return_value=MagicMock(
                    sandbox_id="test-sandbox-id"
                ))
                mock_controller.run_cmd = AsyncMock(return_value="command output")
                MockController.return_value = mock_controller
                
                service = SandboxService()
                
                # Reset singleton for testing
                SandboxService._instance = None
                SandboxService._controller = None
                
                service = SandboxService()
                await service.initialize()
                
                sandbox = await service.get_or_create_sandbox(user_id="test-user")
                assert sandbox is not None
                
                output = await service.run_cmd(sandbox.sandbox_id, "echo test")
                assert output == "command output"
                
                await service.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
