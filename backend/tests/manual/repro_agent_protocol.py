import json
import uuid
import sys
import os
from typing import Any, Dict

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.app.agent.event_adapter import IIAgentSSEAdapter
from backend.src.utils.json_utils import safe_json_serialize
from backend.app.agent.models import ToolCall

def test_tool_call_protocol():
    # Write output to file to avoid Windows console encoding issues
    output_file = os.path.join(os.path.dirname(__file__), '.txt')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        def log(msg):
            print(msg)
            f.write(msg + "\n")
            
        log("\n--- Testing Agent Protocol Compliance ---")
        
        # Simulate a session
        adapter = IIAgentSSEAdapter(session_id="test-session-123")
        tool_run_id = str(uuid.uuid4())
        tool_name = "web_search"
        tool_input = {"query": "agent streaming protocol"}
        
        log(f"\n[1] Tool Call Start (id={tool_run_id})")
        # Simulate agent.py logic
        start_event = adapter.tool_call_start(tool_run_id, tool_name)
        log(f"Generated SSE:\n{start_event.strip()}")
        
        log(f"\n[2] Tool Call Delta (Streaming Args)")
        # Simulate agent.py logic: args_str = _safe_json_serialize(tool_input)
        args_str = safe_json_serialize(tool_input)
        log(f"Serialized Input: {args_str}")
        delta_event = adapter.tool_call_delta(tool_run_id, args_str)
        log(f"Generated SSE:\n{delta_event.strip()}")
        
        log(f"\n[3] Tool Call Stop (Complete Input)")
        # Simulate agent.py logic
        stop_event = adapter.tool_call_stop(tool_run_id, tool_name, args_str)
        log(f"Generated SSE:\n{stop_event.strip()}")
        
        log(f"\n[4] Tool Result")
        tool_output = ["Result 1", "Result 2"]
        result_event = adapter.tool_result(tool_run_id, tool_name, tool_output)
        log(f"Generated SSE:\n{result_event.strip()}")
        
        log("\n--- Protocol Verification ---")
        
        # Parse SSE to verify structure
        def parse_sse(sse_str):
            lines = sse_str.strip().split('\n')
            event_type = lines[0].split(': ')[1]
            data_str = lines[1].split(': ', 1)[1]
            return event_type, json.loads(data_str)

        # Check match with II-Agent Protocol
        # Event: tool_call -> data: {status: start, ...}
        t1, d1 = parse_sse(start_event)
        assert t1 == "tool_call"
        assert d1["status"] == "start"
        assert d1["type"] == "function"
        log("✅ Start event matches protocol")

        # Event: tool_call -> data: {status: delta, ...}
        t2, d2 = parse_sse(delta_event)
        assert t2 == "tool_call"
        assert d2["status"] == "delta"
        assert "delta" in d2
        log("✅ Delta event matches protocol")

        # Event: tool_call -> data: {status: stop, ...}
        t3, d3 = parse_sse(stop_event)
        assert t3 == "tool_call"
        assert d3["status"] == "stop"
        assert "input" in d3
        log("✅ Stop event matches protocol")

        log("\n--- Serialization Robustness Test ---")
        try:
            # Simulate a non-serializable object (like ToolMessage logic before fix)
            class ComplexObj:
                def __init__(self):
                    self.circular = self
                    self.name = "MyComplexObject"
                def __repr__(self):
                    return "<ComplexObject>"
                    
            bad_input = {"key": ComplexObj(), "val": "test"}
            log("Attempting to serialize complex object...")
            safe_str = safe_json_serialize(bad_input)
            log(f"Safe Serialization Result: {safe_str}")
            
            # Verify it doesn't crash event generation
            bad_delta = adapter.tool_call_delta(tool_run_id, safe_str)
            log(f"Generated Safe SSE:\n{bad_delta.strip()}")
            log("✅ Serialization robustness confirmed")
            
        except Exception as e:
            log(f"❌ Serialization Failed: {e}")

if __name__ == "__main__":
    test_tool_call_protocol()
