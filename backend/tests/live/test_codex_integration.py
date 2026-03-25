#!/usr/bin/env python3
"""
Test Script for Codex and Claude Code Integration

This script tests the integration of Codex SSE server and Claude Code MCP
with the agents-backend project.

Usage:
    python backend/tests/live/test_codex_integration.py

Requirements:
    - Backend server running (docker-compose up -d)
    - E2B API key configured
    - User configured with Codex credentials (optional)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
API_V1 = f"{BASE_URL}/api/v1"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


async def test_agent_stream_with_codex():
    """
    Test that the agent stream endpoint:
    1. Creates a sandbox
    2. Registers Codex SSE server (if credentials available)
    3. Exposes VS Code URL
    4. Returns proper status events
    
    This test acts as a USER - sending a real task and expecting results.
    """
    print("\n" + "=" * 70)
    print("TEST: Agent Stream with Codex Integration (USER SIMULATION)")
    print("=" * 70)
    
    # First, we need to login to get a JWT token
    print("\n1. Logging in to get JWT token...")
    async with httpx.AsyncClient(timeout=30) as client:
        # Use the swagger login endpoint with query params (not JSON body)
        # See: backend/tests/live/backend_endpoints/test_agent_endpoints.py line 242-244
        login_resp = await client.post(
            f"{API_V1}/auth/login/swagger",
            params={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        
        if login_resp.status_code != 200:
            print(f"   ❌ Login failed: {login_resp.status_code}")
            print(f"   Response: {login_resp.text[:500]}")
            print("\n   Note: Make sure the backend is running and test user exists.")
            print("   Create test user with: python backend/tests/create_test_user.py")
            return False
        
        token_data = login_resp.json()
        # Token is directly in response, not nested under 'data'
        token = token_data.get("access_token")
        token_type = token_data.get("token_type", "Bearer")
        if not token:
            print(f"   ❌ No access token in response: {token_data}")
            return False
        
        print(f"   ✅ Login successful (token_type: {token_type})")
    
    # Now test the agent stream with a REAL task
    print("\n2. Testing /agent/agent/stream endpoint...")
    print("   📝 Task: Build a basic calculator app and deploy it")
    
    headers = {"Authorization": f"{token_type} {token}"}
    
    # Use a realistic user prompt that will use the sandbox
    payload = {
        "module": "general",
        "messages": [
            {"role": "user", "content": "Create a simple Python calculator that can add, subtract, multiply and divide. Save it as calculator.py in the workspace and run it to test it works."}
        ],
        "thread_id": f"test-codex-{asyncio.get_event_loop().time()}",
        "enable_background_investigation": False,  # Faster
        "enable_web_search": False,  # Use only sandbox tools
    }
    
    events_received = []
    codex_ready = False
    vscode_ready = False
    mcp_ready = False
    sandbox_id = None
    vscode_url = None
    codex_url = None
    
    print("\n3. Streaming agent response...")
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            async with client.stream(
                "POST",
                f"{BASE_URL}/agent/agent/stream",  # Note: /agent/agent/stream, not /api/v1/agent/agent/stream
                json=payload,
                headers={**headers, "Accept": "text/event-stream"},
            ) as response:
                if response.status_code != 200:
                    print(f"   ❌ Stream failed: {response.status_code}")
                    error_text = await response.aread()
                    print(f"   Response: {error_text.decode()[:500]}")
                    return False
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # Parse SSE
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            events_received.append((event_type, data))
                            
                            # Track specific events
                            if data.get("type") == "sandbox_ready":
                                sandbox_id = data.get("sandbox_id")
                                print(f"   📦 Sandbox ready: {sandbox_id}")
                            
                            elif data.get("type") == "mcp_ready":
                                mcp_ready = True
                                print(f"   🔧 MCP ready at: {data.get('mcp_url')}")
                            
                            elif data.get("type") == "codex_ready":
                                codex_ready = True
                                codex_url = data.get("codex_url")
                                print(f"   🤖 Codex ready at: {codex_url}")
                            
                            elif data.get("type") == "vscode_ready":
                                vscode_ready = True
                                vscode_url = data.get("vscode_url")
                                print(f"\n   " + "=" * 50)
                                print(f"   💻 VS CODE URL (click to open in browser):")
                                print(f"   👉 {vscode_url}")
                                print(f"   " + "=" * 50 + "\n")
                            
                            elif data.get("type") == "complete":
                                print(f"   ✅ Stream complete")
                                # Check completion event for URLs
                                if data.get("vscode_url"):
                                    vscode_url = data.get("vscode_url")
                                if data.get("codex_url"):
                                    codex_url = data.get("codex_url")
                                break
                            
                            elif event_type == "message":
                                content = data.get("content", "")[:100]
                                if content:
                                    print(f"   💬 Message: {content}...")
                            
                            elif event_type == "tool":
                                tool_name = data.get("name", data.get("tool_name", "?"))
                                tool_type = data.get("type", "?")
                                print(f"   🔧 Tool {tool_type}: {tool_name}")
                                    
                        except json.JSONDecodeError:
                            pass
                            
        except httpx.TimeoutException:
            print("   ⚠️ Stream timed out (this is expected for long operations)")
    
    # Print summary with prominent URL display
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Total events received: {len(events_received)}")
    print(f"Sandbox ID: {sandbox_id}")
    print(f"MCP Ready: {'✅' if mcp_ready else '❌'}")
    print(f"Codex Ready: {'✅' if codex_ready else '❌ (Codex credentials may not be configured)'}")
    print(f"VS Code Ready: {'✅' if vscode_ready else '❌'}")
    
    # Prominently display the VS Code URL
    if vscode_url:
        print("\n" + "*" * 70)
        print("*" + " " * 68 + "*")
        print("*   🖥️  VS CODE URL - CLICK TO VIEW CODE IN BROWSER:                *")
        print("*" + " " * 68 + "*")
        print(f"*   {vscode_url:<62} *")
        print("*" + " " * 68 + "*")
        print("*" * 70)
    else:
        print("\n⚠️  VS Code URL not received - check if sandbox was created properly")
    
    if codex_url:
        print(f"\n🤖 Codex SSE URL: {codex_url}")
    
    # Event type summary
    print("\nEvent types received:")
    event_counts = {}
    for event_type, _ in events_received:
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    for event_type, count in sorted(event_counts.items()):
        print(f"  - {event_type}: {count}")
    
    return mcp_ready  # At minimum, MCP should be ready


async def test_codex_agent_tool():
    """
    Test the CodexAgentTool directly (without full agent integration).
    
    This requires a running sandbox with Codex SSE server.
    """
    print("\n" + "=" * 60)
    print("TEST: CodexAgentTool Direct Test")
    print("=" * 60)
    
    try:
        from backend.src.agents.tools.codex_agent import create_codex_tool
        print("   ✅ CodexAgentTool imported successfully")
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    # Create a mock Codex URL (would need actual sandbox for full test)
    codex_tool = create_codex_tool(
        codex_url="http://localhost:1324/messages",
        timeout=60,
        session_id="test-session"
    )
    
    print(f"   ✅ CodexAgentTool created")
    print(f"      Name: {codex_tool.name}")
    print(f"      Description: {codex_tool.description[:100]}...")
    
    return True


async def test_configuration_fields():
    """
    Test that Configuration class has all required fields.
    """
    print("\n" + "=" * 60)
    print("TEST: Configuration Fields")
    print("=" * 60)
    
    try:
        from backend.src.config.configuration import Configuration
        
        # Check for new fields
        required_fields = ["codex_url", "vscode_url", "thread_id", "sandbox_id", "mcp_url"]
        
        config = Configuration()
        
        for field in required_fields:
            if hasattr(config, field):
                print(f"   ✅ Field '{field}' exists")
            else:
                print(f"   ❌ Field '{field}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CODEX & CLAUDE CODE INTEGRATION TESTS")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Configuration fields
    results["Configuration Fields"] = await test_configuration_fields()
    
    # Test 2: CodexAgentTool import
    results["CodexAgentTool Import"] = await test_codex_agent_tool()
    
    # Test 3: Agent stream with Codex (requires running server)
    print("\n\n⚠️  The following test requires the backend server to be running.")
    print("   Start with: docker-compose up -d")
    
    try:
        results["Agent Stream Integration"] = await test_agent_stream_with_codex()
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        results["Agent Stream Integration"] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! 🎉")
    else:
        print("Some tests failed. Check the output above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
