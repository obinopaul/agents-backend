#!/usr/bin/env python3
"""
WebSocket Transform Pipeline Test
==================================
This test feeds known SSE events through the EXACT same pipeline
that _forward_sse_event uses (IIAgentWebSocketAdapter → StreamBuffer → _transform_data),
and captures the transformed output — i.e., exactly what the frontend
receives via Socket.IO "chat_event".

The goal: see what the frontend ACTUALLY gets, not what the SSE stream produces.

Usage:
    cd agents-backend
    python -m tests.test_websocket_transform

Output:
    - Prints every event the frontend would receive
    - Saves to tests/captured_websocket_events.json
"""

import json
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.app.agent.event_adapter import IIAgentWebSocketAdapter, humanize_tool_name, normalize_tool_name


# =============================================================================
# Simulated SSE events — matching EXACTLY what agent.py yields for a web_search
# =============================================================================
# These are the (event_type, data) pairs that _forward_sse_event would parse
# from SSE strings like "event: tool_call_start\ndata: {...}\n\n"

TOOL_RUN_ID = "019c38bb-bda4-7e02-a9f7-18c2129a0c35"
THREAD_ID = "test-session-20250207"

# Realistic web_search result (what Tavily returns)
WEB_SEARCH_RESULT = {
    "content": json.dumps([
        {
            "type": "page",
            "url": "https://docs.python.org/3.13/whatsnew/3.13.html",
            "title": "What's New In Python 3.13",
            "content": "Python 3.13 introduces several new features including...",
            "score": 0.95
        },
        {
            "type": "page",
            "url": "https://realpython.com/python313-new-features/",
            "title": "Python 3.13: Cool New Features",
            "content": "The latest version of Python brings exciting improvements...",
            "score": 0.88
        }
    ])
}

# The full sequence of SSE events for ONE web_search tool call
SSE_EVENTS = [
    # --- II-Agent format tool_call start (should be SKIPPED by StreamBuffer) ---
    ("tool_call", {
        "status": "start",
        "id": TOOL_RUN_ID,
        "tool_call_id": TOOL_RUN_ID,
        "tool_name": "web_search",
        "tool_display_name": "Searching Web",
        "type": "function",
    }),

    # --- AG-UI format tool_call_start (buffered by StreamBuffer) ---
    ("tool_call_start", {
        "toolCallId": TOOL_RUN_ID,
        "toolCallName": "web_search",
        "thread_id": THREAD_ID,
    }),

    # --- II-Agent format tool_call delta (should be SKIPPED) ---
    ("tool_call", {
        "status": "delta",
        "tool_call_id": TOOL_RUN_ID,
        "tool_input": '{"query": "Python 3.13 new features"}',
    }),

    # --- AG-UI format tool_call_args (buffered by StreamBuffer) ---
    ("tool_call_args", {
        "toolCallId": TOOL_RUN_ID,
        "delta": '{"query": "Python 3.13 new features"}',
    }),

    # --- II-Agent format tool_call stop (should be SKIPPED) ---
    ("tool_call", {
        "status": "stop",
        "tool_call_id": TOOL_RUN_ID,
        "tool_name": "web_search",
        "tool_display_name": "Searching Web",
        "tool_input": '{"query": "Python 3.13 new features"}',
    }),

    # --- AG-UI format tool_call_end (StreamBuffer emits ATOMIC tool_call) ---
    ("tool_call_end", {
        "toolCallId": TOOL_RUN_ID,
    }),

    # --- II-Agent format tool_result (should be SKIPPED by dedupe) ---
    ("tool_result", {
        "status": "info",
        "tool_call_id": TOOL_RUN_ID,
        "tool_name": "web_search",
        "tool_display_name": "Searching Web",
        "result": WEB_SEARCH_RESULT,
        "is_error": False,
    }),

    # --- AG-UI format tool_result from _make_event (passes through → _transform_data) ---
    ("tool_result", {
        "tool_call_id": TOOL_RUN_ID,
        "tool_name": "web_search",
        "tool_display_name": humanize_tool_name("web_search"),
        "tool_input": {"query": "Python 3.13 new features"},
        "result": WEB_SEARCH_RESULT,
        "is_error": False,
        "thread_id": THREAD_ID,
    }),
]


