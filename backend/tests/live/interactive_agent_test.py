#!/usr/bin/env python3
"""
Interactive LangChain Agent Test - Testing REAL LangChain Tools via MCP

This script tests the ACTUAL LangChain tools from backend.src.tool_server.tools by:
1. Creating an E2B sandbox with the MCP tool server running
2. Connecting via langchain-mcp-adapters to get REAL LangChain tools
3. Running an interactive agent session with these tools

This is NOT the same as run_langchain_agent.py which uses REST API wrappers.
This tests the actual langchain_tools.py implementations via MCP.

Prerequisites:
    - FastAPI backend running at localhost:8000
    - E2B API key configured
    - Test user created (python backend/tests/live/create_test_user.py)

Usage:
    python backend/tests/live/interactive_agent_test.py
    python backend/tests/live/interactive_agent_test.py --task "create a hello world python file"
"""

import asyncio
import argparse
import sys
import os
import httpx
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Fix Windows encoding issues with emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.getcwd())

# LangChain imports
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


# =============================================================================
# Interactive Agent Tester - Tests REAL LangChain Tools via MCP
# =============================================================================

class InteractiveAgentTester:
    """
    Interactive tester that connects to E2B sandbox and tests the REAL LangChain tools
    from backend.src.tool_server.tools via MCP.
    
    This uses langchain-mcp-adapters to get the actual LangChain tools that are
    exposed by the MCP server running inside the E2B sandbox.
    """
    
    def __init__(self, args):
        self.args = args
        self.llm = None
        self.agent = None
        self.langchain_tools = []
        self.token = None
        self.sandbox_id = None
        self.mcp_url = None
        self.client = None
        self.mcp_client = None

    async def setup(self):
        """Initialize sandbox connection and get real LangChain tools via MCP."""
        print("\n" + "=" * 70)
        print("🤖 Interactive LangChain Agent - Testing REAL Tools via MCP")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # 1. Initialize HTTP client
        print("\n📋 Step 1: Connecting to backend...")
        self.client = httpx.AsyncClient(
            timeout=180.0,
            headers={
                'User-Agent': 'InteractiveAgentTest/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
        
        # 2. Login
        if not await self._login():
            print("❌ Login failed. Make sure the backend is running and test user exists.")
            print("   Run: python backend/tests/live/create_test_user.py")
            sys.exit(1)
        
        # 3. Create sandbox
        print("\n📋 Step 2: Creating E2B sandbox with MCP tool server...")
        if not await self._create_sandbox():
            print("❌ Sandbox creation failed. Check E2B_API_KEY in backend/.env")
            sys.exit(1)
        
        # Wait for MCP server to start inside sandbox
        print("   ⏳ Waiting for MCP server to initialize...")
        if not await self._wait_for_mcp_server(max_wait_seconds=60):
            print("❌ MCP server did not become available")
            print("   Check if the tool server is running inside the sandbox.")
            await self.cleanup()
            sys.exit(1)
        
        # 4. Get REAL LangChain tools via MCP adapter
        print("\n📋 Step 3: Getting LangChain tools via MCP...")
        self.langchain_tools = await self._get_langchain_tools_via_mcp()
        
        if not self.langchain_tools:
            print("❌ Failed to get LangChain tools from MCP server")
            print("   The MCP server may not be running or connection failed.")
            await self.cleanup()
            sys.exit(1)
        
        print(f"   ✅ Retrieved {len(self.langchain_tools)} LangChain tools!")
        
        # Show available tools
        tool_names = sorted([t.name for t in self.langchain_tools])
        print(f"\n   Available tools ({len(tool_names)}):")
        for i, name in enumerate(tool_names[:15], 1):
            print(f"   {i:2}. {name}")
        if len(tool_names) > 15:
            print(f"   ... and {len(tool_names) - 15} more")
        
        # 5. Initialize LLM
        print("\n📋 Step 4: Initializing LLM...")
        try:
            from backend.src.llms.llm import get_llm
            self.llm = get_llm()
            model_name = getattr(self.llm, 'model_name', getattr(self.llm, 'model', 'Unknown'))
            print(f"   ✅ LLM: {model_name}")
        except Exception as e:
            print(f"   ❌ Failed to initialize LLM: {e}")
            await self.cleanup()
            sys.exit(1)
        
        # 6. Create agent with real LangChain tools
        print("\n📋 Step 5: Creating LangChain agent with MCP tools...")
        try:
            self.agent = create_react_agent(self.llm, self.langchain_tools)
            print(f"   ✅ Agent ready with {len(self.langchain_tools)} REAL LangChain tools!")
        except Exception as e:
            print(f"   ❌ Agent creation failed: {e}")
            await self.cleanup()
            sys.exit(1)
        
        print("\n" + "=" * 70)

    async def _login(self) -> bool:
        """Authenticate with the backend."""
        r = await self.client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code == 200:
            self.token = r.json().get('access_token')
            self.client.headers['Authorization'] = f'Bearer {self.token}'
            print("   ✅ Authenticated as sandbox_test")
            return True
        print(f"   ❌ Login failed: {r.status_code}")
        return False

    async def _create_sandbox(self) -> bool:
        """Create E2B sandbox with MCP server."""
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'interactive-agent-test'}
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            self.sandbox_id = data.get('sandbox_id')
            self.mcp_url = data.get('mcp_url')
            print(f"   ✅ Sandbox: {self.sandbox_id}")
            print(f"   ✅ MCP URL: {self.mcp_url}")
            return True
        print(f"   ❌ Sandbox creation failed: {r.status_code} - {r.text}")
        return False

    async def _check_mcp_health(self) -> bool:
        """Check if MCP server is responding."""
        if not self.mcp_url:
            return False
        try:
            health_url = f"{self.mcp_url}/health"
            r = await self.client.get(health_url, timeout=10.0)
            return r.status_code == 200
        except Exception:
            return False

    async def _wait_for_mcp_server(self, max_wait_seconds=60) -> bool:
        """Wait for MCP server to become available with retries."""
        start = datetime.now()
        attempt = 0
        
        # Try to kickstart services just in case backend didn't start them
        try:
            # We use a separate client to run the command since self.client is for REST API
            # But here we need to use the E2B SDK's Sandbox object if possible. 
            # However, we only have REST API access here.
            # So we rely on the backend to have started it.
            # Wait! We can use E2B SDK directly here if we have the ID!
            pass 
        except Exception:
            pass

        print(f"   ⏳ Waiting for MCP server ({self.mcp_url})...")
        while (datetime.now() - start).seconds < max_wait_seconds:
            attempt += 1
            if await self._check_mcp_health():
                print(f"   ✅ MCP server is ready (attempt {attempt})")
                return True
            
            # If it's been 5 seconds and still not ready, try to manually start services using E2B SDK
            # This is a fallback in case the backend server wasn't restarted
            if attempt == 2:
                print("   ⚠️ MCP not ready yet. Attempting manual startup via E2B SDK...")
                try:
                    from e2b import Sandbox
                    # Connect to the existing sandbox
                    sbx = await Sandbox.connect(self.sandbox_id)
                    await sbx.commands.run("bash /app/start-services.sh &", timeout=5, background=True)
                    print("   ✅ Manual startup command sent")
                except Exception as e:
                    print(f"   ⚠️ Manual startup failed (ignoring): {e}")

            # Show progress
            elapsed = (datetime.now() - start).seconds
            print(f"   ⏳ Waiting... ({elapsed}s / {max_wait_seconds}s)", end="\r")
            await asyncio.sleep(5)
        return False

    async def _initialize_mcp_tools(self) -> bool:
        """
        CRITICAL: Initialize MCP tools by calling /credential and /tool-server-url.
        
        The MCP server starts quickly with /health available, but tools are NOT
        registered until these endpoints are called. This is an optimization to
        reduce startup time - tools are registered on-demand.
        """
        session_id = str(uuid.uuid4())
        
        # Step 1: Set credentials
        print("   ⏳ Initializing MCP tools (setting credentials)...")
        try:
            credential_payload = {
                "user_api_key": self.token,
                "session_id": session_id
            }
            r = await self.client.post(
                f"{self.mcp_url}/credential",
                json=credential_payload,
                timeout=30.0
            )
            if r.status_code != 200:
                print(f"   ⚠️ Credential setup returned: {r.status_code}")
                return False
            print("   ✅ Credentials set")
        except Exception as e:
            print(f"   ❌ Credential setup failed: {e}")
            return False
        
        # Step 2: Set tool server URL (triggers tool registration)
        print("   ⏳ Registering tools (this may take 30-60 seconds)...")
        try:
            r = await self.client.post(
                f"{self.mcp_url}/tool-server-url",
                json={"tool_server_url": self.mcp_url},
                timeout=120.0  # Tool registration can take a while
            )
            if r.status_code != 200:
                print(f"   ⚠️ Tool registration returned: {r.status_code} - {r.text[:200]}")
                return False
            print("   ✅ Tools registered successfully")
        except Exception as e:
            print(f"   ❌ Tool registration failed: {e}")
            return False
        
        return True

    async def _get_langchain_tools_via_mcp(self) -> List:
        """
        Get the REAL LangChain tools from the MCP server via langchain-mcp-adapters.
        
        These are the actual tools from backend.src.tool_server.tools, not REST wrappers.
        
        IMPORTANT: This method now first initializes the MCP tools by calling
        /credential and /tool-server-url endpoints before connecting.
        """
        # First, initialize MCP tools (this is the critical step that was missing!)
        if not await self._initialize_mcp_tools():
            print("   ⚠️ MCP tool initialization failed, attempting to connect anyway...")
        
        # Wait a moment for tools to be fully available
        await asyncio.sleep(3)
        
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            # Connect to MCP server inside the sandbox
            self.mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": f"{self.mcp_url}/mcp",
                    "transport": "http"
                },
            })
            
            # Get all tools from MCP as LangChain tools
            tools = await self.mcp_client.get_tools()
            return tools
            
        except ImportError:
            print("   ❌ langchain-mcp-adapters not installed")
            print("   Run: pip install langchain-mcp-adapters")
            return []
        except Exception as e:
            print(f"   ❌ Failed to get tools via MCP adapter: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def run_single_task(self, task: str):
        """Run a single task and exit."""
        print(f"\n📝 Task: {task}")
        print("-" * 70)
        
        try:
            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=task)]
            })
            
            # Print agent messages
            for msg in result.get("messages", []):
                role = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                if content:
                    if role in ['ai', 'assistant']:
                        print(f"\n🤖 Agent:\n{content}")
                    elif role == 'tool':
                        tool_name = getattr(msg, 'name', 'unknown')
                        print(f"\n🔧 Tool [{tool_name}]: {content[:200]}..." if len(content) > 200 else f"\n🔧 Tool [{tool_name}]: {content}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    async def run_repl(self):
        """Run interactive REPL session with the agent."""
        print("\n💬 Interactive Session Started. Type 'exit' to quit.")
        print("-" * 70)
        print("These are the REAL LangChain tools from backend.src.tool_server.tools")
        print("connected via MCP to the E2B sandbox.")
        print("-" * 70)
        print("\nExample commands:")
        print("  • 'list all files in /workspace'")
        print("  • 'create a python file that prints hello world'")
        print("  • 'run echo test command'")
        print("-" * 70)
        
        chat_history = []
        while True:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "\nYou: "
                )
                if user_input.strip().lower() in ["exit", "quit", "q"]:
                    break
                
                if not user_input.strip():
                    continue
                
                print("Agent is thinking...", end="", flush=True)
                
                inputs = {"messages": chat_history + [HumanMessage(content=user_input)]}
                result = await self.agent.ainvoke(inputs)
                
                chat_history = result["messages"]
                last_msg = chat_history[-1]
                
                print("\r" + " " * 25 + "\r", end="")
                print(f"Agent: {last_msg.content}")
                
            except KeyboardInterrupt:
                print("\n\n⚠️ Interrupted")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()

    async def cleanup(self):
        """Cleanup resources."""
        print("\n📋 Cleanup...")
        
        # Close MCP client if exists
        if self.mcp_client:
            try:
                # MCP client cleanup if needed
                pass
            except Exception as e:
                print(f"   ⚠️ MCP client cleanup error: {e}")
        
        # Delete sandbox
        if self.sandbox_id and self.client:
            try:
                await self.client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                print("   ✅ Sandbox deleted")
            except Exception as e:
                print(f"   ⚠️ Sandbox cleanup error: {e}")
        
        # Close HTTP client
        if self.client:
            await self.client.aclose()
        
        print("👋 Done!")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Interactive LangChain Agent - Test REAL Tools via MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script tests the ACTUAL LangChain tools from backend.src.tool_server.tools
by connecting to the MCP server inside an E2B sandbox via langchain-mcp-adapters.

Examples:
  # Interactive mode (REPL)
  python interactive_agent_test.py
  
  # Run a single task
  python interactive_agent_test.py --task "create a hello.py file that prints Hello World"
  python interactive_agent_test.py --task "list files in /workspace"
        """
    )
    parser.add_argument(
        "--task", 
        type=str, 
        default=None,
        help="Run a single task instead of interactive mode"
    )
    return parser.parse_args()


async def main():
    args = parse_arguments()
    tester = InteractiveAgentTester(args)
    
    try:
        await tester.setup()
        
        if args.task:
            # Run single task
            await tester.run_single_task(args.task)
        else:
            # Interactive REPL
            await tester.run_repl()
            
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
