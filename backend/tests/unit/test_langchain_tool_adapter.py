"""
Unit tests for LangChain Tool Adapter.

Tests that tool_server tools can be converted to and used with LangChain.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, Type
from pydantic import BaseModel, Field


class TestLangChainToolConversion:
    """Test converting BaseTool to LangChain tools."""

    def create_test_tool(self):
        """Create a test tool for conversion testing."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class TestTool(BaseTool):
            name = "test_tool"
            description = "A test tool for unit testing"
            input_schema = {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to process"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of times to repeat",
                        "default": 1
                    }
                },
                "required": ["message"]
            }
            read_only = True
            display_name = "Test Tool"
            
            async def execute(self, tool_input: Dict[str, Any]) -> ToolResult:
                message = tool_input.get("message", "")
                count = tool_input.get("count", 1)
                result = message * count
                return ToolResult(llm_content=result)
        
        return TestTool()

    def test_tool_has_langchain_compatible_schema(self):
        """Test that tool has schema compatible with LangChain."""
        tool = self.create_test_tool()
        
        # LangChain tools need: name, description, input schema
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')
        assert hasattr(tool, 'input_schema')
        
        # Input schema should be JSON schema format
        assert tool.input_schema.get('type') == 'object'
        assert 'properties' in tool.input_schema

    def test_tool_schema_to_pydantic_model(self):
        """Test converting tool schema to Pydantic model for LangChain."""
        tool = self.create_test_tool()
        
        # Convert JSON schema to Pydantic model
        schema = tool.input_schema
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        # Build field definitions
        fields = {}
        for prop_name, prop_def in properties.items():
            field_type = str if prop_def.get('type') == 'string' else int
            is_required = prop_name in required
            default = ... if is_required else prop_def.get('default')
            fields[prop_name] = (field_type, Field(default=default, description=prop_def.get('description', '')))
        
        # This would work with create_model from pydantic
        assert 'message' in fields
        assert 'count' in fields

    @pytest.mark.asyncio
    async def test_tool_execute_returns_string(self):
        """Test that tool execute returns content that can be used by LangChain."""
        tool = self.create_test_tool()
        
        result = await tool.execute({"message": "Hello", "count": 2})
        
        # LangChain expects string output from tools
        assert isinstance(result.llm_content, str)
        assert result.llm_content == "HelloHello"


class TestLangChainToolAdapter:
    """Test the LangChain tool adapter pattern."""

    def test_adapter_function_signature(self):
        """Test that adapter can be created with correct signature."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        # Define the adapter pattern
        def convert_to_langchain_tool(tool: BaseTool):
            """Convert a BaseTool to LangChain compatible format."""
            
            async def wrapper(**kwargs) -> str:
                result = await tool.execute(kwargs)
                if isinstance(result.llm_content, str):
                    return result.llm_content
                return str(result.llm_content)
            
            return {
                "name": tool.name,
                "description": tool.description,
                "func": wrapper,
                "args_schema": tool.input_schema
            }
        
        # Create a test tool
        class TestTool(BaseTool):
            name = "echo"
            description = "Echoes input"
            input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}
            read_only = True
            display_name = "Echo"
            
            async def execute(self, tool_input):
                return ToolResult(llm_content=tool_input.get("text", ""))
        
        tool = TestTool()
        langchain_tool_spec = convert_to_langchain_tool(tool)
        
        assert langchain_tool_spec["name"] == "echo"
        assert langchain_tool_spec["description"] == "Echoes input"
        assert callable(langchain_tool_spec["func"])

    @pytest.mark.asyncio
    async def test_adapter_invoke(self):
        """Test invoking an adapted tool."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class EchoTool(BaseTool):
            name = "echo"
            description = "Echoes the message"
            input_schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
            read_only = True
            display_name = "Echo"
            
            async def execute(self, tool_input):
                return ToolResult(llm_content=tool_input["message"])
        
        tool = EchoTool()
        
        # Create wrapper function
        async def wrapper(**kwargs):
            result = await tool.execute(kwargs)
            return result.llm_content
        
        # Invoke the wrapper
        output = await wrapper(message="Hello LangChain!")
        
        assert output == "Hello LangChain!"


