"""
Test StreamBuffer reasoning/thinking event handling.

Tests that the StreamBuffer properly:
1. Receives AG-UI reasoning events (reasoning_start, reasoning_message_content, reasoning_end)
2. Buffers them correctly
3. Emits a single atomic "agent_thinking" event at reasoning_end
4. Skips II-Agent format "thinking" events (to avoid duplicates)
5. Flushes incomplete reasoning on stream end
6. Handles interleaved reasoning + text correctly

Uses ACTUAL event payloads as emitted by agent.py and chat.py.
"""

import json
import pytest
from uuid import uuid4

from backend.app.agent.stream_buffer import StreamBuffer


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def buffer():
    """Fresh StreamBuffer for each test."""
    return StreamBuffer()


# =============================================================================
# 1. Basic Reasoning Lifecycle
# =============================================================================

class TestReasoningLifecycle:
    """Test the full reasoning_start → content → reasoning_end lifecycle."""

    def test_reasoning_start_buffers(self, buffer):
        """reasoning_start should buffer (return None, None) and set thinking_id."""
        event_type, data = buffer.process_event("reasoning_start", {
            "messageId": "reasoning-abc123",
        })
        assert event_type is None
        assert data is None
        assert buffer.thinking_id is not None
        assert buffer.thinking_parts == []

    def test_reasoning_message_start_buffers(self, buffer):
        """reasoning_message_start should also trigger buffering."""
        event_type, data = buffer.process_event("reasoning_message_start", {
            "messageId": "reasoning-def456",
            "role": "assistant",
        })
        assert event_type is None
        assert data is None
        assert buffer.thinking_id is not None

    def test_reasoning_content_accumulates(self, buffer):
        """reasoning_message_content deltas should accumulate in the buffer."""
        # Start reasoning
        buffer.process_event("reasoning_start", {"messageId": "reasoning-abc"})

        # Send multiple content deltas
        r1 = buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "Let me think ",
        })
        assert r1 == (None, None)

        r2 = buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "about this ",
        })
        assert r2 == (None, None)

        r3 = buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "carefully.",
        })
        assert r3 == (None, None)

        # Buffer should have accumulated all parts
        assert buffer.thinking_parts == ["Let me think ", "about this ", "carefully."]

    def test_reasoning_end_emits_atomic_event(self, buffer):
        """reasoning_end should emit the complete atomic agent_thinking event."""
        # Full lifecycle
        buffer.process_event("reasoning_start", {"messageId": "reasoning-abc"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "I need to analyze ",
        })
        buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "the user's request.",
        })

        # End reasoning
        event_type, data = buffer.process_event("reasoning_end", {
            "messageId": "reasoning-abc",
        })

        assert event_type == "agent_thinking"
        assert data is not None
        assert data["text"] == "I need to analyze the user's request."
        assert "thinking_id" in data
        assert data["status"] == "stop"

    def test_reasoning_message_end_also_emits(self, buffer):
        """reasoning_message_end should also emit the atomic event."""
        buffer.process_event("reasoning_start", {"messageId": "reasoning-abc"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "Thinking...",
        })

        event_type, data = buffer.process_event("reasoning_message_end", {
            "messageId": "reasoning-abc",
        })

        assert event_type == "agent_thinking"
        assert data["text"] == "Thinking..."

    def test_buffer_resets_after_emit(self, buffer):
        """After emitting, thinking buffer should be clean."""
        buffer.process_event("reasoning_start", {"messageId": "reasoning-abc"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "reasoning-abc",
            "delta": "Some thought",
        })
        buffer.process_event("reasoning_end", {"messageId": "reasoning-abc"})

        # Buffer should be reset
        assert buffer.thinking_id is None
        assert buffer.thinking_parts == []

    def test_multiple_reasoning_sessions(self, buffer):
        """Multiple reasoning sessions should each produce their own event."""
        # Session 1
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {"messageId": "r-1", "delta": "First thought."})
        et1, d1 = buffer.process_event("reasoning_end", {"messageId": "r-1"})
        assert et1 == "agent_thinking"
        assert d1["text"] == "First thought."

        # Session 2
        buffer.process_event("reasoning_start", {"messageId": "r-2"})
        buffer.process_event("reasoning_message_content", {"messageId": "r-2", "delta": "Second thought."})
        et2, d2 = buffer.process_event("reasoning_end", {"messageId": "r-2"})
        assert et2 == "agent_thinking"
        assert d2["text"] == "Second thought."


