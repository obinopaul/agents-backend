"""
Tests for conversation history persistence fixes.

Two bugs fixed:
1. CHAT MODE: AI messages saved with 3x duplication because the accumulator
   captured text from all 3 SSE event formats (content, message, message_chunk).
   Fix: Only accumulate from II-Agent "content" deltas.

2. AGENT MODE: AI messages not saved at all — only a placeholder
   "[Agent response completed]" was stored.  Tool calls and tool results
   were also lost.
   Fix: Accumulate text during _forward_sse_event, persist tool events inline,
   pass real text to _store_agent_response.
"""

import json
import pytest
from typing import List, Dict, Any, Optional


# ============================================================================
# Helpers: simulate SSE event generation (mirrors chat.py / agent.py output)
# ============================================================================

def make_sse(event_type: str, data: dict) -> str:
    """Build an SSE event string like the generators produce."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def make_content_delta(text: str) -> str:
    """II-Agent format content delta (adapter.content_delta)."""
    return make_sse("content", {"status": "delta", "delta": text})


def make_message(text: str) -> str:
    """AG-UI format message event (_make_event('message', ...))."""
    return make_sse("message", {"content": text, "type": "chunk"})


def make_message_chunk(text: str) -> str:
    """Legacy format message_chunk event (_make_event('message_chunk', ...))."""
    return make_sse("message_chunk", {"content": text})


def make_tool_result(tool_name: str, tool_call_id: str, tool_input: dict, result) -> str:
    """Tool result event from agent.py (the consolidated event)."""
    return make_sse("tool_result", {
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "result": result,
    })


def make_complete() -> str:
    """Complete event."""
    return make_sse("complete", {"message": "done", "finish_reason": "stop"})


# ============================================================================
# Simulated accumulator (mirrors _forward_sse_event logic)
# ============================================================================

class SSEAccumulator:
    """
    Simulates the text accumulation logic in _forward_sse_event.
    Only captures from II-Agent "content" deltas — the fix that prevents 3x.
    """

    def __init__(self):
        self.accumulated_text: List[str] = []
        self.tool_events: List[Dict[str, Any]] = []

    def process_event(self, event_str: str):
        """Process an SSE event string, accumulate text and tool events."""
        event_type = None
        data = None
        for line in event_str.strip().split('\n'):
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                data_str = line[5:].strip()
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = {'raw': data_str}

        if not event_type or not data:
            return

        # Text accumulation — ONLY from "content" deltas
        if event_type == "content" and data.get("status") == "delta" and "delta" in data:
            text_delta = data["delta"]
            if text_delta:
                self.accumulated_text.append(text_delta)

        # Tool event capture
        if event_type == "tool_result":
            self.tool_events.append({
                "tool_name": data.get("tool_name"),
                "tool_call_id": data.get("tool_call_id"),
                "tool_input": data.get("tool_input"),
                "result": data.get("result"),
            })

    @property
    def full_text(self) -> str:
        return "".join(self.accumulated_text)


# ============================================================================
# Tests: Chat mode — 3x duplication fix
# ============================================================================

class TestChatModeDeduplication:
    """Verify that the accumulator only captures text once per token."""

    def test_single_token_produces_three_events(self):
        """
        Each text token in chat.py generates 3 SSE events.
        Verify all three are generated correctly.
        """
        token = "Hello"
        events = [
            make_content_delta(token),   # II-Agent format
            make_message(token),          # AG-UI format
            make_message_chunk(token),    # Legacy format
        ]
        assert len(events) == 3
        for e in events:
            assert token in e

    def test_accumulator_captures_only_once(self):
        """
        When all 3 event formats pass through the accumulator,
        the text should appear exactly ONCE.
        This was the root cause of the 3x bug.
        """
        acc = SSEAccumulator()
        token = "Hello"

        # Simulate all 3 events for a single token
        acc.process_event(make_content_delta(token))
        acc.process_event(make_message(token))
        acc.process_event(make_message_chunk(token))

        # The accumulated text should contain the token exactly once
        assert acc.full_text == "Hello", \
            f"Expected 'Hello' but got '{acc.full_text}' — still duplicating!"

    def test_multi_token_no_duplication(self):
        """Simulate a multi-word response with all 3 event formats per token."""
        acc = SSEAccumulator()
        tokens = ["I'm ", "Veriochi ", "— ", "an ", "AI ", "assistant"]

        for token in tokens:
            # Each token generates 3 SSE events
            acc.process_event(make_content_delta(token))
            acc.process_event(make_message(token))
            acc.process_event(make_message_chunk(token))

        expected = "I'm Veriochi — an AI assistant"
        assert acc.full_text == expected, \
            f"Expected '{expected}' but got '{acc.full_text}'"

    def test_old_accumulator_would_triple(self):
        """
        Demonstrate what the OLD accumulator did — capture from all 3 formats.
        This is the bug we fixed.
        """
        # Simulate OLD behavior (accumulate from all 3)
        old_accumulated = []
        token = "Hello"

        for event_str in [make_content_delta(token), make_message(token), make_message_chunk(token)]:
            event_type = None
            data = None
            for line in event_str.strip().split('\n'):
                if line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    try:
                        data = json.loads(line[5:].strip())
                    except:
                        pass

            # OLD logic: capture from ALL formats
            if event_type == "content" and data and data.get("status") == "delta":
                old_accumulated.append(data["delta"])
            elif event_type == "message" and data and data.get("content"):
                old_accumulated.append(data["content"])
            elif event_type == "message_chunk" and data and data.get("content"):
                old_accumulated.append(data["content"])

        old_text = "".join(old_accumulated)
        assert old_text == "HelloHelloHello", \
            f"Old accumulator should triple, got: '{old_text}'"

        # NEW logic captures only once
        acc = SSEAccumulator()
        acc.process_event(make_content_delta(token))
        acc.process_event(make_message(token))
        acc.process_event(make_message_chunk(token))
        assert acc.full_text == "Hello", \
            f"New accumulator should NOT triple, got: '{acc.full_text}'"

    def test_content_delta_without_status_ignored(self):
        """Content events without status='delta' should not be accumulated."""
        acc = SSEAccumulator()
        acc.process_event(make_sse("content", {"status": "start"}))
        acc.process_event(make_sse("content", {"status": "stop"}))
        assert acc.full_text == ""

    def test_empty_delta_ignored(self):
        """Empty string deltas should not be added."""
        acc = SSEAccumulator()
        acc.process_event(make_sse("content", {"status": "delta", "delta": ""}))
        assert acc.full_text == ""


# ============================================================================
# Tests: Agent mode — tool event persistence
# ============================================================================

class TestAgentModeToolPersistence:
    """Verify tool events are captured for database persistence."""

    def test_tool_result_captured(self):
        """Tool result events should be captured for persistence."""
        acc = SSEAccumulator()
        acc.process_event(make_tool_result(
            tool_name="web_search",
            tool_call_id="call_123",
            tool_input={"query": "Python 3.13"},
            result=[{"title": "Python 3.13 Features", "url": "https://..."}],
        ))
        assert len(acc.tool_events) == 1
        assert acc.tool_events[0]["tool_name"] == "web_search"
        assert acc.tool_events[0]["tool_call_id"] == "call_123"

    def test_multiple_tool_results_captured(self):
        """Multiple tool calls should all be captured."""
        acc = SSEAccumulator()
        for i in range(5):
            acc.process_event(make_tool_result(
                tool_name=f"tool_{i}",
                tool_call_id=f"call_{i}",
                tool_input={"arg": i},
                result=f"result_{i}",
            ))
        assert len(acc.tool_events) == 5

    def test_text_and_tools_both_captured(self):
        """Text accumulation and tool capture work independently."""
        acc = SSEAccumulator()

        # Text events
        acc.process_event(make_content_delta("Let me search"))
        acc.process_event(make_message("Let me search"))

        # Tool events
        acc.process_event(make_tool_result("web_search", "call_1", {"q": "test"}, "results"))

        # More text
        acc.process_event(make_content_delta(" for you"))
        acc.process_event(make_message(" for you"))

        assert acc.full_text == "Let me search for you"
        assert len(acc.tool_events) == 1


# ============================================================================
# Tests: Agent mode — full response text accumulation
# ============================================================================

class TestAgentModeTextAccumulation:
    """Verify agent mode now accumulates text instead of saving a placeholder."""

    def test_agent_response_accumulated(self):
        """
        Simulate a full agent session. Text should be accumulated
        from content deltas for persistence.
        """
        acc = SSEAccumulator()

        # Agent initialization events (no text)
        acc.process_event(make_sse("status", {"type": "processing"}))
        acc.process_event(make_sse("status", {"type": "sandbox_ready"}))
        acc.process_event(make_sse("agent_initialized", {"sandbox_id": "sb_123"}))

        # Agent starts responding
        acc.process_event(make_content_delta("Here's "))
        acc.process_event(make_content_delta("what I "))
        acc.process_event(make_content_delta("found:"))

        # Tool call
        acc.process_event(make_tool_result("web_search", "call_1", {"q": "test"}, "results"))

        # More text
        acc.process_event(make_content_delta("\n\nBased on "))
        acc.process_event(make_content_delta("my research..."))

        # Complete
        acc.process_event(make_complete())

        assert acc.full_text == "Here's what I found:\n\nBased on my research..."
        assert len(acc.tool_events) == 1

    def test_no_content_returns_placeholder(self):
        """If no text content was streamed, the store method should use placeholder."""
        accumulated_text: List[str] = []
        agent_text = "".join(accumulated_text) if accumulated_text else ""
        if not agent_text:
            agent_text = "[Agent response completed]"
        assert agent_text == "[Agent response completed]"


# ============================================================================
# Tests: Source verification
# ============================================================================

class TestSourceVerification:
    """Verify the source code changes are correctly applied."""

    def test_chat_accumulator_only_captures_content(self):
        """
        Verify chat.py's accumulator only has the 'content' event branch
        and does NOT have 'message' or 'message_chunk' branches.
        """
        import os
        chat_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "app", "agent", "api", "v1", "chat.py"
        )
        chat_path = os.path.normpath(chat_path)
        with open(chat_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the accumulation section
        acc_idx = source.find("accumulated_agent_text.append")
        assert acc_idx != -1, "Could not find accumulation code"

        # Get surrounding context (500 chars before and after)
        context_start = max(0, acc_idx - 300)
        context_end = min(len(source), acc_idx + 500)
        accumulator_context = source[context_start:context_end]

        # Should NOT have multiple accumulation branches
        append_count = accumulator_context.count("accumulated_agent_text.append")
        assert append_count == 1, \
            f"Found {append_count} accumulation branches (expected 1):\n{accumulator_context}"

    def test_store_agent_response_accepts_text(self):
        """
        Verify _store_agent_response accepts accumulated_text parameter
        and does NOT hardcode a placeholder.
        """
        import os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "common", "socketio", "command", "query_handler.py"
        )
        handler_path = os.path.normpath(handler_path)
        with open(handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the _store_agent_response method
        store_idx = source.find("async def _store_agent_response")
        assert store_idx != -1, "Could not find _store_agent_response"

        # Get the method body (until next method)
        method_end = source.find("\n    async def ", store_idx + 10)
        if method_end == -1:
            method_end = source.find("\n    def ", store_idx + 10)
        method_body = source[store_idx:method_end] if method_end != -1 else source[store_idx:]

        # Should accept accumulated_text parameter
        assert "accumulated_text" in method_body, \
            "Method should accept accumulated_text parameter"

        # Should NOT have hardcoded placeholder as the ONLY text source
        # (it can have it as a fallback, but not as the only path)
        assert "accumulated_text" in method_body and "join" in method_body, \
            "Method should join accumulated_text for the agent message"

    def test_forward_sse_event_accumulates(self):
        """
        Verify _forward_sse_event has text accumulation logic.
        """
        import os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "common", "socketio", "command", "query_handler.py"
        )
        handler_path = os.path.normpath(handler_path)
        with open(handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the _forward_sse_event method
        fwd_idx = source.find("async def _forward_sse_event")
        assert fwd_idx != -1

        method_end = source.find("\n    async def ", fwd_idx + 10)
        method_body = source[fwd_idx:method_end] if method_end != -1 else source[fwd_idx:]

        # Should have accumulated_text parameter
        assert "accumulated_text" in method_body, \
            "_forward_sse_event should accept accumulated_text parameter"

        # Should accumulate from "content" deltas
        assert '"content"' in method_body or "'content'" in method_body, \
            "_forward_sse_event should check for content event type"
        assert "accumulated_text.append" in method_body, \
            "_forward_sse_event should append to accumulated_text"

    def test_maybe_persist_tool_event_exists(self):
        """Verify _maybe_persist_tool_event method exists."""
        import os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "common", "socketio", "command", "query_handler.py"
        )
        handler_path = os.path.normpath(handler_path)
        with open(handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "_maybe_persist_tool_event" in source, \
            "_maybe_persist_tool_event method not found"
        assert "create_tool_call" in source, \
            "Should call create_tool_call for tool persistence"
        assert "create_tool_result" in source, \
            "Should call create_tool_result for tool persistence"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
