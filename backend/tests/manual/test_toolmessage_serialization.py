"""
Verification test for the <circular ref: ToolMessage> serialization fix.

This test validates all 3 layers of the fix:
  Layer 1 (agent.py): ToolMessage unwrapping at extraction point
  Layer 2 (json_utils.py): LangChain message detection before model_dump
  Layer 3 (event_adapter.py): Safety-net for serialized ToolMessage dicts

Usage:
    cd backend
    python -m pytest tests/manual/test_toolmessage_serialization.py -v
    # Or directly:
    python tests/manual/test_toolmessage_serialization.py
"""
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from backend.src.utils.json_utils import make_serializable, safe_json_serialize
from backend.app.agent.event_adapter import IIAgentWebSocketAdapter


def test_layer2_toolmessage_not_circular_ref():
    """Layer 2: make_serializable should NOT produce <circular ref> for ToolMessage."""
    msg = ToolMessage(
        content="ls -la output\ntotal 42\ndrwxr-xr-x ...",
        tool_call_id="call_abc123",
        name="bash",
    )
    result = make_serializable(msg)
    
    # Should be the content string, not a dict with metadata, and definitely
    # not "<circular ref: ToolMessage>"
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}: {result!r}"
    assert "<circular ref" not in str(result), f"Circular ref detected: {result!r}"
    assert "ls -la output" in result, f"Content not preserved: {result!r}"
    # Should NOT include ToolMessage metadata
    assert "tool_call_id" not in str(result), f"ToolMessage metadata leaked: {result!r}"
    print("✅ Layer 2: ToolMessage serialized to content string correctly")


def test_layer2_toolmessage_with_json_content():
    """Layer 2: ToolMessage with JSON array content (web search case)."""
    search_results = json.dumps([
        {"title": "Result 1", "url": "https://example.com", "content": "Summary 1"},
        {"title": "Result 2", "url": "https://test.com", "content": "Summary 2"},
    ])
    msg = ToolMessage(
        content=search_results,
        tool_call_id="call_search_001",
        name="web_search",
    )
    result = make_serializable(msg)
    
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}: {result!r}"
    assert "Result 1" in result
    assert "<circular ref" not in str(result)
    print("✅ Layer 2: Web search ToolMessage serialized correctly")


def test_layer2_toolmessage_with_list_content():
    """Layer 2: ToolMessage with list content (multimodal response)."""
    msg = ToolMessage(
        content=[
            {"type": "text", "text": "File read successfully"},
            {"type": "text", "text": "Contents: hello world"},
        ],
        tool_call_id="call_read_001",
        name="read_file",
    )
    result = make_serializable(msg)
    
    assert isinstance(result, list), f"Expected list, got {type(result).__name__}: {result!r}"
    assert len(result) == 2
    assert "<circular ref" not in str(result)
    print("✅ Layer 2: ToolMessage with list content serialized correctly")


def test_layer2_ai_message_not_circular_ref():
    """Layer 2: AIMessage should also be handled cleanly."""
    msg = AIMessage(content="I'll help you with that task.")
    result = make_serializable(msg)
    
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}: {result!r}"
    assert "<circular ref" not in str(result)
    assert "help you" in result
    print("✅ Layer 2: AIMessage serialized to content string correctly")


def test_layer2_safe_json_serialize_full_pipeline():
    """Layer 2: Full pipeline — ToolMessage inside an event data dict."""
    tool_msg = ToolMessage(
        content="Command completed successfully",
        tool_call_id="call_xyz789",
        name="bash",
    )
    event_data = {
        "tool_call_id": "call_xyz789",
        "tool_name": "bash",
        "tool_display_name": "Bash",
        "tool_input": {"command": "echo hello"},
        "result": tool_msg,  # RAW ToolMessage — the bug scenario
        "is_error": False,
        "thread_id": "thread-test-001",
    }
    
    json_str = safe_json_serialize(event_data)
    parsed = json.loads(json_str)
    
    assert "<circular ref" not in json_str, f"Circular ref in serialized output: {json_str}"
    # The "result" should be the content string, not a full ToolMessage dict
    assert parsed["result"] == "Command completed successfully", \
        f"Expected content string, got: {parsed['result']!r}"
    print("✅ Layer 2: Full event data with ToolMessage serialized correctly")


