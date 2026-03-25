
import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.agent.event_adapter import IIAgentWebSocketAdapter

async def simulate_stream_generator():
    """
    Generator that mimics the SSE stream from agent.py
    with interleaved tool calls and reasoning.
    """
    events = [
        # 1. Start Tool Call (should be buffered)
        'event: tool_call_start',
        'data: {"toolCallId": "call_123", "toolName": "web_search", "run_id": "run_1"}',
        
        # 2. Tool Args (should be buffered)
        'event: tool_call_args',
        'data: {"delta": "{\\"qu", "run_id": "run_1"}',
        'event: tool_call_args',
        'data: {"delta": "ery\\": \\"python\\"}", "run_id": "run_1"}',
        
        # 3. Tool End (should trigger ATOMIC emit)
        'event: tool_call_end',
        'data: {"toolCallId": "call_123", "run_id": "run_1"}',

        # 4. Thinking Start (should be buffered)
        'event: reasoning_start',
        'data: {"messageId": "msg_think_1", "run_id": "run_1"}',
        
        # 5. Thinking Content (should be buffered)
        'event: reasoning_message_content',
        'data: {"delta": "I need to ", "run_id": "run_1"}',
        'event: reasoning_message_content',
        'data: {"delta": "search for python.", "run_id": "run_1"}',
        
        # 6. Thinking End (should trigger ATOMIC emit)
        'event: reasoning_end',
        'data: {"messageId": "msg_think_1", "run_id": "run_1"}',
        
        # 7. Message text (should be buffered)
        'event: message_chunk',
        'data: {"content": "Here is ", "id": "msg_final", "run_id": "run_1"}',
        'event: message_chunk',
        'data: {"content": "the result.", "id": "msg_final", "run_id": "run_1"}',
        
        # 8. Complete (should flush message)
        'event: complete',
        'data: {"status": "success", "run_id": "run_1"}',
    ]
    
    for evt in events:
        yield evt
        await asyncio.sleep(0.01)

async def main():
    print(f"\n[Simulation] Starting simulation...")
    
    # Instantiate stateful adapter
    adapter = IIAgentWebSocketAdapter()

    # Simulate SSE stream
    async for line in simulate_stream_generator():
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:") and locals().get('current_event'):
            data_str = line[5:].strip()
            try:
                data = json.loads(data_str)
                # print(f"\n[SSE In]: event: {current_event}")
                
                # Transform using stateful adapter
                ws_type, ws_data = adapter.process_event(current_event, data)
                
                if ws_type:
                    print(f"\n[WS Out]: Type='{ws_type}'")
                    print(f"          Data={json.dumps(ws_data, indent=2)}")
                else:
                    # print(f"[WS Out]: (Buffered)")
                    pass
                    
            except json.JSONDecodeError:
                pass
            current_event = None

    # Flush at end
    print("\n[Simulation] End of stream - Flushing buffer...")
    flushed = adapter.buffer.flush()
    for f_type, f_data in flushed:
        print(f"\n[WS Out]: Type='{f_type}' (Flushed)")
        print(f"          Data={json.dumps(f_data, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())
