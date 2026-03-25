# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Unit tests for JSON serialization edge cases.

Tests the safe serialization functions in json_utils.py with various
complex objects including:
- Pydantic v1/v2 models
- LangChain messages (ToolMessage, AIMessage)
- Circular references
- Bytes and sets
- Callables and functions
"""

import pytest
import json
from typing import Optional, List, Dict, Any

# Import the safe serialization functions
from backend.src.utils.json_utils import (
    make_serializable,
    safe_json_serialize,
)


class TestMakeSerializable:
    """Test the make_serializable function."""

    def test_primitives(self):
        """Test that primitives pass through unchanged."""
        assert make_serializable(None) is None
        assert make_serializable(True) is True
        assert make_serializable(False) is False
        assert make_serializable(42) == 42
        assert make_serializable(3.14) == 3.14
        assert make_serializable("hello") == "hello"

    def test_list(self):
        """Test list serialization."""
        result = make_serializable([1, 2, "three", None])
        assert result == [1, 2, "three", None]

    def test_tuple(self):
        """Test tuple gets converted to list."""
        result = make_serializable((1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_set(self):
        """Test set gets converted to list."""
        result = make_serializable({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_dict(self):
        """Test dict serialization."""
        result = make_serializable({"name": "test", "count": 5})
        assert result == {"name": "test", "count": 5}

    def test_dict_skips_private_keys(self):
        """Test that private keys (starting with _) are skipped."""
        result = make_serializable({
            "public": "value",
            "_private": "secret",
            "__dunder": "also_hidden"
        })
        assert result == {"public": "value"}

    def test_bytes(self):
        """Test bytes get decoded to string."""
        result = make_serializable(b"hello world")
        assert result == "hello world"

    def test_bytes_invalid_utf8(self):
        """Test invalid UTF-8 bytes get replaced gracefully."""
        result = make_serializable(b"\xff\xfe")
        assert isinstance(result, str)
        # Should contain replacement characters
        assert "�" in result or "bytes" in str(result).lower()

    def test_circular_reference(self):
        """Test circular reference detection."""
        circular_list = [1, 2]
        circular_list.append(circular_list)  # Create circular reference
        result = make_serializable(circular_list)
        assert result[0] == 1
        assert result[1] == 2
        assert "<circular ref:" in result[2]

    def test_nested_structure(self):
        """Test deeply nested structure serialization."""
        data = {
            "level1": {
                "level2": {
                    "level3": [1, 2, {"level4": "deep"}]
                }
            }
        }
        result = make_serializable(data)
        assert result["level1"]["level2"]["level3"][2]["level4"] == "deep"

    def test_callable(self):
        """Test callable gets converted to placeholder string."""
        def my_func():
            pass
        result = make_serializable(my_func)
        assert "<function>" in result.lower()

    def test_lambda(self):
        """Test lambda gets converted to placeholder string."""
        result = make_serializable(lambda x: x + 1)
        assert "<function>" in result.lower()


class TestPydanticModels:
    """Test Pydantic model serialization."""

    def test_pydantic_v2_model(self):
        """Test Pydantic v2 model with model_dump."""
        try:
            from pydantic import BaseModel

            class User(BaseModel):
                name: str
                age: int

            user = User(name="Alice", age=30)
            result = make_serializable(user)
            assert result["name"] == "Alice"
            assert result["age"] == 30
        except ImportError:
            pytest.skip("Pydantic not installed")


class TestLangChainObjects:
    """Test LangChain object serialization."""

    def test_mock_tool_message(self):
        """Test mock ToolMessage-like object with content attribute."""
        class MockToolMessage:
            def __init__(self, content):
                self.content = content
        
        mock_tool_msg = MockToolMessage("Tool result: success")
        result = make_serializable(mock_tool_msg)
        assert result == "Tool result: success"

    def test_mock_tool_message_list_content(self):
        """Test mock ToolMessage with list content (multimodal)."""
        class MockToolMessage:
            def __init__(self, content):
                self.content = content
        
        mock_tool_msg = MockToolMessage([
            {"type": "text", "text": "Here's the result"},
            {"type": "image", "url": "https://example.com/img.png"}
        ])
        result = make_serializable(mock_tool_msg)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "image"

    def test_object_with_public_attrs(self):
        """Test object with __dict__ public attributes."""
        class CustomTool:
            def __init__(self):
                self.name = "my_tool"
                self.description = "Does things"
                self._private = "hidden"

        tool = CustomTool()
        result = make_serializable(tool)
        assert result["name"] == "my_tool"
        assert result["description"] == "Does things"
        assert "_private" not in result


class TestSafeJsonSerialize:
    """Test the safe_json_serialize function."""

    def test_simple_dict(self):
        """Test simple dict serialization."""
        result = safe_json_serialize({"key": "value"})
        assert result == '{"key": "value"}'
        # Verify it's valid JSON
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_complex_nested(self):
        """Test complex nested structure."""
        data = {
            "users": [
                {"name": "Alice", "scores": [100, 95, 88]},
                {"name": "Bob", "scores": [90, 92, 85]},
            ],
            "metadata": {"version": 1, "timestamp": 12345}
        }
        result = safe_json_serialize(data)
        parsed = json.loads(result)
        assert parsed["users"][0]["name"] == "Alice"
        assert parsed["metadata"]["version"] == 1

    def test_with_unserializable_object(self):
        """Test that unserializable objects don't raise exceptions."""
        class WeirdObject:
            def __repr__(self):
                return "WeirdObject()"

        data = {"normal": "value", "weird": WeirdObject()}
        # Should not raise
        result = safe_json_serialize(data)
        parsed = json.loads(result)
        assert parsed["normal"] == "value"
        # The weird object should be handled gracefully
        assert "<WeirdObject>" in parsed["weird"]

    def test_never_raises(self):
        """Test that function never raises, even with extreme edge cases."""
        # Create an object that is difficult to serialize
        class EvilObject:
            """An object where common serialization methods fail."""
            @property
            def model_dump(self):
                raise Exception("boom")
            
            @property
            def dict(self):
                raise Exception("boom")
            
            @property
            def content(self):
                raise Exception("boom")
            
            @property
            def __dict__(self):
                # Return something that triggers recursion
                return {"nested": self}
        
        evil_obj = EvilObject()
        # Should not raise
        result = safe_json_serialize(evil_obj)
        # Should return valid JSON (might be fallback or circular ref placeholder)
        parsed = json.loads(result)
        # Just verify we got valid JSON back
        assert isinstance(parsed, (dict, str))

    def test_unicode_characters(self):
        """Test unicode characters are preserved (ensure_ascii=False default)."""
        data = {"message": "Hello 世界! 🌍"}
        result = safe_json_serialize(data)
        assert "世界" in result
        assert "🌍" in result

    def test_circular_reference_in_json(self):
        """Test circular references produce valid JSON."""
        circular_dict = {"name": "root"}
        circular_dict["self"] = circular_dict

        result = safe_json_serialize(circular_dict)
        parsed = json.loads(result)
        assert parsed["name"] == "root"
        assert "<circular ref:" in parsed["self"]


