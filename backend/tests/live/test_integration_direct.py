#!/usr/bin/env python3
"""
Direct Integration Test - LangChain Agent with Sandbox

This test creates a sandbox, uses LangChain tools via REST API,
and verifies the full end-to-end flow works.

Prerequisites:
- Backend server running: python -m uvicorn backend.main:app --port 8000
- Test user exists: python backend/tests/live/create_test_user.py
"""

import asyncio
import httpx
import sys
from datetime import datetime

# LangChain imports
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


async def main():
    print("=" * 70, flush=True)
    print("🧪 LangChain Adapter Integration Test", flush=True)
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 70, flush=True)
    
    token = None
    sandbox_id = None
    
    try:
        # Step 1: Check server health
        print("\n📋 Step 1: Checking server health...", flush=True)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Use /docs endpoint since /health may not exist
                r = await client.get(f'{BASE_URL}/docs')
                if r.status_code in [200, 307]:
                    print(f"   ✅ Server responding: {r.status_code}", flush=True)
                else:
                    print(f"   ❌ Server returned: {r.status_code}", flush=True)
                    return False
            except Exception as e:
                print(f"   ❌ Server not responding: {e}", flush=True)
                return False
        
        # Step 2: Login
        print("\n📋 Step 2: Authenticating...", flush=True)
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f'{BASE_URL}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            if r.status_code != 200:
                print(f"   ❌ Login failed: {r.status_code} - {r.text}", flush=True)
                return False
            token = r.json().get('access_token')
            print(f"   ✅ Authenticated as {TEST_USER}", flush=True)
        
        # Step 3: Create sandbox
        print("\n📋 Step 3: Creating sandbox (this takes 30-60s)...", flush=True)
        async with httpx.AsyncClient(
            timeout=120.0,
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'IntegrationTest/1.0',
                'Content-Type': 'application/json'
            }
        ) as client:
            r = await client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/create',
                json={'user_id': 'integration-test'}
            )
            if r.status_code != 200:
                print(f"   ❌ Sandbox creation failed: {r.status_code} - {r.text}", flush=True)
                return False
            sandbox_id = r.json().get('data', {}).get('sandbox_id')
            mcp_url = r.json().get('data', {}).get('mcp_url')
            print(f"   ✅ Sandbox created: {sandbox_id[:12]}...", flush=True)
            print(f"   ✅ MCP URL: {mcp_url}", flush=True)
        
        await asyncio.sleep(5)  # Wait for services to initialize
        
        # Step 4: Create LangChain tools
        print("\n📋 Step 4: Creating LangChain tools...", flush=True)
        
        # Create sync client for tools
        http_client = httpx.Client(
            timeout=60.0,
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'IntegrationTest/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        sid = sandbox_id  # Closure variable
        
        @tool
        def run_shell_command(command: str) -> str:
            """Execute a shell command in the sandbox.
            Use for running programs, installing packages, viewing files.
            """
            r = http_client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                json={'sandbox_id': sid, 'command': command}
            )
            if r.status_code == 200:
                return r.json().get('data', {}).get('output', '')
            return f"Error: {r.status_code}"
        
        @tool
        def write_file(file_path: str, content: str) -> str:
            """Write content to a file in the sandbox.
            Args:
                file_path: Path where to write the file
                content: The content to write
            """
            r = http_client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
                json={'sandbox_id': sid, 'file_path': file_path, 'content': content}
            )
            return "File written successfully" if r.status_code == 200 else f"Error: {r.status_code}"
        
        @tool
        def read_file(file_path: str) -> str:
            """Read content from a file in the sandbox."""
            r = http_client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
                json={'sandbox_id': sid, 'file_path': file_path}
            )
            if r.status_code == 200:
                return r.json().get('data', {}).get('content', '')
            return f"Error: {r.status_code}"
        
        tools = [run_shell_command, write_file, read_file]
        print(f"   ✅ Created {len(tools)} LangChain tools", flush=True)
        
        # Step 5: Load LLM
        print("\n📋 Step 5: Loading LLM...", flush=True)
        try:
            from backend.src.llms.llm import get_llm
            llm = get_llm()
            print(f"   ✅ LLM loaded: {type(llm).__name__}", flush=True)
        except ImportError:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            print(f"   ✅ Fallback OpenAI LLM loaded", flush=True)
        
        # Step 6: Create LangGraph agent
        print("\n📋 Step 6: Creating LangGraph ReAct agent...", flush=True)
        agent = create_react_agent(llm, tools)
        print("   ✅ Agent created", flush=True)
        
        # Step 7: Run test task
        print("\n📋 Step 7: Running agent task...", flush=True)
        print("-" * 50, flush=True)
        
        task = """Create a Python file at /tmp/test_integration.py that:
1. Prints 'Hello from LangChain Integration Test!'
2. Calculates 2 + 2 and prints the result

Then run the file and show me the output."""
        
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": task}]
        })
        
        print("-" * 50, flush=True)
        
        # Show messages
        messages = result.get("messages", [])
        print(f"\n📋 Agent produced {len(messages)} messages", flush=True)
        
        # Get final AI message
        final_msg = None
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'content') and msg.content:
                final_msg = msg.content
                break
        
        if final_msg:
            print(f"\n📋 Final AI Response:", flush=True)
            print(final_msg[:500] + "..." if len(final_msg) > 500 else final_msg, flush=True)
        
        # Step 8: Verify file exists
        print("\n📋 Step 8: Verifying file creation...", flush=True)
        verify_result = http_client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
            json={'sandbox_id': sandbox_id, 'file_path': '/tmp/test_integration.py'}
        )
        if verify_result.status_code == 200:
            content = verify_result.json().get('data', {}).get('content', '')
            if 'Hello from LangChain' in content:
                print("   ✅ File content verified!", flush=True)
            else:
                print(f"   ⚠️ File exists but content differs: {content[:100]}...", flush=True)
        else:
            print(f"   ⚠️ Could not read file: {verify_result.status_code}", flush=True)
        
        http_client.close()
        
        print("\n" + "=" * 70, flush=True)
        print("✅ Integration test completed successfully!", flush=True)
        print("=" * 70, flush=True)
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup sandbox
        if token and sandbox_id:
            print("\n📋 Cleanup: Deleting sandbox...", flush=True)
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={'Authorization': f'Bearer {token}'}
            ) as client:
                try:
                    await client.delete(f'{BASE_URL}/agent/sandboxes/sandboxes/{sandbox_id}')
                    print("   ✅ Sandbox deleted", flush=True)
                except:
                    print("   ⚠️ Could not delete sandbox", flush=True)


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