def run_transform_pipeline():
    """
    Run all SSE events through IIAgentWebSocketAdapter.process_event()
    (the same function _forward_sse_event calls) and capture output.
    """
    adapter = IIAgentWebSocketAdapter()
    run_id = "run-test-001"
    
    captured_events = []
    
    print("=" * 80)
    print("WebSocket Transform Pipeline Test")
    print("=" * 80)
    print(f"\nFeeding {len(SSE_EVENTS)} SSE events through the pipeline...\n")
    
    for i, (event_type, data) in enumerate(SSE_EVENTS):
        # This is EXACTLY what _forward_sse_event does:
        ws_event_type, ws_data = adapter.process_event(event_type, data)
        
        if ws_event_type is not None and ws_data is not None:
            # Add run_id (same as _forward_sse_event does)
            ws_data['run_id'] = run_id
            
            # This is what broadcast_to_session emits via Socket.IO:
            socket_event = {
                "type": ws_event_type,
                "content": ws_data,
                "run_id": run_id,
            }
            
            captured_events.append(socket_event)
            
            print(f"[{i+1}/{len(SSE_EVENTS)}] SSE: {event_type} → WebSocket: {ws_event_type}")
            print(f"  Frontend receives: {json.dumps(socket_event, indent=2, default=str)}")
            print()
        else:
            print(f"[{i+1}/{len(SSE_EVENTS)}] SSE: {event_type} → SKIPPED (buffering or filtered)")
    
    print("=" * 80)
    print(f"\nTotal events emitted to frontend: {len(captured_events)}")
    print()
    
    # Analyze each captured event
    for i, evt in enumerate(captured_events):
        evt_type = evt["type"]
        content = evt["content"]
        
        print(f"--- Event {i+1}: {evt_type} ---")
        
        if evt_type == "tool_call":
            print(f"  tool_name:         {content.get('tool_name')!r}")
            print(f"  tool_display_name: {content.get('tool_display_name')!r}")
            print(f"  tool_input:        {content.get('tool_input')!r}")
            print(f"  tool_input type:   {type(content.get('tool_input')).__name__}")
            
            tool_input = content.get("tool_input")
            if isinstance(tool_input, dict):
                print(f"  tool_input.query:  {tool_input.get('query')!r}")
            else:
                print(f"  ⚠️  tool_input is NOT a dict — frontend will see empty query!")
                
        elif evt_type == "tool_result":
            result = content.get("result")
            print(f"  tool_name:          {content.get('tool_name')!r}")
            print(f"  result type:        {type(result).__name__}")
            print(f"  result value:       {str(result)[:200]}...")
            
            # Critical check: Frontend calls parseJson(result) which is JSON.parse(result)
            # If result is a dict, JSON.parse receives "[object Object]" and returns null
            if isinstance(result, str):
                print(f"  ✅ result is a string — frontend parseJson() will work")
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, list):
                        print(f"  ✅ Parses to array with {len(parsed)} items — SearchBrowser will render")
                    else:
                        print(f"  ⚠️  Parses to {type(parsed).__name__} — SearchBrowser expects array")
                except json.JSONDecodeError as e:
                    print(f"  ❌ JSON parse error: {e}")
            elif isinstance(result, dict):
                print(f"  ❌ result is a DICT — frontend parseJson() will FAIL!")
                print(f"     JS: JSON.parse({{...}}) → JSON.parse('[object Object]') → null")
                if "content" in result:
                    print(f"     result has 'content' key with type: {type(result['content']).__name__}")
                    print(f"     The INNER content should be sent as result instead!")
            elif isinstance(result, list):
                print(f"  ⚠️  result is a list — frontend parseJson() will fail")
                print(f"     Should be JSON.stringify'd to string first")
            else:
                print(f"  ❌ result type is unexpected: {type(result).__name__}")
        
        print()
    
    # Frontend simulation: TOOL_CALL matching
    print("=" * 80)
    print("Frontend Matching Simulation")
    print("=" * 80)
    
    tool_calls = [e for e in captured_events if e["type"] == "tool_call"]
    tool_results = [e for e in captured_events if e["type"] == "tool_result"]
    
    print(f"\nTool calls:   {len(tool_calls)}")
    print(f"Tool results: {len(tool_results)}")
    
    # Simulate matching (frontend searches backwards for action.type === tool_name)
    messages = []
    for tc in tool_calls:
        messages.append({
            "action": {
                "type": tc["content"]["tool_name"],
                "data": {**tc["content"]},
            }
        })
    
    for tr in tool_results:
        tool_name = tr["content"]["tool_name"]
        matched = False
        for msg in reversed(messages):
            if msg["action"]["type"] == tool_name and not msg["action"]["data"].get("isResult"):
                msg["action"]["data"]["result"] = tr["content"]["result"]
                msg["action"]["data"]["isResult"] = True
                matched = True
                print(f"\n✅ TOOL_RESULT '{tool_name}' matched TOOL_CALL '{msg['action']['type']}'")
                break
        
        if not matched:
            print(f"\n❌ TOOL_RESULT '{tool_name}' did NOT match any TOOL_CALL!")
            print(f"   Available action types: {[m['action']['type'] for m in messages]}")
    
    # Show final message state (this is what AgentBuild reads)
    print("\n" + "=" * 80)
    print("Final Message State (what AgentBuild renders)")
    print("=" * 80)
    
    for i, msg in enumerate(messages):
        action = msg["action"]
        print(f"\nMessage {i}:")
        print(f"  action.type:              {action['type']!r}")
        print(f"  action.data.tool_input:   {action['data'].get('tool_input')!r}")
        print(f"  action.data.result type:  {type(action['data'].get('result')).__name__}")
        print(f"  action.data.isResult:     {action['data'].get('isResult')}")
        
        # Simulate buildingTitle for WEB_SEARCH
        if action["type"] == "web_search":
            tool_input = action["data"].get("tool_input")
            if isinstance(tool_input, dict):
                search_term = tool_input.get("query", "") or ""
            else:
                search_term = ""
            title = f'Searching: "{search_term}"'
            print(f"  buildingTitle:            {title!r}")
            
            if not search_term:
                print(f"  ⚠️  Empty search term! User would see: Searching: \"\"")
        
        # Simulate parseJson(result)
        result = action["data"].get("result")
        if result is not None:
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    print(f"  parseJson(result):        {type(parsed).__name__} with {len(parsed) if isinstance(parsed, list) else '?'} items")
                except:
                    print(f"  parseJson(result):        null (parse failed)")
            elif isinstance(result, dict):
                print(f"  parseJson(result):        null (JS would get [object Object])")
                print(f"  ❌ THIS IS THE BUG — result is dict, not string!")
            elif isinstance(result, list):
                print(f"  parseJson(result):        null (JS would stringify then fail)")
            else:
                print(f"  parseJson(result):        null (unexpected type)")
    
    # Save captured events to JSON
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(output_dir, "captured_websocket_events.json")
    
    # Also save the final message state
    output_data = {
        "description": "Events captured from IIAgentWebSocketAdapter.process_event() pipeline",
        "total_sse_events_fed": len(SSE_EVENTS),
        "total_websocket_events_emitted": len(captured_events),
        "websocket_events": captured_events,
        "final_message_state": messages,
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\n\n✅ Captured events saved to: {output_file}")
    
    return captured_events, messages


if __name__ == "__main__":
    run_transform_pipeline()
