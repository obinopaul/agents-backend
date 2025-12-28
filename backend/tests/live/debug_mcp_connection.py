#!/usr/bin/env python3
"""
Debug MCP Connection Issues
============================

This script provides detailed diagnostics for MCP client-server communication issues.
It tests various endpoints and connection methods to identify where the connection fails.
"""

import asyncio
import httpx
import sys
import os
from datetime import datetime

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.getcwd())

from e2b import Sandbox
from dotenv import load_dotenv

load_dotenv()

TEMPLATE_ID = "vg6mdf4wgu5qoijamwb5"


async def test_mcp_endpoints(mcp_base_url: str):
    """Test various MCP endpoint configurations."""
    print(f"\n{'='*70}")
    print(f"Testing MCP Endpoints")
    print(f"Base URL: {mcp_base_url}")
    print(f"{'='*70}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        endpoints_to_test = [
            ("/health", "GET"),
            ("/mcp/", "GET"),
            ("/mcp/", "POST"),
            ("/mcp", "GET"),
            ("/mcp", "POST"),
            # FastMCP default
            ("/", "GET"),
        ]
        
        for endpoint, method in endpoints_to_test:
            url = f"{mcp_base_url}{endpoint}"
            try:
                if method == "GET":
                    r = await client.get(url)
                else:
                    # Try a simple MCP initialize message
                    r = await client.post(url, json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "debug-client", "version": "0.1"}
                        },
                        "id": 1
                    }, headers={"Content-Type": "application/json"})
                
                print(f"\n{method} {endpoint}")
                print(f"   Status: {r.status_code}")
                content = r.text[:300] if len(r.text) > 300 else r.text
                print(f"   Body: {content}")
            except Exception as e:
                print(f"\n{method} {endpoint}")
                print(f"   ERROR: {type(e).__name__}: {e}")


async def test_langchain_mcp_adapter(mcp_base_url: str):
    """Test various URL patterns with langchain-mcp-adapters."""
    print(f"\n{'='*70}")
    print(f"Testing langchain-mcp-adapters URL patterns")
    print(f"{'='*70}")
    
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        print("ERROR: langchain-mcp-adapters not installed")
        return []
    
    # Test different URL patterns
    url_patterns = [
        f"{mcp_base_url}/mcp/",
        f"{mcp_base_url}/mcp",
        f"{mcp_base_url}/",
        f"{mcp_base_url}",
    ]
    
    for url in url_patterns:
        print(f"\nTrying URL: {url}")
        try:
            mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": url,
                    "transport": "http"
                },
            })
            
            # Set a short timeout for testing
            tools = await asyncio.wait_for(
                mcp_client.get_tools(),
                timeout=30.0
            )
            print(f"   SUCCESS! Got {len(tools)} tools")
            for tool in tools[:5]:
                print(f"      - {tool.name}")
            if len(tools) > 5:
                print(f"      ... and {len(tools) - 5} more")
            return tools
            
        except asyncio.TimeoutError:
            print(f"   TIMEOUT after 30 seconds")
        except Exception as e:
            error_str = str(e)[:300]
            print(f"   ERROR: {type(e).__name__}: {error_str}")
    
    return []


async def test_fastmcp_client(mcp_base_url: str):
    """Test using fastmcp's native client."""
    print(f"\n{'='*70}")
    print(f"Testing FastMCP native client")
    print(f"{'='*70}")
    
    try:
        from fastmcp.client import Client
    except ImportError:
        print("ERROR: fastmcp not installed")
        return []
    
    url_patterns = [
        f"{mcp_base_url}/mcp/",
        f"{mcp_base_url}/mcp",
        f"{mcp_base_url}",
    ]
    
    for url in url_patterns:
        print(f"\nTrying URL: {url}")
        try:
            async with Client(url) as client:
                tools = await client.list_tools()
                print(f"   SUCCESS! Got {len(tools)} tools")
                for tool in tools[:5]:
                    print(f"      - {tool.name}")
                return tools
        except Exception as e:
            error_str = str(e)[:300]
            print(f"   ERROR: {type(e).__name__}: {error_str}")
    
    return []


def check_sandbox_mcp_logs(sandbox):
    """Check MCP server logs inside sandbox."""
    print(f"\n{'='*70}")
    print(f"Checking MCP Server Logs Inside Sandbox")
    print(f"{'='*70}")
    
    commands = [
        ("tmux list-sessions 2>&1 || echo 'No tmux'", "tmux sessions"),
        ("cat /tmp/mcp-server.log 2>&1 | tail -30 || echo 'No log file'", "MCP log file"),
        ("tmux capture-pane -t mcp-server-system-never-kill -p -S -20 2>&1 || echo 'No tmux pane'", "tmux MCP output"),
        ("netstat -tuln | grep -E '(6060|LISTEN)' || echo 'No listeners'", "Port listeners"),
        ("ps aux | grep -E '(python|mcp)' | head -5", "Python/MCP processes"),
    ]
    
    for cmd, desc in commands:
        print(f"\n--- {desc} ---")
        try:
            result = sandbox.commands.run(cmd, timeout=10)
            output = result.stdout.strip() if result.stdout else ""
            if output:
                # Limit output length
                if len(output) > 400:
                    output = output[:400] + "...(truncated)"
                print(output)
            if result.stderr:
                print(f"STDERR: {result.stderr[:150]}")
        except Exception as e:
            print(f"Error: {e}")


async def main():
    print("=" * 70)
    print("MCP Connection Diagnostics")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Create sandbox
    print("\nCreating E2B sandbox...")
    sandbox = Sandbox.create(TEMPLATE_ID)
    
    try:
        sandbox_id = sandbox.sandbox_id
        print(f"   Sandbox ID: {sandbox_id}")
        
        # Get MCP URL
        mcp_url = f"https://6060-{sandbox_id}.e2b.app"
        print(f"   MCP URL: {mcp_url}")
        
        # Manually start services
        print("\nStarting services...")
        try:
            result = sandbox.commands.run("bash /app/start-services.sh &", timeout=5)
            print(f"   Start script sent")
        except Exception:
            print("   Start script sent (background)")
        
        # Wait for services
        print("\nWaiting 20 seconds for services to start...")
        await asyncio.sleep(20)
        
        # Check logs first
        check_sandbox_mcp_logs(sandbox)
        
        # Test endpoints
        await test_mcp_endpoints(mcp_url)
        
        # Test FastMCP native client
        await test_fastmcp_client(mcp_url)
        
        # Test LangChain adapter
        await test_langchain_mcp_adapter(mcp_url)
        
    finally:
        print("\nCleanup...")
        sandbox.kill()
        print("   Sandbox killed")
    
    print("\nDiagnostics complete")


if __name__ == "__main__":
    asyncio.run(main())
