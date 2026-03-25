"""
Test IIAgentWebSocketAdapter reasoning/thinking event handling.

Tests the WebSocket adapter's:
1. Stateful process_event() path (via StreamBuffer) for AG-UI reasoning events
2. Static transform() path for individual reasoning events
3. Data shape output compatibility with frontend's use-app-events.tsx
4. Event type mapping (reasoning_* → agent_thinking)

Compares working tool_call flow vs reasoning flow to identify discrepancies.
"""

import json
import pytest

from backend.app.agent.event_adapter import (
    IIAgentWebSocketAdapter,
    IIAgentSSEAdapter,
    create_sse_adapter,
    humanize_tool_name,
    normalize_tool_name,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def ws_adapter():
    """Fresh WebSocket adapter for each test."""
    return IIAgentWebSocketAdapter()


@pytest.fixture
def sse_adapter():
    """Fresh SSE adapter for each test."""
    return IIAgentSSEAdapter(session_id="test-session-001", model_id="claude-3-5-sonnet")


# =============================================================================
# 1. WebSocket Adapter Stateful Processing (via StreamBuffer)
# =============================================================================

class TestWSAdapterStatefulReasoning:
    """Test the stateful process_event() path for reasoning."""

    def test_reasoning_lifecycle_produces_agent_thinking(self, ws_adapter):
        """Full AG-UI reasoning lifecycle should produce agent_thinking event."""
        # Start
        et1, d1 = ws_adapter.process_event("reasoning_start", {"messageId": "r-1"})
        assert et1 is None  # Buffering

        # Content
        et2, d2 = ws_adapter.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Let me think...",
        })
        assert et2 is None  # Buffering

        # End
        et3, d3 = ws_adapter.process_event("reasoning_end", {"messageId": "r-1"})
        assert et3 == "agent_thinking"
        assert d3 is not None
        assert d3["text"] == "Let me think..."

    def test_buffered_reasoning_bypasses_transform(self, ws_adapter):
        """
        Buffered agent_thinking events should be returned directly,
        NOT go through the static _transform_data method.
        
        This is the key behavior: StreamBuffer returns ("agent_thinking", data)
        and the adapter returns it directly at line 1418.
        """
        ws_adapter.process_event("reasoning_start", {"messageId": "r-1"})
        ws_adapter.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Analyzing...",
        })
        et, data = ws_adapter.process_event("reasoning_end", {"messageId": "r-1"})

        # The data should have the StreamBuffer format, not _transform_data format
        assert et == "agent_thinking"
        assert "text" in data
        assert data["text"] == "Analyzing..."
        # StreamBuffer format includes these fields:
        assert "thinking_id" in data
        assert "status" in data

    def test_ii_agent_thinking_events_skipped(self, ws_adapter):
        """II-Agent format thinking events should be skipped."""
        et, d = ws_adapter.process_event("thinking", {
            "status": "delta",
            "delta": "Some thinking",
            "thinking_id": "t-1",
        })
        assert et is None
        assert d is None

    def test_multi_chunk_reasoning(self, ws_adapter):
        """Multiple reasoning content chunks accumulate correctly."""
        ws_adapter.process_event("reasoning_start", {"messageId": "r-1"})

        for i in range(5):
            ws_adapter.process_event("reasoning_message_content", {
                "messageId": "r-1",
                "delta": f"Chunk {i}. ",
            })

        et, data = ws_adapter.process_event("reasoning_end", {"messageId": "r-1"})
        assert et == "agent_thinking"
        assert data["text"] == "Chunk 0. Chunk 1. Chunk 2. Chunk 3. Chunk 4. "


# =============================================================================
# 2. WebSocket Adapter Static Transform (for individual events)
# =============================================================================

