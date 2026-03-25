
import unittest
from backend.app.agent.stream_buffer import StreamBuffer

class TestStreamBuffer(unittest.TestCase):
    def setUp(self):
        self.buffer = StreamBuffer()

    def test_tool_call_buffering(self):
        # 1. Start
        evt, data = self.buffer.process_event("tool_call_start", {
            "toolCallId": "call_1", 
            "toolName": "web_search"
        })
        self.assertIsNone(evt)

        # 2. Args Deltas
        evt, data = self.buffer.process_event("tool_call_args", {"delta": '{"que'})
        self.assertIsNone(evt)
        evt, data = self.buffer.process_event("tool_call_args", {"delta": 'ry": "python"}'})
        self.assertIsNone(evt)

        # 3. End -> Expect Atomic
        evt, data = self.buffer.process_event("tool_call_end", {})
        self.assertEqual(evt, "tool_call")
        self.assertEqual(data["tool_call_id"], "call_1")
        self.assertEqual(data["tool_name"], "web_search")
        self.assertEqual(data["tool_input"], {"query": "python"})

    def test_reasoning_buffering(self):
        # 1. Start
        evt, data = self.buffer.process_event("reasoning_start", {"messageId": "msg_think"})
        self.assertIsNone(evt)

        # 2. Delta
        evt, data = self.buffer.process_event("reasoning_message_content", {"delta": "Thinking..."})
        self.assertIsNone(evt)

        # 3. End
        evt, data = self.buffer.process_event("reasoning_end", {})
        self.assertEqual(evt, "agent_thinking")
        self.assertEqual(data["text"], "Thinking...")

    def test_message_flushing(self):
        # 1. Message chunks
        evt, data = self.buffer.process_event("message_chunk", {"content": "Hello", "id": "msg_1"})
        self.assertIsNone(evt)
        evt, data = self.buffer.process_event("message_chunk", {"content": " World", "id": "msg_1"})
        self.assertIsNone(evt)

        # 2. Flush manually (simulating end of stream or interleaved event)
        flushed = self.buffer.flush()
        self.assertEqual(len(flushed), 1)
        evt, data = flushed[0]
        self.assertEqual(evt, "agent_response")
        self.assertEqual(data["text"], "Hello World")
        self.assertEqual(data["message_id"], "msg_1")

    def test_passthrough(self):
        evt, data = self.buffer.process_event("status", {"type": "info"})
        self.assertEqual(evt, "status")

if __name__ == "__main__":
    unittest.main()
