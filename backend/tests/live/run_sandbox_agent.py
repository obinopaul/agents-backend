#!/usr/bin/env python3
"""
Live Sandbox Agent Test - Uses Agent-Infra Sandbox with LangChain tools

This script tests the sandbox container via the LangChain tools integration.
It requires the sandbox container to be running on port 8090.

Requirements:
- Docker container running: cd backend/src/sandbox/agent_infra_sandbox && docker-compose up -d
- OPENAI_API_KEY set in environment

Usage:
    cd backend
    python tests/live/run_sandbox_agent.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv

load_dotenv(backend_path / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_sandbox_connection():
    """Test basic sandbox connectivity."""
    from agent_sandbox import AsyncSandbox
    
    print("\n" + "=" * 60)
    print("🔌 Testing Sandbox Connection")
    print("=" * 60)
    
    url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    timeout = float(os.environ.get("AGENT_INFRA_TIMEOUT", "60"))
    
    try:
        client = AsyncSandbox(base_url=url, timeout=timeout)
        context = await client.sandbox.get_context()
        print(f"✅ Sandbox connected!")
        print(f"   Home directory: {context.home_dir}")
        return True
    except Exception as e:
        print(f"❌ Sandbox connection failed: {e}")
        print("   Make sure sandbox is running:")
        print("   cd backend/src/sandbox/agent_infra_sandbox && docker-compose up -d")
        return False


async def test_shell_command():
    """Test shell command execution."""
    from agent_sandbox import AsyncSandbox
    
    print("\n" + "=" * 60)
    print("🐚 Testing Shell Command Execution")
    print("=" * 60)
    
    url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    timeout = float(os.environ.get("AGENT_INFRA_TIMEOUT", "60"))
    
    try:
        client = AsyncSandbox(base_url=url, timeout=timeout)
        
        # Execute command
        result = await client.shell.exec_command(
            command="echo 'Hello from sandbox!' && date",
            timeout=30
        )
        
        output = result.data.output if hasattr(result, 'data') else str(result)
        print(f"✅ Shell output:\n{output}")
        return True
    except Exception as e:
        print(f"❌ Shell command failed: {e}")
        return False


async def test_file_operations():
    """Test file write and read."""
    from agent_sandbox import AsyncSandbox
    
    print("\n" + "=" * 60)
    print("📁 Testing File Operations")
    print("=" * 60)
    
    url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    timeout = float(os.environ.get("AGENT_INFRA_TIMEOUT", "60"))
    
    try:
        client = AsyncSandbox(base_url=url, timeout=timeout)
        
        # Write a file
        test_content = f"Test file created at {datetime.now()}"
        await client.file.write(
            path="/tmp/sandbox_test.txt",
            content=test_content
        )
        print(f"✅ File written: /tmp/sandbox_test.txt")
        
        # Read the file back
        content = await client.file.read(path="/tmp/sandbox_test.txt")
        print(f"✅ File content: {content}")
        return True
    except Exception as e:
        print(f"❌ File operation failed: {e}")
        return False


async def test_langchain_tools():
    """Test LangChain tools integration."""
    print("\n" + "=" * 60)
    print("🔧 Testing LangChain Tools")
    print("=" * 60)
    
    try:
        from src.sandbox.agent_infra_sandbox.langchain_tools import create_sandbox_tools
        
        tools = create_sandbox_tools()
        print(f"✅ Created {len(tools)} LangChain tools:")
        for tool in tools[:10]:
            print(f"   - {tool.name}")
        return True
    except Exception as e:
        print(f"❌ LangChain tools error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_langchain_agent():
    """Run a full LangChain agent with sandbox tools."""
    print("\n" + "=" * 60)
    print("🤖 Running LangChain Agent with Sandbox Tools")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set - skipping agent test")
        return True  # Not a failure, just skipped
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_react_agent, AgentExecutor
        from langchain import hub
        from src.sandbox.agent_infra_sandbox.langchain_tools import create_sandbox_tools
        
        # Create LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        print(f"✅ LLM initialized")
        
        # Create sandbox tools
        tools = create_sandbox_tools()
        print(f"✅ Created {len(tools)} sandbox tools")
        
        # Get ReAct prompt
        try:
            prompt = hub.pull("hwchase17/react")
        except Exception:
            from langchain_core.prompts import PromptTemplate
            prompt = PromptTemplate.from_template("""
You are a helpful assistant. Use the tools to complete tasks.

Tools: {tools}
Tool Names: {tool_names}

Question: {input}
Thought: {agent_scratchpad}
""")
        
        # Create agent
        agent = create_react_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=3,
        )
        
        # Run a simple task
        print("\n" + "-" * 40)
        print("Running agent task...")
        print("-" * 40)
        
        result = await agent_executor.ainvoke({
            "input": "Check the current directory and list files"
        })
        
        print("\n" + "-" * 40)
        print("✅ Agent Result:")
        print("-" * 40)
        print(result.get("output", result))
        return True
        
    except Exception as e:
        print(f"❌ Agent error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test runner."""
    print("\n" + "=" * 70)
    print("🚀 Live Sandbox Agent Integration Test")
    print("=" * 70)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Sandbox URL: {os.environ.get('AGENT_INFRA_URL', 'http://localhost:8090')}")
    print("=" * 70)
    
    results = {}
    
    # Run tests
    results["Connection"] = await test_sandbox_connection()
    
    if results["Connection"]:
        results["Shell"] = await test_shell_command()
        results["Files"] = await test_file_operations()
        results["LangChainTools"] = await test_langchain_tools()
        
        # Only run agent if tools work
        if results["LangChainTools"]:
            results["Agent"] = await run_langchain_agent()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"   {icon} {test_name}")
    
    print("-" * 70)
    print(f"   Passed: {passed}/{total}")
    print("=" * 70)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