class TestWSAdapterStaticTransform:
    """
    Test the static transform() method for reasoning events.
    
    NOTE: In the buffered path, most reasoning events are handled by StreamBuffer
    and never reach the static transform. But the transform code exists and
    should be tested for the non-buffered code paths.
    """

    def test_reasoning_start_transforms(self):
        """reasoning_start → agent_thinking with status 'start'."""
        et, data = IIAgentWebSocketAdapter.transform("reasoning_start", {
            "messageId": "r-1",
        })
        assert et == "agent_thinking"
        assert data["status"] == "start"
        assert data["thinking_id"] == "r-1"

    def test_reasoning_content_transforms(self):
        """reasoning_message_content → agent_thinking with status 'delta'."""
        et, data = IIAgentWebSocketAdapter.transform("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Thinking text",
        })
        assert et == "agent_thinking"
        assert data["status"] == "delta"
        assert data["text"] == "Thinking text"

    def test_reasoning_end_transforms(self):
        """reasoning_end → agent_thinking with status 'stop'."""
        et, data = IIAgentWebSocketAdapter.transform("reasoning_end", {
            "messageId": "r-1",
        })
        assert et == "agent_thinking"
        assert data["status"] == "stop"
        assert data["thinking_id"] == "r-1"

    def test_reasoning_message_start_skipped(self):
        """reasoning_message_start should be skipped (None mapped in EVENT_TYPE_MAP)."""
        et, data = IIAgentWebSocketAdapter.transform("reasoning_message_start", {
            "messageId": "r-1",
            "role": "assistant",
        })
        assert et is None
        assert data is None

    def test_reasoning_message_end_skipped(self):
        """reasoning_message_end should be skipped."""
        et, data = IIAgentWebSocketAdapter.transform("reasoning_message_end", {
            "messageId": "r-1",
        })
        assert et is None
        assert data is None


# =============================================================================
# 3. Comparison: Tool Call vs Reasoning (Working vs Broken)
# =============================================================================