class TestIntegrationWithSSE:
    """Integration tests simulating SSE event serialization."""

    def test_tool_call_event(self):
        """Test tool_call event data serialization."""
        event_data = {
            "toolCallId": "tc-123",
            "toolCallName": "web_search",
            "thread_id": "session-456",
            "delta": '{"query": "test search"}',
        }
        result = safe_json_serialize(event_data)
        parsed = json.loads(result)
        assert parsed["toolCallId"] == "tc-123"

    def test_tool_result_with_complex_content(self):
        """Test tool_result event with multimodal content."""
        event_data = {
            "toolCallId": "tc-789",
            "content": [
                {"type": "text", "text": "Analysis complete"},
                {"type": "image", "url": "https://chart.example.com/plot.png"}
            ],
            "is_error": False,
        }
        result = safe_json_serialize(event_data)
        parsed = json.loads(result)
        assert len(parsed["content"]) == 2
        assert parsed["is_error"] is False

    def test_reasoning_event(self):
        """Test reasoning/thinking event serialization."""
        event_data = {
            "messageId": "msg-001",
            "delta": "Let me think about this problem step by step...",
            "role": "assistant",
        }
        result = safe_json_serialize(event_data)
        parsed = json.loads(result)
        assert parsed["delta"].startswith("Let me think")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
