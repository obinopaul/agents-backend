"""
Test chat.py SSE reasoning pipeline.

chat.py uses IIAgentSSEAdapter for chat mode (direct SSE to browser).
Tests verify:
1. Reasoning extraction from content_blocks works (same as agent.py)
2. List content fallback MISSING reasoning (identified gap)
3. SSE adapter produces correct thinking events
4. End-to-end SSE event format for chat mode
"""

import json
import pytest
from typing import List, Tuple, Optional

from backend.app.agent.event_adapter import IIAgentSSEAdapter

TEST_SESSION_ID = "test-session-001"


# =============================================================================
# Helpers
# =============================================================================

def parse_sse_string(sse_str: str) -> Tuple[Optional[str], Optional[dict]]:
    """Parse an SSE string into (event_type, data)."""
    lines = sse_str.strip().split('\n')
    event_type = None
    data = None
    for line in lines:
        if line.startswith('event:'):
            event_type = line.split(':', 1)[1].strip()
        elif line.startswith('data:'):
            data_str = line.split(':', 1)[1].strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}
    return event_type, data


# =============================================================================
# Test: IIAgentSSEAdapter thinking lifecycle
# =============================================================================

class TestSSEAdapterThinking:
    """Test the SSE adapter's thinking methods (used by chat.py)."""

    def test_thinking_start_sse_format(self):
        """Test adapter.thinking_start() produces correct SSE."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        sse = adapter.thinking_start()
        event_type, data = parse_sse_string(sse)

        assert event_type == "thinking"
        assert data["status"] == "start"
        assert "thinking_id" in data

    def test_thinking_delta_sse_format(self):
        """Test adapter.thinking_delta() produces correct SSE."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        adapter.thinking_start()  # Must start first
        sse = adapter.thinking_delta("Let me think...")
        event_type, data = parse_sse_string(sse)

        assert event_type == "thinking"
        assert data["status"] == "delta"
        assert data["delta"] == "Let me think..."

    def test_thinking_stop_sse_format(self):
        """Test adapter.thinking_stop() produces correct SSE."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        adapter.thinking_start()
        sse = adapter.thinking_stop()
        event_type, data = parse_sse_string(sse)

        assert event_type == "thinking"
        assert data["status"] == "stop"

    def test_full_thinking_lifecycle(self):
        """Test complete start → delta → stop lifecycle."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        events = []

        events.append(parse_sse_string(adapter.thinking_start()))
        events.append(parse_sse_string(adapter.thinking_delta("Step 1")))
        events.append(parse_sse_string(adapter.thinking_delta("Step 2")))
        events.append(parse_sse_string(adapter.thinking_stop()))

        assert len(events) == 4
        statuses = [d["status"] for _, d in events]
        assert statuses == ["start", "delta", "delta", "stop"]

        # All deltas preserved
        deltas = [d.get("delta", "") for _, d in events]
        assert "Step 1" in deltas
        assert "Step 2" in deltas


# =============================================================================
# Test: Chat SSE stream simulation 
# =============================================================================

class TestChatSSEStream:
    """
    Simulate what chat.py produces for the frontend SSE stream.
    
    In chat mode, the adapter produces SSE strings directly.
    The frontend (chat.service.ts) parses these SSE strings and
    dispatches thinking events via StreamCallbacks.
    """

    def test_chat_reasoning_produces_both_formats(self):
        """
        chat.py produces BOTH:
        1. adapter.thinking_*() → SSE "thinking" events (II-Agent format)
        2. _make_event("reasoning_*") → SSE reasoning events (AG-UI format)
        
        For SSE mode (direct to browser), the frontend uses chat.service.ts 
        which only handles "thinking" events (not reasoning_*).
        """
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        
        # Simulate what chat.py yields for one reasoning block
        sse_events = []

        # 1. adapter.thinking_start()
        sse_events.append(("ii-agent", adapter.thinking_start()))
        
        # 2. _make_event("reasoning_start", ...)
        sse_events.append(("ag-ui", f'event: reasoning_start\ndata: {{"messageId": "r-001"}}\n\n'))
        
        # 3. _make_event("reasoning_message_start", ...)
        sse_events.append(("ag-ui", f'event: reasoning_message_start\ndata: {{"messageId": "r-001", "role": "assistant"}}\n\n'))
        
        # 4. adapter.thinking_delta(text)
        sse_events.append(("ii-agent", adapter.thinking_delta("Deep analysis")))
        
        # 5. _make_event("reasoning_message_content", ...)
        sse_events.append(("ag-ui", f'event: reasoning_message_content\ndata: {{"messageId": "r-001", "delta": "Deep analysis"}}\n\n'))
        
        # 6. adapter.thinking_stop()
        sse_events.append(("ii-agent", adapter.thinking_stop()))
        
        # 7. _make_event("reasoning_message_end", ...)
        sse_events.append(("ag-ui", f'event: reasoning_message_end\ndata: {{"messageId": "r-001"}}\n\n'))
        
        # 8. _make_event("reasoning_end", ...)
        sse_events.append(("ag-ui", f'event: reasoning_end\ndata: {{"messageId": "r-001"}}\n\n'))

        # The frontend (chat.service.ts) ONLY processes "thinking" events
        thinking_events = []
        for source, sse in sse_events:
            et, data = parse_sse_string(sse)
            if et == "thinking":
                thinking_events.append((et, data))

        assert len(thinking_events) == 3  # start, delta, stop
        assert thinking_events[0][1]["status"] == "start"
        assert thinking_events[1][1]["status"] == "delta"
        assert thinking_events[1][1]["delta"] == "Deep analysis"
        assert thinking_events[2][1]["status"] == "stop"


