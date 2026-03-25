"""
Test script: Connect to a real MCP server and examine actual tool output formats.

This script:
1. Connects to the MCP server via HTTP transport
2. Lists all available tools
3. Runs several tools (bash, filesystem, etc.)
4. Prints the EXACT output at every level:
   - Raw MCP CallToolResult
   - After langchain-mcp-adapters conversion (_convert_call_tool_result)
   - The ToolMessage object that LangChain creates
   - What astream_events would emit for on_tool_end

Usage:
    python -m backend.tests.manual.test_mcp_tool_outputs
"""

import asyncio
import json
import sys
from pprint import pprint

# MCP SDK
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent, CallToolResult

# LangChain MCP Adapters
from langchain_mcp_adapters.tools import (
    _convert_call_tool_result,
    load_mcp_tools,
)
from langchain_mcp_adapters.client import MultiServerMCPClient

# LangChain core
from langchain_core.messages import ToolMessage, BaseMessage


MCP_URL = "https://6060-iyjjh9bg5lssuiuhzemgk.e2b.app/"


def separator(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def inspect_object(label: str, obj):
    """Deep inspect an object's type, attributes, and content."""
    print(f"--- {label} ---")
    print(f"  type: {type(obj).__name__}")
    print(f"  module: {type(obj).__module__}")
    
    if isinstance(obj, (str, int, float, bool)):
        print(f"  value: {repr(obj)[:500]}")
    elif isinstance(obj, list):
        print(f"  len: {len(obj)}")
        for i, item in enumerate(obj[:5]):
            print(f"  [{i}] type={type(item).__name__}: {repr(item)[:300]}")
    elif isinstance(obj, dict):
        print(f"  keys: {list(obj.keys())}")
        for k, v in list(obj.items())[:10]:
            print(f"  [{k}] type={type(v).__name__}: {repr(v)[:200]}")
    elif isinstance(obj, tuple):
        print(f"  len: {len(obj)}")
        for i, item in enumerate(obj):
            print(f"  ({i}) type={type(item).__name__}: {repr(item)[:300]}")
    elif hasattr(obj, '__dict__'):
        print(f"  attrs: {list(obj.__dict__.keys())}")
        for k, v in list(obj.__dict__.items())[:10]:
            print(f"  .{k} type={type(v).__name__}: {repr(v)[:200]}")
    
    # Special handling for LangChain messages
    if hasattr(obj, 'content'):
        print(f"  .content type={type(obj.content).__name__}: {repr(obj.content)[:500]}")
    if hasattr(obj, 'tool_call_id'):
        print(f"  .tool_call_id: {obj.tool_call_id}")
    if hasattr(obj, 'response_metadata'):
        print(f"  .response_metadata: {repr(obj.response_metadata)[:200]}")
    if hasattr(obj, 'type'):
        print(f"  .type: {obj.type}")
    
    # Check isinstance checks
    if isinstance(obj, ToolMessage):
        print(f"  isinstance(ToolMessage): True")
    elif isinstance(obj, BaseMessage):
        print(f"  isinstance(BaseMessage): True (but NOT ToolMessage)")
    
    print()


async def test_raw_mcp_session():
    """Test 1: Connect directly via MCP SDK and call tools."""
    separator("TEST 1: Raw MCP Session (mcp SDK direct)")

    try:
        async with streamablehttp_client(f"{MCP_URL}mcp") as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                print(f"Available tools ({len(tool_names)}):")
                for name in sorted(tool_names)[:20]:
                    print(f"  - {name}")
                if len(tool_names) > 20:
                    print(f"  ... and {len(tool_names) - 20} more")
                print()

                # Test 1a: Run Bash tool with correct args
                print("\n--- Test 1a: Bash tool ---")
                print("Calling raw MCP tool: Bash")
                try:
                    result = await session.call_tool("Bash", {"command": "echo hello world", "session_name": "default", "description": "Test echo"})
                    inspect_object("Raw CallToolResult from 'Bash'", result)
                    inspect_object("result.content", result.content)
                    for i, block in enumerate(result.content):
                        inspect_object(f"result.content[{i}]", block)
                except Exception as e:
                    print(f"  Bash Error: {e}")

                # Test 1b: Run Read tool
                print("\n--- Test 1b: Read tool ---")
                print("Calling raw MCP tool: Read")
                try:
                    result = await session.call_tool("Read", {"file_path": "/workspace/README.md"})
                    inspect_object("Raw CallToolResult from 'Read'", result)
                    for i, block in enumerate(result.content[:3]):
                        inspect_object(f"result.content[{i}]", block)
                except Exception as e:
                    print(f"  Read Error: {e}")

                # Test 1c: Check what _convert_call_tool_result does
                print("\n--- Testing _convert_call_tool_result ---")
                # Create a mock result similar to what bash would return
                mock_result = CallToolResult(
                    content=[TextContent(type="text", text="hello world\n")],
                    isError=False,
                )
                converted = _convert_call_tool_result(mock_result)
                inspect_object("_convert_call_tool_result output (tuple)", converted)
                inspect_object("converted[0] (content)", converted[0])
                inspect_object("converted[1] (artifact)", converted[1])

    except Exception as e:
        print(f"Raw MCP session failed: {e}")
        import traceback
        traceback.print_exc()


async def test_langchain_mcp_tools():
    """Test 2: Use MultiServerMCPClient to get LangChain tools and call them."""
    separator("TEST 2: LangChain MCP Tools (via MultiServerMCPClient)")

    mcp_servers = {
        "sandbox": {
            "transport": "http",
            "url": f"{MCP_URL}mcp",
        }
    }

    try:
        client = MultiServerMCPClient(mcp_servers)
        tools = await client.get_tools()
        tool_names = [t.name for t in tools]
        print(f"LangChain tools loaded: {len(tools)}")
        
        # Show first few tool details
        for tool in tools[:5]:
            print(f"  Tool: name={tool.name}, type={type(tool).__name__}")
            if hasattr(tool, 'response_format'):
                print(f"    response_format: {tool.response_format}")
        print()

        # Find Bash tool (the sandbox uses "Bash" with session_name + command)
        bash_tool = None
        for t in tools:
            if t.name == 'Bash':
                bash_tool = t
                break
        if not bash_tool:
            for t in tools:
                if 'bash' in t.name.lower():
                    bash_tool = t
                    break
        
        if bash_tool:
            print(f"\n--- Calling LangChain tool: {bash_tool.name} ---")
            print(f"  Tool type: {type(bash_tool).__name__}")
            print(f"  response_format: {getattr(bash_tool, 'response_format', 'N/A')}")
            print(f"  args_schema: {bash_tool.args_schema if hasattr(bash_tool, 'args_schema') else 'N/A'}")
            
            # Call via ainvoke (simulating what the ReAct agent does)
            try:
                result = await bash_tool.ainvoke({
                    "args": {"command": "echo 'test from langchain tool'", "session_name": "default", "description": "Test echo command"},
                    "id": "test-call-001",
                    "type": "tool_call",
                })
                separator("CRITICAL: LangChain tool.ainvoke() result")
                inspect_object("tool.ainvoke() result", result)
                
                # This is what ends up in astream_events on_tool_end
                # event["data"]["output"]
                print("THIS IS WHAT on_tool_end event['data']['output'] WILL BE")
                print(f"  The result IS a ToolMessage: {isinstance(result, ToolMessage)}")
                print(f"  The result IS a BaseMessage: {isinstance(result, BaseMessage)}")
                if isinstance(result, ToolMessage):
                    print(f"  result.content = {repr(result.content)[:500]}")
                    print(f"  type(result.content) = {type(result.content).__name__}")
                    if isinstance(result.content, list):
                        for i, block in enumerate(result.content):
                            print(f"  result.content[{i}] = {repr(block)}")
                    print(f"  result.tool_call_id = {result.tool_call_id}")
                    print(f"  result.name = {result.name}")
                    print(f"  result.type = {result.type}")
            except Exception as e:
                print(f"  ainvoke Error: {e}")
                import traceback
                traceback.print_exc()

        # Find and test Read tool
        read_tool = None
        for t in tools:
            if t.name == 'Read':
                read_tool = t
                break
        
        if read_tool:
            print(f"\n--- Calling LangChain tool: {read_tool.name} ---")
            print(f"  args_schema: {read_tool.args_schema if hasattr(read_tool, 'args_schema') else 'N/A'}")
            try:
                result = await read_tool.ainvoke({
                    "args": {"file_path": "/workspace/README.md"},
                    "id": "test-call-002",
                    "type": "tool_call",
                })
                separator("CRITICAL: Read tool ainvoke() result")
                inspect_object("Read tool result", result)
                if isinstance(result, ToolMessage):
                    print(f"  .content = {repr(result.content)[:500]}")
            except Exception as e:
                print(f"  Error: {e}")
                import traceback
                traceback.print_exc()

        # Find and test Write tool
        write_tool = None
        for t in tools:
            if t.name == 'Write':
                write_tool = t
                break
        
        if write_tool:
            print(f"\n--- Calling LangChain tool: {write_tool.name} ---")
            print(f"  args_schema: {write_tool.args_schema if hasattr(write_tool, 'args_schema') else 'N/A'}")
            try:
                result = await write_tool.ainvoke({
                    "args": {"file_path": "/workspace/test_output.txt", "content": "hello from test"},
                    "id": "test-call-003",
                    "type": "tool_call",
                })
                separator("CRITICAL: Write tool ainvoke() result")
                inspect_object("Write tool result", result)
                if isinstance(result, ToolMessage):
                    print(f"  .content = {repr(result.content)[:500]}")
            except Exception as e:
                print(f"  Error: {e}")
                import traceback
                traceback.print_exc()

    except Exception as e:
        print(f"MultiServerMCPClient failed: {e}")
        import traceback
        traceback.print_exc()


async def test_serialization_of_real_output():
    """Test 3: See what happens when we serialize the actual tool output."""
    separator("TEST 3: Serialization of Real Tool Output")

    from backend.src.utils.json_utils import make_serializable, safe_json_serialize

    mcp_servers = {
        "sandbox": {
            "transport": "http",
            "url": f"{MCP_URL}mcp",
        }
    }

    try:
        client = MultiServerMCPClient(mcp_servers)
        tools = await client.get_tools()
        
        # Find Bash tool
        bash_tool = None
        for t in tools:
            if t.name == 'Bash':
                bash_tool = t
                break
        
        if not bash_tool:
            print("No Bash tool found, skipping serialization test")
            return
        
        result = await bash_tool.ainvoke({
            "args": {"command": "echo serialization_test", "session_name": "default", "description": "Test echo"},
            "id": "test-serialize-001",
            "type": "tool_call",
        })
            
        print("Step 1: Raw ToolMessage from ainvoke()")
        inspect_object("raw result", result)
        
        print("\nStep 2: make_serializable(result) — BEFORE any unwrapping")
        serialized = make_serializable(result)
        inspect_object("make_serializable(ToolMessage)", serialized)
        
        print("\nStep 3: safe_json_serialize(result)")
        json_str = safe_json_serialize(result)
        print(f"  JSON string: {json_str[:500]}")
        
        print("\nStep 4: Unwrap .content then serialize")
        content = result.content
        inspect_object("result.content (unwrapped)", content)
        
        serialized_content = make_serializable(content)
        inspect_object("make_serializable(content)", serialized_content)
        
        json_content = safe_json_serialize(content)
        print(f"  JSON of content: {json_content[:500]}")
        
        # Step 5: If content is list of blocks, extract text
        if isinstance(content, list):
            print("\nStep 5: Content is a list — checking for content blocks")
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            if text_parts:
                extracted = "\n".join(text_parts)
                print(f"  Extracted text: {repr(extracted)}")
                json_extracted = safe_json_serialize(extracted)
                print(f"  JSON of extracted: {json_extracted[:500]}")
        elif isinstance(content, str):
            print("\nStep 5: Content is already a string!")
            print(f"  value: {repr(content)[:500]}")

    except Exception as e:
        print(f"Serialization test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("=" * 80)
    print("  MCP TOOL OUTPUT FORMAT INVESTIGATION")
    print(f"  MCP URL: {MCP_URL}")
    print("=" * 80)

    await test_raw_mcp_session()
    await test_langchain_mcp_tools()
    await test_serialization_of_real_output()

    separator("SUMMARY")
    print("Check the output above to understand:")
    print("1. What raw MCP CallToolResult looks like (content blocks)")
    print("2. What langchain-mcp-adapters converts it to (ToolMessage)")
    print("3. What ToolMessage.content actually is (list of dicts? string?)")
    print("4. What happens when we serialize the ToolMessage")
    print("5. The correct way to extract displayable text")


if __name__ == "__main__":
    asyncio.run(main())
