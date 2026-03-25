"""
Test QueryHandler._forward_sse_event reasoning flow.

This is the CRITICAL integration test that simulates the full backend
pipeline from SSE string → parsed → WebSocket adapter → Socket.IO emission.

Tests verify:
1. SSE strings from agent.py are correctly parsed
2. IIAgentWebSocketAdapter processes reasoning events properly
3. The final Socket.IO payload has the correct shape for the frontend
4. Comparison with working tool_call flow
5. Missing 'id' field analysis

Uses actual SSE strings as produced by agent.py's _make_event.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List, Optional, Tuple

from backend.app.agent.event_adapter import IIAgentWebSocketAdapter


# =============================================================================
# Helpers
# =============================================================================

def make_sse(event_type: str, data: dict) -> str:
    """Create an SSE string exactly as _make_event does."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def parse_and_process_sse(
    adapter: IIAgentWebSocketAdapter,
    event_str: str,
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Simulate _forward_sse_event's parsing + adapter.process_event logic.
    
    This replicates the exact parsing logic from query_handler.py lines 1042-1060.
    """
    lines = event_str.strip().split('\n')
    event_type = None
    data = None

    for line in lines:
        if line.startswith('event:'):
            event_type = line[6:].strip()
        elif line.startswith('data:'):
            data_str = line[5:].strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {'raw': data_str}

    if event_type and data:
        return adapter.process_event(event_type, data)
    return None, None


def simulate_socket_emission(
    event_type: str,
    data: dict,
    run_id: str = "test-run-001",
) -> dict:
    """
    Simulate what emit_chat_event produces for Socket.IO.
    
    From base_handler.py lines 102-110:
    event_data = {
        'type': event_type,
        'content': content,
    }
    if run_id:
        event_data['run_id'] = run_id
    """
    return {
        "type": event_type,
        "content": data,
        "run_id": run_id,
    }


# =============================================================================
# Test: Full Reasoning Pipeline (SSE → Parser → Adapter → Socket.IO)
# =============================================================================

class TestReasoningPipeline:
    """Test the complete reasoning event pipeline."""

    def test_full_reasoning_pipeline(self):
        """
        Simulate the COMPLETE reasoning flow as it happens in production:
        1. agent.py emits II-Agent format thinking events (adapter.thinking_*)
        2. agent.py emits AG-UI format reasoning events (_make_event)
        3. QueryHandler._forward_sse_event parses them
        4. IIAgentWebSocketAdapter.process_event processes them
        5. broadcast_to_session emits to Socket.IO
        
        The key insight: _forward_sse_event receives ALL events sequentially,
        including both II-Agent and AG-UI formats for the same reasoning content.
        """
        adapter = IIAgentWebSocketAdapter()
        emitted_events = []

        # agent.py emits these SSE strings in this order for one reasoning block:
        sse_events = [
            # 1. II-Agent format: adapter.thinking_start()
            make_sse("thinking", {"status": "start", "thinking_id": "thinking-abc"}),
            # 2. AG-UI format: _make_event("reasoning_start", ...)
            make_sse("reasoning_start", {"messageId": "reasoning-001"}),
            # 3. AG-UI format: _make_event("reasoning_message_start", ...)
            make_sse("reasoning_message_start", {"messageId": "reasoning-001", "role": "assistant"}),
            # 4. II-Agent format: adapter.thinking_delta(text)
            make_sse("thinking", {"status": "delta", "delta": "Let me analyze...", "thinking_id": "thinking-abc"}),
            # 5. AG-UI format: _make_event("reasoning_message_content", ...)
            make_sse("reasoning_message_content", {"messageId": "reasoning-001", "delta": "Let me analyze..."}),
            # 6. II-Agent format: adapter.thinking_stop()
            make_sse("thinking", {"status": "stop", "thinking_id": "thinking-abc"}),
            # 7. AG-UI format: _make_event("reasoning_message_end", ...)
            make_sse("reasoning_message_end", {"messageId": "reasoning-001"}),
            # 8. AG-UI format: _make_event("reasoning_end", ...)
            make_sse("reasoning_end", {"messageId": "reasoning-001"}),
        ]

        for sse in sse_events:
            ws_event_type, ws_data = parse_and_process_sse(adapter, sse)
            if ws_event_type and ws_data:
                emitted_events.append((ws_event_type, ws_data))

        # Analysis: What actually gets emitted?
        print("\n=== EMITTED EVENTS ===")
        for et, data in emitted_events:
            print(f"  {et}: {json.dumps(data, indent=2)}")

        # Find agent_thinking events
        thinking_events = [(et, d) for et, d in emitted_events if et == "agent_thinking"]
        
        # There should be at least one agent_thinking event
        assert len(thinking_events) >= 1, (
            f"Expected at least 1 agent_thinking event, got {len(thinking_events)}. "
            f"All events: {[(et, list(d.keys())) for et, d in emitted_events]}"
        )

        # The event should have the thinking text
        has_text = any(d.get("text") == "Let me analyze..." for _, d in thinking_events)
        assert has_text, (
            f"No agent_thinking event has text 'Let me analyze...'. "
            f"Events: {thinking_events}"
        )

    def test_only_agui_reasoning_pipeline(self):
        """
        Test with ONLY AG-UI format events (no II-Agent format).
        This is what StreamBuffer is designed to handle.
        """
        adapter = IIAgentWebSocketAdapter()
        emitted_events = []

        sse_events = [
            make_sse("reasoning_start", {"messageId": "r-001"}),
            make_sse("reasoning_message_start", {"messageId": "r-001", "role": "assistant"}),
            make_sse("reasoning_message_content", {"messageId": "r-001", "delta": "Step 1: "}),
            make_sse("reasoning_message_content", {"messageId": "r-001", "delta": "Analyze. "}),
            make_sse("reasoning_message_content", {"messageId": "r-001", "delta": "Step 2: Plan."}),
            make_sse("reasoning_message_end", {"messageId": "r-001"}),
            make_sse("reasoning_end", {"messageId": "r-001"}),
        ]

        for sse in sse_events:
            ws_event_type, ws_data = parse_and_process_sse(adapter, sse)
            if ws_event_type and ws_data:
                emitted_events.append((ws_event_type, ws_data))

        thinking_events = [(et, d) for et, d in emitted_events if et == "agent_thinking"]
        
        # StreamBuffer should accumulate and emit at reasoning_end
        assert len(thinking_events) >= 1
        
        # Check accumulated text
        # NOTE: reasoning_message_end and reasoning_end both trigger emission
        # in StreamBuffer. The FIRST one (reasoning_message_end) emits the content,
        # the SECOND one (reasoning_end) emits an empty buffer.
        first_thinking = thinking_events[0]
        assert first_thinking[1]["text"] == "Step 1: Analyze. Step 2: Plan."

    def test_reasoning_pipeline_data_shape_for_frontend(self):
        """
        Verify the EXACT shape the frontend receives via Socket.IO.
        
        Frontend handler (use-app-events.tsx):
        case AgentEvent.AGENT_THINKING:
            addMessage({
                id: data.id,
                content: data.content.text,
                isThinkMessage: true,
            })
        """
        adapter = IIAgentWebSocketAdapter()

        # Process reasoning events
        parse_and_process_sse(adapter, make_sse("reasoning_start", {"messageId": "r-1"}))
        parse_and_process_sse(adapter, make_sse("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "My deep analysis.",
        }))
        ws_event_type, ws_data = parse_and_process_sse(
            adapter, make_sse("reasoning_end", {"messageId": "r-1"})
        )

        assert ws_event_type == "agent_thinking"

        # Simulate Socket.IO emission
        socket_payload = simulate_socket_emission(
            ws_event_type, ws_data, run_id="run-001"
        )

        print("\n=== SOCKET.IO PAYLOAD (what frontend receives) ===")
        print(json.dumps(socket_payload, indent=2))

        # Frontend access patterns:
        assert socket_payload["type"] == "agent_thinking"  # → AgentEvent.AGENT_THINKING ✓

        # data.content.text → the thinking text
        assert "text" in socket_payload["content"]
        assert socket_payload["content"]["text"] == "My deep analysis."

        # data.id → problem! The 'id' field is NOT in the payload!
        # emit_chat_event does NOT add an 'id' field.
        # The frontend reads data.id → undefined!
        assert "id" not in socket_payload, (
            "Expected 'id' to NOT be in socket_payload (this is likely a bug)"
        )

    def test_tool_call_pipeline_for_reference(self):
        """
        Reference test: verify working tool_call pipeline shape.
        Compare with reasoning to identify differences.
        """
        adapter = IIAgentWebSocketAdapter()

        # Tool call events
        parse_and_process_sse(adapter, make_sse("tool_call_start", {
            "toolCallId": "tc-001",
            "toolName": "web_search",
        }))
        parse_and_process_sse(adapter, make_sse("tool_call_args", {
            "toolCallId": "tc-001",
            "delta": '{"query": "test search"}',
        }))
        ws_event_type, ws_data = parse_and_process_sse(
            adapter, make_sse("tool_call_end", {"toolCallId": "tc-001"})
        )

        socket_payload = simulate_socket_emission(ws_event_type, ws_data)

        print("\n=== TOOL_CALL SOCKET.IO PAYLOAD (reference) ===")
        print(json.dumps(socket_payload, indent=2))

        # Frontend sees: data.content.tool_name, data.content.tool_call_id
        assert socket_payload["type"] == "tool_call"
        assert "tool_name" in socket_payload["content"]
        assert "tool_call_id" in socket_payload["content"]


# =============================================================================
# Test: Missing 'id' Field Analysis
# =============================================================================

class TestMissingIdField:
    """
    Analyze the missing 'id' field issue.
    
    Frontend handler (use-app-events.tsx line 369):
        addMessage({
            id: data.id,     // <-- This is the message ID
            ...
        })
    
    emit_chat_event (base_handler.py line 102):
        event_data = {
            'type': event_type,
            'content': content,
        }
        if run_id:
            event_data['run_id'] = run_id
    
    The handler fires on 'chat_event' with data = event_data.
    So data.id is NOT present unless we add it.
    
    For tool_call, the frontend reads data.id, which would also be undefined.
    But tool_call WORKS — why?
    
    Looking at addMessage in use-app-events.tsx for TOOL_CALL (line ~384),
    the frontend also reads data.id. Tool calls work because they create
    separate messages with unique IDs.
    
    For AGENT_THINKING, the same data.id would be undefined.
    With undefined id, addMessage might deduplicate or fail silently.
    """

    def test_socket_payload_missing_id(self):
        """Verify that the socket payload does NOT include an 'id' field."""
        adapter = IIAgentWebSocketAdapter()

        parse_and_process_sse(adapter, make_sse("reasoning_start", {"messageId": "r-1"}))
        parse_and_process_sse(adapter, make_sse("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Thinking...",
        }))
        ws_et, ws_data = parse_and_process_sse(
            adapter, make_sse("reasoning_end", {"messageId": "r-1"})
        )

        # Simulate broadcast_to_session
        socket_payload = {
            "type": ws_et,
            "content": ws_data,
            "run_id": "run-001",
        }

        # The 'id' field is at the top level, NOT inside content
        # Frontend reads: data.id → undefined
        assert "id" not in socket_payload
        
        # But thinking_id IS inside content
        assert "thinking_id" in socket_payload["content"]

    def test_run_id_present_but_id_not(self):
        """run_id is added but id is not — this is likely the root issue."""
        adapter = IIAgentWebSocketAdapter()

        parse_and_process_sse(adapter, make_sse("reasoning_start", {"messageId": "r-1"}))
        parse_and_process_sse(adapter, make_sse("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Analysis.",
        }))

        # Add run_id as query_handler does
        ws_et, ws_data = parse_and_process_sse(
            adapter, make_sse("reasoning_end", {"messageId": "r-1"})
        )
        ws_data["run_id"] = "run-001"

        socket_payload = simulate_socket_emission(ws_et, ws_data, "run-001")

        # run_id is present at top level
        assert "run_id" in socket_payload
        # content.run_id is also present (added by _forward_sse_event)
        assert "run_id" in socket_payload["content"]
        # But 'id' is nowhere
        assert "id" not in socket_payload


# =============================================================================
# Test: Frontend handleEvent data structure
# =============================================================================

class TestFrontendDataStructure:
    """
    The frontend's handleEvent receives:
    data = {
        id: string,          // <-- from where?
        type: AgentEvent,    // e.g., "agent_thinking"
        content: {...}       // event payload
    }
    
    Looking at the Socket.IO listener registration, events are emitted as:
    sio.emit('chat_event', event_data, room=room)
    
    The frontend listener receives event_data directly.
    So data = event_data = { type, content, run_id }
    
    data.id would be undefined for reasoning events!
    
    But wait — the QueryHandler adds run_id to the content dict:
    ws_data['run_id'] = run_id
    
    And the emit_chat_event wraps it in:
    { type: event_type, content: ws_data }
    
    So data.id is indeed undefined. The frontend at line 369:
    id: data.id → undefined
    
    With undefined ID, the addMessage call creates a message with
    undefined id. uniqBy([...messages, newMessage], 'id') may
    deduplicate incorrectly since all thinking messages get id=undefined.
    """

    def test_data_id_impact_on_uniq_by(self):
        """
        Simulate the frontend's uniqBy behavior with undefined IDs.
        
        If multiple agent_thinking events have id=undefined,
        uniqBy would only keep the FIRST one (since all have same undefined "id").
        """
        # Simulate multiple thinking messages with undefined ID
        messages = [
            {"id": None, "content": "First thought", "isThinkMessage": True},
            {"id": None, "content": "Second thought", "isThinkMessage": True},
        ]
        
        # Simple uniqBy implementation
        seen_ids = set()
        unique_messages = []
        for msg in messages:
            msg_id = msg["id"]
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_messages.append(msg)
        
        # With None/undefined IDs, only ONE message survives!
        assert len(unique_messages) == 1, (
            "uniqBy with None IDs deduplicates all thinking messages to one!"
        )

    def test_unique_id_fixes_deduplication(self):
        """If we give each event a unique ID, deduplication works correctly."""
        messages = [
            {"id": "thinking-001", "content": "First thought", "isThinkMessage": True},
            {"id": "thinking-002", "content": "Second thought", "isThinkMessage": True},
        ]
        
        seen_ids = set()
        unique_messages = []
        for msg in messages:
            msg_id = msg["id"]
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_messages.append(msg)
        
        assert len(unique_messages) == 2  # Both messages survive


# =============================================================================
# Test: Flush at stream end
# =============================================================================

class TestStreamEndFlush:
    """Test that flush at stream end captures incomplete reasoning."""

    def test_flush_before_complete(self):
        """
        QueryHandler flushes the buffer before emitting 'complete'.
        Verify this captures any remaining reasoning.
        """
        adapter = IIAgentWebSocketAdapter()

        # Start reasoning but don't end it before complete
        parse_and_process_sse(adapter, make_sse("reasoning_start", {"messageId": "r-1"}))
        parse_and_process_sse(adapter, make_sse("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Incomplete thought...",
        }))

        # Flush (as QueryHandler does before complete)
        flushed = adapter.buffer.flush()
        thinking_events = [(et, d) for et, d in flushed if et == "agent_thinking"]
        
        assert len(thinking_events) == 1
        assert thinking_events[0][1]["text"] == "Incomplete thought..."


# =============================================================================
# Test: Save Output for Manual Inspection
# =============================================================================

class TestSaveOutput:
    """Save reasoning pipeline output to file for manual inspection."""

    def test_save_reasoning_output(self, tmp_path):
        """Save all pipeline stages to a JSON file."""
        adapter = IIAgentWebSocketAdapter()
        
        output = {
            "description": "Reasoning pipeline output at each stage",
            "stages": []
        }

        # Stage 1: SSE events as produced by agent.py
        sse_events = [
            ("II-Agent thinking start", make_sse("thinking", {"status": "start", "thinking_id": "t-1"})),
            ("AG-UI reasoning_start", make_sse("reasoning_start", {"messageId": "r-1"})),
            ("AG-UI reasoning_message_start", make_sse("reasoning_message_start", {"messageId": "r-1", "role": "assistant"})),
            ("II-Agent thinking delta", make_sse("thinking", {"status": "delta", "delta": "Analyzing the problem step by step.", "thinking_id": "t-1"})),
            ("AG-UI reasoning_content", make_sse("reasoning_message_content", {"messageId": "r-1", "delta": "Analyzing the problem step by step."})),
            ("II-Agent thinking stop", make_sse("thinking", {"status": "stop", "thinking_id": "t-1"})),
            ("AG-UI reasoning_message_end", make_sse("reasoning_message_end", {"messageId": "r-1"})),
            ("AG-UI reasoning_end", make_sse("reasoning_end", {"messageId": "r-1"})),
        ]

        for label, sse in sse_events:
            ws_et, ws_data = parse_and_process_sse(adapter, sse)
            
            stage = {
                "label": label,
                "sse_input": sse.strip(),
                "adapter_output_event_type": ws_et,
                "adapter_output_data": ws_data,
            }
            
            if ws_et and ws_data:
                socket_payload = simulate_socket_emission(ws_et, ws_data)
                stage["socket_io_payload"] = socket_payload
                stage["frontend_sees"] = {
                    "data.type": socket_payload.get("type"),
                    "data.id": socket_payload.get("id", "UNDEFINED"),
                    "data.content.text": socket_payload.get("content", {}).get("text", "MISSING"),
                    "data.content.thinking_id": socket_payload.get("content", {}).get("thinking_id", "MISSING"),
                }
            
            output["stages"].append(stage)

        # Save to file
        output_file = tmp_path / "reasoning_pipeline_output.json"
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n=== SAVED OUTPUT TO: {output_file} ===")
        print(json.dumps(output, indent=2, default=str))

        # Verify at least one stage produced agent_thinking
        agent_thinking_stages = [
            s for s in output["stages"]
            if s.get("adapter_output_event_type") == "agent_thinking"
        ]
        assert len(agent_thinking_stages) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
