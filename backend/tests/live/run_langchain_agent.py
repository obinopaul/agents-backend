#!/usr/bin/env python3
"""
LangChain Agent with Sandbox Tools

This script demonstrates:
1. Using get_llm() from the backend for LLM access
2. Creating LangChain tools that wrap sandbox REST API
3. Running an agent that performs tasks in the sandbox

Usage:
    python run_langchain_agent.py
"""

import asyncio
import httpx
import uuid
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# LangChain imports
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class SandboxToolkit:
    """Creates LangChain tools that wrap the sandbox REST API."""
    
    def __init__(self, token: str, sandbox_id: str):
        self.token = token
        self.sandbox_id = sandbox_id
        self.client = httpx.Client(
            timeout=60.0,
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'LangChainAgent/1.0',
                'Content-Type': 'application/json'
            }
        )
    
    def run_command(self, command: str) -> str:
        """Execute a shell command in the sandbox."""
        r = self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
            json={'sandbox_id': self.sandbox_id, 'command': command}
        )
        if r.status_code == 200:
            return r.json().get('data', {}).get('output', '')
        return f"Error: {r.status_code}"
    
    def write_file(self, file_path: str, content: str) -> str:
        """Write content to a file in the sandbox."""
        r = self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
            json={
                'sandbox_id': self.sandbox_id,
                'file_path': file_path,
                'content': content
            }
        )
        if r.status_code == 200:
            return f"Successfully wrote to {file_path}"
        return f"Error writing file: {r.status_code}"
    
    def read_file(self, file_path: str) -> str:
        """Read content from a file in the sandbox."""
        r = self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
            json={'sandbox_id': self.sandbox_id, 'file_path': file_path}
        )
        if r.status_code == 200:
            return r.json().get('data', {}).get('content', '')
        return f"Error reading file: {r.status_code}"
    
    def list_directory(self, path: str = "/tmp") -> str:
        """List contents of a directory."""
        return self.run_command(f"ls -la {path}")
    
    def run_python(self, code: str) -> str:
        """Execute Python code in the sandbox."""
        temp_file = f"/tmp/temp_code_{uuid.uuid4().hex[:8]}.py"
        self.write_file(temp_file, code)
        result = self.run_command(f"python3 {temp_file}")
        self.run_command(f"rm {temp_file}")
        return result
    
    def create_tools(self):
        """Create LangChain tools bound to this sandbox instance."""
        toolkit = self
        
        @tool
        def run_shell_command(command: str) -> str:
            """Execute a shell command in the sandbox. 
            Use for running programs, installing packages, viewing files, etc.
            Args:
                command: The shell command to execute
            """
            return toolkit.run_command(command)
        
        @tool
        def write_file(file_path: str, content: str) -> str:
            """Write content to a file in the sandbox.
            Args:
                file_path: Path where to write the file (e.g., /tmp/myfile.py)
                content: The content to write to the file
            """
            return toolkit.write_file(file_path, content)
        
        @tool
        def read_file(file_path: str) -> str:
            """Read content from a file in the sandbox.
            Args:
                file_path: Path of the file to read
            """
            return toolkit.read_file(file_path)
        
        @tool
        def list_directory(path: str = "/tmp") -> str:
            """List contents of a directory in the sandbox.
            Args:
                path: Directory path to list (default: /tmp)
            """
            return toolkit.list_directory(path)
        
        @tool
        def run_python_code(code: str) -> str:
            """Execute Python code in the sandbox.
            Args:
                code: The Python code to execute
            """
            return toolkit.run_python(code)
        
        return [
            run_shell_command,
            write_file,
            read_file,
            list_directory,
            run_python_code,
        ]
    
    def close(self):
        self.client.close()


async def setup_sandbox() -> tuple[str, str]:
    """Login and create sandbox, return (token, sandbox_id)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Login
        r = await client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code != 200:
            raise Exception("Login failed")
        token = r.json().get('access_token')
        
        # Create sandbox
        client.headers['Authorization'] = f'Bearer {token}'
        r = await client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'langchain-agent'}
        )
        if r.status_code != 200:
            raise Exception("Sandbox creation failed")
        sandbox_id = r.json().get('data', {}).get('sandbox_id')
        
        return token, sandbox_id


async def cleanup_sandbox(token: str, sandbox_id: str):
    """Delete sandbox when done."""
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={'Authorization': f'Bearer {token}'}
    ) as client:
        await client.delete(f'{BASE_URL}/agent/sandboxes/sandboxes/{sandbox_id}')


async def run_langchain_agent():
    """Main function to run the LangChain agent."""
    print("=" * 70)
    print("🤖 LangChain Agent with Sandbox Tools")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    token = None
    sandbox_id = None
    toolkit = None
    
    try:
        # Step 1: Import get_llm from backend
        print("\n📋 Step 1: Loading LLM...")
        try:
            from backend.src.llms.llm import get_llm
            llm = get_llm()
            print(f"   ✅ LLM loaded: {type(llm).__name__}")
        except ImportError as e:
            print(f"   ⚠️ Could not import get_llm: {e}")
            print("   Falling back to OpenAI...")
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            print(f"   ✅ LLM loaded: {type(llm).__name__}")
        
        # Step 2: Create sandbox
        print("\n📋 Step 2: Creating sandbox...")
        token, sandbox_id = await setup_sandbox()
        print(f"   ✅ Sandbox: {sandbox_id}")
        
        await asyncio.sleep(5)  # Wait for services
        
        # Step 3: Create tools
        print("\n📋 Step 3: Creating sandbox tools...")
        toolkit = SandboxToolkit(token, sandbox_id)
        tools = toolkit.create_tools()
        print(f"   ✅ Created {len(tools)} tools:")
        for tool_item in tools:
            print(f"      - {tool_item.name}")
        
        # Step 4: Create agent using langgraph's create_react_agent
        print("\n📋 Step 4: Creating LangGraph ReAct agent...")
        agent = create_react_agent(llm, tools)
        print("   ✅ Agent ready!")
        
        # Step 5: Run task
        print("\n📋 Step 5: Running agent task...")
        print("-" * 70)
        
        task = """Create a Python file called /tmp/fibonacci.py that:
1. Defines a function to calculate the nth Fibonacci number
2. Prints the first 10 Fibonacci numbers when run
Then run the file and show me the output."""
        
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": task}]
        })
        
        print("-" * 70)
        print("\n📋 Agent Messages:")
        for msg in result.get("messages", []):
            role = getattr(msg, 'type', 'unknown')
            content = getattr(msg, 'content', '')
            if content:
                print(f"\n[{role.upper()}]")
                print(f"{content[:500]}{'...' if len(content) > 500 else ''}")
        
        print("\n✅ Agent task completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        print("\n📋 Cleanup...")
        if toolkit:
            toolkit.close()
        if token and sandbox_id:
            await cleanup_sandbox(token, sandbox_id)
            print("   ✅ Sandbox deleted")
    
    print("\n" + "=" * 70)
    print("✅ LangChain Agent Example Complete!")
    print("=" * 70)


if __name__ == '__main__':
    success = asyncio.run(run_langchain_agent())
    sys.exit(0 if success else 1)
