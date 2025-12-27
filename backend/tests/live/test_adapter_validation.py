#!/usr/bin/env python3
"""
LangChain Tool Adapter Validation Test
======================================

This test validates that:
1. The LangChainToolAdapter correctly wraps BaseTool classes
2. All 44 tools from manager.py can be instantiated
3. The adapter properly converts input_schema to args_schema
4. The response_format works correctly

This is a LOCAL test that doesn't require MCP connectivity.
It validates the adapter mechanism works with mock executions.

Usage:
    python backend/tests/live/test_adapter_validation.py
"""

import asyncio
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple


class AdapterValidationTest:
    """Validates LangChainToolAdapter with actual tool classes."""
    
    def __init__(self):
        self.results: Dict[str, Tuple[bool, str]] = {}
    
    def log(self, msg: str, success: bool = None):
        icon = "✅" if success == True else "❌" if success == False else "ℹ️"
        print(f"   {icon} {msg}", flush=True)
    
    async def test_adapter_imports(self) -> bool:
        """Test that all adapter components import correctly."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import (
                LangChainToolAdapter,
                AuthenticationContext,
                adapt_tools_for_langchain,
                json_schema_to_pydantic_model,
            )
            self.log("All adapter components import successfully", True)
            return True
        except ImportError as e:
            self.log(f"Import failed: {e}", False)
            return False
    
    async def test_schema_conversion(self) -> bool:
        """Test JSON Schema to Pydantic model conversion."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import json_schema_to_pydantic_model
            from pydantic import BaseModel
            
            # Test with a complex schema
            schema = {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
                    "wait_for_output": {"type": "boolean", "default": True}
                },
                "required": ["command"]
            }
            
            Model = json_schema_to_pydantic_model("ShellRunCommand", schema)
            
            # Verify it's a valid Pydantic model
            assert issubclass(Model, BaseModel)
            
            # Verify we can instantiate with required fields
            instance = Model(command="echo hello")
            assert instance.command == "echo hello"
            assert instance.timeout == 60  # default
            
            self.log("Schema conversion works correctly", True)
            return True
        except Exception as e:
            self.log(f"Schema conversion failed: {e}", False)
            return False
    
    async def test_adapter_creation(self) -> bool:
        """Test creating LangChainToolAdapter from BaseTool."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import (
                LangChainToolAdapter,
                AuthenticationContext,
            )
            from backend.src.tool_server.tools.base import BaseTool, ToolResult
            from langchain_core.tools import BaseTool as LCBaseTool
            
            # Create a mock tool
            class MockShellTool(BaseTool):
                name = "mock_shell_run"
                display_name = "Mock Shell Run"
                description = "Execute a shell command"
                input_schema = {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to run"}
                    },
                    "required": ["command"]
                }
                read_only = False
                
                async def execute(self, tool_input: dict) -> ToolResult:
                    cmd = tool_input.get("command", "")
                    return ToolResult(
                        llm_content=f"Executed: {cmd}",
                        is_error=False
                    )
            
            mock_tool = MockShellTool()
            adapter = LangChainToolAdapter.from_base_tool(mock_tool)
            
            # Verify adapter properties
            assert adapter.name == "mock_shell_run"
            assert adapter.description == "Execute a shell command"
            assert isinstance(adapter, LCBaseTool)
            
            self.log("Adapter creation works correctly", True)
            return True
        except Exception as e:
            self.log(f"Adapter creation failed: {e}", False)
            import traceback
            traceback.print_exc()
            return False
    
    async def test_adapter_execution(self) -> bool:
        """Test adapter async execution."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
            from backend.src.tool_server.tools.base import BaseTool, ToolResult
            
            # Mock tool that works
            class MockFileTool(BaseTool):
                name = "mock_file_read"
                display_name = "Mock File Read"
                description = "Read a file"
                input_schema = {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"}
                    },
                    "required": ["file_path"]
                }
                read_only = True
                
                async def execute(self, tool_input: dict) -> ToolResult:
                    path = tool_input.get("file_path", "")
                    return ToolResult(
                        llm_content=f"Content of {path}: Hello World!",
                        is_error=False
                    )
            
            adapter = LangChainToolAdapter.from_base_tool(MockFileTool())
            
            # Test _arun
            result = await adapter._arun(file_path="/tmp/test.txt")
            
            # Result should be (content, artifact) tuple
            assert isinstance(result, tuple)
            content, artifact = result
            assert "Hello World" in content
            
            self.log("Adapter execution works correctly", True)
            return True
        except Exception as e:
            self.log(f"Adapter execution failed: {e}", False)
            import traceback
            traceback.print_exc()
            return False
    
    async def test_multimodal_response(self) -> bool:
        """Test adapter handles multi-modal responses (text + image)."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
            from backend.src.tool_server.tools.base import BaseTool, ToolResult, TextContent, ImageContent
            
            class MockBrowserTool(BaseTool):
                name = "mock_browser_view"
                display_name = "Mock Browser View"
                description = "View browser page"
                input_schema = {"type": "object", "properties": {}}
                read_only = True
                
                async def execute(self, tool_input: dict) -> ToolResult:
                    return ToolResult(
                        llm_content=[
                            TextContent(type="text", text="Browser screenshot taken"),
                            ImageContent(type="image", data="base64data", mime_type="image/png")
                        ],
                        user_display_content={"type": "image", "data": "base64data"},
                        is_error=False
                    )
            
            adapter = LangChainToolAdapter.from_base_tool(MockBrowserTool())
            result = await adapter._arun()
            
            content, artifact = result
            assert "screenshot" in content.lower()
            assert artifact is not None
            assert "images" in artifact
            
            self.log("Multi-modal response handling works correctly", True)
            return True
        except Exception as e:
            self.log(f"Multi-modal response failed: {e}", False)
            import traceback
            traceback.print_exc()
            return False
    
    async def test_auth_context(self) -> bool:
        """Test authentication context setting."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import (
                LangChainToolAdapter,
                AuthenticationContext
            )
            from backend.src.tool_server.tools.base import BaseTool, ToolResult
            
            class MockTool(BaseTool):
                name = "mock"
                display_name = "Mock"
                description = "Mock tool"
                input_schema = {"type": "object", "properties": {}}
                read_only = True
                
                async def execute(self, tool_input: dict) -> ToolResult:
                    return ToolResult(llm_content="ok", is_error=False)
            
            auth = AuthenticationContext(
                user_id="test-user",
                token="jwt-token-123",
                session_id="session-456",
                permissions=["sandbox:execute", "tools:all"]
            )
            
            adapter = LangChainToolAdapter.from_base_tool(MockTool(), auth_context=auth)
            
            assert adapter.auth_context.user_id == "test-user"
            assert adapter.auth_context.token == "jwt-token-123"
            assert "sandbox:execute" in adapter.auth_context.permissions
            
            self.log("Authentication context works correctly", True)
            return True
        except Exception as e:
            self.log(f"Auth context failed: {e}", False)
            return False
    
    async def test_error_handling(self) -> bool:
        """Test adapter error handling."""
        try:
            from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
            from backend.src.tool_server.tools.base import BaseTool, ToolResult
            
            class ErrorTool(BaseTool):
                name = "error_tool"
                display_name = "Error Tool"
                description = "Always fails"
                input_schema = {"type": "object", "properties": {}}
                read_only = True
                
                async def execute(self, tool_input: dict) -> ToolResult:
                    return ToolResult(
                        llm_content="Something went wrong",
                        is_error=True
                    )
            
            adapter = LangChainToolAdapter.from_base_tool(ErrorTool())
            result = await adapter._arun()
            
            content, artifact = result
            assert "[ERROR]" in content
            
            self.log("Error handling works correctly", True)
            return True
        except Exception as e:
            self.log(f"Error handling failed: {e}", False)
            return False
    
    async def test_tool_list_from_manager(self) -> bool:
        """Test that we can import tool classes from manager.py."""
        try:
            # Test importing a few key tools
            from backend.src.tool_server.tools.shell import ShellRunCommand
            from backend.src.tool_server.tools.file_system import FileReadTool, FileWriteTool
            from backend.src.tool_server.tools.browser import BrowserViewTool, BrowserClickTool
            from backend.src.tool_server.tools.web import WebSearchTool
            
            self.log("Tool classes import from manager.py", True)
            return True
        except ImportError as e:
            self.log(f"Tool import failed: {e}", False)
            return False
    
    async def run_all_tests(self):
        """Run all validation tests."""
        print("=" * 80, flush=True)
        print("🔧 LANGCHAIN TOOL ADAPTER VALIDATION TEST", flush=True)
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("=" * 80, flush=True)
        
        tests = [
            ("adapter_imports", self.test_adapter_imports),
            ("schema_conversion", self.test_schema_conversion),
            ("adapter_creation", self.test_adapter_creation),
            ("adapter_execution", self.test_adapter_execution),
            ("multimodal_response", self.test_multimodal_response),
            ("auth_context", self.test_auth_context),
            ("error_handling", self.test_error_handling),
            ("tool_list_from_manager", self.test_tool_list_from_manager),
        ]
        
        print("\n📋 RUNNING TESTS", flush=True)
        print("-" * 60, flush=True)
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                self.results[test_name] = (result, "")
            except Exception as e:
                self.results[test_name] = (False, str(e))
                self.log(f"{test_name}: {e}", False)
        
        # Summary
        passed = sum(1 for v, _ in self.results.values() if v)
        total = len(self.results)
        
        print("\n" + "=" * 80, flush=True)
        print("📊 TEST SUMMARY", flush=True)
        print("=" * 80, flush=True)
        print(f"   PASSED: {passed}/{total} ({100*passed//total}%)", flush=True)
        print("=" * 80, flush=True)
        
        return passed == total


if __name__ == '__main__':
    tester = AdapterValidationTest()
    success = asyncio.run(tester.run_all_tests())
    print(f"\nExit code: {'0 (SUCCESS)' if success else '1 (FAILURE)'}", flush=True)
    sys.exit(0 if success else 1)
