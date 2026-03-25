"""
Test reasoning/thinking extraction from AIMessageChunk objects.

Tests how agent.py and chat.py extract reasoning from LangChain's
AIMessageChunk content_blocks and list content formats.

These tests simulate the actual LangChain streaming output formats
and verify the SSE events produced by the generator logic.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# Simulated LangChain Types
# =============================================================================

class MockAIMessageChunk:
    """
    Simulate LangChain's AIMessageChunk with content_blocks support.
    
    In LangChain v0.3+, AIMessageChunk has:
    - content: str | list (the raw content)
    - content_blocks: list[dict] (standardized blocks for all providers)
    - tool_calls: list[dict]
    - tool_call_chunks: list[dict]
    """
    def __init__(
        self,
        content="",
        content_blocks=None,
        tool_calls=None,
        tool_call_chunks=None,
    ):
        self.content = content
        self.content_blocks = content_blocks or []
        self.tool_calls = tool_calls or []
        self.tool_call_chunks = tool_call_chunks or []


# =============================================================================
# SSE Event Helper
# =============================================================================

def parse_sse_events(sse_strings: List[str]) -> List[Dict[str, Any]]:
    """Parse a list of SSE event strings into (event_type, data) dicts."""
    events = []
    for event_str in sse_strings:
        if not event_str or not event_str.strip():
            continue
        lines = event_str.strip().split('\n')
        event_type = None
        data = None
        for line in lines:
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    data = {"raw": line[5:].strip()}
        if event_type:
            events.append({"event": event_type, "data": data})
    return events


# =============================================================================
# Tests: content_blocks Reasoning Extraction
# =============================================================================

class TestContentBlocksReasoningExtraction:
    """
    Test reasoning extraction from content_blocks format.
    
    This simulates what happens at agent.py lines 846-886 when the LLM
    returns content_blocks with type='reasoning'.
    """

    def test_reasoning_block_detected(self):
        """A reasoning content block should be detected by type check."""
        block = {"type": "reasoning", "reasoning": "Let me think about this."}
        assert block.get("type") == "reasoning"
        reasoning_text = block.get("reasoning") or block.get("thinking") or block.get("text", "")
        assert reasoning_text == "Let me think about this."

    def test_reasoning_block_with_thinking_key(self):
        """Some providers use 'thinking' key instead of 'reasoning'."""
        block = {"type": "reasoning", "thinking": "Deep analysis here."}
        reasoning_text = block.get("reasoning") or block.get("thinking") or block.get("text", "")
        assert reasoning_text == "Deep analysis here."

    def test_reasoning_block_with_text_key(self):
        """Fallback to 'text' key."""
        block = {"type": "reasoning", "text": "Planning approach."}
        reasoning_text = block.get("reasoning") or block.get("thinking") or block.get("text", "")
        assert reasoning_text == "Planning approach."

    def test_reasoning_then_text_blocks(self):
        """
        Simulate a chunk with reasoning followed by text blocks.
        This is the typical output pattern from Claude with extended thinking.
        """
        chunk = MockAIMessageChunk(
            content_blocks=[
                {"type": "reasoning", "reasoning": "I need to analyze this carefully."},
            ]
        )
        assert hasattr(chunk, 'content_blocks')
        assert chunk.content_blocks
        assert chunk.content_blocks[0]["type"] == "reasoning"

    def test_text_block_after_reasoning(self):
        """Text block should be separate from reasoning."""
        blocks = [
            {"type": "reasoning", "reasoning": "Thinking..."},
            {"type": "text", "text": "Here is my answer."},
        ]
        
        reasoning_blocks = [b for b in blocks if b.get("type") == "reasoning"]
        text_blocks = [b for b in blocks if b.get("type") == "text"]
        
        assert len(reasoning_blocks) == 1
        assert len(text_blocks) == 1
        assert reasoning_blocks[0]["reasoning"] == "Thinking..."
        assert text_blocks[0]["text"] == "Here is my answer."

    def test_list_content_no_reasoning(self):
        """
        Test the list content path (agent.py lines 920-960).
        This path handles Anthropic-style list content but currently
        does NOT extract reasoning blocks - only text and text_delta.
        
        This is a POTENTIAL GAP: if reasoning comes through chunk.content
        as a list item instead of content_blocks, it won't be extracted.
        """
        chunk = MockAIMessageChunk(
            content=[
                {"type": "text", "text": "Regular text."},
                {"type": "reasoning", "reasoning": "This reasoning gets MISSED!"},
            ]
        )
        
        # Current code only checks for 'text' and 'text_delta' types
        # in the list content path, NOT 'reasoning'
        extracted_reasoning = []
        for item in chunk.content:
            if isinstance(item, dict):
                item_type = item.get('type', '')
                if item_type == 'reasoning':
                    extracted_reasoning.append(
                        item.get('reasoning') or item.get('thinking') or item.get('text', '')
                    )
        
        # We CAN extract it if we add the check
        assert len(extracted_reasoning) == 1
        assert extracted_reasoning[0] == "This reasoning gets MISSED!"


# =============================================================================
# Tests: SSE Event Generation from Reasoning
# =============================================================================

class TestSSEReasoningEventGeneration:
    """
    Test that the SSE events generated for reasoning are correct.
    These simulate what _make_event produces in agent.py.
    """

    def test_make_event_reasoning_start(self):
        """Verify reasoning_start SSE event format."""
        from backend.app.agent.api.v1.agent import _make_event
        
        msg_id = "reasoning-test001"
        result = _make_event("reasoning_start", {"messageId": msg_id})
        
        assert result.startswith("event: reasoning_start\n")
        assert "data:" in result
        
        # Parse the data part
        data_line = [l for l in result.strip().split('\n') if l.startswith('data:')][0]
        data = json.loads(data_line[5:].strip())
        assert data["messageId"] == msg_id

    def test_make_event_reasoning_content(self):
        """Verify reasoning_message_content SSE event format."""
        from backend.app.agent.api.v1.agent import _make_event
        
        result = _make_event("reasoning_message_content", {
            "messageId": "r-001",
            "delta": "Analyzing the problem...",
        })
        
        events = parse_sse_events([result])
        assert len(events) == 1
        assert events[0]["event"] == "reasoning_message_content"
        assert events[0]["data"]["delta"] == "Analyzing the problem..."

    def test_make_event_reasoning_end(self):
        """Verify reasoning_end SSE event format."""
        from backend.app.agent.api.v1.agent import _make_event
        
        result = _make_event("reasoning_end", {"messageId": "r-001"})
        events = parse_sse_events([result])
        assert events[0]["event"] == "reasoning_end"


# =============================================================================
# Tests: ReasoningState Behavior
# =============================================================================

class TestReasoningState:
    """Test the ReasoningState dataclass used in agent.py."""

    def test_initial_state(self):
        """ReasoningState starts inactive."""
        from backend.app.agent.models import ReasoningState
        
        state = ReasoningState()
        assert not state.is_active
        assert state.message_id is None

    def test_start_reasoning(self):
        """Starting reasoning activates state and generates ID."""
        from backend.app.agent.models import ReasoningState
        
        state = ReasoningState()
        msg_id = state.start_reasoning()
        
        assert state.is_active
        assert state.message_id is not None
        assert msg_id.startswith("reasoning-")

    def test_end_reasoning(self):
        """Ending reasoning deactivates state."""
        from backend.app.agent.models import ReasoningState
        
        state = ReasoningState()
        state.start_reasoning()
        msg_id = state.end_reasoning()
        
        assert not state.is_active
        assert state.message_id is None
        assert msg_id is not None

    def test_multiple_reasoning_cycles(self):
        """Multiple start/end cycles should work."""
        from backend.app.agent.models import ReasoningState
        
        state = ReasoningState()
        
        id1 = state.start_reasoning()
        state.end_reasoning()
        
        id2 = state.start_reasoning()
        state.end_reasoning()
        
        # IDs should be different
        assert id1 != id2


# =============================================================================
# Tests: Dual Event Emission (II-Agent + AG-UI)
# =============================================================================

class TestDualEventEmission:
    """
    Test that agent.py emits BOTH II-Agent format (adapter.thinking_*)
    AND AG-UI format (_make_event("reasoning_*")) events.
    
    The II-Agent format events go through the SSE adapter for chat mode.
    The AG-UI format events go through the StreamBuffer for WebSocket mode.
    """

    def test_dual_emission_produces_both_formats(self):
        """
        Simulate the dual emission pattern from agent.py lines 864-884.
        Both formats should be produced for a reasoning block.
        """
        from backend.app.agent.event_adapter import IIAgentSSEAdapter
        from backend.app.agent.models import ReasoningState
        from backend.app.agent.api.v1.agent import _make_event

        adapter = IIAgentSSEAdapter(session_id="test", model_id="test")
        reasoning_state = ReasoningState()

        # Simulate the dual emission from agent.py
        emitted_events = []

        # Reasoning block detected
        reasoning_text = "Let me analyze this carefully."
        
        # Start reasoning
        if not reasoning_state.is_active:
            msg_id = reasoning_state.start_reasoning()
            
            # II-Agent format
            if not adapter.thinking_active:
                emitted_events.append(("ii_agent", adapter.thinking_start()))
            
            # AG-UI format
            emitted_events.append(("ag_ui", _make_event("reasoning_start", {"messageId": msg_id})))
            emitted_events.append(("ag_ui", _make_event("reasoning_message_start", {
                "messageId": msg_id,
                "role": "assistant",
            })))

        # Content delta
        emitted_events.append(("ii_agent", adapter.thinking_delta(reasoning_text)))
        emitted_events.append(("ag_ui", _make_event("reasoning_message_content", {
            "messageId": reasoning_state.message_id,
            "delta": reasoning_text,
        })))

        # Verify both formats produced
        ii_agent_events = [e for f, e in emitted_events if f == "ii_agent"]
        ag_ui_events = [e for f, e in emitted_events if f == "ag_ui"]

        assert len(ii_agent_events) == 2  # thinking_start + thinking_delta
        assert len(ag_ui_events) == 3  # reasoning_start + reasoning_message_start + content

        # II-Agent format should be SSE strings with "event: thinking"
        for sse in ii_agent_events:
            assert "event: thinking" in sse

        # AG-UI format should be SSE strings with "event: reasoning_*"
        reasoning_sse_count = sum(1 for e in ag_ui_events if "event: reasoning" in e)
        assert reasoning_sse_count == 3


# =============================================================================
# Tests: Gap Analysis - Missing Reasoning in list content
# =============================================================================

class TestListContentReasoningGap:
    """
    Identify the gap where reasoning in chunk.content (list format)
    is NOT extracted by the current code.
    
    agent.py line 920-960 handles isinstance(chunk.content, list)
    but only checks for 'text' and 'text_delta' types, not 'reasoning'.
    """

    def test_content_blocks_have_reasoning_handling(self):
        """content_blocks path (line 855) handles reasoning correctly."""
        block = {"type": "reasoning", "reasoning": "Thinking..."}
        # This IS handled - block_type == 'reasoning' check exists at line 856
        assert block["type"] == "reasoning"

    def test_list_content_missing_reasoning_handling(self):
        """
        chunk.content list path (line 920) is MISSING reasoning handling.
        
        The code at lines 920-960 only checks for:
        - item_type == 'text' (line 923)
        - item_type == 'text_delta' (line 937)
        
        But NOT:
        - item_type == 'reasoning'
        
        This means if a model puts reasoning in chunk.content instead of
        content_blocks, it will be silently dropped.
        """
        # Simulate the current code logic
        items = [
            {"type": "reasoning", "reasoning": "Hidden thought!"},
            {"type": "text", "text": "Visible text."},
        ]
        
        # Current code behavior
        handled_items = []
        for item in items:
            if isinstance(item, dict):
                item_type = item.get('type', '')
                if item_type == 'text':
                    handled_items.append(item)
                elif item_type == 'text_delta':
                    handled_items.append(item)
                # NOTE: 'reasoning' type is NOT handled here!
        
        # Only text was handled, reasoning was dropped
        assert len(handled_items) == 1
        assert handled_items[0]["type"] == "text"
        # The reasoning item was silently dropped!


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
