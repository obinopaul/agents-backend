#!/usr/bin/env python
"""
Direct Slide Tool Test - Isolated Testing with create_react_agent

This script tests the slide tools directly using create_react_agent,
bypassing the main agent infrastructure to isolate tool invocation issues.

Usage:
    python tests/live/slide_system/test_slide_tools_direct.py
"""

import asyncio
import os
import sys
from pathlib import Path

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

# Constants
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TEST_USER = os.getenv("TEST_USER", "sandbox_test")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "TestPass123!")


async def main():
    """Test slide tools directly with create_react_agent."""
    print("=" * 70)
    print("🧪 Direct Slide Tool Test")
    print("   Testing SlideWrite with create_react_agent (no middleware)")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Login
        print("\n📋 Step 1: Authenticating...")
        login_resp = await client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if login_resp.status_code != 200:
            print(f"   ❌ Login failed: {login_resp.status_code}")
            print(f"   Response: {login_resp.text}")
            return
        
        token = login_resp.json().get('access_token')
        token_type = login_resp.json().get('token_type', 'Bearer')
        if not token:
            print(f"   ❌ No token received. Response: {login_resp.json()}")
            return
        print(f"   ✅ Authenticated as {TEST_USER}")
        
        headers = {"Authorization": f"{token_type} {token}"}
        # Set headers on client for all subsequent requests
        client.headers.update(headers)
        
        # Step 2: Create sandbox
        print("\n📋 Step 2: Creating sandbox...")
        sandbox_resp = await client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            headers=headers,
            json={'user_id': 'slide-tools-test'}
        )
        if sandbox_resp.status_code != 200:
            print(f"   ❌ Sandbox creation failed: {sandbox_resp.status_code}")
            return
        
        sandbox_data = sandbox_resp.json().get('data', {})
        sandbox_id = sandbox_data.get('sandbox_id')
        mcp_url = sandbox_data.get('mcp_url')
        
        if not sandbox_id or not mcp_url:
            print(f"   ❌ Missing sandbox_id or mcp_url in response")
            return
        
        print(f"   ✅ Sandbox: {sandbox_id[:20]}...")
        print(f"   ✅ MCP URL: {mcp_url}")
        
        try:
            # Step 3: Wait for MCP server (with manual startup fallback)
            print("\n📋 Step 3: Waiting for MCP server...")
            mcp_ready = False
            for i in range(15):  # 75s total
                try:
                    health_resp = await client.get(f"{mcp_url}/health", timeout=5.0)
                    if health_resp.status_code == 200:
                        print(f"   ✅ MCP server ready (attempt {i+1})")
                        mcp_ready = True
                        break
                except Exception:
                    pass
                
                # Try manual startup after 2 failed attempts
                if i == 2:
                    print("   ⚠️ MCP not ready, attempting manual startup via E2B SDK...")
                    try:
                        from e2b import Sandbox
                        # Connect to the existing sandbox (sync E2B SDK)
                        sbx = Sandbox.connect(sandbox_id)
                        sbx.commands.run("bash /app/start-services.sh &", timeout=5, background=True)
                        print("   ✅ Manual startup command sent")
                    except Exception as e:
                        print(f"   ⚠️ Manual startup failed (ignoring): {e}")
                
                await asyncio.sleep(5)
            
            if not mcp_ready:
                print("   ❌ MCP server not ready after 75s")
                return
            
            # Step 4: Get tools via MCP adapter
            print("\n📋 Step 4: Loading tools from MCP...")
            try:
                mcp_client = MultiServerMCPClient({
                    "sandbox": {
                        "url": f"{mcp_url}/mcp",
                        "transport": "http"
                    }
                })
                tools = await mcp_client.get_tools()
                print(f"   ✅ Loaded {len(tools)} tools")
                
                # Filter to just slide tools for focused testing
                slide_tools = [t for t in tools if 'slide' in t.name.lower()]
                print(f"   📌 Slide tools found: {[t.name for t in slide_tools]}")
                
                if not slide_tools:
                    print("   ⚠️ No slide tools found! Using all tools.")
                    test_tools = tools
                else:
                    # Use only slide tools + minimal helpers for focused test
                    test_tools = slide_tools
                    print(f"   📌 Using {len(test_tools)} tools for focused test")
                
            except Exception as e:
                print(f"   ❌ Failed to load tools: {e}")
                import traceback
                traceback.print_exc()
                return
            
            # Step 5: Create agent with create_react_agent
            print("\n📋 Step 5: Creating ReAct agent...")
            from backend.src.llms.llm import get_llm
            
            llm = get_llm()
            agent = create_react_agent(llm, test_tools)
            print(f"   ✅ Agent created with {len(test_tools)} tools")
            
            # Step 6: Test slide creation
            print("\n📋 Step 6: Testing slide creation...")
            print("   Task: Create a slide using SlideWrite tool")
            print("-" * 50)
            
            task = """
Use the SlideWrite tool to create a slide with these parameters:
- presentation_name: "Test Presentation"
- slide_number: 1
- title: "Hello World"
- content: "<h1>Welcome</h1><p>This is a test slide.</p>"

Just call the tool and report the result.
"""
            
            try:
                result = await agent.ainvoke({
                    "messages": [HumanMessage(content=task)]
                })
                
                # Print all messages
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
                else:
                    print("\n   ⚠️ WARNING: No tools were invoked - agent just generated text")
                    
            except Exception as e:
                print(f"\n   ❌ Error during agent execution: {e}")
                import traceback
                traceback.print_exc()
        
        finally:
            # Cleanup
            print("\n📋 Cleanup: Deleting sandbox...")
            try:
                await client.delete(
                    f'{BASE_URL}/api/v1/agent/sandbox/{sandbox_id}',
                    headers=headers
                )
                print("   ✅ Sandbox deleted")
            except Exception as e:
                print(f"   ⚠️ Cleanup failed: {e}")
    
    print("\n👋 Done!")


if __name__ == "__main__":
    asyncio.run(main())
