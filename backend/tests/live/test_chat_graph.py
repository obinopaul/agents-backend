#!/usr/bin/env python3
"""
Chat Graph Direct Test - Tests the main agent graph without HTTP/SSE layer.

Usage:
    python backend/tests/live/test_chat_graph.py

This script:
1. Imports the same graph used by chat.py (backend.src.graph.builder.graph)
2. Runs a web_search tool call directly
3. Checks if tool execution succeeds or fails
4. Helps isolate whether the issue is in the graph or in chat.py's event handling
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


async def test_graph_with_web_search():
    """Test the chat graph directly with a web_search prompt."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain_core.runnables import RunnableConfig
    
    print("\n" + "=" * 70)
    print("📦 LOADING MAIN CHAT GRAPH (backend.src.graph.builder.graph)")
    print("=" * 70)
    
    try:
        from backend.src.graph.builder import graph
        print("✅ Successfully imported main graph")
        print(f"   Type: {type(graph).__name__}")
        print(f"   Nodes: {list(graph.nodes.keys())}")
    except ImportError as e:
        print(f"❌ Failed to import graph: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test prompts that should trigger web_search
    test_prompts = [
        "Search the web for weather in New York today"
    ]
    
    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore()
    
    for prompt in test_prompts:
        print("\n" + "=" * 70)
        print(f"🧪 TEST: {prompt}")
        print("=" * 70)
        
        # Create initial state
        messages = [HumanMessage(content=prompt)]
        
        # Configuration matching what chat.py uses
        config = RunnableConfig(
            recursion_limit=100,
            configurable={
                "thread_id": f"test-graph-{id(prompt)}",
                "enable_web_search": True,
                "max_search_results": 5,
                "store": store,
            }
        )
        
        initial_state = {
            "messages": messages,
            "locale": "en-US",
            "enable_background_investigation": False,
        }
        
        tool_call_count = 0
        tool_result_count = 0
        errors = []
        
        try:
            print("\n🤖 Streaming graph events...")
            
            async for event in graph.astream_events(
                initial_state,
                config=config,
                version="v2",
            ):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # Node transitions
                if event_type == "on_chain_start":
                    if event_name in ["background_investigator", "base", "human_feedback"]:
                        print(f"\n  🔄 ENTERING NODE: {event_name}")
                
                elif event_type == "on_chain_end":
                    if event_name in ["background_investigator", "base", "human_feedback"]:
                        print(f"  ✅ EXITING NODE: {event_name}")
                
                # Tool call started
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_call_count += 1
                    data = event.get("data", {})
                    args = data.get("input", {})
                    print(f"\n  📤 TOOL CALL #{tool_call_count}: {tool_name}")
                    args_str = str(args)[:200]
                    print(f"     Args: {args_str}")
                
                # Tool call finished - THIS IS WHAT WE'RE TESTING
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_result_count += 1
                    data = event.get("data", {})
                    output = data.get("output", "")
                    output_str = str(output)[:300]
                    print(f"  📥 TOOL RESULT #{tool_result_count} [{tool_name}]:")
                    print(f"     Output: {output_str}")
                    
                    if not output:
                        print("  ⚠️  WARNING: Empty tool output!")
                
                # LLM streaming - just show we're getting responses
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        if isinstance(chunk.content, str) and len(chunk.content) < 50:
                            print(chunk.content, end="", flush=True)
            
            print("\n\n" + "-" * 70)
            print("📊 RESULTS:")
            print(f"   Tool calls: {tool_call_count}")
            print(f"   Tool results: {tool_result_count}")
            
            if tool_call_count > 0 and tool_result_count == tool_call_count:
                print("   ✅ All tool calls received results - GRAPH WORKS!")
            elif tool_call_count > 0 and tool_result_count < tool_call_count:
                print("   ❌ Missing tool results - TOOL EXECUTION FAILED!")
            elif tool_call_count == 0:
                print("   ⚠️  No tool calls made (LLM may not have used tools)")
            
        except Exception as e:
            print(f"\n\n❌ ERROR during graph execution: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            errors.append(str(e))
        
        if errors:
            print("\n❌ ERRORS FOUND:")
            for err in errors:
                print(f"   - {err}")
            return 1
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)
    return 0


def main():
    print("\n" + "=" * 70)
    print("🚀 CHAT GRAPH DIRECT TEST")
    print("=" * 70)
    print("Testing: backend.src.graph.builder.graph (same as chat.py)")
    print("Purpose: Check if tool execution works without HTTP/SSE layer")
    print("=" * 70)
    
    try:
        exit_code = asyncio.run(test_graph_with_web_search())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted. Goodbye!")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
