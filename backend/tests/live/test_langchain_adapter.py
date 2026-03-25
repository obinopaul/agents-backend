#!/usr/bin/env python3
"""
LangChain Adapter Test Suite

This comprehensive test validates the LangChainToolAdapter integration:
1. Unit tests for adapter functionality
2. Integration tests with actual sandbox
3. Multi-modal response handling (text + images)
4. JWT authentication context support

Prerequisites:
- Backend server running: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
- Test user created: python backend/tests/live/create_test_user.py

Usage:
    cd backend/tests/live
    python test_langchain_adapter.py
"""

import asyncio
import httpx
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# LangChain imports
from langchain_core.tools import BaseTool as LangChainBaseTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class TestResult:
    """Simple test result tracker."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, name: str):
        self.passed += 1
        print(f"  ✅ {name}")
    
    def add_fail(self, name: str, error: str):
        self.failed += 1
        self.errors.append((name, error))
        print(f"  ❌ {name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\nResults: {self.passed}/{total} passed")
        if self.errors:
            print("\nFailures:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


# =============================================================================
# UNIT TESTS - Test adapter without sandbox
# =============================================================================

def test_json_schema_to_pydantic():
    """Test JSON Schema to Pydantic model conversion."""
    results = TestResult()
    
    try:
        from backend.src.tool_server.tools.langchain_adapter import json_schema_to_pydantic_model
        
        # Test 1: Simple schema
        schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 60
                }
            },
            "required": ["command"]
        }
        
        Model = json_schema_to_pydantic_model("TestTool", schema)
        
        # Validate the model was created correctly
        assert issubclass(Model, BaseModel), "Model should be a Pydantic BaseModel"
        results.add_pass("Created Pydantic model from schema")
        
        # Test 2: Validate required field
        try:
            instance = Model(command="echo hello")
            assert instance.command == "echo hello"
            assert instance.timeout == 60  # default value
            results.add_pass("Model validates required and default fields")
        except Exception as e:
            results.add_fail("Model validation", str(e))
        
        # Test 3: Optional fields without default become None
        schema2 = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path"},
                "limit": {"type": "integer", "description": "Line limit"}
            },
            "required": ["file_path"]
        }
        
        Model2 = json_schema_to_pydantic_model("ReadTool", schema2)
        instance2 = Model2(file_path="/tmp/test.txt")
        assert instance2.limit is None
        results.add_pass("Optional fields default to None")
        
    except ImportError as e:
        results.add_fail("Import adapter", str(e))
    except Exception as e:
        results.add_fail("Schema conversion", str(e))
    
    return results


def test_adapter_creation():
    """Test LangChainToolAdapter creation from BaseTool."""
    results = TestResult()
    
    try:
        from backend.src.tool_server.tools.langchain_adapter import (
            LangChainToolAdapter,
            AuthenticationContext
        )
        from backend.src.tool_server.tools.base import BaseTool, ToolResult
        
        # Create a mock tool for testing
        class MockTool(BaseTool):
            name = "mock_tool"
            display_name = "Mock Tool"
            description = "A mock tool for testing"
            input_schema = {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo"}
                },
                "required": ["message"]
            }
            read_only = True
            
            async def execute(self, tool_input: Dict[str, Any]) -> ToolResult:
                return ToolResult(
                    llm_content=f"Echo: {tool_input.get('message', '')}",
                    is_error=False
                )
        
        mock_tool = MockTool()
        
        # Test 1: Create adapter
        adapter = LangChainToolAdapter.from_base_tool(mock_tool)
        
        assert adapter.name == "mock_tool"
        assert adapter.description == "A mock tool for testing"
        results.add_pass("Adapter created with correct name/description")
        
        # Test 2: Check it's a LangChain tool
        assert isinstance(adapter, LangChainBaseTool)
        results.add_pass("Adapter is a LangChain BaseTool")
        
        # Test 3: args_schema is a Pydantic model
        assert issubclass(adapter.args_schema, BaseModel)
        results.add_pass("Adapter has Pydantic args_schema")
        
        # Test 4: response_format is content_and_artifact
        assert adapter.response_format == "content_and_artifact"
        results.add_pass("Response format is content_and_artifact")
        
        # Test 5: Auth context
        auth = AuthenticationContext(
            user_id="test-user",
            token="test-token-123"
        )
        adapter.set_auth_context(auth)
        assert adapter.auth_context.user_id == "test-user"
        results.add_pass("Auth context set correctly")
        
    except Exception as e:
        results.add_fail("Adapter creation", str(e))
        import traceback
        traceback.print_exc()
    
    return results


async def test_adapter_execution():
    """Test adapter async execution."""
    results = TestResult()
    
    try:
        from backend.src.tool_server.tools.langchain_adapter import LangChainToolAdapter
        from backend.src.tool_server.tools.base import BaseTool, ToolResult, TextContent, ImageContent
        
        # Test 1: Simple text response
        class TextTool(BaseTool):
            name = "text_tool"
            display_name = "Text Tool"
            description = "Returns text"
            input_schema = {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
            read_only = True
            
            async def execute(self, tool_input: Dict[str, Any]) -> ToolResult:
                return ToolResult(
                    llm_content=f"Result: {tool_input.get('query')}",
                    is_error=False
                )
        
        text_adapter = LangChainToolAdapter.from_base_tool(TextTool())
        result = await text_adapter._arun(query="test query")
        
        content, artifact = result
        assert "Result: test query" in content
        results.add_pass("Text response handled correctly")
        
        # Test 2: Multi-modal response (text + image)
        class ImageTool(BaseTool):
            name = "image_tool"
            display_name = "Image Tool"
            description = "Returns image"
            input_schema = {
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"]
            }
            read_only = True
            
            async def execute(self, tool_input: Dict[str, Any]) -> ToolResult:
                return ToolResult(
                    llm_content=[
                        TextContent(type="text", text="Image generated"),
                        ImageContent(type="image", data="base64data", mime_type="image/png")
                    ],
                    is_error=False
                )
        
        image_adapter = LangChainToolAdapter.from_base_tool(ImageTool())
        result = await image_adapter._arun(prompt="test image")
        
        content, artifact = result
        assert "Image generated" in content
        assert artifact is not None
        assert "images" in artifact
        assert len(artifact["images"]) == 1
        results.add_pass("Multi-modal response handled correctly")
        
        # Test 3: Error response
        class ErrorTool(BaseTool):
            name = "error_tool"
            display_name = "Error Tool"
            description = "Always errors"
            input_schema = {"type": "object", "properties": {}}
            read_only = True
            
            async def execute(self, tool_input: Dict[str, Any]) -> ToolResult:
                return ToolResult(
                    llm_content="Something went wrong",
                    is_error=True
                )
        
        error_adapter = LangChainToolAdapter.from_base_tool(ErrorTool())
        result = await error_adapter._arun()
        
        content, artifact = result
        assert "[ERROR]" in content
        results.add_pass("Error response formatted correctly")
        
    except Exception as e:
        results.add_fail("Adapter execution", str(e))
        import traceback
        traceback.print_exc()
    
    return results


# =============================================================================
# INTEGRATION TESTS - Test with actual sandbox
# =============================================================================

async def setup_sandbox() -> tuple[str, str]:
    """Login and create sandbox, return (token, sandbox_id)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Login
        r = await client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code != 200:
            raise Exception(f"Login failed: {r.status_code} - {r.text}")
        token = r.json().get('access_token')
        
        # Create sandbox
        client.headers['Authorization'] = f'Bearer {token}'
        r = await client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'langchain-adapter-test'}
        )
        if r.status_code != 200:
            raise Exception(f"Sandbox creation failed: {r.status_code} - {r.text}")
        sandbox_id = r.json().get('data', {}).get('sandbox_id')
        
        return token, sandbox_id


