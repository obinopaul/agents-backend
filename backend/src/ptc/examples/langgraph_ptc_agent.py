#!/usr/bin/env python3
"""LangGraph Agent with PTC Integration Example.

This script demonstrates how to create a LangGraph agent that uses
the PTC (Programmatic Tool Calling) module for code execution.

The agent:
1. Receives a task from the user
2. Plans the approach
3. Writes Python code to solve the problem
4. Executes the code in a secure Daytona sandbox via PTCSandbox
5. Returns the results

Requirements:
    pip install langchain-openai langgraph

Environment Variables:
    OPENAI_API_KEY: Your OpenAI API key
    DAYTONA_API_KEY: Your Daytona API key (get from https://app.daytona.io)

Usage:
    cd backend
    python -m src.ptc.examples.langgraph_ptc_agent
"""

import asyncio
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# Step 1: Import PTC Module Components
# =============================================================================

from backend.src.ptc import PTCSandbox, Session, SessionManager
from backend.src.config.core import (
    CoreConfig,
    DaytonaConfig,
    FilesystemConfig,
    LoggingConfig,
    MCPConfig,
    SecurityConfig,
)


# =============================================================================
# Step 2: Define Agent State
# =============================================================================

class AgentState(TypedDict):
    """State for our LangGraph agent."""
    
    task: str  # The user's task/question
    plan: str  # The agent's plan
    code: str  # Generated Python code
    result: str  # Execution result from sandbox
    error: str | None  # Any errors
    messages: list  # Conversation messages


# =============================================================================
# Step 3: Create PTC Config and Sandbox
# =============================================================================

def create_ptc_config() -> CoreConfig:
    """Create configuration for PTC module."""
    return CoreConfig(
        daytona=DaytonaConfig(
            api_key=os.getenv("DAYTONA_API_KEY", ""),
            base_url="https://app.daytona.io/api",
            python_version="3.12",
            snapshot_enabled=False,  # Disabled due to API bug
        ),
        security=SecurityConfig(
            max_execution_time=300,  # 5 minutes
            max_code_length=50000,
        ),
        mcp=MCPConfig(servers=[]),  # No MCP servers for this demo
        logging=LoggingConfig(level="INFO"),
        filesystem=FilesystemConfig(),
    )


# =============================================================================
# Step 4: Define Agent Nodes
# =============================================================================

async def planner_node(state: AgentState) -> AgentState:
    """Plan how to solve the task."""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    response = await llm.ainvoke([
        {"role": "system", "content": """You are a planning assistant. 
Given a task, create a brief plan to solve it using Python code.
Keep the plan concise - just 2-3 bullet points."""},
        {"role": "user", "content": f"Task: {state['task']}"}
    ])
    
    state["plan"] = response.content
    return state


async def coder_node(state: AgentState) -> AgentState:
    """Generate Python code to execute the plan."""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    response = await llm.ainvoke([
        {"role": "system", "content": """You are a Python code generator.
Write Python code to accomplish the task. The code will run in a sandbox.
Rules:
- Use print() to output results
- Keep code simple and focused
- Only output the Python code, no markdown or explanations"""},
        {"role": "user", "content": f"""Task: {state['task']}

Plan: {state['plan']}

Write Python code to accomplish this:"""}
    ])
    
    # Clean code (remove markdown if present)
    code = response.content
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    
    state["code"] = code.strip()
    return state


async def executor_node(state: AgentState, sandbox: PTCSandbox) -> AgentState:
    """Execute code in the PTC sandbox."""
    try:
        result = await sandbox.execute(state["code"])
        
        if result.success:
            state["result"] = result.output
            state["error"] = None
        else:
            state["result"] = ""
            state["error"] = result.error or "Unknown execution error"
            
    except Exception as e:
        state["result"] = ""
        state["error"] = f"Execution failed: {str(e)}"
    
    return state


# =============================================================================
# Step 5: Build the LangGraph
# =============================================================================

def build_agent_graph(sandbox: PTCSandbox):
    """Build the LangGraph agent with PTC integration."""
    from langgraph.graph import StateGraph, END
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("executor", lambda state: asyncio.get_event_loop().run_until_complete(
        executor_node(state, sandbox)
    ))
    
    # Define edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "coder")
    workflow.add_edge("coder", "executor")
    workflow.add_edge("executor", END)
    
    return workflow.compile()


# =============================================================================
# Step 6: Main Async Runner
# =============================================================================

async def run_agent(task: str) -> dict:
    """Run the LangGraph agent with PTC sandbox."""
    
    print("\n" + "=" * 60)
    print("LangGraph + PTC Agent")
    print("=" * 60)
    
    # Validate environment
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable not set")
    if not os.getenv("DAYTONA_API_KEY"):
        raise ValueError("DAYTONA_API_KEY environment variable not set")
    
    # Create PTC config and sandbox
    config = create_ptc_config()
    config.validate_api_keys()
    
    sandbox = PTCSandbox(config)
    
    try:
        # Initialize sandbox
        print("\n[1] Initializing Daytona sandbox...")
        await sandbox.setup()
        print(f"    Sandbox ID: {sandbox.sandbox_id}")
        
        # Build and run the agent graph
        print("\n[2] Running LangGraph agent...")
        graph = build_agent_graph(sandbox)
        
        # Initial state
        initial_state: AgentState = {
            "task": task,
            "plan": "",
            "code": "",
            "result": "",
            "error": None,
            "messages": [],
        }
        
        # Run the graph
        final_state = await asyncio.to_thread(graph.invoke, initial_state)
        
        # Display results
        print("\n[3] Results:")
        print("-" * 40)
        print(f"Task: {final_state['task']}")
        print(f"\nPlan:\n{final_state['plan']}")
        print(f"\nGenerated Code:\n{final_state['code']}")
        print(f"\nExecution Output:\n{final_state['result']}")
        
        if final_state['error']:
            print(f"\nError: {final_state['error']}")
        
        return final_state
        
    finally:
        # Cleanup sandbox
        print("\n[4] Cleaning up sandbox...")
        await sandbox.cleanup()
        print("    Done!")


# =============================================================================
# Demo Runner
# =============================================================================

async def main():
    """Run demo tasks through the agent."""
    
    # Example tasks to demonstrate
    demo_tasks = [
        "Calculate the first 10 Fibonacci numbers and print them",
        # Uncomment for more examples:
        # "Create a list of the first 5 prime numbers",
        # "Calculate the factorial of 10",
    ]
    
    for task in demo_tasks:
        try:
            await run_agent(task)
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    print(__doc__)
    asyncio.run(main())
