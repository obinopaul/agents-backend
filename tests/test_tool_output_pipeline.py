"""
Test suite verifying the complete tool output data flow.

Covers the exact ToolMessage formats produced by LangChain tools
and MCP tools (via langchain-mcp-adapters), verifying that:
  1. agent.py extracts .content from ToolMessage objects
  2. MCP content blocks ([{"type":"text","text":"..."}]) are normalized to strings
  3. json_utils.make_serializable handles any ToolMessage that slips through
  4. event_adapter._transform_data produces clean results for the frontend
"""
import json
import unittest
from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage, AIMessage

from backend.src.utils.json_utils import make_serializable, safe_json_serialize
from backend.app.agent.event_adapter import IIAgentWebSocketAdapter


# ═══════════════════════════════════════════════════════════════════
# Helpers — simulate agent.py extraction logic
# ═══════════════════════════════════════════════════════════════════

def extract_tool_output(tool_output):
    """
    Replicates the extraction logic from agent.py on_tool_end handler.
    """
    from langchain_core.messages import ToolMessage, BaseMessage

    # Step 1: Unwrap ToolMessage/BaseMessage to .content
    if isinstance(tool_output, (ToolMessage, BaseMessage)):
        tool_output = tool_output.content
    elif hasattr(tool_output, 'content') and hasattr(tool_output, 'tool_call_id'):
        tool_output = tool_output.content

    # Step 2: Normalize MCP content blocks to plain text
    if isinstance(tool_output, list) and tool_output:
        if all(
            isinstance(b, dict) and b.get("type") in ("text", "image", "file")
            for b in tool_output
        ):
            text_parts = [b["text"] for b in tool_output if b.get("type") == "text" and "text" in b]
            image_blocks = [b for b in tool_output if b.get("type") == "image"]
            if text_parts and not image_blocks:
                tool_output = "\n".join(text_parts) if len(text_parts) > 1 else text_parts[0]

    return tool_output


def simulate_full_pipeline(tool_output):
    """
    Simulate: agent.py extraction → _make_event serialization →
    _forward_sse_event parsing → _transform_data.
    Returns the final dict that goes to the frontend.
    """
    # 1. Agent.py extraction
    extracted = extract_tool_output(tool_output)

    # 2. _make_event serializes data dict
    event_data = {
        "tool_call_id": "test-001",
        "tool_name": "test_tool",
        "tool_display_name": "Test Tool",
        "tool_input": {},
        "result": extracted,
        "is_error": False,
        "thread_id": "thread-001",
    }
    json_data = safe_json_serialize(event_data)
    sse_str = f"event: tool_result\ndata: {json_data}\n\n"

    # 3. _forward_sse_event parses it back
    parsed_data = json.loads(json_data)

    # 4. _transform_data transforms for WebSocket
    ws_type, ws_data = IIAgentWebSocketAdapter.transform("tool_result", parsed_data)

    return ws_type, ws_data


# ═══════════════════════════════════════════════════════════════════
# Test Cases
# ═══════════════════════════════════════════════════════════════════

class TestToolOutputExtraction(unittest.TestCase):
    """Test agent.py extraction logic."""

    def test_plain_string_toolmessage(self):
        """Built-in LangChain tools return ToolMessage with string content."""
        tm = ToolMessage(content="Hello world", tool_call_id="tc-1", name="bash")
        result = extract_tool_output(tm)
        self.assertEqual(result, "Hello world")
        self.assertIsInstance(result, str)

    def test_mcp_single_text_block(self):
        """MCP tools via langchain-mcp-adapters return content block list."""
        tm = ToolMessage(
            content=[{"type": "text", "text": "file contents here", "id": "uuid-1"}],
            tool_call_id="tc-2",
            name="read_file",
        )
        result = extract_tool_output(tm)
        self.assertEqual(result, "file contents here")
        self.assertIsInstance(result, str)

    def test_mcp_multiple_text_blocks(self):
        """MCP tool returning multiple text blocks."""
        tm = ToolMessage(
            content=[
                {"type": "text", "text": "line 1", "id": "uuid-1"},
                {"type": "text", "text": "line 2", "id": "uuid-2"},
            ],
            tool_call_id="tc-3",
            name="bash",
        )
        result = extract_tool_output(tm)
        self.assertEqual(result, "line 1\nline 2")

    def test_mcp_empty_content(self):
        """MCP tool returning empty content."""
        tm = ToolMessage(content="", tool_call_id="tc-4", name="write_file")
        result = extract_tool_output(tm)
        self.assertEqual(result, "")

    def test_mcp_image_blocks_preserved(self):
        """Image blocks should NOT be flattened to text."""
        tm = ToolMessage(
            content=[
                {"type": "image", "source": {"type": "base64", "data": "abc123"}},
            ],
            tool_call_id="tc-5",
            name="screenshot",
        )
        result = extract_tool_output(tm)
        # Image blocks stay as list for downstream image processing
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "image")

    def test_json_string_content(self):
        """Web search tools return JSON string content."""
        json_results = json.dumps([{"title": "Result 1", "url": "http://example.com"}])
        tm = ToolMessage(content=json_results, tool_call_id="tc-6", name="web_search")
        result = extract_tool_output(tm)
        self.assertEqual(result, json_results)
        self.assertIsInstance(result, str)

    def test_plain_string_passthrough(self):
        """Non-ToolMessage strings pass through unchanged."""
        result = extract_tool_output("just a string")
        self.assertEqual(result, "just a string")

    def test_search_results_list_not_content_blocks(self):
        """Lists of search results (no 'type' key) should not be flattened."""
        search_results = [
            {"title": "Result 1", "url": "http://example.com", "snippet": "..."},
            {"title": "Result 2", "url": "http://example2.com", "snippet": "..."},
        ]
        result = extract_tool_output(search_results)
        # These are NOT content blocks — they don't have "type" in ("text","image","file")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)