async def cleanup_sandbox(token: str, sandbox_id: str):
    """Delete sandbox when done."""
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={'Authorization': f'Bearer {token}'}
    ) as client:
        await client.delete(f'{BASE_URL}/agent/sandboxes/sandboxes/{sandbox_id}')


async def test_with_langchain_agent():
    """Integration test: run LangChain agent with adapted tools."""
    results = TestResult()
    
    token = None
    sandbox_id = None
    
    try:
        # Step 1: Import backend LLM
        try:
            from backend.src.llms.llm import get_llm
            llm = get_llm()
            results.add_pass("Backend LLM loaded")
        except ImportError:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            results.add_pass("Fallback OpenAI LLM loaded")
        
        # Step 2: Setup sandbox
        print("\n  Creating sandbox (this may take 30-60s)...")
        token, sandbox_id = await setup_sandbox()
        results.add_pass(f"Sandbox created: {sandbox_id[:8]}...")
        
        await asyncio.sleep(5)  # Wait for services
        
        # Step 3: Create REST API tools (since we're outside sandbox)
        # The LangChainToolAdapter is for inside-sandbox use
        # For external use, we use the @tool pattern from run_langchain_agent.py
        from langchain_core.tools import tool
        
        client = httpx.Client(
            timeout=60.0,
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'AdapterTest/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        sid = sandbox_id
        
        @tool
        def run_command(command: str) -> str:
            """Execute a shell command in the sandbox."""
            r = client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                json={'sandbox_id': sid, 'command': command}
            )
            if r.status_code == 200:
                return r.json().get('data', {}).get('output', '')
            return f"Error: {r.status_code}"
        
        @tool
        def write_file(file_path: str, content: str) -> str:
            """Write content to a file."""
            r = client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
                json={'sandbox_id': sid, 'file_path': file_path, 'content': content}
            )
            return "File written" if r.status_code == 200 else f"Error: {r.status_code}"
        
        @tool
        def read_file(file_path: str) -> str:
            """Read content from a file."""
            r = client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
                json={'sandbox_id': sid, 'file_path': file_path}
            )
            if r.status_code == 200:
                return r.json().get('data', {}).get('content', '')
            return f"Error: {r.status_code}"
        
        tools = [run_command, write_file, read_file]
        results.add_pass(f"Created {len(tools)} REST API tools")
        
        # Step 4: Create agent
        agent = create_react_agent(llm, tools)
        results.add_pass("LangGraph agent created")
        
        # Step 5: Run simple task
        task = "Create a file at /tmp/hello.txt with content 'Hello from LangChain!', then read it back to verify."
        
        print("\n  Running agent task...")
        agent_result = await agent.ainvoke({
            "messages": [{"role": "user", "content": task}]
        })
        
        # Check that messages were generated
        messages = agent_result.get("messages", [])
        assert len(messages) > 2, "Agent should produce messages"
        results.add_pass("Agent executed task successfully")
        
        # Verify the file was created
        verify_result = client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
            json={'sandbox_id': sandbox_id, 'file_path': '/tmp/hello.txt'}
        )
        if verify_result.status_code == 200:
            content = verify_result.json().get('data', {}).get('content', '')
            if 'Hello from LangChain!' in content:
                results.add_pass("File content verified")
            else:
                results.add_fail("File verification", f"Content mismatch: {content}")
        else:
            results.add_fail("File verification", f"Read failed: {verify_result.status_code}")
        
        client.close()
        
    except Exception as e:
        results.add_fail("Integration test", str(e))
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if token and sandbox_id:
            await cleanup_sandbox(token, sandbox_id)
            print("  ✓ Sandbox cleaned up")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Run all tests."""
    print("=" * 70)
    print("🧪 LangChain Adapter Test Suite")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    all_passed = True
    
    # Unit Tests
    print("\n📋 Unit Tests: JSON Schema to Pydantic")
    print("-" * 50)
    r1 = test_json_schema_to_pydantic()
    all_passed = all_passed and r1.summary()
    
    print("\n📋 Unit Tests: Adapter Creation")
    print("-" * 50)
    r2 = test_adapter_creation()
    all_passed = all_passed and r2.summary()
    
    print("\n📋 Unit Tests: Adapter Execution")
    print("-" * 50)
    r3 = await test_adapter_execution()
    all_passed = all_passed and r3.summary()
    
    # Integration Test (optional - requires server)
    print("\n" + "=" * 70)
    print("📋 Integration Test: LangChain Agent with Sandbox")
    print("-" * 50)
    
    try:
        # Check if server is running
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f'{BASE_URL}/health')
            if r.status_code != 200:
                raise Exception("Server not healthy")
        
        r4 = await test_with_langchain_agent()
        all_passed = all_passed and r4.summary()
        
    except Exception as e:
        print(f"  ⚠️ Skipping integration test: {e}")
        print("  (Start server with: python -m uvicorn backend.main:app --port 8000)")
    
    # Final Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print("=" * 70)
    
    return all_passed


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
