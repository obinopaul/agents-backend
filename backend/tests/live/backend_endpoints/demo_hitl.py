#!/usr/bin/env python
"""
Demo script showing Human-in-the-Loop (HITL) with the agent graph.

This demonstrates:
1. Starting the agent with a user query
2. Agent requesting human input via request_human_input tool
3. Handling the interrupt and providing a decision
4. Resuming the workflow based on the decision

Run with: python -m backend.src.graph.demo_hitl
"""

import asyncio
import json
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from backend.src.graph.builder import _build_base_graph


def build_graph_with_checkpointer(checkpointer) -> CompiledStateGraph:
    """Build the graph with a checkpointer for HITL support."""
    builder = _build_base_graph()
    return builder.compile(checkpointer=checkpointer)


async def run_hitl_demo():
    """Run a demo of the HITL workflow."""
    
    print("=" * 70)
    print("HUMAN-IN-THE-LOOP (HITL) DEMO")
    print("=" * 70)
    
    # Build the graph with a memory checkpointer for interrupt/resume
    memory = MemorySaver()
    graph = build_graph_with_checkpointer(checkpointer=memory)
    
    # Configuration with thread_id for state persistence
    config = {
        "configurable": {
            "thread_id": "demo-hitl-001",
            "enable_web_search": False,  # Disable for demo
        }
    }
    
    # Initial state with user query
    initial_state = {
        "messages": [
            HumanMessage(content="I want to build a web app. Can you help me choose a framework?")
        ],
        "enable_background_investigation": False,  # Skip for faster demo
    }
    
    print("\n[USER] I want to build a web app. Can you help me choose a framework?")
    print("-" * 70)
    
    # Run the graph - it will execute until it hits an interrupt or completes
    print("\n[AGENT] Processing...")
    
    final_state = None
    interrupted = False
    interrupt_data = None
    
    try:
        async for event in graph.astream(initial_state, config=config, stream_mode="values"):
            final_state = event
            
            # Show agent messages as they come
            if "messages" in event:
                for msg in event["messages"]:
                    if isinstance(msg, AIMessage) and msg.content:
                        content = str(msg.content)
                        if "[HITL_REQUEST]" in content:
                            # Parse the HITL request
                            marker_idx = content.find("[HITL_REQUEST]")
                            json_part = content[marker_idx + len("[HITL_REQUEST]"):]
                            try:
                                interrupt_data = json.loads(json_part)
                                print(f"\n[AGENT NEEDS INPUT]")
                                for i, q in enumerate(interrupt_data.get("questions", []), 1):
                                    print(f"  Q{i}: {q}")
                            except json.JSONDecodeError:
                                print(f"\n[AGENT] {content[:200]}...")
                        else:
                            print(f"\n[AGENT] {content[:500]}...")
                            
    except Exception as e:
        if "interrupt" in str(e).lower() or "GraphInterrupt" in str(type(e).__name__):
            interrupted = True
            print("\n[SYSTEM] Agent requested human input - workflow paused")
        else:
            raise
    
    # Check if we hit an interrupt
    state = graph.get_state(config)
    if state.next:  # There's a pending node (human_feedback)
        interrupted = True
        print(f"\n[SYSTEM] Workflow paused at node: {state.next}")
        
        # Get the interrupt value if available
        if hasattr(state, 'tasks') and state.tasks:
            for task in state.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    interrupt_data = task.interrupts[0].value
                    print(f"\n[HITL REQUEST]")
                    if isinstance(interrupt_data, dict):
                        print(f"  Questions: {interrupt_data.get('questions', [])}")
                        print(f"  Allowed decisions: {interrupt_data.get('allowed_decisions', [])}")
    
    if interrupted:
        print("\n" + "=" * 70)
        print("HUMAN DECISION TIME")
        print("=" * 70)
        print("\nOptions:")
        print("  1. APPROVE - Accept the agent's work and finish")
        print("  2. EDIT - Provide feedback and let agent continue")
        print("  3. REJECT - Reject and end the workflow")
        
        # Simulate user choosing EDIT with feedback
        print("\n[SIMULATING USER CHOICE: EDIT with feedback]")
        
        user_response = {
            "decision": "edit",
            "feedback": "I prefer React for the frontend. Please focus on React-based solutions.",
            "answers": ["React"]
        }
        
        print(f"\n[USER RESPONSE]")
        print(f"  Decision: {user_response['decision']}")
        print(f"  Feedback: {user_response['feedback']}")
        
        # Resume the graph with the user's response
        print("\n" + "-" * 70)
        print("[RESUMING WORKFLOW WITH USER FEEDBACK]")
        print("-" * 70)
        
        try:
            # Use LangGraph Command to resume after interrupt
            resume_command = Command(resume=user_response)
            async for event in graph.astream(
                resume_command,
                config=config,
                stream_mode="values"
            ):
                final_state = event
                if "messages" in event:
                    last_msg = event["messages"][-1]
                    if isinstance(last_msg, AIMessage) and last_msg.content:
                        content = str(last_msg.content)
                        if "[HITL_REQUEST]" not in content:
                            print(f"\n[AGENT] {content[:500]}...")
                            
        except Exception as e:
            if "interrupt" in str(e).lower():
                print("\n[SYSTEM] Another interrupt requested")
            else:
                print(f"\n[SYSTEM] Workflow completed or error: {e}")
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    
    # Show final state summary
    if final_state:
        msg_count = len(final_state.get("messages", []))
        print(f"\nFinal state:")
        print(f"  - Total messages: {msg_count}")
        print(f"  - needs_human_feedback: {final_state.get('needs_human_feedback', False)}")
        print(f"  - hitl_questions: {final_state.get('hitl_questions')}")


async def run_simple_demo():
    """Run a simpler demo without the interrupt complexity."""
    
    print("=" * 70)
    print("SIMPLE AGENT DEMO (No HITL)")
    print("=" * 70)
    
    # Build the graph (no checkpointer needed for simple demo)
    graph = build_graph_with_checkpointer(checkpointer=None)
    
    config = {
        "configurable": {
            "thread_id": "demo-simple-001",
            "enable_web_search": False,
        }
    }
    
    # Simple query that doesn't need HITL
    initial_state = {
        "messages": [
            HumanMessage(content="What is 2 + 2? Give me a direct answer.")
        ],
        "enable_background_investigation": False,
    }
    
    print("\n[USER] What is 2 + 2? Give me a direct answer.")
    print("-" * 70)
    
    final_state = None
    async for event in graph.astream(initial_state, config=config, stream_mode="values"):
        final_state = event
        if "messages" in event and len(event["messages"]) > 1:
            last_msg = event["messages"][-1]
            if isinstance(last_msg, AIMessage) and last_msg.content:
                print(f"\n[AGENT] {last_msg.content}")
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE - Agent completed without needing HITL")
    print("=" * 70)


if __name__ == "__main__":
    print("\nChoose demo:")
    print("  1. Simple demo (no HITL)")
    print("  2. HITL demo (with interrupt/resume)")
    
    # For automated testing, run the simple demo
    # In interactive mode, you could prompt for choice
    
    print("\nRunning Simple Demo...")
    asyncio.run(run_simple_demo())
    
    print("\n\n")
    print("Running HITL Demo...")
    asyncio.run(run_hitl_demo())
