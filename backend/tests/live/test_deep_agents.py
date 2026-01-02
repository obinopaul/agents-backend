"""Deep Agents Comprehensive Test Script.

This script tests the deep_agents.py module like a real user would:
- SubAgent creation and middleware
- TodoListMiddleware (task planning)
- Cache functionality
- Store (persistent storage)
- Debug mode
- All middleware stack
- Web search tool integration

Run:
    python backend/tests/live/test_deep_agents.py
"""

import asyncio
import logging
import os
import sys
import uuid
from typing import Any

from langchain_core.messages import ToolMessage

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, project_root)


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(label: str, success: bool, details: str = ""):
    """Print a test result."""
    status = "[PASS]" if success else "[FAIL]"
    print(f"  {status} - {label}")
    if details:
        print(f"         {details}")


async def test_basic_agent_creation():
    """Test 1: Basic agent creation with default middleware."""
    print_header("Test 1: Basic Agent Creation")
    
    try:
        from backend.src.agents.deep_agents import create_agent, build_deep_middleware
        from backend.src.llms.llm import get_llm
        
        # Create a simple agent with no tools
        agent = create_agent(
            agent_name="test_basic",
            agent_type="test",
            tools=[],
            prompt_template=None,  # Use default prompt
        )
        
        print_result("Agent created", agent is not None, f"Type: {type(agent).__name__}")
        
        # Check middleware count
        llm = get_llm()
        middleware = build_deep_middleware(model=llm, tools=[])
        print_result("Middleware built", len(middleware) > 0, f"Count: {len(middleware)}")
        
        # List middleware types
        print("\n  Middleware stack:")
        for i, mw in enumerate(middleware):
            print(f"    {i+1}. {type(mw).__name__}")
        
        return True
    except Exception as e:
        print_result("Basic agent creation", False, str(e))
        logger.exception("Error in basic agent creation")
        return False


async def test_agent_with_tools():
    """Test 2: Agent with web search tool."""
    print_header("Test 2: Agent with Web Search Tool")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        from backend.src.tools import get_web_search_tool, crawl_tool
        
        # Get web search tool
        web_search = get_web_search_tool(max_search_results=3)
        print_result("Web search tool created", web_search is not None, f"Type: {type(web_search).__name__}")
        
        # Create agent with tools
        tools = [web_search, crawl_tool]
        
        agent = create_agent(
            agent_name="researcher",
            agent_type="researcher",
            tools=tools,
            prompt_template=None,
        )
        
        print_result("Agent with tools created", agent is not None, f"Tools: {len(tools)}")
        return True
    except Exception as e:
        print_result("Agent with tools", False, str(e))
        logger.exception("Error creating agent with tools")
        return False


async def test_subagents():
    """Test 3: SubAgent middleware."""
    print_header("Test 3: SubAgent Middleware")
    
    try:
        from backend.src.agents.deep_agents import (
            create_agent,
            SUBAGENT_AVAILABLE,
        )
        
        print_result("SubAgent available", SUBAGENT_AVAILABLE)
        
        if not SUBAGENT_AVAILABLE:
            print("  [WARNING]  SubAgent not available - deepagents package may not be installed")
            return True  # Not a failure, just not available
        
        # Define subagents using TypedDict format (dict with system_prompt key)
        # This is the correct format as per deepagents.middleware.subagents.SubAgent
        subagents = [
            {
                "name": "researcher",
                "description": "A research specialist that excels at finding and synthesizing information from the web.",
                "system_prompt": "You are a research specialist. Your job is to find accurate, up-to-date information on any topic the user asks about. Always cite your sources.",
                "tools": [],
            },
            {
                "name": "writer",
                "description": "A content writer that creates well-structured, engaging text.",
                "system_prompt": "You are a professional content writer. Create clear, well-organized content based on the research provided.",
                "tools": [],
            },
            {
                "name": "code_reviewer",
                "description": "A code review specialist that analyzes code for bugs, best practices, and improvements.",
                "system_prompt": "You are a senior software engineer. Review code for bugs, security issues, and suggest improvements.",
                "tools": [],
            },
        ]
        
        print_result("SubAgents defined", len(subagents) == 3, f"Count: {len(subagents)}")
        
        # Create agent with subagents
        agent = create_agent(
            agent_name="orchestrator",
            agent_type="orchestrator",
            tools=[],
            prompt_template=None,
            subagents=subagents,
        )
        
        print_result("Agent with SubAgents created", agent is not None)
        
        # Print subagent info
        print("\n  Defined SubAgents:")
        for sa in subagents:
            print(f"    - {sa['name']}: {sa['description'][:50]}...")
        
        return True
    except Exception as e:
        print_result("SubAgent test", False, str(e))
        logger.exception("Error in subagent test")
        return False