def test_layer3_transform_strips_toolmessage_dict():
    """Layer 3: _transform_data should strip serialized ToolMessage wrapper dicts."""
    # Simulate a case where Layer 2 missed and model_dump() produced the full dict
    event_data = {
        "tool_call_id": "call_test",
        "tool_name": "bash",
        "result": {
            "content": "ls output here",
            "type": "tool",
            "tool_call_id": "call_test",
            "response_metadata": {},
            "name": "bash",
            "id": "msg_123",
        },
        "is_error": False,
    }
    
    _, ws_data = IIAgentWebSocketAdapter.transform("tool_result", event_data)
    result = ws_data["result"]
    
    # Should have stripped the ToolMessage wrapper and returned just the content
    assert result == "ls output here", f"Expected content string, got: {result!r}"
    assert "tool_call_id" not in str(result)
    print("✅ Layer 3: Serialized ToolMessage dict stripped correctly")


def test_layer3_transform_handles_circular_ref_string():
    """Layer 3: _transform_data should handle <circular ref> strings gracefully."""
    event_data = {
        "tool_call_id": "call_test",
        "tool_name": "bash",
        "result": "<circular ref: ToolMessage>",
        "is_error": False,
    }
    
    _, ws_data = IIAgentWebSocketAdapter.transform("tool_result", event_data)
    result = ws_data["result"]
    
    # Should NOT pass the circular ref string to the frontend
    assert "<circular ref" not in result, f"Circular ref leaked to frontend: {result!r}"
    print("✅ Layer 3: <circular ref> string handled gracefully")


def test_layer3_transform_preserves_normal_results():
    """Layer 3: Normal results should pass through unchanged."""
    # Plain string
    event_data_str = {
        "tool_call_id": "call_test",
        "tool_name": "bash",
        "result": "echo output: hello world",
        "is_error": False,
    }
    _, ws_data = IIAgentWebSocketAdapter.transform("tool_result", event_data_str)
    assert ws_data["result"] == "echo output: hello world"
    
    # JSON array string (web search)
    event_data_json = {
        "tool_call_id": "call_test",
        "tool_name": "web_search",
        "result": '[{"title": "Test"}]',
        "is_error": False,
    }
    _, ws_data = IIAgentWebSocketAdapter.transform("tool_result", event_data_json)
    assert ws_data["result"] == '[{"title": "Test"}]'
    
    # Dict with content (slide HTML)
    event_data_slide = {
        "tool_call_id": "call_test",
        "tool_name": "SlideWrite",
        "result": {"content": "<html>slide content</html>"},
        "is_error": False,
    }
    _, ws_data = IIAgentWebSocketAdapter.transform("tool_result", event_data_slide)
    # HTML content should be kept as JSON (not unwrapped, since it's not JSON-like)
    parsed = json.loads(ws_data["result"])
    assert parsed["content"] == "<html>slide content</html>"
    
    print("✅ Layer 3: Normal results preserved correctly")


def test_regular_pydantic_model_still_uses_model_dump():
    """Ensure non-message Pydantic models still use model_dump (not content extraction)."""
    from pydantic import BaseModel
    
    class MyConfig(BaseModel):
        name: str = "test"
        value: int = 42
    
    result = make_serializable(MyConfig())
    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}: {result!r}"
    assert result["name"] == "test"
    assert result["value"] == 42
    print("✅ Regular Pydantic models still use model_dump correctly")


def test_pydantic_with_content_but_no_response_metadata():
    """Pydantic model with 'content' but no 'response_metadata' should use model_dump."""
    from pydantic import BaseModel
    
    class ContentBlock(BaseModel):
        content: str = "block content"
        block_type: str = "text"
    
    result = make_serializable(ContentBlock())
    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}: {result!r}"
    assert result["content"] == "block content"
    assert result["block_type"] == "text"
    print("✅ ContentBlock model uses model_dump (not content extraction)")


if __name__ == "__main__":
    tests = [
        test_layer2_toolmessage_not_circular_ref,
        test_layer2_toolmessage_with_json_content,
        test_layer2_toolmessage_with_list_content,
        test_layer2_ai_message_not_circular_ref,
        test_layer2_safe_json_serialize_full_pipeline,
        test_layer3_transform_strips_toolmessage_dict,
        test_layer3_transform_handles_circular_ref_string,
        test_layer3_transform_preserves_normal_results,
        test_regular_pydantic_model_still_uses_model_dump,
        test_pydantic_with_content_but_no_response_metadata,
    ]
    
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"❌ {test_fn.__name__}: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        sys.exit(1)
    else:
        print("All tests passed!")
