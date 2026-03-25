#!/usr/bin/env python3
"""
List all MCP tools available from the tool server.

This script connects to a running sandbox MCP server and lists all registered tools.
Run this after starting a sandbox to see what tools are available.

Usage:
    python backend/tests/live/list_mcp_tools.py
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def list_mcp_tools_from_sandbox(mcp_url: str = "http://localhost:6060"):
    """List tools from an MCP server endpoint."""
    print(f"\n🔧 Fetching tools from: {mcp_url}")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try the tools endpoint
            response = await client.get(f"{mcp_url}/tools")
            if response.status_code == 200:
                tools = response.json()
                return tools
            else:
                print(f"❌ Failed to get tools: HTTP {response.status_code}")
                return None
    except httpx.ConnectError:
        print(f"❌ Cannot connect to MCP server at {mcp_url}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def list_local_tools():
    """List tools from local tool directories."""
    print("\n📂 LOCAL TOOL DIRECTORIES")
    print("=" * 60)
    
    tools_dir = project_root / "backend" / "src" / "tool_server" / "tools"
    
    all_tools = {}
    
    for category_dir in sorted(tools_dir.iterdir()):
        if category_dir.is_dir() and not category_dir.name.startswith("__"):
            category = category_dir.name
            tools = []
            
            for tool_file in sorted(category_dir.glob("*.py")):
                if tool_file.name.startswith("__"):
                    continue
                if tool_file.name in ["base.py", "utils.py", "manager.py", "shared_state.py"]:
                    continue
                    
                # Extract tool name from file
                tool_name = tool_file.stem
                # Convert filename to likely tool name
                # e.g., "design_create_tool" -> "design_create"
                if tool_name.endswith("_tool"):
                    tool_name = tool_name[:-5]
                    
                tools.append(tool_name)
            
            if tools:
                all_tools[category] = tools
    
    # Print summary
    total = 0
    for category, tools in all_tools.items():
        print(f"\n📁 {category.upper()} ({len(tools)} tools)")
        for tool in tools:
            print(f"   • {tool}")
        total += len(tools)
    
    print(f"\n{'=' * 60}")
    print(f"📊 TOTAL: {total} tools in {len(all_tools)} categories")
    
    return all_tools




def main():
    print("🔍 MCP TOOL DISCOVERY")
    print("=" * 60)
    
    # List local tools first
    all_tools = list_local_tools()
        
    # Try to connect to live MCP server
    print("\n\n🌐 LIVE MCP SERVER (if running)")
    print("=" * 60)
    print("To list tools from a live sandbox, run with URL:")
    print("  python list_mcp_tools.py <mcp_url>")
    
    if len(sys.argv) > 1:
        mcp_url = sys.argv[1]
        asyncio.run(list_mcp_tools_from_sandbox(mcp_url))


if __name__ == "__main__":
    main()
