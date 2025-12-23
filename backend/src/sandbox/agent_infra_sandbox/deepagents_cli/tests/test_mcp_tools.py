"""Test script to list all MCP tools from the Agent-Infra sandbox.

This script connects to the sandbox MCP endpoint and displays all available tools.

Requirements:
- Docker sandbox running: docker compose up -d
- Install: pip install langchain-mcp-adapters

Usage:
    python tests/test_mcp_tools.py
"""

import asyncio
import os
import sys

# Ensure localhost bypasses proxy
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'


async def list_mcp_tools():
    """Connect to sandbox MCP endpoint and list all available tools."""
    
    from langchain_mcp_adapters.client import MultiServerMCPClient
    
    # Get sandbox URL from environment or default
    base_url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    mcp_url = f"{base_url}/mcp/"
    
    print(f"\n{'='*60}")
    print("MCP Tools Discovery")
    print(f"{'='*60}")
    print(f"Connecting to: {mcp_url}")
    print()
    
    try:
        # Create MCP client
        client = MultiServerMCPClient({
            "sandbox": {
                "url": mcp_url,
                "transport": "http"  # Use "http" per latest docs
            },
        })
        
        # Get all tools
        print("Fetching tools...")
        tools = await client.get_tools()
        
        print(f"\n[OK] Found {len(tools)} tools\n")
        print(f"{'='*60}")
        print("AVAILABLE TOOLS")
        print(f"{'='*60}\n")
        
        # Display each tool
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool.name}")
            print(f"   Description: {tool.description[:100]}..." if len(tool.description) > 100 else f"   Description: {tool.description}")
            
            # Show input schema if available
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema = tool.args_schema.schema() if hasattr(tool.args_schema, 'schema') else {}
                if 'properties' in schema:
                    params = list(schema['properties'].keys())
                    print(f"   Parameters: {', '.join(params)}")
            print()
        
        # Summary by category
        print(f"{'='*60}")
        print("TOOL SUMMARY")
        print(f"{'='*60}\n")
        
        # Group by common prefixes
        categories = {}
        for tool in tools:
            # Try to extract category from tool name (e.g., "file_read" -> "file")
            parts = tool.name.split('_')
            category = parts[0] if len(parts) > 1 else "other"
            if category not in categories:
                categories[category] = []
            categories[category].append(tool.name)
        
        for category, tool_names in sorted(categories.items()):
            print(f"{category.upper()} ({len(tool_names)} tools):")
            for name in tool_names:
                print(f"  - {name}")
            print()
        
        return tools
        
    except Exception as e:
        print(f"\n[ERROR] Error connecting to MCP endpoint: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Docker sandbox is running: docker compose up -d")
        print(f"2. Check sandbox is accessible at {base_url}")
        print("3. Ensure langchain-mcp-adapters is installed: pip install langchain-mcp-adapters")
        raise


async def test_tool_invocation():
    """Test invoking a simple tool."""
    
    from langchain_mcp_adapters.client import MultiServerMCPClient
    
    base_url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    mcp_url = f"{base_url}/mcp/"
    
    print(f"\n{'='*60}")
    print("Testing Tool Invocation")
    print(f"{'='*60}\n")
    
    try:
        client = MultiServerMCPClient({
            "sandbox": {
                "url": mcp_url,
                "transport": "http"
            },
        })
        
        tools = await client.get_tools()
        
        # Find sandbox_execute_bash tool specifically
        test_tool = None
        for tool in tools:
            if tool.name == 'sandbox_execute_bash':
                test_tool = tool
                break
        
        if test_tool:
            print(f"Testing tool: {test_tool.name}")
            print(f"Description: {test_tool.description[:200]}...")
            print()
            
            # Invoke with correct parameter (cmd, not command)
            result = await test_tool.ainvoke({"cmd": "echo 'Hello from MCP!'"})
            print(f"Result: {result}")
            print("\n[OK] Tool invocation successful!")
        else:
            print("sandbox_execute_bash tool not found")
            
    except Exception as e:
        print(f"[ERROR] Tool invocation failed: {e}")


async def main():
    """Run all MCP tests."""
    
    print("\n" + "="*60)
    print("Agent-Infra Sandbox MCP Tools Test")
    print("="*60)
    
    # Test 1: List tools
    try:
        tools = await list_mcp_tools()
        print(f"\n[OK] Successfully listed {len(tools)} MCP tools")
    except Exception as e:
        print(f"\n[FAILED] Failed to list tools: {e}")
        return False
    
    # Test 2: Invoke a tool (optional)
    try:
        await test_tool_invocation()
    except Exception as e:
        print(f"\n[WARNING] Tool invocation test failed (non-critical): {e}")
    
    print("\n" + "="*60)
    print("Tests Complete")
    print("="*60 + "\n")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