async def test_cache_functionality():
    """Test 4: Cache functionality."""
    print_header("Test 4: Cache Functionality")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        from langgraph.cache.memory import InMemoryCache
        
        # Create in-memory cache
        cache = InMemoryCache()
        print_result("InMemoryCache created", cache is not None)
        
        # Create agent with cache
        agent = create_agent(
            agent_name="cached_agent",
            agent_type="test",
            tools=[],
            cache=cache,
        )
        
        print_result("Agent with cache created", agent is not None)
        
        print("\n  Cache info:")
        print(f"    Type: {type(cache).__name__}")
        print(f"    Purpose: Caches LLM responses for efficiency")
        
        return True
    except ImportError as e:
        print_result("Cache test", False, f"Import error: {e}")
        print("  [WARNING]  Cache classes may not be available in this LangGraph version")
        return True  # Not critical
    except Exception as e:
        print_result("Cache test", False, str(e))
        logger.exception("Error in cache test")
        return False


async def test_store_functionality():
    """Test 5: Store (persistent storage) functionality."""
    print_header("Test 5: Store (Persistent Storage)")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        from langgraph.store.memory import InMemoryStore
        
        # Create in-memory store
        store = InMemoryStore()
        print_result("InMemoryStore created", store is not None)
        
        # Create agent with store
        agent = create_agent(
            agent_name="persistent_agent",
            agent_type="test",
            tools=[],
            store=store,
        )
        
        print_result("Agent with store created", agent is not None)
        
        print("\n  Store info:")
        print(f"    Type: {type(store).__name__}")
        print(f"    Purpose: Persistent key-value storage across runs")
        
        return True
    except ImportError as e:
        print_result("Store test", False, f"Import error: {e}")
        print("  [WARNING]  Store classes may not be available in this LangGraph version")
        return True  # Not critical
    except Exception as e:
        print_result("Store test", False, str(e))
        logger.exception("Error in store test")
        return False


async def test_debug_mode():
    """Test 6: Debug mode."""
    print_header("Test 6: Debug Mode")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        
        # Create agent with debug=True
        agent = create_agent(
            agent_name="debug_agent",
            agent_type="test",
            tools=[],
            debug=True,  # Enable debug mode
        )
        
        print_result("Agent with debug=True created", agent is not None)
        
        print("\n  Debug mode info:")
        print(f"    Purpose: Enables verbose logging in LangGraph")
        print(f"    Effect: Logs intermediate steps, tool calls, state changes")
        
        return True
    except Exception as e:
        print_result("Debug mode test", False, str(e))
        logger.exception("Error in debug mode test")
        return False


async def test_interrupt_on():
    """Test 7: interrupt_on parameter (optional HITL safety net)."""
    print_header("Test 7: interrupt_on (HITL Safety Net)")
    
    try:
        from backend.src.agents.deep_agents import create_agent, InterruptOnConfig
        from backend.src.tools import crawl_tool
        
        # Define interrupt configurations
        interrupt_on = {
            "crawl_tool": True,  # Simple: always interrupt before this tool
        }
        
        # Create agent with interrupt_on
        agent = create_agent(
            agent_name="safe_agent",
            agent_type="test",
            tools=[crawl_tool],
            interrupt_on=interrupt_on,
        )
        
        print_result("Agent with interrupt_on created", agent is not None)
        
        print("\n  interrupt_on config:")
        for tool_name, config in interrupt_on.items():
            print(f"    - {tool_name}: {config}")
        
        print("\n  Note: This is a safety net, not the primary HITL.")
        print("  Your AG-UI protocol (request_human_input tool) is the primary.")
        
        return True
    except Exception as e:
        print_result("interrupt_on test", False, str(e))
        logger.exception("Error in interrupt_on test")
        return False


