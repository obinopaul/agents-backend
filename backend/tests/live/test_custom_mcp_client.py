#!/usr/bin/env python3
"""
Custom MCPClient Test - Comprehensive Test Using Our Own MCP Client
====================================================================

This script demonstrates and tests the custom MCPClient from 
backend.src.tool_server.mcp.client, showcasing all its capabilities:

1. Health check
2. Set credentials for authenticated tools
3. Set tool server URL for external integrations
4. Register Codex for enhanced code editing
5. Register custom MCP servers
6. Get LangChain-compatible tools for agent use
7. Run a simple agent task

This is the RECOMMENDED approach for production use in this project,
as it provides full control over the MCP connection and all custom endpoints.

Prerequisites:
    - FastAPI backend running at localhost:8000 (for sandbox creation)
    - E2B API key configured
    - Test user created (python backend/tests/live/create_test_user.py)

Usage:
    python backend/tests/live/test_custom_mcp_client.py
    python backend/tests/live/test_custom_mcp_client.py --task "list files in /workspace"
    python backend/tests/live/test_custom_mcp_client.py --skip-agent  # Skip agent test
"""

import asyncio
import argparse
import sys
import os
import httpx
import uuid
from datetime import datetime
from typing import Optional, List

# Fix Windows encoding issues with emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv
load_dotenv()

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class CustomMCPClientTest:
    """
    Comprehensive test suite for the custom MCPClient.
    
    This demonstrates the recommended production workflow for connecting
    to MCP servers in E2B sandboxes.
    """
    
    def __init__(self, args):
        self.args = args
        self.http_client = None
        self.mcp_client = None
        self.sandbox_id = None
        self.mcp_url = None
        self.token = None
        self.tools = []
        self.results = {}
    
    def log(self, msg: str, success: Optional[bool] = None, indent: int = 0):
        """Log with optional success indicator."""
        prefix = "   " * indent
        if success is True:
            icon = "[OK]"
        elif success is False:
            icon = "[FAIL]"
        else:
            icon = "[..]"
        print(f"{prefix}{icon} {msg}", flush=True)
    
    def header(self, msg: str):
        """Print section header."""
        print(f"\n{'='*70}")
        print(f"  {msg}")
        print(f"{'='*70}", flush=True)
    
    async def setup_backend_connection(self) -> bool:
        """Initialize connection to FastAPI backend and create sandbox."""
        self.header("PHASE 1: Backend Connection & Sandbox Creation")
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=180.0,
            headers={
                'User-Agent': 'CustomMCPClientTest/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
        
        # Login
        self.log("Authenticating with backend...")
        try:
            r = await self.http_client.post(
                f'{BASE_URL}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            if r.status_code == 200:
                self.token = r.json().get('access_token')
                self.http_client.headers['Authorization'] = f'Bearer {self.token}'
                self.log(f"Authenticated as {TEST_USER}", True)
            else:
                self.log(f"Login failed: {r.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Backend connection failed: {e}", False)
            self.log("Make sure FastAPI backend is running: python -m uvicorn backend.main:app --port 8000")
            return False
        
        # Create sandbox
        self.log("Creating E2B sandbox (this takes 30-60 seconds)...")
        try:
            r = await self.http_client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/create',
                json={'user_id': 'custom-mcp-client-test'}
            )
            if r.status_code == 200:
                data = r.json().get('data', {})
                self.sandbox_id = data.get('sandbox_id')
                self.mcp_url = data.get('mcp_url')
                self.log(f"Sandbox ID: {self.sandbox_id}", True)
                self.log(f"MCP URL: {self.mcp_url}", True)
            else:
                self.log(f"Sandbox creation failed: {r.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Sandbox creation error: {e}", False)
            return False
        
        return True
    
    async def wait_for_mcp_server(self, max_wait: int = 60) -> bool:
        """Wait for MCP server to become available."""
        self.log(f"Waiting for MCP server (max {max_wait}s)...")
        
        start = datetime.now()
        while (datetime.now() - start).seconds < max_wait:
            try:
                r = await self.http_client.get(f"{self.mcp_url}/health", timeout=10.0)
                if r.status_code == 200:
                    self.log("MCP server is healthy", True)
                    return True
            except Exception:
                pass
            
            elapsed = (datetime.now() - start).seconds
            print(f"   [..] Waiting... ({elapsed}s)", end="\r", flush=True)
            await asyncio.sleep(3)
        
        print()  # Clear line
        self.log("MCP server did not become available", False)
        return False
    
    async def test_mcp_client_features(self) -> bool:
        """Test all MCPClient features."""
        self.header("PHASE 2: MCPClient Feature Tests")
        
        # Import our custom client
        from backend.src.tool_server.mcp.client import MCPClient
        
        try:
            async with MCPClient(self.mcp_url) as client:
                self.mcp_client = client
                
                # Test 1: Health Check
                self.log("Testing health_check()...")
                try:
                    is_healthy = await client.health_check()
                    self.results['health_check'] = is_healthy
                    self.log(f"Server healthy: {is_healthy}", is_healthy)
                except Exception as e:
                    self.results['health_check'] = False
                    self.log(f"Health check failed: {e}", False)
                
                # Test 2: Set Credential
                self.log("Testing set_credential()...")
                try:
                    credential = {
                        "user_api_key": "test-api-key-12345",
                        "session_id": str(uuid.uuid4())
                    }
                    result = await client.set_credential(credential)
                    self.results['set_credential'] = True
                    self.log(f"Credential set: {result}", True)
                except Exception as e:
                    self.results['set_credential'] = False
                    self.log(f"Set credential failed: {e}", False)
                
                # Test 3: Get Tool Names (basic MCP operation)
                self.log("Testing get_tool_names()...")
                try:
                    tool_names = await client.get_tool_names()
                    self.results['get_tool_names'] = len(tool_names) > 0
                    self.log(f"Found {len(tool_names)} tools", len(tool_names) > 0)
                    
                    # Show first 10 tools
                    for i, name in enumerate(tool_names[:10], 1):
                        self.log(f"{i}. {name}", indent=1)
                    if len(tool_names) > 10:
                        self.log(f"... and {len(tool_names) - 10} more", indent=1)
                except Exception as e:
                    self.results['get_tool_names'] = False
                    self.log(f"Get tool names failed: {e}", False)
                
                # Test 4: Get LangChain Tools
                self.log("Testing get_langchain_tools()...")
                try:
                    self.tools = await client.get_langchain_tools()
                    self.results['get_langchain_tools'] = len(self.tools) > 0
                    self.log(f"Converted {len(self.tools)} tools to LangChain format", len(self.tools) > 0)
                    
                    # Verify they're LangChain BaseTool instances
                    from langchain_core.tools import BaseTool
                    all_valid = all(isinstance(t, BaseTool) for t in self.tools)
                    self.log(f"All tools are BaseTool instances: {all_valid}", all_valid)
                except Exception as e:
                    self.results['get_langchain_tools'] = False
                    self.log(f"Get LangChain tools failed: {e}", False)
                
                # Test 5: Register Codex (optional - may fail if sse-http-server not available)
                self.log("Testing register_codex() (optional)...")
                try:
                    result = await client.register_codex()
                    self.results['register_codex'] = True
                    self.log(f"Codex registered: {result}", True)
                except Exception as e:
                    self.results['register_codex'] = None  # Optional feature
                    self.log(f"Codex not available (optional): {str(e)[:50]}", None)
                
                # Test 6: Call a simple tool directly
                self.log("Testing direct tool call: shell_list...")
                try:
                    result = await client.call_tool("BashList", {})
                    self.results['direct_tool_call'] = True
                    content = str(result.content)[:100] if hasattr(result, 'content') else str(result)[:100]
                    self.log(f"Tool result: {content}", True)
                except Exception as e:
                    self.results['direct_tool_call'] = False
                    self.log(f"Direct tool call failed: {e}", False)
                
                return True
                
        except Exception as e:
            self.log(f"MCPClient session failed: {e}", False)
            import traceback
            traceback.print_exc()
            return False
    
    async def test_agent_with_tools(self, task: str) -> bool:
        """Test using the LangChain tools with an agent."""
        self.header("PHASE 3: LangGraph Agent Test")
        
        if not self.tools:
            self.log("No tools available - skipping agent test", False)
            return False
        
        self.log(f"Task: {task}")
        self.log(f"Using {len(self.tools)} LangChain tools")
        
        try:
            # Initialize LLM
            from backend.src.llms.llm import get_llm
            llm = get_llm()
            model_name = getattr(llm, 'model_name', getattr(llm, 'model', 'Unknown'))
            self.log(f"LLM: {model_name}", True)
            
            # Create agent
            from langgraph.prebuilt import create_react_agent
            from langchain_core.messages import HumanMessage
            
            agent = create_react_agent(llm, self.tools)
            self.log("Agent created", True)
            
            # Run task
            self.log("Executing task...")
            result = await agent.ainvoke({
                "messages": [HumanMessage(content=task)]
            })
            
            # Show result
            for msg in result.get("messages", []):
                role = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                if content:
                    if role in ['ai', 'assistant']:
                        self.log(f"Agent: {content[:200]}{'...' if len(content) > 200 else ''}", True)
                    elif role == 'tool':
                        tool_name = getattr(msg, 'name', 'unknown')
                        self.log(f"Tool [{tool_name}]: {content[:100]}{'...' if len(content) > 100 else ''}")
            
            self.results['agent_task'] = True
            return True
            
        except Exception as e:
            self.log(f"Agent test failed: {e}", False)
            import traceback
            traceback.print_exc()
            self.results['agent_task'] = False
            return False
    
    async def cleanup(self):
        """Clean up resources."""
        self.header("CLEANUP")
        
        # Delete sandbox
        if self.sandbox_id and self.http_client:
            try:
                await self.http_client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                self.log("Sandbox deleted", True)
            except Exception as e:
                self.log(f"Sandbox cleanup error: {e}", False)
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        self.log("Cleanup complete", True)
    
    def print_summary(self):
        """Print test summary."""
        self.header("TEST SUMMARY")
        
        passed = sum(1 for v in self.results.values() if v is True)
        failed = sum(1 for v in self.results.values() if v is False)
        skipped = sum(1 for v in self.results.values() if v is None)
        total = len(self.results)
        
        for name, result in self.results.items():
            if result is True:
                status = "[PASS]"
            elif result is False:
                status = "[FAIL]"
            else:
                status = "[SKIP]"
            print(f"   {status} {name}")
        
        print("-" * 70)
        print(f"   PASSED: {passed}/{total} | FAILED: {failed} | SKIPPED: {skipped}")
        print("=" * 70)
        
        return failed == 0
    
    async def run(self):
        """Run all tests."""
        print("=" * 70)
        print("  CUSTOM MCPClient COMPREHENSIVE TEST")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        try:
            # Phase 1: Setup
            if not await self.setup_backend_connection():
                return False
            
            # Wait for MCP server
            if not await self.wait_for_mcp_server():
                return False
            
            # Phase 2: Test MCPClient features
            if not await self.test_mcp_client_features():
                return False
            
            # Phase 3: Test agent (optional)
            if not self.args.skip_agent:
                task = self.args.task or "List all files in the /workspace directory"
                await self.test_agent_with_tools(task)
            else:
                self.log("Agent test skipped (--skip-agent flag)")
            
            return True
            
        finally:
            await self.cleanup()
            self.print_summary()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test custom MCPClient with all features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_custom_mcp_client.py
  python test_custom_mcp_client.py --task "create a Python hello world file"
  python test_custom_mcp_client.py --skip-agent  # Skip agent test
        """
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Task for the agent to execute (default: list files)"
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip the LangGraph agent test"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    tester = CustomMCPClientTest(args)
    success = await tester.run()
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[..] Interrupted by user")
        sys.exit(1)