# =============================================================================
# Test: Chat.py list content reasoning gap
# =============================================================================

class TestChatListContentGap:
    """
    Verify the list content fallback path in chat.py.
    
    chat.py lines 556-588 handle list content fallback:
    - Handles type='text' ✓
    - Does NOT handle type='reasoning' ✗ (same gap as agent.py)
    
    Some models may send reasoning via chunk.content (list) instead
    of content_blocks. This test documents the gap.
    """

    def test_list_content_text_handled(self):
        """Verify text items in list content are handled."""
        # Simulated chunk.content as list 
        content_items = [
            {"type": "text", "text": "Hello world"},
        ]
        
        # Simulate chat.py's list content handling
        processed = []
        for item in content_items:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    processed.append(("text", item.get("text", "")))
        
        assert len(processed) == 1
        assert processed[0] == ("text", "Hello world")

    def test_list_content_reasoning_NOT_handled(self):
        """
        Verify reasoning items in list content are SILENTLY DROPPED.
        This is the identified bug.
        """
        content_items = [
            {"type": "reasoning", "reasoning": "Let me think about this"},
            {"type": "text", "text": "The answer is 42"},
        ]
        
        # Simulate chat.py's list content handling (current code)
        processed = []
        for item in content_items:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    processed.append(("text", item.get("text", "")))
                # NOTE: No handling for item_type == "reasoning"!
        
        assert len(processed) == 1  # Only text processed
        assert processed[0] == ("text", "The answer is 42")
        # Reasoning is silently dropped!

    def test_list_content_with_reasoning_fix(self):
        """
        Show what the fix should look like for list content reasoning.
        """
        content_items = [
            {"type": "reasoning", "reasoning": "Let me think about this"},
            {"type": "text", "text": "The answer is 42"},
        ]
        
        # Fixed version: also handle reasoning type
        processed = []
        for item in content_items:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    processed.append(("text", item.get("text", "")))
                elif item_type == "reasoning":
                    reasoning_text = (
                        item.get("reasoning") or 
                        item.get("thinking") or 
                        item.get("text", "")
                    )
                    if reasoning_text:
                        processed.append(("reasoning", reasoning_text))
        
        assert len(processed) == 2  # Both processed!
        assert processed[0] == ("reasoning", "Let me think about this")
        assert processed[1] == ("text", "The answer is 42")


# =============================================================================
# Test: Frontend SSE parsing (chat.service.ts)
# =============================================================================

class TestFrontendSSEParsing:
    """
    Simulate how chat.service.ts parses thinking SSE events.
    
    chat.service.ts line 248:
    if (eventName === 'thinking') {
        const data = JSON.parse(eventData)
        if (data.status === 'start') callbacks.onThinkingStart(data)
        else if (data.status === 'delta') callbacks.onThinking(data)
        else if (data.status === 'stop') callbacks.onThinkingStop(data)
    }
    """

    def test_frontend_parses_thinking_start(self):
        """Verify frontend can parse thinking start event."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        sse = adapter.thinking_start()
        _, data = parse_sse_string(sse)

        # Frontend checks: data.status === 'start'
        assert data["status"] == "start"
        # Frontend calls: callbacks.onThinkingStart(data)
        # No assertion needed — just verify the shape is valid

    def test_frontend_parses_thinking_delta(self):
        """Verify frontend can parse thinking delta event."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        adapter.thinking_start()
        sse = adapter.thinking_delta("Analysis in progress")
        _, data = parse_sse_string(sse)

        # Frontend checks: data.status === 'delta'
        assert data["status"] == "delta"
        # Frontend reads: data.delta for thinking text
        assert data["delta"] == "Analysis in progress"

    def test_frontend_parses_thinking_stop(self):
        """Verify frontend can parse thinking stop event."""
        adapter = IIAgentSSEAdapter(session_id=TEST_SESSION_ID)
        adapter.thinking_start()
        sse = adapter.thinking_stop()
        _, data = parse_sse_string(sse)

        # Frontend checks: data.status === 'stop'
        assert data["status"] == "stop"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
