"""Test script for the Claude Code agent graph.

This script tests the claude_code module's graph with subagent support.
Run from the project root:
    python backend/tests/live/claude_code/test_claude_code_agent.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from uuid import uuid4

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_claude_code_agent(user_input: str, thread_id: str = None):
    """Run the claude_code agent with the given user input.
    
    Args:
        user_input: The user's query or request
        thread_id: Optional thread ID for conversation continuity
    """
    from backend.src.module.claude_code import build_graph
    from backend.src.config.configuration import get_recursion_limit
    
    # Build the graph
    graph = build_graph()
    
    print("\n" + "=" * 60)
    print("CLAUDE CODE AGENT TEST")
    print("=" * 60)
    print(f"Thread ID: {thread_id or 'default'}")
    print(f"Input: {user_input}")
    print("=" * 60 + "\n")
    
    # Set up initial state
    initial_state = {
        "messages": [{"role": "user", "content": user_input}],
    }
    
    # Configuration - minimal config without MCP
    config = {
        "configurable": {
            "thread_id": thread_id or str(uuid4()),
            # No MCP settings - we're testing without external tools
            "enable_web_search": True,  # Enable web search if needed
            "enable_feedback_tool": False,  # Disable HITL for testing
            "always_require_feedback": False,  # Don't require feedback after each response
        },
        "recursion_limit": get_recursion_limit(default=100),
    }
    
    print("Starting agent execution...")
    print("-" * 40)
    
    last_message_cnt = 0
    final_state = None
    
    try:
        async for s in graph.astream(
            input=initial_state, 
            config=config, 
            stream_mode="values"
        ):
            try:
                final_state = s
                if isinstance(s, dict) and "messages" in s:
                    if len(s["messages"]) <= last_message_cnt:
                        continue
                    last_message_cnt = len(s["messages"])
                    message = s["messages"][-1]
                    
                    # Print message in a readable format
                    if hasattr(message, 'pretty_print'):
                        message.pretty_print()
                    elif isinstance(message, dict):
                        role = message.get("role", "unknown")
                        content = message.get("content", "")
                        print(f"\n[{role.upper()}]: {content[:500]}...")
                    else:
                        print(f"\nMessage: {message}")
            except Exception as e:
                logger.error(f"Error processing stream output: {e}")
                print(f"Error processing output: {str(e)}")
                
    except Exception as e:
        logger.exception(f"Agent execution failed: {e}")
        print(f"\n[ERROR] Agent execution failed: {e}")
        return None
    
    print("\n" + "-" * 40)
    print("Agent execution completed!")
    
    # Print final response
    if final_state and "messages" in final_state:
        final_messages = final_state["messages"]
        print(f"\nTotal messages: {len(final_messages)}")
        
        # Print the last AI message
        for msg in reversed(final_messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                print("\n" + "=" * 60)
                print("FINAL RESPONSE:")
                print("=" * 60)
                content = msg.content if hasattr(msg, 'content') else str(msg)
                print(content[:2000])  # Limit output length
                if len(content) > 2000:
                    print("... [truncated]")
                break
    
    return final_state


async def test_simple_question():
    """Test with a simple question."""
    print("\n" + "#" * 70)
    print("# TEST 1: Simple Question")
    print("#" * 70)
    
    result = await run_claude_code_agent(
        "What is 2 + 2? Just give me the answer."
    )
    return result is not None


async def test_research_question():
    """Test with a research question that might use the research subagent."""
    print("\n" + "#" * 70)
    print("# TEST 2: Research Question (may trigger subagent)")
    print("#" * 70)
    
    result = await run_claude_code_agent(
        "Search the web for the latest news about AI agents and give me a brief summary."
    )
    return result is not None


async def test_multi_step_task():
    """Test with a multi-step task."""
    print("\n" + "#" * 70)
    print("# TEST 3: Multi-step Task")
    print("#" * 70)
    
    result = await run_claude_code_agent(
        "I need you to help me understand the differences between synchronous and "
        "asynchronous programming. Please explain with examples and use web search "
        "if needed to find the most up-to-date information."
    )
    return result is not None


async def interactive_mode():
    """Run in interactive mode for conversation testing."""
    print("\n" + "=" * 70)
    print("INTERACTIVE MODE - Claude Code Agent")
    print("=" * 70)
    print("Type your messages to chat with the agent.")
    print("Type 'exit' or 'quit' to end the session.")
    print("=" * 70 + "\n")
    
    thread_id = str(uuid4())
    print(f"Session Thread ID: {thread_id}\n")
    
    while True:
        try:
            user_input = input("\n[YOU]: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ("exit", "quit", "q"):
                print("\nEnding session. Goodbye!")
                break
            
            await run_claude_code_agent(user_input, thread_id=thread_id)
            
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


async def main():
    """Main entry point for the test script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the Claude Code agent graph")
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode for conversation testing"
    )
    parser.add_argument(
        "--test", "-t",
        choices=["simple", "research", "multi", "all"],
        default="simple",
        help="Which test to run (default: simple)"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Custom query to run"
    )
    
    args = parser.parse_args()
    
    print(f"\n{'=' * 70}")
    print(f"Claude Code Agent Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")
    
    if args.interactive:
        await interactive_mode()
    elif args.query:
        await run_claude_code_agent(args.query)
    elif args.test == "all":
        results = []
        results.append(("Simple Question", await test_simple_question()))
        results.append(("Research Question", await test_research_question()))
        results.append(("Multi-step Task", await test_multi_step_task()))
        
        print("\n" + "=" * 70)
        print("TEST RESULTS SUMMARY")
        print("=" * 70)
        for name, passed in results:
            status = "✓ PASSED" if passed else "✗ FAILED"
            print(f"  {name}: {status}")
        print("=" * 70)
    elif args.test == "simple":
        await test_simple_question()
    elif args.test == "research":
        await test_research_question()
    elif args.test == "multi":
        await test_multi_step_task()


if __name__ == "__main__":
    asyncio.run(main())
