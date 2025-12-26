#!/usr/bin/env python3
"""
Live Agent Integration Test with MCP Tool Server

This script creates a LangChain agent that connects to the MCP tool server
and tests various sandbox tools. It's designed to verify end-to-end
functionality of the sandbox and tool server integration.

Requirements:
- MCP server running on port 6060
- Redis running
- Environment variables configured in backend/.env

Usage:
    cd backend
    python tests/live/run_mcp_agent.py
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime
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


# ============================================================================
# Configuration
# ============================================================================

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:6060")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")


# ============================================================================
# MCP Client Integration
# ============================================================================

async def test_mcp_server_connection():
    """Test basic MCP server connectivity."""
    import httpx
    
    print("\n" + "=" * 60)
    print("🔌 Testing MCP Server Connection")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test health endpoint
            response = await client.get(f"{MCP_SERVER_URL}/health")
            if response.status_code == 200:
                print(f"✅ MCP Server is healthy at {MCP_SERVER_URL}")
                return True
            else:
                print(f"❌ MCP Server returned status {response.status_code}")
                return False
    except httpx.ConnectError:
        print(f"❌ Cannot connect to MCP server at {MCP_SERVER_URL}")
        print("   Make sure the MCP server is running:")
        print("   cd backend/src/tool_server && python -m uvicorn main:app --port 6060")
        return False
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        return False


async def list_available_mcp_tools():
    """List all available tools from the MCP server."""
    from src.tool_server.mcp.client import MCPClient
    
    print("\n" + "=" * 60)
    print("🔧 Listing Available MCP Tools")
    print("=" * 60)
    
    try:
        async with MCPClient(server_url=MCP_SERVER_URL) as client:
            # Set test credentials
            credential = {
                "user_api_key": os.getenv("OPENAI_API_KEY", "test"),
                "session_id": str(uuid.uuid4())
            }
            await client.set_credential(credential)
            
            # List tools
            tools = await client.list_tools()
            print(f"\n✅ Found {len(tools)} tools:")
            for tool in tools[:15]:  # Show first 15
                print(f"   - {tool.name}: {tool.description[:50]}...")
            if len(tools) > 15:
                print(f"   ... and {len(tools) - 15} more tools")
            
            return tools
    except Exception as e:
        print(f"❌ Error listing tools: {e}")
        return []


# ============================================================================
# LangChain Agent with MCP Tools
# ============================================================================

async def create_langchain_agent_with_mcp():
    """Create a LangChain agent using MCP tools."""
    
    print("\n" + "=" * 60)
    print("🤖 Creating LangChain Agent with MCP Tools")
    print("=" * 60)
    
    # Check for API key
    if not OPENAI_API_KEY:
        print("⚠️  No OPENAI_API_KEY found. Using mock mode.")
        return None
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_react_agent, AgentExecutor
        from langchain_core.tools import Tool
        from langchain import hub
        from src.tool_server.mcp.client import MCPClient
        
        # Create LLM
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=OPENAI_API_KEY
        )
        print(f"✅ LLM initialized: {llm.model_name}")
        
        # Connect to MCP and get tools
        async with MCPClient(server_url=MCP_SERVER_URL) as mcp_client:
            # Set credentials
            session_id = str(uuid.uuid4())
            await mcp_client.set_credential({
                "user_api_key": OPENAI_API_KEY,
                "session_id": session_id
            })
            print(f"✅ MCP Client connected (session: {session_id[:8]}...)")
            
            # Get available MCP tools
            mcp_tools = await mcp_client.list_tools()
            print(f"✅ Retrieved {len(mcp_tools)} MCP tools")
            
            # Convert MCP tools to LangChain format
            langchain_tools = []
            for mcp_tool in mcp_tools[:10]:  # Limit to first 10 for testing
                
                async def make_tool_func(tool_name):
                    async def tool_func(**kwargs):
                        result = await mcp_client.call_tool(tool_name, kwargs)
                        return str(result)
                    return tool_func
                
                lc_tool = Tool(
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    func=lambda x, tn=mcp_tool.name: f"Async tool {tn} - use with agent",
                    coroutine=await make_tool_func(mcp_tool.name),
                )
                langchain_tools.append(lc_tool)
            
            print(f"✅ Created {len(langchain_tools)} LangChain tools")
            
            # Get ReAct prompt
            try:
                prompt = hub.pull("hwchase17/react")
            except Exception:
                # Fallback prompt if hub is not available
                from langchain_core.prompts import PromptTemplate
                prompt = PromptTemplate.from_template("""
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}
""")
            
            # Create agent
            agent = create_react_agent(llm, langchain_tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=langchain_tools,
                verbose=True,
                max_iterations=5,
                handle_parsing_errors=True
            )
            
            print("✅ Agent created successfully!")
            
            return agent_executor
            
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Install with: pip install langchain langchain-openai")
        return None
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        import traceback
        traceback.print_exc()
        return None


async def run_agent_test(agent_executor, task: str):
    """Run a test task with the agent."""
    
    print("\n" + "-" * 60)
    print(f"📋 Running Agent Task")
    print("-" * 60)
    print(f"Task: {task}")
    print("-" * 60 + "\n")
    
    try:
        result = await agent_executor.ainvoke({"input": task})
        print("\n" + "-" * 60)
        print("✅ Agent Result:")
        print("-" * 60)
        print(result.get("output", result))
        return result
    except Exception as e:
        print(f"❌ Agent error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# Direct Tool Testing (Without Agent)
# ============================================================================

async def test_shell_tool_direct():
    """Test shell tool directly via MCP."""
    from src.tool_server.mcp.client import MCPClient
    
    print("\n" + "=" * 60)
    print("🐚 Testing Shell Tool (Direct MCP Call)")
    print("=" * 60)
    
    try:
        async with MCPClient(server_url=MCP_SERVER_URL) as client:
            # Set credentials
            await client.set_credential({
                "user_api_key": "test",
                "session_id": str(uuid.uuid4())
            })
            
            # Call the Bash tool
            result = await client.call_tool("Bash", {
                "command": "echo 'Hello from MCP Shell!'",
                "description": "Test echo command",
                "session_name": "test"
            })
            
            print(f"✅ Shell command result: {result}")
            return result
    except Exception as e:
        print(f"❌ Shell tool error: {e}")
        return None


async def test_file_tool_direct():
    """Test file tool directly via MCP."""
    from src.tool_server.mcp.client import MCPClient
    
    print("\n" + "=" * 60)
    print("📁 Testing File Tool (Direct MCP Call)")
    print("=" * 60)
    
    try:
        async with MCPClient(server_url=MCP_SERVER_URL) as client:
            # Set credentials
            await client.set_credential({
                "user_api_key": "test",
                "session_id": str(uuid.uuid4())
            })
            
            # Write a test file
            write_result = await client.call_tool("Write", {
                "file_path": "/tmp/mcp_test.txt",
                "content": f"Test file created at {datetime.now()}"
            })
            print(f"✅ File write result: {write_result}")
            
            # Read the file back
            read_result = await client.call_tool("Read", {
                "file_path": "/tmp/mcp_test.txt"
            })
            print(f"✅ File read result: {read_result}")
            
            return read_result
    except Exception as e:
        print(f"❌ File tool error: {e}")
        return None


# ============================================================================
# Main Test Runner
# ============================================================================

async def main():
    """Main test runner."""
    
    print("\n" + "=" * 70)
    print("🚀 MCP Tool Server Live Agent Integration Test")
    print("=" * 70)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   MCP Server: {MCP_SERVER_URL}")
    print(f"   LLM Provider: {LLM_PROVIDER}")
    print("=" * 70)
    
    # Step 1: Test MCP server connection
    if not await test_mcp_server_connection():
        print("\n❌ Cannot proceed without MCP server connection")
        print("\nTo start the MCP server:")
        print("  cd backend/src/tool_server")
        print("  python -m uvicorn main:app --port 6060 --reload")
        return
    
    # Step 2: List available tools
    tools = await list_available_mcp_tools()
    
    # Step 3: Test individual tools directly
    await test_shell_tool_direct()
    await test_file_tool_direct()
    
    # Step 4: Create and run LangChain agent
    if OPENAI_API_KEY:
        agent = await create_langchain_agent_with_mcp()
        if agent:
            # Run a simple test task
            await run_agent_test(
                agent,
                "List the files in the current directory using bash"
            )
    else:
        print("\n⚠️  Skipping agent test - no OPENAI_API_KEY set")
    
    print("\n" + "=" * 70)
    print("✅ Live Integration Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
