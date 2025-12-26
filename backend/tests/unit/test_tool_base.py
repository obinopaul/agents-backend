"""
Unit tests for BaseTool and tool utilities.

Tests the abstract tool base class, ToolResult, and MCP wrapper functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestToolResult:
    """Test ToolResult model."""

    def test_tool_result_creation_string_content(self):
        """Test creating ToolResult with string content."""
        from backend.src.tool_server.tools.base import ToolResult
        
        result = ToolResult(
            llm_content="test output",
            user_display_content="display output",
            is_error=False
        )
        
        assert result.llm_content == "test output"
        assert result.user_display_content == "display output"
        assert result.is_error is False
        assert result.is_interrupted is False

    def test_tool_result_with_error(self):
        """Test creating ToolResult with error."""
        from backend.src.tool_server.tools.base import ToolResult
        
        result = ToolResult(
            llm_content="Error: something failed",
            is_error=True
        )
        
        assert result.is_error is True

    def test_tool_result_with_list_content(self):
        """Test creating ToolResult with list content."""
        from backend.src.tool_server.tools.base import ToolResult, TextContent, ImageContent
        
        result = ToolResult(
            llm_content=[
                TextContent(type="text", text="some text"),
                ImageContent(type="image", data="base64data", mime_type="image/png")
            ]
        )
        
        assert len(result.llm_content) == 2
        assert result.llm_content[0].type == "text"
        assert result.llm_content[1].type == "image"


class TestTextContent:
    """Test TextContent model."""

    def test_text_content_creation(self):
        """Test creating TextContent."""
        from backend.src.tool_server.tools.base import TextContent
        
        content = TextContent(type="text", text="Hello world")
        
        assert content.type == "text"
        assert content.text == "Hello world"


class TestImageContent:
    """Test ImageContent model."""

    def test_image_content_creation(self):
        """Test creating ImageContent."""
        from backend.src.tool_server.tools.base import ImageContent
        
        content = ImageContent(
            type="image",
            data="aGVsbG8gd29ybGQ=",  # base64 encoded
            mime_type="image/png"
        )
        
        assert content.type == "image"
        assert content.mime_type == "image/png"


class TestToolParam:
    """Test ToolParam model."""

    def test_tool_param_function_type(self):
        """Test creating function-type ToolParam."""
        from backend.src.tool_server.tools.base import ToolParam
        
        param = ToolParam(
            type="function",
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}}
        )
        
        assert param.type == "function"
        assert param.name == "test_tool"

    def test_tool_param_custom_type(self):
        """Test creating custom-type ToolParam."""
        from backend.src.tool_server.tools.base import ToolParam
        
        param = ToolParam(
            type="custom",
            name="custom_tool",
            description="A custom tool",
            input_schema={"custom": "format"}
        )
        
        assert param.type == "custom"


class TestBaseTool:
    """Test BaseTool abstract class functionality."""

    def test_should_confirm_execute_default(self):
        """Test that default should_confirm_execute returns False."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        # Create a concrete implementation for testing
        class TestTool(BaseTool):
            name = "test"
            description = "test"
            input_schema = {}
            read_only = True
            display_name = "Test"
            
            async def execute(self, tool_input):
                return ToolResult(llm_content="test")
        
        tool = TestTool()
        result = tool.should_confirm_execute({})
        
        assert result is False

    def test_get_tool_params_function(self):
        """Test get_tool_params returns correct ToolParam for function tool."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class TestTool(BaseTool):
            name = "my_tool"
            description = "My description"
            input_schema = {"type": "object", "properties": {"arg": {"type": "string"}}}
            read_only = True
            display_name = "My Tool"
            metadata = None
            
            async def execute(self, tool_input):
                return ToolResult(llm_content="test")
        
        tool = TestTool()
        params = tool.get_tool_params()
        
        assert params.type == "function"
        assert params.name == "my_tool"
        assert params.description == "My description"

    def test_get_tool_params_custom_with_metadata(self):
        """Test get_tool_params returns custom type when metadata is set."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class TestTool(BaseTool):
            name = "custom_tool"
            description = "Custom description"
            input_schema = {}
            read_only = True
            display_name = "Custom Tool"
            metadata = {"format": {"special": "format"}}
            
            async def execute(self, tool_input):
                return ToolResult(llm_content="test")
        
        tool = TestTool()
        params = tool.get_tool_params()
        
        assert params.type == "custom"


class TestMCPWrapper:
    """Test BaseTool MCP wrapper functionality."""

    @pytest.mark.asyncio
    async def test_mcp_wrapper_text_content(self):
        """Test _mcp_wrapper converts string to MCP TextContent."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class TestTool(BaseTool):
            name = "test"
            description = "test"
            input_schema = {}
            read_only = True
            display_name = "Test"
            
            async def execute(self, tool_input):
                return ToolResult(llm_content="Hello from tool")
        
        tool = TestTool()
        result = await tool._mcp_wrapper({})
        
        # The result should be a FastMCPToolResult with content
        assert result is not None
        assert hasattr(result, 'content')
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_mcp_wrapper_image_content(self):
        """Test _mcp_wrapper converts ImageContent to MCP format."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult, ImageContent, TextContent
        
        class TestTool(BaseTool):
            name = "test"
            description = "test"
            input_schema = {}
            read_only = True
            display_name = "Test"
            
            async def execute(self, tool_input):
                return ToolResult(
                    llm_content=[
                        TextContent(type="text", text="Caption"),
                        ImageContent(type="image", data="base64data", mime_type="image/png")
                    ]
                )
        
        tool = TestTool()
        result = await tool._mcp_wrapper({})
        
        # Verify the result contains both text and image
        assert result is not None
        assert hasattr(result, 'content')


class TestToolConfirmationDetails:
    """Test ToolConfirmationDetails model."""

    def test_confirmation_details_edit(self):
        """Test creating edit confirmation details."""
        from backend.src.tool_server.tools.base import ToolConfirmationDetails
        
        details = ToolConfirmationDetails(
            type="edit",
            message="Editing file.txt"
        )
        
        assert details.type == "edit"
        assert "Editing" in details.message

    def test_confirmation_details_bash(self):
        """Test creating bash confirmation details."""
        from backend.src.tool_server.tools.base import ToolConfirmationDetails
        
        details = ToolConfirmationDetails(
            type="bash",
            message="Running: rm -rf /tmp/test"
        )
        
        assert details.type == "bash"

    def test_confirmation_details_mcp(self):
        """Test creating MCP confirmation details."""
        from backend.src.tool_server.tools.base import ToolConfirmationDetails
        
        details = ToolConfirmationDetails(
            type="mcp",
            message="Calling external MCP tool"
        )
        
        assert details.type == "mcp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