# =============================================================================
# 2. II-Agent "thinking" Event Skipping
# =============================================================================

class TestThinkingEventSkipping:
    """Test that II-Agent format 'thinking' events are properly skipped."""

    def test_thinking_event_skipped(self, buffer):
        """II-Agent format 'thinking' events should return (None, None)."""
        event_type, data = buffer.process_event("thinking", {
            "status": "start",
            "thinking_id": "thinking-xyz",
        })
        assert event_type is None
        assert data is None

    def test_thinking_delta_skipped(self, buffer):
        """II-Agent thinking delta should be skipped."""
        event_type, data = buffer.process_event("thinking", {
            "status": "delta",
            "delta": "Some reasoning text",
            "thinking_id": "thinking-xyz",
        })
        assert event_type is None
        assert data is None

    def test_thinking_stop_skipped(self, buffer):
        """II-Agent thinking stop should be skipped."""
        event_type, data = buffer.process_event("thinking", {
            "status": "stop",
            "thinking_id": "thinking-xyz",
        })
        assert event_type is None
        assert data is None


# =============================================================================
# 3. Flush Behavior
# =============================================================================

class TestFlushReasoning:
    """Test that flush() properly handles incomplete reasoning."""

    def test_flush_incomplete_reasoning(self, buffer):
        """Flushing mid-reasoning should emit the partial thinking."""
        buffer.process_event("reasoning_start", {"messageId": "r-partial"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-partial",
            "delta": "Partial thought that ",
        })
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-partial",
            "delta": "was never completed",
        })

        # No end event - flush should emit what we have
        flushed = buffer.flush()
        assert len(flushed) >= 1

        # Find the agent_thinking event
        thinking_events = [(et, d) for et, d in flushed if et == "agent_thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0][1]["text"] == "Partial thought that was never completed"

    def test_flush_no_reasoning(self, buffer):
        """Flushing with no reasoning content should produce no thinking events."""
        flushed = buffer.flush()
        thinking_events = [(et, d) for et, d in flushed if et == "agent_thinking"]
        assert len(thinking_events) == 0

    def test_flush_after_completed_reasoning(self, buffer):
        """Flushing after reasoning_end should produce nothing extra."""
        buffer.process_event("reasoning_start", {"messageId": "r-done"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-done",
            "delta": "Complete thought.",
        })
        buffer.process_event("reasoning_end", {"messageId": "r-done"})

        flushed = buffer.flush()
        thinking_events = [(et, d) for et, d in flushed if et == "agent_thinking"]
        assert len(thinking_events) == 0


# =============================================================================
# 4. Interleaved Events
# =============================================================================

class TestInterleavedEvents:
    """Test reasoning interleaved with tool calls and message chunks."""

    def test_reasoning_then_text(self, buffer):
        """Reasoning followed by text should flush properly."""
        # Start reasoning
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Let me analyze this.",
        })
        et1, d1 = buffer.process_event("reasoning_end", {"messageId": "r-1"})
        assert et1 == "agent_thinking"

        # Then text message
        buffer.process_event("message", {
            "type": "chunk",
            "content": "Here is my response.",
        })
        # Text should be buffered
        flushed = buffer.flush()
        text_events = [(et, d) for et, d in flushed if et == "agent_response"]
        assert len(text_events) == 1
        assert text_events[0][1]["text"] == "Here is my response."

    def test_reasoning_then_tool_call(self, buffer):
        """Reasoning followed by a tool call should work."""
        # Reasoning
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "I should use a tool for this.",
        })
        et1, d1 = buffer.process_event("reasoning_end", {"messageId": "r-1"})
        assert et1 == "agent_thinking"
        assert d1["text"] == "I should use a tool for this."

        # Tool call
        buffer.process_event("tool_call_start", {
            "toolCallId": "tc-001",
            "toolName": "web_search",
        })
        buffer.process_event("tool_call_args", {
            "toolCallId": "tc-001",
            "delta": '{"query": "test"}',
        })
        et2, d2 = buffer.process_event("tool_call_end", {
            "toolCallId": "tc-001",
        })
        assert et2 == "tool_call"
        assert d2["tool_call_id"] == "tc-001"

    def test_empty_reasoning_content(self, buffer):
        """Reasoning with empty deltas should produce empty text."""
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "",
        })
        et, d = buffer.process_event("reasoning_end", {"messageId": "r-1"})
        assert et == "agent_thinking"
        assert d["text"] == ""


