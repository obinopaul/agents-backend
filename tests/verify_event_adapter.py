
import sys
import os
import unittest
import json
from uuid import uuid4

# Add the project root to the python path so we can import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.agent.event_adapter import IIAgentWebSocketAdapter, transform_sse_to_websocket

class TestIIAgentWebSocketAdapter(unittest.TestCase):

    def test_transform_agent_response_start(self):
        """Test transforming message_chunk start event (agent_response)"""
        event_type = "message_chunk"
        data = {
            "type": "message_chunk",
            "content": "",
            "id": "msg-123"
        }
        
        # This usually maps to "agent_response" in the adapter
        new_type, new_data = IIAgentWebSocketAdapter.transform(event_type, data)
        
        self.assertEqual(new_type, "agent_response")
        self.assertEqual(new_data["text"], "")
        self.assertEqual(new_data["message_id"], "msg-123")

    def test_transform_agent_response_delta(self):
        """Test transforming message_chunk delta event"""
        event_type = "message_chunk"
        data = {
            "type": "message_chunk",
            "content": "Hello",
            "id": "msg-123"
        }
        
        new_type, new_data = IIAgentWebSocketAdapter.transform(event_type, data)
        
        self.assertEqual(new_type, "agent_response")
        self.assertEqual(new_data["text"], "Hello")
        self.assertEqual(new_data["message_id"], "msg-123")

    def test_transform_tool_call_start(self):
        """Test transforming tool_call_start event (tool_call)"""
        event_type = "tool_call_start"
        data = {
            "type": "tool_call_start",
            "toolCallId": "call_123",
            "toolName": "search_web",
            "toolDisplayName": "Search Web"
        }
        
        # Should map to "tool_call"
        new_type, new_data = IIAgentWebSocketAdapter.transform(event_type, data)
        
        self.assertEqual(new_type, "tool_call")
        self.assertEqual(new_data["status"], "start")
        self.assertEqual(new_data["tool_call_id"], "call_123")
        self.assertEqual(new_data["tool_name"], "search_web")
        self.assertEqual(new_data["tool_display_name"], "Search Web")

    def test_transform_tool_call_delta(self):
        """Test transforming tool_call_args event"""
        event_type = "tool_call_args"
        data = {
            "type": "tool_call_args",
            "toolCallId": "call_123",
            "delta": "{\"query\": \"python\"}"
        }
        
        new_type, new_data = IIAgentWebSocketAdapter.transform(event_type, data)
        
        self.assertEqual(new_type, "tool_call")
        self.assertEqual(new_data["status"], "delta")
        self.assertEqual(new_data["tool_call_id"], "call_123")
        self.assertEqual(new_data["tool_input"], "{\"query\": \"python\"}")

    def test_transform_tool_result(self):
        """Test transforming tool_result event"""
        event_type = "tool_result"
        data = {
            "type": "tool_result",
            "toolCallId": "call_123",
            "toolName": "search_web",
            "content": "Search results...",
            "is_error": False
        }
        
        new_type, new_data = IIAgentWebSocketAdapter.transform(event_type, data)
        
        self.assertEqual(new_type, "tool_result")
        self.assertEqual(new_data["tool_call_id"], "call_123")
        self.assertEqual(new_data["tool_name"], "search_web")
        self.assertEqual(new_data["result"], "Search results...")
        self.assertEqual(new_data["is_error"], False)

    def test_transform_sse_string(self):
        """Test complete SSE string transformation via transform_sse_to_websocket"""
        sse_string = 'event: message_chunk\ndata: {"content": "Hello", "id": "1", "type": "message_chunk"}\n\n'
        
        new_type, new_data = transform_sse_to_websocket(sse_string)
        
        self.assertEqual(new_type, "agent_response")
        self.assertEqual(new_data["text"], "Hello")

    def test_transform_sse_string_tool(self):
        """Test complete SSE string transformation for tool"""
        # Note: double escaping for JSON string inside JSON string if needed, but here it's simple
        sse_string = 'event: tool_call_start\ndata: {"toolCallId": "123", "toolName": "foo", "toolDisplayName": "Foo", "type": "tool_call_start"}\n\n'
        
        new_type, new_data = transform_sse_to_websocket(sse_string)
        
        self.assertEqual(new_type, "tool_call")
        self.assertEqual(new_data["tool_name"], "foo")
        self.assertEqual(new_data["status"], "start")

if __name__ == '__main__':
    unittest.main()