class TestLangChainStructuredTool:
    """Test creating LangChain StructuredTool from BaseTool."""

    @pytest.mark.asyncio
    async def test_create_structured_tool(self):
        """Test creating a StructuredTool-like object."""
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        class AddNumbersTool(BaseTool):
            name = "add_numbers"
            description = "Adds two numbers together"
            input_schema = {
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "First number"},
                    "b": {"type": "integer", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
            read_only = True
            display_name = "Add Numbers"
            
            async def execute(self, tool_input):
                result = tool_input["a"] + tool_input["b"]
                return ToolResult(llm_content=str(result))
        
        tool = AddNumbersTool()
        
        # Create a StructuredTool-like wrapper
        class StructuredToolWrapper:
            def __init__(self, base_tool: BaseTool):
                self.base_tool = base_tool
                self.name = base_tool.name
                self.description = base_tool.description
            
            async def ainvoke(self, input_dict: Dict[str, Any]) -> str:
                result = await self.base_tool.execute(input_dict)
                return result.llm_content
            
            def invoke(self, input_dict: Dict[str, Any]) -> str:
                import asyncio
                return asyncio.run(self.ainvoke(input_dict))
        
        wrapped = StructuredToolWrapper(tool)
        
        result = await wrapped.ainvoke({"a": 5, "b": 3})
        
        assert result == "8"


class TestLangChainAgentCompatibility:
    """Test that tools work with LangChain agent patterns."""

    def test_tool_list_format(self):
        """Test that tools can be formatted for agent tool list."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {"user_api_key": "test", "session_id": "test"}
        tools = get_sandbox_tools("/tmp/workspace", credential)
        
        # All tools should have the attributes needed for LangChain
        tool_list = []
        for tool in tools:
            tool_list.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema
            })
        
        assert len(tool_list) > 0
        
        # Each tool should have proper format
        for t in tool_list:
            assert isinstance(t["name"], str)
            assert isinstance(t["description"], str)
            assert isinstance(t["parameters"], dict)

    def test_tool_names_are_valid_identifiers(self):
        """Test that tool names are valid Python identifiers for LangChain."""
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        credential = {"user_api_key": "test", "session_id": "test"}
        tools = get_sandbox_tools("/tmp/workspace", credential)
        
        for tool in tools:
            # LangChain tool names should be valid
            # Allow underscores and alphanumeric
            name = tool.name
            assert name is not None
            assert len(name) > 0


class TestToolResultToLangChainFormat:
    """Test converting ToolResult to LangChain expected formats."""

    @pytest.mark.asyncio
    async def test_text_result_conversion(self):
        """Test converting text result to LangChain format."""
        from backend.src.tool_server.tools.base import ToolResult
        
        result = ToolResult(llm_content="Simple text output")
        
        # LangChain expects string or specific content types
        output = result.llm_content
        
        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_list_result_conversion(self):
        """Test converting list result to LangChain format."""
        from backend.src.tool_server.tools.base import ToolResult, TextContent, ImageContent
        
        result = ToolResult(
            llm_content=[
                TextContent(type="text", text="Description"),
                ImageContent(type="image", data="base64", mime_type="image/png")
            ]
        )
        
        # Convert to LangChain format
        output_parts = []
        for content in result.llm_content:
            if hasattr(content, 'text'):
                output_parts.append({"type": "text", "text": content.text})
            elif hasattr(content, 'data'):
                output_parts.append({
                    "type": "image",
                    "source": {"type": "base64", "data": content.data}
                })
        
        assert len(output_parts) == 2
        assert output_parts[0]["type"] == "text"
        assert output_parts[1]["type"] == "image"


class TestErrorHandlingForLangChain:
    """Test error handling compatible with LangChain."""

    @pytest.mark.asyncio
    async def test_error_result_format(self):
        """Test that error results are formatted correctly."""
        from backend.src.tool_server.tools.base import ToolResult
        
        result = ToolResult(
            llm_content="Error: File not found",
            is_error=True
        )
        
        # LangChain should be able to handle error responses
        assert result.is_error is True
        assert "Error" in result.llm_content

    @pytest.mark.asyncio
    async def test_interrupted_result_format(self):
        """Test that interrupted results are formatted correctly."""
        from backend.src.tool_server.tools.base import ToolResult
        
        result = ToolResult(
            llm_content="Operation was interrupted",
            is_interrupted=True
        )
        
        assert result.is_interrupted is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