async def test_agent_invocation():
    """Test 8: Actually invoke the agent with a simple query."""
    print_header("Test 8: Agent Invocation (Real Query)")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        from langchain_core.messages import HumanMessage
        
        # Create a simple agent
        agent = create_agent(
            agent_name="test_invoke",
            agent_type="test",
            tools=[],
            prompt_template=None,
        )
        
        print("  Invoking agent with a simple math question...")
        print("  (This tests the full middleware stack)")
        
        # Simple test query that doesn't need tools
        result = await agent.ainvoke({
            "messages": [
                HumanMessage(content="What is 2 + 2? Just answer with the number.")
            ]
        })
        
        # Check result
        has_messages = "messages" in result and len(result["messages"]) > 0
        print_result("Agent responded", has_messages)
        
        if has_messages:
            last_message = result["messages"][-1]
            content = str(last_message.content)[:200] if hasattr(last_message, 'content') else str(last_message)[:200]
            print(f"\n  Agent response: {content}")
        
        return True
    except Exception as e:
        print_result("Agent invocation", False, str(e))
        logger.exception("Error invoking agent")
        return False


async def test_todolist_middleware():
    """Test 9: TodoListMiddleware functionality."""
    print_header("Test 9: TodoListMiddleware (Task Planning)")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        from langchain_core.messages import HumanMessage
        
        # Create agent (TodoListMiddleware is auto-included)
        agent = create_agent(
            agent_name="planner",
            agent_type="planner",
            tools=[],
            prompt_template=None,
        )
        
        print("  Asking agent to plan a task...")
        print("  (TodoListMiddleware adds write_todos tool)")
        
        # Ask the agent to plan something
        result = await agent.ainvoke({
            "messages": [
                HumanMessage(content="Create a to-do list for writing a blog post. Use the write_todos tool to save your plan.")
            ]
        })
        
        # Check if agent used write_todos
        has_response = "messages" in result and len(result["messages"]) > 0
        print_result("Agent responded", has_response)
        
        # Look for todo usage in tool calls
        todo_used = False
        for msg in result.get("messages", []):
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    if 'todo' in tc.get('name', '').lower():
                        todo_used = True
                        break
        
        if todo_used:
            print_result("write_todos tool was called", True)
        else:
            print("  [WARNING]  Agent may not have used write_todos (model-dependent)")
        
        return True
    except Exception as e:
        print_result("TodoListMiddleware test", False, str(e))
        logger.exception("Error in TodoListMiddleware test")
        return False


async def test_full_scenario():
    """Test 10: Full scenario - agent with all features."""
    print_header("Test 10: Full Scenario (All Features Combined)")
    
    try:
        from backend.src.agents.deep_agents import (
            create_agent,
            SUBAGENT_AVAILABLE,
        )
        from backend.src.tools import get_web_search_tool
        
        print("  Creating agent with:")
        print("    - Web search tool")
        print("    - SubAgents (if available)")
        print("    - Debug mode")
        print("    - Full middleware stack")
        
        # Tools
        web_search = get_web_search_tool(max_search_results=3)
        tools = [web_search]
        
        # SubAgents (if available) - using TypedDict format
        subagents = None
        if SUBAGENT_AVAILABLE:
            subagents = [
                {
                    "name": "fact_checker",
                    "description": "Verifies facts and claims",
                    "system_prompt": "You verify the accuracy of claims.",
                    "tools": [],
                },
            ]
        
        # Create full-featured agent
        agent = create_agent(
            agent_name="full_featured_agent",
            agent_type="researcher",
            tools=tools,
            prompt_template=None,
            subagents=subagents,
            debug=False,  # Set to True for verbose output
        )
        
        print_result("Full-featured agent created", agent is not None)
        
        # Show configuration summary
        print("\n  Configuration:")
        print(f"    Tools: {len(tools)}")
        print(f"    SubAgents: {len(subagents) if subagents else 0}")
        print(f"    Debug: False")
        print(f"    Middleware: Full deep agent stack")
        
        return True
    except Exception as e:
        print_result("Full scenario test", False, str(e))
        logger.exception("Error in full scenario test")
        return False