class TestToolCallVsReasoning:
    """
    Compare the working tool_call flow with the reasoning flow.
    Both should follow the same pattern through the adapter.
    """

    def test_tool_call_works_end_to_end(self, ws_adapter):
        """Verify tool_call flow works (reference implementation)."""
        ws_adapter.process_event("tool_call_start", {
            "toolCallId": "tc-001",
            "toolName": "web_search",
        })
        ws_adapter.process_event("tool_call_args", {
            "toolCallId": "tc-001",
            "delta": '{"query": "test"}',
        })
        et, data = ws_adapter.process_event("tool_call_end", {
            "toolCallId": "tc-001",
        })

        assert et == "tool_call"
        assert "tool_call_id" in data
        assert "tool_name" in data
        assert "tool_input" in data

    def test_reasoning_follows_same_pattern(self, ws_adapter):
        """Reasoning should follow the same buffer → atomic pattern as tool_call."""
        ws_adapter.process_event("reasoning_start", {"messageId": "r-1"})
        ws_adapter.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "My reasoning.",
        })
        et, data = ws_adapter.process_event("reasoning_end", {"messageId": "r-1"})

        assert et == "agent_thinking"
        assert "text" in data
        # Key difference: tool_call has tool-specific fields, reasoning has text

    def test_flush_handles_both(self, ws_adapter):
        """Flush should handle incomplete reasoning same as incomplete tool."""
        # Start reasoning but don't end it
        ws_adapter.process_event("reasoning_start", {"messageId": "r-1"})
        ws_adapter.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Partial thought",
        })

        flushed = ws_adapter.buffer.flush()
        thinking_events = [(et, d) for et, d in flushed if et == "agent_thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0][1]["text"] == "Partial thought"


# =============================================================================
# 4. SSE Adapter Thinking Methods (Chat Mode)
# =============================================================================

class TestSSEAdapterThinking:
    """Test the SSE adapter's thinking methods for chat mode."""

    def test_thinking_start_format(self, sse_adapter):
        """thinking_start should produce correct SSE format."""
        result = sse_adapter.thinking_start()
        assert "event: thinking" in result
        assert '"status": "start"' in result
        assert '"thinking_id"' in result

    def test_thinking_delta_format(self, sse_adapter):
        """thinking_delta should produce correct SSE format."""
        sse_adapter.thinking_start()  # Must start first
        result = sse_adapter.thinking_delta("Let me think...")
        assert "event: thinking" in result
        assert '"status": "delta"' in result
        assert '"delta": "Let me think..."' in result

    def test_thinking_stop_format(self, sse_adapter):
        """thinking_stop should produce correct SSE format."""
        sse_adapter.thinking_start()
        result = sse_adapter.thinking_stop()
        assert "event: thinking" in result
        assert '"status": "stop"' in result

    def test_thinking_lifecycle_state(self, sse_adapter):
        """SSE adapter tracks thinking state correctly."""
        assert not sse_adapter.thinking_active
        assert sse_adapter.thinking_id is None

        sse_adapter.thinking_start()
        assert sse_adapter.thinking_active
        assert sse_adapter.thinking_id is not None

        sse_adapter.thinking_stop()
        assert not sse_adapter.thinking_active
        assert sse_adapter.thinking_id is None

    def test_thinking_with_signature(self, sse_adapter):
        """thinking_delta with signature (Anthropic extended thinking)."""
        sse_adapter.thinking_start()
        result = sse_adapter.thinking_delta("Deep thought", signature="sig-abc123")
        assert '"signature": "sig-abc123"' in result

    def test_sse_thinking_parseable(self, sse_adapter):
        """SSE thinking events should be parseable by the frontend parser."""
        # Simulate the full lifecycle and parse each event
        events = [
            sse_adapter.thinking_start(),
            sse_adapter.thinking_delta("Step 1: Analyze. "),
            sse_adapter.thinking_delta("Step 2: Plan. "),
            sse_adapter.thinking_stop(),
        ]

        for event_str in events:
            lines = event_str.strip().split('\n')
            event_type = None
            data = None
            for line in lines:
                if line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    data = json.loads(line[5:].strip())

            assert event_type == "thinking"
            assert data is not None
            assert "status" in data


# =============================================================================
# 5. Event Type Mapping Verification  
# =============================================================================

class TestEventTypeMapping:
    """Verify the EVENT_TYPE_MAP for reasoning events."""

    def test_all_reasoning_events_mapped(self):
        """All AG-UI reasoning event types should be in the map."""
        expected_reasoning_events = [
            "reasoning_start",
            "reasoning_message_start",
            "reasoning_message_content",
            "reasoning_message_end",
            "reasoning_end",
        ]
        for event in expected_reasoning_events:
            assert event in IIAgentWebSocketAdapter.EVENT_TYPE_MAP, (
                f"'{event}' not found in EVENT_TYPE_MAP"
            )

    def test_reasoning_events_map_correctly(self):
        """Verify exact mapping of reasoning events."""
        m = IIAgentWebSocketAdapter.EVENT_TYPE_MAP
        assert m["reasoning_start"] == "agent_thinking"
        assert m["reasoning_message_start"] is None  # Merged
        assert m["reasoning_message_content"] == "agent_thinking"
        assert m["reasoning_message_end"] is None  # Skipped
        assert m["reasoning_end"] == "agent_thinking"


# =============================================================================
# 6. Data Shape for WebSocket Emission
# =============================================================================

class TestWSEmissionShape:
    """
    Test that the data shape produced by the adapter matches what
    emit_chat_event wraps and the frontend expects.

    emit_chat_event wraps as:
    {
        type: event_type,     # e.g. "agent_thinking"
        content: content,     # our data dict
        run_id: "..."
    }

    Frontend accesses:
    - data.type → AgentEvent.AGENT_THINKING
    - data.id → message ID (from run_id or uuid)
    - data.content.text → thinking text
    """

    def test_buffered_output_shape(self, ws_adapter):
        """Verify the buffered output has the right shape for emit_chat_event."""
        ws_adapter.process_event("reasoning_start", {"messageId": "r-1"})
        ws_adapter.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "My deep thought.",
        })
        et, data = ws_adapter.process_event("reasoning_end", {"messageId": "r-1"})

        # This data becomes the 'content' field in emit_chat_event
        # Frontend reads: data.content.text
        assert et == "agent_thinking"
        assert isinstance(data, dict)
        assert "text" in data
        assert data["text"] == "My deep thought."

        # Simulate what emit_chat_event does
        socket_payload = {
            "type": et,
            "content": data,
            "run_id": "test-run-001",
        }

        # Frontend access pattern: data.content.text
        assert socket_payload["content"]["text"] == "My deep thought."
        # Frontend access pattern: data.type
        assert socket_payload["type"] == "agent_thinking"

    def test_tool_call_output_shape_for_reference(self, ws_adapter):
        """Reference: verify tool_call output shape (known working)."""
        ws_adapter.process_event("tool_call_start", {
            "toolCallId": "tc-001",
            "toolName": "web_search",
        })
        ws_adapter.process_event("tool_call_args", {
            "toolCallId": "tc-001",
            "delta": '{"query": "test"}',
        })
        et, data = ws_adapter.process_event("tool_call_end", {
            "toolCallId": "tc-001",
        })

        # This is the working reference shape
        socket_payload = {
            "type": et,
            "content": data,
            "run_id": "test-run-001",
        }

        # Frontend reads: data.content.tool_name, data.content.tool_call_id etc.
        assert socket_payload["content"]["tool_name"] is not None
        assert socket_payload["content"]["tool_call_id"] == "tc-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