# =============================================================================
# 5. Data Shape Verification (Frontend Compatibility)
# =============================================================================

class TestDataShapeForFrontend:
    """
    Verify the exact data shape emitted by StreamBuffer matches what the
    frontend expects at use-app-events.tsx:

    case AgentEvent.AGENT_THINKING:
        addMessage({
            id: data.id,
            role: 'assistant',
            content: data.content.text as string,
            timestamp: Date.now(),
            isThinkMessage: true,
        })

    The frontend accesses:
    - data.id         -> from the emit_chat_event envelope
    - data.content.text -> the thinking text (our 'text' field goes into 'content')
    """

    def test_atomic_event_has_text_field(self, buffer):
        """The atomic event data MUST have a 'text' field."""
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Deep reasoning here.",
        })
        _, data = buffer.process_event("reasoning_end", {"messageId": "r-1"})

        assert "text" in data, "atomic agent_thinking event must have 'text' field"
        assert isinstance(data["text"], str), "'text' must be a string"

    def test_atomic_event_has_thinking_id(self, buffer):
        """The atomic event data MUST have a 'thinking_id' field."""
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Some thought.",
        })
        _, data = buffer.process_event("reasoning_end", {"messageId": "r-1"})

        assert "thinking_id" in data, "Must have thinking_id"
        assert data["thinking_id"] is not None

    def test_output_serializable_to_json(self, buffer):
        """The output must be JSON-serializable (for Socket.IO transport)."""
        buffer.process_event("reasoning_start", {"messageId": "r-1"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-1",
            "delta": "Thought with special chars: <>&\"'{}[]",
        })
        _, data = buffer.process_event("reasoning_end", {"messageId": "r-1"})

        # Must not raise
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["text"] == "Thought with special chars: <>&\"'{}[]"


# =============================================================================
# 6. Realistic Multi-Chunk Reasoning (Long Thinking)
# =============================================================================

class TestRealisticReasoning:
    """Test with realistic multi-chunk reasoning as produced by Claude/GPT."""

    def test_long_reasoning_stream(self, buffer):
        """Simulate a long reasoning stream with many small deltas."""
        msg_id = "reasoning-real-001"
        buffer.process_event("reasoning_start", {"messageId": msg_id})

        # Simulate 20 small chunks of reasoning
        expected_parts = []
        for i in range(20):
            chunk = f"Step {i+1}: Analyzing component {i+1} of the problem. "
            expected_parts.append(chunk)
            result = buffer.process_event("reasoning_message_content", {
                "messageId": msg_id,
                "delta": chunk,
            })
            # While buffering, should return None
            assert result == (None, None), f"Chunk {i} should be buffered"

        # End reasoning
        event_type, data = buffer.process_event("reasoning_end", {"messageId": msg_id})
        assert event_type == "agent_thinking"
        assert data["text"] == "".join(expected_parts)
        assert len(data["text"]) > 0

    def test_unicode_reasoning(self, buffer):
        """Test reasoning with unicode characters (multilingual support)."""
        buffer.process_event("reasoning_start", {"messageId": "r-unicode"})
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-unicode",
            "delta": "让我想想这个问题。",  # Chinese: Let me think about this
        })
        buffer.process_event("reasoning_message_content", {
            "messageId": "r-unicode",
            "delta": " この問題を分析します。",  # Japanese: I'll analyze this problem
        })
        _, data = buffer.process_event("reasoning_end", {"messageId": "r-unicode"})

        assert data["text"] == "让我想想这个问题。 この問題を分析します。"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