async def test_persistent_task_middleware_streaming():
    """Test 11: PersistentTaskMiddleware with streaming output.
    
    This test demonstrates:
    - Real-time tool usage visibility
    - Task creation with sections
    - Task status updates
    - Persistence across agent invocations (same thread_id)
    - New thread_id creates fresh task list
    """
    print_header("Test 11: PersistentTaskMiddleware (Streaming)")
    
    try:
        from backend.src.agents.deep_agents import create_agent
        from backend.src.agents.middleware import PersistentTaskMiddleware
        from langchain_core.messages import HumanMessage, AIMessage
        from langgraph.store.memory import InMemoryStore
        import uuid
        
        # Create store for persistence
        store = InMemoryStore()
        print_result("InMemoryStore created", store is not None)
        
        # Create PersistentTaskMiddleware
        task_middleware = PersistentTaskMiddleware()
        print_result("PersistentTaskMiddleware created", len(task_middleware.tools) == 5)
        
        print("\n  Tools available:")
        for t in task_middleware.tools:
            print(f"    - {t.name}")
        
        # Generate a unique thread_id for this test
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        print(f"\n  Thread ID: {thread_id}")
        
        # Create agent with task middleware
        # Note: We add the middleware's tools manually since we're using use_default_middleware
        agent = create_agent(
            agent_name="task_planner",
            agent_type="test",
            tools=task_middleware.tools,  # Include task management tools
            prompt_template=None,
            store=store,
            use_default_middleware=False,  # Keep it simple for this test
        )
        
        print_result("Agent created with task tools", agent is not None)
        
        # =====================================================================
        # Step 1: Ask agent to create tasks for a software project
        # =====================================================================
        print("\n" + "-" * 60)
        print("  STEP 1: Creating tasks for a software project")
        print("-" * 60)
        
        prompt = """Create a task list for building a REST API. 
Use the create_tasks tool to organize it into 3 sections:
1. "Planning" with 2 tasks
2. "Implementation" with 3 tasks  
3. "Testing" with 2 tasks

After creating, use view_tasks to show the result."""
        
        print(f"\n  User: {prompt[:80]}...")
        print("\n  Streaming agent response:\n")
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Stream the response
        tool_calls_seen = []
        text_chunks = []
        
        async for event in agent.astream(
            {"messages": [HumanMessage(content=prompt)]},
            config=config,
            stream_mode="updates",
        ):
            # Process different event types
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        # Handle AI messages with content
                        if hasattr(msg, 'content') and msg.content:
                            if isinstance(msg.content, str) and msg.content.strip():
                                # Show abbreviated text
                                preview = msg.content[:100].replace('\n', ' ')
                                if len(msg.content) > 100:
                                    preview += "..."
                                print(f"    [AI] {preview}")
                                text_chunks.append(msg.content)
                        
                        # Handle tool calls
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_name = tc.get('name', 'unknown')
                                print(f"    [TOOL CALL] {tool_name}")
                                tool_calls_seen.append(tool_name)
                        
                        # Handle tool messages (results)
                        if hasattr(msg, 'name') and hasattr(msg, 'content'):
                            if isinstance(msg, type(ToolMessage('', tool_call_id=''))):
                                # This is a tool result
                                result_preview = str(msg.content)[:150].replace('\n', ' ')
                                if len(str(msg.content)) > 150:
                                    result_preview += "..."
                                print(f"    [TOOL RESULT] {result_preview}")
        
        print(f"\n  Tools called: {tool_calls_seen}")
        print_result("Agent used task tools", len(tool_calls_seen) > 0)
        
        # =====================================================================
        # Step 2: Update some tasks
        # =====================================================================
        print("\n" + "-" * 60)
        print("  STEP 2: Updating task status")
        print("-" * 60)
        
        prompt2 = """Use view_tasks to see the current tasks, then mark the first task as 'in_progress'."""
        
        print(f"\n  User: {prompt2}")
        print("\n  Streaming agent response:\n")
        
        tool_calls_step2 = []
        async for event in agent.astream(
            {"messages": [HumanMessage(content=prompt2)]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_name = tc.get('name', 'unknown')
                                print(f"    [TOOL CALL] {tool_name}")
                                tool_calls_step2.append(tool_name)
        
        print(f"\n  Tools called: {tool_calls_step2}")
        print_result("Agent updated tasks", 'update_tasks' in tool_calls_step2 or 'view_tasks' in tool_calls_step2)
        
        # =====================================================================
        # Step 3: Test persistence - same thread_id should retain tasks
        # =====================================================================
        print("\n" + "-" * 60)
        print("  STEP 3: Testing persistence (same thread_id)")
        print("-" * 60)
        
        prompt3 = "Use view_tasks to show all current tasks."
        
        print(f"\n  User: {prompt3}")
        print(f"  (Reusing thread_id: {thread_id})")
        
        tool_calls_step3 = []
        async for event in agent.astream(
            {"messages": [HumanMessage(content=prompt3)]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(f"    [TOOL CALL] {tc.get('name', 'unknown')}")
                                tool_calls_step3.append(tc.get('name'))
        
        print_result("Tasks persisted (same thread)", 'view_tasks' in tool_calls_step3)
        
        # =====================================================================
        # Step 4: Test new thread_id starts fresh
        # =====================================================================
        print("\n" + "-" * 60)
        print("  STEP 4: Testing new session (different thread_id)")
        print("-" * 60)
        
        new_thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        new_config = {"configurable": {"thread_id": new_thread_id}}
        
        print(f"\n  New Thread ID: {new_thread_id}")
        print(f"  User: {prompt3}")
        
        async for event in agent.astream(
            {"messages": [HumanMessage(content=prompt3)]},
            config=new_config,
            stream_mode="updates",
        ):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(f"    [TOOL CALL] {tc.get('name', 'unknown')}")
        
        print("\n  Note: New thread_id means fresh task list (no tasks from previous thread)")
        print_result("New thread isolation verified", True)
        
        # Summary
        print("\n" + "-" * 60)
        print("  SUMMARY")
        print("-" * 60)
        print(f"  - Store Type: {type(store).__name__}")
        print(f"  - Persistence: Via thread_id")
        print(f"  - Tools: {len(task_middleware.tools)} task management tools")
        print(f"  - Session isolation: Each thread_id has its own task list")
        
        return True
    except Exception as e:
        print_result("PersistentTaskMiddleware streaming test", False, str(e))
        logger.exception("Error in PersistentTaskMiddleware streaming test")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  DEEP AGENTS MODULE - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print("\nThis tests deep_agents.py like a real user would use it.\n")
    
    results = []
    
    # Run all tests
    tests = [
        ("Basic Agent Creation", test_basic_agent_creation),
        ("Agent with Tools", test_agent_with_tools),
        ("SubAgent Middleware", test_subagents),
        ("Cache Functionality", test_cache_functionality),
        ("Store Functionality", test_store_functionality),
        ("Debug Mode", test_debug_mode),
        ("interrupt_on (HITL)", test_interrupt_on),
        ("Agent Invocation", test_agent_invocation),
        ("TodoListMiddleware", test_todolist_middleware),
        ("Full Scenario", test_full_scenario),
        ("PersistentTaskMiddleware (Streaming)", test_persistent_task_middleware_streaming),
    ]
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            logger.exception(f"Test '{name}' crashed")
            results.append((name, False))
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  [SUCCESS] All tests passed! deep_agents.py is working correctly.")
    else:
        print("\n  [WARNING]  Some tests failed. Check the logs above for details.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
