#!/usr/bin/env python
"""
Direct Slide Tool Test - Isolated Testing with create_react_agent

This script tests the slide tools directly using create_react_agent,
bypassing the main agent infrastructure to isolate tool invocation issues.

Based directly on interactive_agent_test.py which is confirmed working.

Usage:
    python tests/live/slide_system/test_slide_tools_direct.py
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load environment
load_dotenv(project_root / ".env")
load_dotenv(project_root / ".env.server")

# Constants - matches interactive_agent_test.py
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class DirectSlideToolTester:
    """
    Tests slide tools directly using create_react_agent.
    Based on working interactive_agent_test.py pattern.
    """
    
    def __init__(self):
        self.token = None
        self.sandbox_id = None
        self.mcp_url = None
        self.client = None
        self.mcp_client = None
        self.langchain_tools = []
        self.agent = None
        self.llm = None
    
    async def setup(self) -> bool:
        """Initialize sandbox and get tools."""
        print("\n" + "=" * 70)
        print("🧪 Direct Slide Tool Test")
        print(f"   Testing SlideWrite with create_react_agent (no middleware)")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # 1. Initialize HTTP client - EXACTLY like interactive_agent_test.py
        print("\n📋 Step 1: Connecting to backend...")
        self.client = httpx.AsyncClient(
            timeout=180.0,  # Same as working test
            headers={
                'User-Agent': 'DirectSlideToolTest/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
        
        # 2. Login
        if not await self._login():
            print("   ❌ Login failed")
            return False
        
        # 3. Create sandbox
        print("\n📋 Step 2: Creating E2B sandbox...")
        if not await self._create_sandbox():
            print("   ❌ Sandbox creation failed")
            return False
        
        # 4. Wait for MCP server
        print("   ⏳ Waiting for MCP server to initialize...")
        if not await self._wait_for_mcp_server(max_wait_seconds=60):
            print("   ❌ MCP server did not become available")
            return False
        
        # 5. Get tools via MCP adapter
        print("\n📋 Step 3: Getting LangChain tools via MCP...")
        if not await self._get_tools():
            print("   ❌ Failed to get tools")
            return False
        
        # 6. Create agent
        print("\n📋 Step 4: Creating ReAct agent...")
        if not await self._create_agent():
            print("   ❌ Failed to create agent")
            return False
        
        return True
    
    async def _login(self) -> bool:
        """Authenticate with backend - same as interactive_agent_test.py."""
        r = await self.client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code == 200:
            self.token = r.json().get('access_token')
            self.client.headers['Authorization'] = f'Bearer {self.token}'
            print(f"   ✅ Authenticated as {TEST_USER}")
            return True
        print(f"   ❌ Login failed: {r.status_code} - {r.text}")
        return False
    
    async def _create_sandbox(self) -> bool:
        """Create E2B sandbox - same as interactive_agent_test.py."""
        # Use random user_id to ensure a fresh sandbox is created every time
        # This avoids issues with stale/paused sandboxes causing 404s
        user_id = f'direct-slide-test-{uuid.uuid4().hex[:6]}'
        print(f"   📋 Creating sandbox for user: {user_id}")
        
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': user_id}
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
        """Check MCP server health."""
        if not self.mcp_url:
            return False
        try:
            health_url = f"{self.mcp_url}/health"
            r = await self.client.get(health_url, timeout=5.0)
            if r.status_code == 200:
                return True
            print(f"       Health check status: {r.status_code}", end="\r")
            return False
        except Exception as e:
            # print(f"       Health check failed: {e}", end="\r")
            return False
    
    async def _wait_for_mcp_server(self, max_wait_seconds=60) -> bool:
        """Wait for MCP server - same as interactive_agent_test.py."""
        start = datetime.now()
        attempt = 0
        
        print(f"   ⏳ Waiting for MCP server ({self.mcp_url})...")
        while (datetime.now() - start).seconds < max_wait_seconds:
            attempt += 1
            if await self._check_mcp_health():
                print(f"   ✅ MCP server is ready (attempt {attempt})")
                return True
            
            # Skip manual startup - it was causing 404s and confusion
            # The backend's create_sandbox should handle startup.
            # If it fails consistently, it's a backend config issue, not something client should fix.
            if attempt == 10:
                print("   ⚠️ MCP still not ready after 10 attempts...")
            
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
        import uuid as uuid_mod
        session_id = str(uuid_mod.uuid4())
        
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
        # CRITICAL: Use internal localhost URL, NOT the external mcp_url!
        # The MCP server inside the sandbox communicates with tools on localhost:6060
        print("   ⏳ Registering tools (this may take 30-60 seconds)...")
        try:
            internal_tool_url = "http://127.0.0.1:6060"  # Internal sandbox URL
            r = await self.client.post(
                f"{self.mcp_url}/tool-server-url",
                json={"tool_server_url": internal_tool_url},
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
    
    async def _get_tools(self) -> bool:
        """Get tools from MCP server - includes proper initialization."""
        # First, initialize MCP tools (this is the critical step that was missing!)
        if not await self._initialize_mcp_tools():
            print("   ⚠️ MCP tool initialization failed, attempting to connect anyway...")
        
        # Wait a moment for tools to be fully available
        await asyncio.sleep(3)
        
        try:
            self.mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": f"{self.mcp_url}/mcp",
                    "transport": "http"
                },
            })
            
            self.langchain_tools = await self.mcp_client.get_tools()
            print(f"   ✅ Retrieved {len(self.langchain_tools)} LangChain tools")
            
            # Show slide tools specifically
            slide_tools = [t for t in self.langchain_tools if 'slide' in t.name.lower()]
            print(f"   📌 Slide tools: {[t.name for t in slide_tools]}")
            
            return len(self.langchain_tools) > 0
            
        except Exception as e:
            print(f"   ❌ Failed to get tools via MCP: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _create_agent(self) -> bool:
        """Create ReAct agent - same as interactive_agent_test.py."""
        try:
            from backend.src.llms.llm import get_llm
            
            self.llm = get_llm()
            
            # Filter to slide tools only for focused testing
            slide_tools = [t for t in self.langchain_tools if 'slide' in t.name.lower()]
            if slide_tools:
                print(f"   📌 Using {len(slide_tools)} slide tools for focused test")
                self.agent = create_react_agent(self.llm, slide_tools)
            else:
                print(f"   ⚠️ No slide tools found, using all {len(self.langchain_tools)} tools")
                self.agent = create_react_agent(self.llm, self.langchain_tools)
            
            print(f"   ✅ Agent ready!")
            return True
            
        except Exception as e:
            print(f"   ❌ Agent creation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_slide_creation(self):
        """Test slide creation with SlideWrite tool."""
        print("\n📋 Step 5: Testing slide creation...")
        print("-" * 50)
        
        task = """
