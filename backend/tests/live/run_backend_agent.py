#!/usr/bin/env python3
"""
Standalone Agent Test using Backend's create_agent

This script creates an agent using the FastAPI backend's agent factory
and connects it to the MCP tool server.

Usage:
    cd backend
    python tests/live/run_backend_agent.py
"""

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(backend_path / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_backend_agent():
    """Run an agent using the backend's create_agent factory."""
    
    print("\n" + "=" * 70)
    print("🤖 Running Backend Agent with MCP Tools")
    print("=" * 70)
    
    # Import backend components
    try:
        from src.agents.agents import create_agent
        from src.llms.llm import get_llm
        from src.tool_server.tools.manager import get_sandbox_tools
        from src.tool_server.mcp.client import MCPClient
        
        print("✅ Backend imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're running from the backend directory")
        return
    
    # Configuration
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:6060")
    session_id = str(uuid.uuid4())
    user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    
    print(f"   Session ID: {session_id[:8]}...")
    print(f"   User ID: {user_id}")
    print(f"   MCP Server: {MCP_SERVER_URL}")
    
    # Create credential
    credential = {
        "user_api_key": os.getenv("OPENAI_API_KEY", "test"),
        "session_id": session_id
    }
    
    # Get tools from tool_server
    try:
        # Get sandbox tools (shell, file, web, browser)
        workspace_path = "/tmp/workspace"
        tools = get_sandbox_tools(
            workspace_path=workspace_path,
            credential=credential
        )
        print(f"✅ Got {len(tools)} sandbox tools")
        
        # Show tool names
        for tool in tools[:10]:
            print(f"   - {tool.name}")
        if len(tools) > 10:
            print(f"   ... and {len(tools) - 10} more")
            
    except Exception as e:
        print(f"❌ Error getting tools: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Create agent using backend factory
    try:
        agent = create_agent(
            agent_name="test-agent",
            agent_type="sandbox",
            tools=tools,
            prompt_template="default",
            locale="en-US",
            use_default_middleware=False  # Keep it simple for testing
        )
        print("✅ Agent created using backend factory")
        
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Run a test task
    print("\n" + "-" * 60)
    print("📋 Running Test Task")
    print("-" * 60)
    
    task = "Create a file called test.txt with the content 'Hello World'"
    print(f"Task: {task}")
    
    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": task}]},
            config={"configurable": {"thread_id": session_id}}
        )
        print("\n" + "-" * 60)
        print("✅ Agent Result:")
        print("-" * 60)
        print(result)
        
    except Exception as e:
        print(f"❌ Agent execution error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ Backend Agent Test Complete!")
    print("=" * 70)


async def main():
    """Main entry point."""
    try:
        await run_backend_agent()
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
