#!/usr/bin/env python3
"""
Interactive Sample Graph Test - Tests the DS* Sample Agent Graph.

Usage:
    python backend/tests/live/test_sample_graph.py

This script:
1. Imports and builds the sample graph from backend.src.module.sample.builder
2. Allows interactive input from terminal
3. Streams the graph execution with full visibility into nodes and tool calls
4. Helps identify any errors with the current graph implementation
"""

import asyncio
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
env_file = project_root / "backend" / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  No .env file found at {env_file}")


async def run_interactive_test():
    """Run interactive sample graph test with full streaming visibility."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain_core.runnables import RunnableConfig
    
    # Import the sample graph
    print("\n" + "=" * 60)
    print("📦 LOADING SAMPLE GRAPH")
    print("=" * 60)
    
    try:
        from backend.src.module.sample.builder import graph, build_graph
        from backend.src.module.sample.types import State, VerificationStatus
        print("✅ Successfully imported sample graph modules")
    except ImportError as e:
        print(f"❌ Failed to import sample graph: {e}")
        import traceback
        traceback.print_exc()
        return
    
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()  # For local testing - enables background_tasks middleware

    # Use the pre-compiled graph or build a new one
    print("\n📊 Graph Information:")
    print(f"   Type: {type(graph).__name__}")
    print(f"   Nodes: {list(graph.nodes.keys())}")
    
    # 1. Graph structure as Mermaid diagram (for docs/debugging)
    mermaid_diagram = graph.get_graph().draw_mermaid()
    print(mermaid_diagram)
    # Copy output to mermaid.live for interactive visualization
    
    print("\n" + "=" * 60)
    print("🎯 INTERACTIVE SAMPLE GRAPH TEST")
    print("=" * 60)
    print("This is an interactive test for the DS* Sample Agent Graph.")
    print("The graph follows: START → analyzer → coder → executor → verifier")
    print("\nCommands:")
    print("  - Type your question/task to send to the graph")
    print("  - 'quit', 'exit', or 'q' to stop")
    print("  - 'state' to show current state info")
    print("  - 'clear' to reset conversation")
    print("=" * 60 + "\n")
    
    # Initialize conversation state
    messages = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == "clear":
                messages = []
                print("🧹 Conversation cleared.\n")
                continue
            
            if user_input.lower() == "state":
                print(f"\n📊 Current State:")
                print(f"   Messages: {len(messages)}")
                for i, msg in enumerate(messages):
                    msg_type = type(msg).__name__
                    content = str(msg.content)[:100] + "..." if len(str(msg.content)) > 100 else str(msg.content)
                    print(f"   [{i}] {msg_type}: {content}")
                print()
                continue
            
            # Add user message
            messages.append(HumanMessage(content=user_input))
            
            # Create initial state matching the State TypedDict
            test_state = {
                "messages": messages,
                "needs_human_feedback": False,
                "hitl_questions": None,
                "goto": "analyzer",
                "verification_status": VerificationStatus.PENDING,
                "resources": [],
            }
            
            # Configuration for the graph
            # Note: recursion_limit is the GRAPH-level limit (number of node transitions)
            # This is separate from the node-internal agent recursion limit
            config = RunnableConfig(
                recursion_limit=1000,  # Allow many node transitions in the graph
                configurable={
                    "thread_id": "test_session",
                    "store": store,  # Pass store for InjectedStore tools
                }
            )
            
            print("\n🤖 Processing through graph...\n")
            
            current_node = None
            response_messages = []
            
            try:
                # Stream with events for full visibility
                async for event in graph.astream_events(
                    test_state,
                    config=config,
                    version="v2",
                ):
                    event_type = event.get("event")
                    event_name = event.get("name", "")
                    
                    # Node start
                    if event_type == "on_chain_start":
                        if event_name in ["analyzer", "human_feedback", "coder", "executor", "verifier"]:
                            current_node = event_name
                            print(f"\n  🔄 ENTERING NODE: {event_name}")
                            print("  " + "-" * 40)
                    
                    # Node end
                    elif event_type == "on_chain_end":
                        output = event.get("data", {}).get("output", {})
                        
                        if event_name in ["analyzer", "human_feedback", "coder", "executor", "verifier"]:
                            print(f"\n  ✅ EXITING NODE: {event_name}")
                            if isinstance(output, dict):
                                if "goto" in output:
                                    print(f"     → Next: {output.get('goto', 'unknown')}")
                        
                        # Capture final output
                        if isinstance(output, dict) and "messages" in output:
                            response_messages = output["messages"]
                    
                    # Tool call started
                    elif event_type == "on_tool_start":
                        name = event.get("name", "unknown")
                        data = event.get("data", {})
                        inp = data.get("input", {})
                        print(f"\n  📤 TOOL CALL: {name}")
                        inp_str = str(inp)
                        if len(inp_str) > 400:
                            inp_str = inp_str[:400] + "..."
                        print(f"     Args: {inp_str}")
                    
                    # Tool call finished
                    elif event_type == "on_tool_end":
                        name = event.get("name", "unknown")
                        data = event.get("data", {})
                        out = str(data.get("output", ""))
                        if len(out) > 600:
                            out = out[:600] + "..."
                        print(f"  📥 RESULT [{name}]: {out}")
                    
                    # LLM streaming tokens
                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            # Only print text content, not tool calls
                            if isinstance(chunk.content, str):
                                print(chunk.content, end="", flush=True)
                
                # Update conversation history with response
                if response_messages:
                    messages = response_messages
                    
                    # Print final AI response summary
                    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
                    if ai_messages:
                        last_ai = ai_messages[-1]
                        print("\n\n  📝 FINAL AI RESPONSE:")
                        print("  " + "-" * 40)
                        content = str(last_ai.content)
                        # Wrap long content
                        if len(content) > 500:
                            print(f"  {content[:500]}...")
                        else:
                            print(f"  {content}")
                
            except Exception as e:
                print(f"\n❌ Error during graph execution: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
            
            print("\n")
            
        except KeyboardInterrupt:
            print("\n\n⚡ Interrupted. Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Goodbye!")
            break


def main():
    print("\n" + "=" * 60)
    print("🚀 SAMPLE GRAPH INTERACTIVE TEST")
    print("=" * 60)
    print("Testing: backend.src.module.sample.builder.graph")
    print("=" * 60)
    
    try:
        asyncio.run(run_interactive_test())
    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