Use the SlideWrite tool to create a slide with these EXACT parameters:
- presentation_name: "Test Presentation"
- slide_number: 1
- title: "Hello World"
- content: "<h1>Welcome</h1><p>This is a test slide.</p>"

Call the SlideWrite tool NOW and report the result.
"""
        
        print(f"   Task: Create a slide using SlideWrite tool")
        
        try:
            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=task)]
            })
            
            print("\n📋 Agent Response:")
            for msg in result.get("messages", []):
                role = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                tool_calls = getattr(msg, 'tool_calls', [])
                
                if role == 'human':
                    print(f"   👤 Human: {content[:100]}...")
                elif role in ['ai', 'assistant']:
                    if tool_calls:
                        print(f"   🤖 AI (tool calls): {[tc.get('name', 'unknown') for tc in tool_calls]}")
                    if content:
                        print(f"   🤖 AI: {content[:200]}...")
                elif role == 'tool':
                    tool_name = getattr(msg, 'name', 'unknown')
                    print(f"   🔧 Tool [{tool_name}]: {str(content)[:150]}...")
            
            # Check if any tool was called
            tool_messages = [m for m in result.get("messages", []) if getattr(m, 'type', '') == 'tool']
            if tool_messages:
                print(f"\n   ✅ SUCCESS: {len(tool_messages)} tool(s) were invoked!")
                return True
            else:
                print("\n   ⚠️ WARNING: No tools were invoked - agent just generated text")
                return False
                
        except Exception as e:
            print(f"\n   ❌ Error during agent execution: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Clean up resources."""
        print("\n📋 Cleanup...")
        if self.sandbox_id and self.client:
            try:
                await self.client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                print("   ✅ Sandbox deleted")
            except Exception as e:
                print(f"   ⚠️ Cleanup failed: {e}")
        if self.client:
            await self.client.aclose()


async def main():
    tester = DirectSlideToolTester()
    try:
        if await tester.setup():
            await tester.test_slide_creation()
    finally:
        await tester.cleanup()
    print("\n👋 Done!")


if __name__ == "__main__":
    asyncio.run(main())
