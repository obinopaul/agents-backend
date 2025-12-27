#!/usr/bin/env python3
"""
Sandbox Agent Example

This script demonstrates how to use the sandbox tools via the FastAPI backend.
It creates an E2B sandbox and executes commands/file operations.

Note: The MCP SSE connection may timeout depending on your MCP server configuration.
This example uses the direct REST API which is fully functional.

Usage:
    python run_mcp_agent.py
"""

import asyncio
import httpx
import uuid
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class SandboxAgent:
    """Agent that uses sandbox tools via REST API."""
    
    def __init__(self):
        self.token = None
        self.sandbox_id = None
        self.mcp_url = None
        self.client = None
    
    async def setup(self):
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                'User-Agent': 'SandboxAgent/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
        return await self.login()
    
    async def login(self) -> bool:
        """Authenticate and get JWT token."""
        r = await self.client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code == 200:
            self.token = r.json().get('access_token')
            self.client.headers['Authorization'] = f'Bearer {self.token}'
            print("✅ Authenticated")
            return True
        print(f"❌ Login failed: {r.status_code}")
        return False
    
    async def create_sandbox(self) -> bool:
        """Create a new E2B sandbox."""
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'sandbox-agent'}
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            self.sandbox_id = data.get('sandbox_id')
            self.mcp_url = data.get('mcp_url')
            print(f"✅ Sandbox created: {self.sandbox_id}")
            print(f"   MCP URL: {self.mcp_url}")
            return True
        print(f"❌ Sandbox creation failed: {r.status_code}")
        return False
    
    async def write_file(self, path: str, content: str) -> bool:
        """Write a file to the sandbox."""
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
            json={
                'sandbox_id': self.sandbox_id,
                'file_path': path,
                'content': content
            }
        )
        return r.status_code == 200
    
    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox."""
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
            json={
                'sandbox_id': self.sandbox_id,
                'file_path': path
            }
        )
        if r.status_code == 200:
            return r.json().get('data', {}).get('content', '')
        return ''
    
    async def run_command(self, command: str) -> str:
        """Execute a command in the sandbox."""
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
            json={
                'sandbox_id': self.sandbox_id,
                'command': command
            }
        )
        if r.status_code == 200:
            return r.json().get('data', {}).get('output', '')
        return f"Error: {r.status_code}"
    
    async def cleanup(self):
        """Delete sandbox and close client."""
        if self.sandbox_id:
            await self.client.delete(
                f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
            )
            print("✅ Sandbox cleaned up")
        if self.client:
            await self.client.aclose()


async def main():
    """Main example: create sandbox, write code, run it."""
    print("=" * 70)
    print("🤖 Sandbox Agent Example")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    agent = SandboxAgent()
    
    try:
        # Setup
        print("\n📋 Step 1: Setting up...")
        if not await agent.setup():
            return False
        
        # Create sandbox
        print("\n📋 Step 2: Creating sandbox...")
        if not await agent.create_sandbox():
            return False
        
        # Wait for services
        print("\n⏳ Waiting for sandbox services...")
        await asyncio.sleep(5)
        
        # Write Python file
        print("\n📋 Step 3: Writing Python code...")
        code = '''
import sys
import os

print("=" * 50)
print("Hello from Sandbox Agent!")
print("=" * 50)
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"User: {os.environ.get('USER', 'unknown')}")

# Do some computation
result = sum(range(1, 101))
print(f"Sum of 1-100: {result}")
print("SUCCESS!")
'''
        if await agent.write_file('/tmp/agent_demo.py', code):
            print("   ✅ File written: /tmp/agent_demo.py")
        else:
            print("   ❌ Failed to write file")
            return False
        
        # Read it back
        content = await agent.read_file('/tmp/agent_demo.py')
        print(f"   ✅ File content length: {len(content)} chars")
        
        # Run the code
        print("\n📋 Step 4: Executing Python code...")
        output = await agent.run_command('python3 /tmp/agent_demo.py')
        print(f"\n   Output:\n{output}")
        
        # Run some shell commands
        print("\n📋 Step 5: Running shell commands...")
        
        commands = [
            "uname -a",
            "python3 --version",
            "which python3",
        ]
        for cmd in commands:
            output = await agent.run_command(cmd)
            print(f"   $ {cmd}")
            print(f"   → {output.strip()}")
        
        print("\n" + "=" * 70)
        print("✅ Example completed successfully!")
        print("=" * 70)
        
        print("\n📋 Available Tools via this API:")
        print("   • write_file / read_file - File operations")
        print("   • run_command - Shell execution")
        print("   • create_sandbox / cleanup - Sandbox lifecycle")
        print("\n   For full tool list, see: docs/api-contracts/tool-server.md")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await agent.cleanup()


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
