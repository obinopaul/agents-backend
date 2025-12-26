#!/usr/bin/env python3
"""
Standalone Tool Test - Tests tools directly without MCP server

This script tests the tool_server tools directly (not via MCP)
to verify they work correctly. It's useful for debugging when
the MCP server is not running.

Usage:
    cd backend
    python tests/live/test_tools_direct.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv

# Load environment variables
env_path = backend_path / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"Warning: No .env file found at {env_path}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Helpers
# ============================================================================

def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"🧪 {title}")
    print("=" * 60)


def print_result(success: bool, message: str):
    """Print a test result."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


# ============================================================================
# Direct Tool Tests
# ============================================================================

async def test_tool_manager_import():
    """Test that tool manager can be imported."""
    print_header("Testing Tool Manager Import")
    
    try:
        from src.tool_server.tools.manager import get_sandbox_tools, get_common_tools
        print_result(True, "Tool manager imported successfully")
        return True
    except ImportError as e:
        print_result(False, f"Import error: {e}")
        return False


async def test_get_sandbox_tools():
    """Test getting sandbox tools."""
    print_header("Testing get_sandbox_tools()")
    
    from src.tool_server.tools.manager import get_sandbox_tools
    
    credential = {
        "user_api_key": os.getenv("OPENAI_API_KEY", "test"),
        "session_id": "test-session"
    }
    
    try:
        tools = get_sandbox_tools(
            workspace_path="/tmp/test_workspace",
            credential=credential
        )
        print_result(True, f"Got {len(tools)} sandbox tools")
        
        # List tool categories
        shell_tools = [t for t in tools if "bash" in t.name.lower() or "shell" in t.name.lower()]
        file_tools = [t for t in tools if "file" in t.name.lower() or "read" in t.name.lower() or "write" in t.name.lower()]
        browser_tools = [t for t in tools if "browser" in t.name.lower()]
        web_tools = [t for t in tools if "search" in t.name.lower() or "web" in t.name.lower()]
        
        print(f"   Shell tools: {len(shell_tools)}")
        print(f"   File tools: {len(file_tools)}")
        print(f"   Browser tools: {len(browser_tools)}")
        print(f"   Web tools: {len(web_tools)}")
        
        # List all tool names
        print("\n   All tools:")
        for tool in tools:
            print(f"     - {tool.name}: {tool.description[:40]}...")
        
        return tools
    except Exception as e:
        print_result(False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_tool_base_classes():
    """Test BaseTool and ToolResult."""
    print_header("Testing Tool Base Classes")
    
    from src.tool_server.tools.base import BaseTool, ToolResult, TextContent, ImageContent
    
    # Test ToolResult creation
    result = ToolResult(llm_content="Test output", is_error=False)
    print_result(True, f"Created ToolResult: {result.llm_content[:30]}")
    
    # Test with list content
    result_list = ToolResult(
        llm_content=[
            TextContent(type="text", text="Caption"),
            ImageContent(type="image", data="base64data", mime_type="image/png")
        ]
    )
    print_result(True, f"Created ToolResult with list content ({len(result_list.llm_content)} items)")
    
    return True


async def test_shell_tool_execute():
    """Test ShellRunCommand tool execution."""
    print_header("Testing ShellRunCommand Tool")
    
    from src.tool_server.tools.manager import get_sandbox_tools
    
    credential = {
        "user_api_key": "test",
        "session_id": "test-session"
    }
    
    tools = get_sandbox_tools("/tmp/test_workspace", credential)
    
    # Find the Bash/shell tool
    shell_tool = None
    for tool in tools:
        if tool.name.lower() == "bash" or "shell" in tool.name.lower():
            shell_tool = tool
            break
    
    if not shell_tool:
        print_result(False, "No shell tool found")
        return False
    
    print(f"   Found shell tool: {shell_tool.name}")
    print(f"   Description: {shell_tool.description[:50]}...")
    print(f"   Input schema: {list(shell_tool.input_schema.get('properties', {}).keys())}")
    
    # Try to execute (this may fail if terminal manager isn't set up)
    try:
        result = await shell_tool.execute({
            "command": "echo 'Hello from direct tool test'",
            "description": "Test echo",
            "session_name": "test"
        })
        print_result(True, f"Shell execution result: {result.llm_content[:50]}...")
        return True
    except Exception as e:
        print_result(False, f"Execution error (expected if no terminal): {e}")
        return False


async def test_file_tool_schema():
    """Test file tool schema."""
    print_header("Testing File Tool Schema")
    
    from src.tool_server.tools.manager import get_sandbox_tools
    
    credential = {"user_api_key": "test", "session_id": "test"}
    tools = get_sandbox_tools("/tmp/test_workspace", credential)
    
    # Find file tools
    file_tools = [t for t in tools if "read" in t.name.lower() or "write" in t.name.lower() or "file" in t.name.lower()]
    
    print(f"   Found {len(file_tools)} file-related tools:")
    for tool in file_tools[:5]:
        print(f"     - {tool.name}")
        props = tool.input_schema.get("properties", {})
        print(f"       Parameters: {list(props.keys())}")
    
    return len(file_tools) > 0


async def test_web_search_tool():
    """Test web search tool."""
    print_header("Testing Web Search Tool")
    
    from src.tool_server.tools.manager import get_sandbox_tools
    
    credential = {
        "user_api_key": os.getenv("OPENAI_API_KEY", "test"),
        "session_id": "test"
    }
    tools = get_sandbox_tools("/tmp/test_workspace", credential)
    
    # Find web search tool
    search_tool = None
    for tool in tools:
        if "search" in tool.name.lower() and "web" in tool.name.lower():
            search_tool = tool
            break
    
    if not search_tool:
        # Try alternative name
        for tool in tools:
            if "search" in tool.name.lower():
                search_tool = tool
                break
    
    if not search_tool:
        print_result(False, "No search tool found")
        return False
    
    print(f"   Found search tool: {search_tool.name}")
    print(f"   Description: {search_tool.description[:60]}...")
    
    # Check schema
    props = search_tool.input_schema.get("properties", {})
    print(f"   Parameters: {list(props.keys())}")
    
    return True


async def test_browser_tools():
    """Test browser tools."""
    print_header("Testing Browser Tools")
    
    from src.tool_server.tools.manager import get_sandbox_tools
    
    credential = {"user_api_key": "test", "session_id": "test"}
    tools = get_sandbox_tools("/tmp/test_workspace", credential)
    
    # Find browser tools
    browser_tools = [t for t in tools if "browser" in t.name.lower()]
    
    print(f"   Found {len(browser_tools)} browser tools:")
    for tool in browser_tools[:8]:
        print(f"     - {tool.name}: {tool.description[:40]}...")
    
    return len(browser_tools) > 0


async def test_mcp_wrapper():
    """Test MCP wrapper functionality."""
    print_header("Testing MCP Wrapper")
    
    from src.tool_server.tools.base import BaseTool, ToolResult
    
    class TestTool(BaseTool):
        name = "test_tool"
        description = "A test tool"
        input_schema = {"type": "object", "properties": {"msg": {"type": "string"}}}
        read_only = True
        display_name = "Test"
        
        async def execute(self, tool_input):
            return ToolResult(llm_content=f"Echo: {tool_input.get('msg', '')}")
    
    tool = TestTool()
    
    # Test direct execution
    result = await tool.execute({"msg": "Hello"})
    print_result(True, f"Direct execute: {result.llm_content}")
    
    # Test MCP wrapper
    try:
        mcp_result = await tool._mcp_wrapper({"msg": "Hello MCP"})
        print_result(True, f"MCP wrapper result: {type(mcp_result).__name__}")
        print(f"   Content: {mcp_result.content if hasattr(mcp_result, 'content') else mcp_result}")
        return True
    except Exception as e:
        print_result(False, f"MCP wrapper error: {e}")
        return False


# ============================================================================
# Main Test Runner
# ============================================================================

async def main():
    """Main test runner."""
    
    print("\n" + "=" * 70)
    print("🔧 Tool Server Direct Testing (No MCP Server Required)")
    print("=" * 70)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Backend path: {backend_path}")
    print("=" * 70)
    
    results = {}
    
    # Run tests
    results["Import"] = await test_tool_manager_import()
    results["BaseTool"] = await test_tool_base_classes()
    results["SandboxTools"] = bool(await test_get_sandbox_tools())
    results["FileTool"] = await test_file_tool_schema()
    results["WebSearch"] = await test_web_search_tool()
    results["Browser"] = await test_browser_tools()
    results["MCPWrapper"] = await test_mcp_wrapper()
    results["ShellTool"] = await test_shell_tool_execute()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"   {icon} {test_name}")
    
    print("-" * 70)
    print(f"   Passed: {passed}/{total}")
    print("=" * 70)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
