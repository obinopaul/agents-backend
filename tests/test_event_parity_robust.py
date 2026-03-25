import pytest
import json
import asyncio
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock

# Import adapters and buffer
from backend.app.agent.event_adapter import IIAgentSSEAdapter, IIAgentWebSocketAdapter
from backend.app.agent.stream_buffer import StreamBuffer

# Import LangChain types for simulating chat.py
from langchain_core.messages import ToolMessage, AIMessageChunk

# Import specific function to test from chat.py
# We need to handle potential import errors if environment is not perfect
try:
    from backend.app.agent.api.v1.chat import _process_message_chunk, ReasoningState
except ImportError:
    _process_message_chunk = None
    ReasoningState = None

@pytest.fixture
def complex_tool_content() -> List[Dict[str, Any]]:
    """Sample complex tool content (Image + Text)."""
    return [
        {"type": "text", "text": "Here is the screenshot:"},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNiAAAABgDNjd8qAAAAAElFTkSuQmCC"
            }
        }
    ]

class TestIIAgentSSEAdapter:
    """Tests for the SSE Adapter (used in chat.py and agent.py)."""

    def test_tool_result_multimedia_serialization(self, complex_tool_content):
        """Verify that tool_result correctly serializes non-string output (Multimedia)."""
        adapter = IIAgentSSEAdapter(session_id="test_sess")
        
        # Call tool_result with LIST content (not string)
        sse_event = adapter.tool_result(
            tool_id="call_123",
            tool_name="browser_screenshot",
            output=complex_tool_content,  # Passing list directly
            is_error=False
        )
        
        # Verify SSE format
        assert sse_event.startswith("event: tool_result\n")
        
        # Verify JSON payload
        # SSE format: event: ...\ndata: {...}\n\n
        lines = sse_event.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        json_str = data_line[len("data: "):]
        payload = json.loads(json_str)
        
        # Check payload structure
        assert payload["status"] == "info"
        assert payload["tool_call_id"] == "call_123"
        assert payload["output"] == complex_tool_content
        assert isinstance(payload["output"], list)
        assert payload["output"][1]["type"] == "image"

class TestIIAgentWebSocketAdapter:
    """Tests for the WebSocket Adapter + StreamBuffer (used in QueryHandler)."""

    def test_tool_result_passthrough_multimedia(self, complex_tool_content):
        """Verify WebSocket adapter passes through atomic tool_result with list content."""
        adapter = IIAgentWebSocketAdapter()
        
        # Simulate AG-UI event (already atomic for tool_result, but maybe buffering passthrough)
        # Note: In WebSocket path, the event often comes from StreamBuffer logic.
        # But 'tool_result' is usually a direct emit or comes after tool_call_end if generated locally.
        # Let's test process_event logic.
        
        event_type = "tool_result"
        event_data = {
            "toolCallId": "call_123",
            "toolName": "browser_screenshot",
            "output": complex_tool_content, # Passing list
            "is_error": False
        }
        
        # Process via adapter (which uses StreamBuffer)
        out_type, out_data = adapter.process_event(event_type, event_data)
        
        # Should be passthrough (StreamBuffer ignores it -> transform called)
        # Or StreamBuffer might return it as 'tool_result' directly.
        
        assert out_type == "tool_result"
        assert out_data["tool_call_id"] == "call_123"
        assert out_data["result"] == complex_tool_content
        assert isinstance(out_data["result"], list)

    def test_buffer_atomic_tool_call(self):
        """Verify that streaming tool calls are buffered into an atomic event."""
        adapter = IIAgentWebSocketAdapter()
        
        # 1. Start
        t1, d1 = adapter.process_event("tool_call_start", {
            "toolCallId": "call_999",
            "toolCallName": "read_file"
        })
        assert t1 is None # Buffered
        
        # 2. Args Delta
        t2, d2 = adapter.process_event("tool_call_args", {
            "delta": '{"path": "RE'
        })
        assert t2 is None # Buffered
        
        t3, d3 = adapter.process_event("tool_call_args", {
            "delta": 'ADME.md"}'
        })
        assert t3 is None # Buffered
        
        # 3. End -> Atomic Emission
        t4, d4 = adapter.process_event("tool_call_end", {})
        
        assert t4 == "tool_call"
        assert d4["tool_name"] == "read_file"
        assert d4["tool_input"] == {"path": "README.md"}
        assert d4["tool_call_id"] == "call_999"

@pytest.mark.asyncio
async def test_chat_process_message_chunk_multimedia_fix(complex_tool_content):
    """
    Integration test for chat.py's _process_message_chunk.
    Verifies that the `chat.py` fix (removing string conversion) works.
    """
    if _process_message_chunk is None:
        pytest.skip("chat.py imports failed")

    # Mock inputs
    thread_id = "test_thread"
    agent = ("agent_node",)
    metadata = {}
    reasoning_state = ReasoningState()
    
    # Create a ToolMessage with LIST content
    message = ToolMessage(
        content=complex_tool_content, # List[Dict]
        tool_call_id="call_mock_1",
        name="browser_screenshot"
    )
    
    # Create a real adapter to capture output
    adapter = IIAgentSSEAdapter(session_id="test_sess")
    
    # Collect yielded events
    events = []
    async for event in _process_message_chunk(
        message_chunk=message,
        message_metadata=metadata,
        thread_id=thread_id,
        agent=agent,
        reasoning_state=reasoning_state,
        adapter=adapter
    ):
        events.append(event)
        
    # Analysis
    # We expect:
    # 1. adapter.tool_result event (II-Agent format)
    # 2. tool_result event (AG-UI format)
    # 3. tool_call_result event (Legacy)
    
    # Find the II-Agent tool_result event
    tool_result_event = next((e for e in events if "event: tool_result" in e), None)
    assert tool_result_event is not None, "Did not find tool_result event"
    
    # Parse proper SSE output
    lines = tool_result_event.strip().split("\n")
    data_line = next(line for line in lines if line.startswith("data: "))
    payload = json.loads(data_line[len("data: "):])
    
    # CRITICAL CHECK: Verify 'output' is a LIST, not a STRING representation of a list
    assert isinstance(payload["output"], list), "Output should be a list (Multimedia preservation failure)"
    assert payload["output"][1]["type"] == "image"
    
    print("\n✅ Verification Successful: Image data preserved as List object!")

if __name__ == "__main__":
    # Allow running directly
    import sys
    sys.exit(pytest.main([__file__]))
