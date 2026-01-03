#!/usr/bin/env python3
"""
Interactive Chat Script - Switch between Standard and Deep Agents.

This script allows you to chat with an agent created by either:
1. backend.src.agents.agents.create_agent (Standard)
2. backend.src.agents.deep_agents.create_agent (Deep)

It uses a simple mock tool to verify tool execution without complex dependencies.
"""

import sys
import os
import asyncio
import structlog
from typing import List

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.getcwd())

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

# Import agent factories via string or direct import
# We import both to ensure they are available
try:
    from backend.src.agents.agents import create_agent as create_standard_agent
    from backend.src.agents.deep_agents import create_agent as create_deep_agent
    from backend.src.llms.llm import get_llm
    from backend.src.tools import get_web_search_tool, crawl_tool, create_view_image_tool
    from langgraph.store.memory import InMemoryStore
except ImportError as e:
    print(f"❌ Error importing backend modules: {e}")
    print("Make sure you are running this from the project root.")
    sys.exit(1)


# Setup logging to avoid clutter
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()

store = InMemoryStore()

# --- Mock Tool ---
@tool
def get_current_time(timezone: str = "UTC") -> str:
    """Get the current time for a timezone.
    
    Args:
        timezone: The timezone to get time for (e.g. 'UTC', 'America/New_York').
    """
    from datetime import datetime
    return f"The current time in {timezone} is {datetime.now().isoformat()}"

# Note: crawl_tool and get_web_search_tool are tools/factories. 
# get_web_search_tool() returns a tool. crawl_tool is a tool instance (usually).
# create_view_image_tool() returns a tool.
# We must instantiate factories.

# Safely instantiate tools that are factories
tools_list = [get_current_time, crawl_tool]

try:
    tools_list.append(get_web_search_tool())
except Exception:
    # Fallback if get_web_search_tool fails (e.g. API keys)
    pass

try:
    tools_list.append(create_view_image_tool())
except Exception:
    pass

TEST_TOOLS = tools_list


async def run_chat(agent, agent_name: str):
    """Run the chat loop."""
    print(f"\n💬 Chatting with {agent_name}. Type 'exit' to quit.")
    print("-" * 60)
    
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
            
            print("🤖 Agent is thinking...", end="", flush=True)
            
            # Prepare input
            inputs = {"messages": chat_history + [HumanMessage(content=user_input)]}
            
            # Run agent
            # Use ainvoke for async execution
            result = await agent.ainvoke(inputs, config={"recursion_limit": 50})
            
            # Update history
            messages = result["messages"] if isinstance(result, dict) else result
            
            # Find the new messages (simple diff logic or just take the last AI message)
            # Standard LangGraph returns full state
            if "messages" in result:
                # Get the last AI message
                last_msg = result["messages"][-1]
                print("\r" + " " * 30 + "\r", end="") # Clear thinking line
                print(f"Agent: {last_msg.content}")
                
                # Check for tool calls in the sequence
                # (Optional: print tool calls if they happened recently)
                for msg in result["messages"][len(chat_history):]:
                     if isinstance(msg, AIMessage) and msg.tool_calls:
                         for tc in msg.tool_calls:
                             print(f"   🛠️  Called Tool: {tc['name']} ({tc['args']})")
                     elif isinstance(msg, ToolMessage):
                         print(f"   ✅ Tool Result: {msg.content[:100]}...")
                         
                chat_history = result["messages"]
            else:
                 print("\rAgent response format unexpected.")
            
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

async def main():
    print("\nSelect Agent Factory:")
    print("1. Standard Agent (backend.src.agents.agents.create_agent)")
    print("2. Deep Agent     (backend.src.agents.deep_agents.create_agent)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    factory = None
    name = ""
    
    if choice == "1":
        factory = create_standard_agent
        name = "Standard Agent"
    elif choice == "2":
        factory = create_deep_agent
        name = "Deep Agent"
    else:
        print("Invalid choice.")
        return

    print(f"\nInitializing {name}...")
    try:
        # We assume standard creating signature.
        # deep_agents.py create_agent has args like "agent_name", "agent_type".
        # agents.py create_agent has args like "agent_name", "agent_type".
        # Check signatures from my memory/views:
        # agents.py: create_agent(agent_name, agent_type, tools, prompt_template, ...)
        # deep_agents.py: create_agent(agent_name, agent_type, tools, prompt_template, ..., subagents=...)
        
        args = {
            "agent_name": "TestAgent",
            "agent_type": "general",
            "tools": TEST_TOOLS,
            "prompt_template": "general", # Might default?
            "store": store
        }
        
        # Instantiate
        agent = factory(**args)
        print("✅ Agent created successfully.")
        
        await run_chat(agent, name)
        
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
