#!/usr/bin/env python3
"""
Chat Stream Debug Test - Compares astream() vs astream_events() side-by-side.

Usage:
    python backend/tests/live/test_chat_stream_debug.py

This script runs the same graph with both invocation methods to confirm
that astream_events(version="v2") properly propagates tool events from
nested runnables inside graph nodes (which astream() cannot do).
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
    print(f"Loaded environment from {env_file}")
else:
    print(f"No .env file found at {env_file}")


def build_config_and_state(prompt: str):
    """Build shared config and initial state for tests."""
    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    config = RunnableConfig(
        recursion_limit=100,
        configurable={
            "thread_id": f"test-debug-{id(prompt)}",
            "enable_web_search": True,
            "max_search_results": 5,
            "store": store,
        }
    )
    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "locale": "en-US",
        "enable_background_investigation": False,
    }
    return config, initial_state


async def test_a_astream(graph, prompt: str):
    """Test A: graph.astream() with dual stream modes - log event structure."""
    print("\n" + "=" * 70)
    print("TEST A: graph.astream(stream_mode=['messages', 'updates'], subgraphs=True)")
    print("=" * 70)

    config, initial_state = build_config_and_state(prompt)
    event_count = 0
    errors = []
    tool_events = 0

    try:
        async for item in graph.astream(
            initial_state,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            event_count += 1
            item_type = type(item).__name__
            if isinstance(item, tuple):
                print(f"  Event #{event_count}: tuple(len={len(item)}) -> types: {[type(x).__name__ for x in item]}")
                # Try to unpack as expected by old code: agent, _, event_data
                try:
                    agent, _, event_data = item
                    if isinstance(event_data, tuple):
                        message_chunk, message_metadata = event_data
                        chunk_type = type(message_chunk).__name__
                        if "ToolMessage" in chunk_type:
                            tool_events += 1
                            print(f"    -> ToolMessage found! tool_events={tool_events}")
                        else:
                            print(f"    -> {chunk_type}")
                    elif isinstance(event_data, dict):
                        print(f"    -> dict with keys: {list(event_data.keys())[:5]}")
                except (ValueError, TypeError) as e:
                    errors.append(f"Unpacking error at event #{event_count}: {e}")
                    print(f"    -> UNPACKING ERROR: {e}")
            else:
                print(f"  Event #{event_count}: {item_type}")

            if event_count >= 100:
                print("  ... (truncated at 100 events)")
                break

    except Exception as e:
        errors.append(f"Stream error: {type(e).__name__}: {e}")
        print(f"  STREAM ERROR: {e}")

    print(f"\nTest A Results: {event_count} events, {tool_events} tool events, {len(errors)} errors")
    for err in errors:
        print(f"  ERROR: {err}")
    return tool_events, errors


async def test_b_astream_events(graph, prompt: str):
    """Test B: graph.astream_events(version='v2') - count tool events."""
    print("\n" + "=" * 70)
    print("TEST B: graph.astream_events(version='v2')")
    print("=" * 70)

    config, initial_state = build_config_and_state(prompt)
    event_count = 0
    tool_start_count = 0
    tool_end_count = 0
    chat_stream_count = 0

    try:
        async for event in graph.astream_events(
            initial_state,
            config=config,
            version="v2",
        ):
            event_type = event.get("event")
            event_name = event.get("name", "")
            event_count += 1

            if event_type == "on_tool_start":
                tool_start_count += 1
                print(f"  TOOL START #{tool_start_count}: {event_name}")

            elif event_type == "on_tool_end":
                tool_end_count += 1
                output = event.get("data", {}).get("output", "")
                output_str = str(output)[:200]
                print(f"  TOOL END #{tool_end_count}: {event_name} -> {output_str}")

            elif event_type == "on_chat_model_stream":
                chat_stream_count += 1
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    print(f"  CHAT STREAM #{chat_stream_count}: tool_calls={chunk.tool_calls}")

    except Exception as e:
        print(f"  STREAM ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nTest B Results: {event_count} total events")
    print(f"  tool_start: {tool_start_count}, tool_end: {tool_end_count}, chat_stream: {chat_stream_count}")
    return tool_end_count


async def test_c_astream_events_with_processing(graph, prompt: str):
    """Test C: astream_events fed through _process_message_chunk - end-to-end verification."""
    print("\n" + "=" * 70)
    print("TEST C: astream_events + _process_message_chunk (end-to-end)")
    print("=" * 70)

    from langchain_core.messages import AIMessageChunk, ToolMessage

    config, initial_state = build_config_and_state(prompt)
    thread_id = "test-e2e"

    # Import the processing function
    try:
        from backend.app.agent.api.v1.chat import _process_message_chunk, ReasoningState
        print("  Imported _process_message_chunk successfully")
    except ImportError as e:
        print(f"  Could not import _process_message_chunk: {e}")
        return 0

    reasoning_state = ReasoningState()
    sse_events = []
    tool_result_events = 0
    tool_call_start_events = 0
    tool_call_args_events = 0
    tool_call_end_events = 0
    message_events = 0

    try:
        async for event in graph.astream_events(
            initial_state,
            config=config,
            version="v2",
        ):
            event_type = event.get("event")
            metadata = event.get("metadata", {})

            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and isinstance(chunk, AIMessageChunk):
                    langgraph_node = metadata.get("langgraph_node", "unknown")
                    agent_tuple = (langgraph_node,)
                    async for sse_event in _process_message_chunk(
                        chunk, metadata, thread_id, agent_tuple, reasoning_state
                    ):
                        sse_events.append(sse_event)
                        if "event: tool_call_start" in sse_event:
                            tool_call_start_events += 1
                            print(f"  SSE: tool_call_start #{tool_call_start_events}")
                        elif "event: tool_call_args" in sse_event:
                            tool_call_args_events += 1
                        elif "event: tool_call_end" in sse_event:
                            tool_call_end_events += 1
                        elif "event: message" in sse_event:
                            message_events += 1

            elif event_type == "on_tool_end":
                output = event.get("data", {}).get("output")
                if output and isinstance(output, ToolMessage):
                    langgraph_node = metadata.get("langgraph_node", "unknown")
                    agent_tuple = (langgraph_node,)
                    async for sse_event in _process_message_chunk(
                        output, metadata, thread_id, agent_tuple, reasoning_state
                    ):
                        sse_events.append(sse_event)
                        if "tool_result" in sse_event:
                            tool_result_events += 1
                            print(f"  SSE: tool_result #{tool_result_events}")

    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nTest C Results: {len(sse_events)} SSE events emitted")
    print(f"  tool_call_start: {tool_call_start_events}, tool_call_args: {tool_call_args_events}, tool_call_end: {tool_call_end_events}")
    print(f"  tool_result: {tool_result_events}, message: {message_events}")
    if tool_call_start_events <= 2 and tool_result_events >= 1:
        print("  OK: Tool call events are not duplicated")
    elif tool_call_start_events > 2:
        print("  WARNING: Too many tool_call_start events - likely duplicate emissions")
    return tool_result_events


async def main():
    print("\n" + "=" * 70)
    print("CHAT STREAM DEBUG TEST")
    print("Comparing astream() vs astream_events() for tool event propagation")
    print("=" * 70)

    try:
        from backend.src.graph.builder import graph
        print(f"Loaded graph: {type(graph).__name__}, nodes: {list(graph.nodes.keys())}")
    except ImportError as e:
        print(f"Failed to import graph: {e}")
        return 1

    prompt = "Search the web for weather in New York today"
    print(f"Test prompt: {prompt}")

    # Run tests sequentially
    tool_events_a, errors_a = await test_a_astream(graph, prompt)
    tool_events_b = await test_b_astream_events(graph, prompt)
    tool_events_c = await test_c_astream_events_with_processing(graph, prompt)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Test A (astream):              tool events = {tool_events_a}, errors = {len(errors_a)}")
    print(f"  Test B (astream_events):       tool_end events = {tool_events_b}")
    print(f"  Test C (astream_events + SSE): tool_result SSE events = {tool_events_c}")

    if tool_events_b > 0 and tool_events_a == 0:
        print("\n  CONFIRMED: astream() misses tool events that astream_events() captures.")
    if tool_events_c > 0:
        print("  CONFIRMED: The fix (astream_events + _process_message_chunk) works end-to-end.")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