class TestJsonUtilsSafetyNet(unittest.TestCase):
    """Test json_utils.make_serializable handles ToolMessage objects."""

    def test_toolmessage_extracted_by_serializer(self):
        """If a ToolMessage somehow reaches the serializer, it extracts .content."""
        tm = ToolMessage(content="bash output", tool_call_id="tc-1", name="bash")
        result = make_serializable(tm)
        # Should extract content, not produce full model_dump or circular ref
        self.assertEqual(result, "bash output")

    def test_toolmessage_with_content_blocks(self):
        """Serializer handles ToolMessage with content block list."""
        tm = ToolMessage(
            content=[{"type": "text", "text": "hello", "id": "uuid-1"}],
            tool_call_id="tc-2",
            name="bash",
        )
        result = make_serializable(tm)
        # Content is a list of dicts — serializer extracts .content (the list)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "text")

    def test_no_circular_ref(self):
        """safe_json_serialize never produces '<circular ref:' for ToolMessage."""
        tm = ToolMessage(content="test content", tool_call_id="tc-3", name="bash")
        result_str = safe_json_serialize({"result": tm})
        self.assertNotIn("circular ref", result_str)
        self.assertIn("test content", result_str)


class TestFullPipeline(unittest.TestCase):
    """Test complete data flow: ToolMessage → agent.py → SSE → WebSocket adapter."""

    def test_bash_output(self):
        """Bash tool: ToolMessage with plain string content."""
        tm = ToolMessage(content="hello_world\n", tool_call_id="tc-1", name="bash")
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        self.assertEqual(ws_data["result"], "hello_world\n")
        self.assertNotIn("circular ref", str(ws_data))

    def test_mcp_bash_output(self):
        """MCP bash tool: ToolMessage with content block list."""
        tm = ToolMessage(
            content=[{"type": "text", "text": "hello_world\n", "id": "uuid-1"}],
            tool_call_id="tc-2",
            name="bash",
        )
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        self.assertEqual(ws_data["result"], "hello_world\n")

    def test_mcp_read_file(self):
        """MCP read_file tool: file contents in content block."""
        file_content = "import os\nprint('hello')\n"
        tm = ToolMessage(
            content=[{"type": "text", "text": file_content, "id": "uuid-3"}],
            tool_call_id="tc-3",
            name="read_file",
        )
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        self.assertEqual(ws_data["result"], file_content)

    def test_mcp_write_file_success(self):
        """MCP write_file tool: success message in content block."""
        tm = ToolMessage(
            content=[{"type": "text", "text": "Successfully wrote file /tmp/test.txt", "id": "uuid-4"}],
            tool_call_id="tc-4",
            name="write_file",
        )
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        self.assertIn("Successfully wrote", ws_data["result"])

    def test_web_search_json_results(self):
        """Web search tool returns JSON string content."""
        results = [{"title": "Test", "url": "http://example.com", "content": "..."}]
        tm = ToolMessage(content=json.dumps(results), tool_call_id="tc-5", name="web_search")
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        # Should be a JSON string that the frontend can parse
        parsed = json.loads(ws_data["result"])
        self.assertEqual(parsed[0]["title"], "Test")

    def test_empty_tool_output(self):
        """Tool with empty output."""
        tm = ToolMessage(content="", tool_call_id="tc-6", name="write_file")
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        self.assertEqual(ws_data["result"], "")

    def test_mcp_list_directory(self):
        """MCP list_directory tool with multi-line output."""
        dir_listing = "file1.txt\nfile2.py\nfolder1/\nfolder2/"
        tm = ToolMessage(
            content=[{"type": "text", "text": dir_listing, "id": "uuid-7"}],
            tool_call_id="tc-7",
            name="list_directory",
        )
        ws_type, ws_data = simulate_full_pipeline(tm)
        self.assertEqual(ws_type, "tool_result")
        self.assertIn("file1.txt", ws_data["result"])
        self.assertIn("folder2/", ws_data["result"])

    def test_no_circular_ref_in_final_output(self):
        """Ensure no '<circular ref:' appears anywhere in the pipeline."""
        for content in [
            "simple string",
            [{"type": "text", "text": "block content", "id": "uuid-8"}],
            json.dumps({"key": "value"}),
        ]:
            tm = ToolMessage(content=content, tool_call_id="tc-8", name="test")
            ws_type, ws_data = simulate_full_pipeline(tm)
            result_str = json.dumps(ws_data, default=str)
            self.assertNotIn("circular ref", result_str, f"Circular ref for content={content!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
