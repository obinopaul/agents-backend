# Frontend-Backend Chat Integration

## Overview

This document describes the implementation of the event adapter layer that transforms AG-UI Protocol events from the backend to II-Agent frontend format. This enables seamless communication between the LangChain/LangGraph backend and the React/TypeScript frontend.

## Implementation Date

January 25, 2026

## Problem Statement

The backend uses the AG-UI Protocol for streaming events while the frontend expects II-Agent SSE/WebSocket event formats. The key challenge was to transform AG-UI protocol events to match II-Agent frontend expectations without breaking backward compatibility.

---

## Files Created/Modified

### New File

| File | Description |
|------|-------------|
| `backend/app/agent/event_adapter.py` | Event adapter classes for SSE and WebSocket transformation |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/agent/api/v1/chat.py` | Updated `_astream_workflow_generator` and `_process_message_chunk` to emit II-Agent format events |
| `backend/app/agent/api/v1/agent.py` | Updated `_agent_stream_generator` to emit II-Agent format events |
| `backend/common/socketio/command/query_handler.py` | Updated `_forward_sse_event` to use WebSocket adapter |

---

## Event Protocol Mapping

### SSE Events (Chat Mode) - Backend to Frontend

| AG-UI Backend | II-Agent Frontend | Transformation |
|---------------|-------------------|----------------|
| N/A | `session` | **ADD**: Emit on session creation |
| `message_chunk` | `content` (status: delta) | **RENAME** + restructure |
| N/A | `content` (status: start) | **ADD**: Emit before first chunk |
| `reasoning_*` (5 events) | `thinking` (status: delta) | **SIMPLIFY**: Merge to single event |
| `tool_call_start` | `tool_call` (status: start) | **RENAME** + restructure fields |
| `tool_call_args` | `tool_call` (status: delta) | **RENAME** + restructure |
| `tool_call_end` | `tool_call` (status: stop) | **RENAME** + restructure |
| `tool_result` | `tool_result` (status: info) | **RENAME** + add `status` field |
| N/A | `usage` | **ADD**: Track token usage |
| N/A | `complete` (status: done) | **ADD**: Emit on stream end |
| `error` | `error` | Compatible (minor restructure) |

### WebSocket Events (Agent Mode) - Backend to Frontend

| AG-UI Backend | II-Agent Frontend | Transformation |
|---------------|-------------------|----------------|
| `message_chunk` | `agent_response` | **RENAME** |
| `reasoning_*` | `agent_thinking` | **SIMPLIFY** |
| `tool_call_start/args/end` | `tool_call` | **MERGE** lifecycle events |
| `tool_result` | `tool_result` | **COMPATIBLE** |
| `status` (type: processing) | `status_update` | **RENAME** |
| `error` | `error` | **COMPATIBLE** |
| N/A | `complete` | **ADD** |

---

## Event Adapter Classes

### IIAgentSSEAdapter

Located in `backend/app/agent/event_adapter.py`, this class transforms AG-UI events to II-Agent SSE format.

**Key Methods:**

```python
class IIAgentSSEAdapter:
    def session_event(is_new: bool) -> str        # Emit session start
    def content_start() -> str                     # Emit before first text chunk
    def content_delta(delta: str) -> str           # Emit text chunk
    def content_stop() -> str                      # Emit text completion
    def thinking_start() -> str                    # Emit reasoning start
    def thinking_delta(delta: str) -> str          # Emit reasoning chunk
    def thinking_stop() -> str                     # Emit reasoning end
    def tool_call_start(id, name) -> str           # Emit tool call start
    def tool_call_delta(id, delta) -> str          # Emit tool args chunk
    def tool_call_stop(id, name, input) -> str     # Emit tool call end
    def tool_result(id, name, output) -> str       # Emit tool result
    def usage(input_tokens, output_tokens) -> str  # Emit token usage
    def complete(finish_reason) -> str             # Emit stream completion
    def error(message, code) -> str                # Emit error
    def transform_ag_ui_event(type, data) -> str   # Auto-transform AG-UI event
```

### IIAgentWebSocketAdapter

Static class for WebSocket event transformation.

**Key Methods:**

```python
class IIAgentWebSocketAdapter:
    @classmethod
    def transform(ag_ui_event_type: str, data: dict) -> Tuple[str, dict]
        # Returns (new_event_type, transformed_data)
```

---

## Event Formats

### II-Agent SSE Event Format

```
event: <event_type>
data: {"status": "<status>", ...payload}

```

**Event Types and Payloads:**

```json
// Session start
{"status": "created", "session_id": "uuid", "model_id": "model"}

// Content streaming
{"status": "start", "message_id": "uuid"}
{"status": "delta", "delta": "text chunk", "message_id": "uuid"}
{"status": "stop", "message_id": "uuid"}

// Thinking/reasoning
{"status": "start", "thinking_id": "uuid"}
{"status": "delta", "delta": "reasoning text", "thinking_id": "uuid"}
{"status": "stop", "thinking_id": "uuid"}

// Tool calls
{"status": "start", "id": "tool_id", "name": "tool_name", "type": "function"}
{"status": "delta", "id": "tool_id", "delta": "{\"arg\": \"value\"}"}
{"status": "stop", "id": "tool_id", "name": "tool_name", "input": "{...}"}

// Tool results
{"status": "info", "tool_call_id": "id", "name": "tool", "output": "result"}

// Usage statistics
{"status": "info", "input_tokens": 100, "output_tokens": 50, "total_tokens": 150}

// Completion
{"status": "done", "message_id": "uuid", "finish_reason": "end_turn", "elapsed_ms": 1234}

// Error
{"status": "error", "error": "message", "code": "error_code"}
```

### II-Agent WebSocket Event Format

```javascript
// Agent response (text)
socket.emit('agent_response', { text: "response text", message_id: "uuid" })

// Agent thinking
socket.emit('agent_thinking', { status: "start|delta|stop", text: "thinking" })

// Tool call
socket.emit('tool_call', {
  status: "start|delta|stop",
  tool_name: "name",
  tool_call_id: "id",
  tool_input: "args"
})

// Tool result
socket.emit('tool_result', {
  tool_call_id: "id",
  tool_name: "name",
  result: "output",
  is_error: false
})

// Status update
socket.emit('status_update', { status_type: "processing", message: "..." })

// Completion
socket.emit('complete', { status: "done", finish_reason: "end_turn" })
```

---

## Backward Compatibility

The implementation maintains full backward compatibility:

1. **Both formats emitted**: All endpoints emit both II-Agent format events AND original AG-UI events
2. **No breaking changes**: Existing clients using AG-UI events continue to work
3. **Gradual migration**: Frontend can migrate to new event format incrementally

---

## Usage Examples

### SSE Endpoint (chat.py)

```python
from backend.app.agent.event_adapter import create_sse_adapter

async def _astream_workflow_generator(...):
    # Create adapter
    adapter = create_sse_adapter(session_id=thread_id, model_id=model_id)

    # Emit session event at start
    yield adapter.session_event(is_new=True)

    # Stream content
    for chunk in chunks:
        if not adapter.content_started:
            yield adapter.content_start()
        yield adapter.content_delta(chunk.text)

    # Complete
    yield adapter.complete(finish_reason="end_turn")
```

### WebSocket Handler (query_handler.py)

```python
from backend.app.agent.event_adapter import IIAgentWebSocketAdapter

async def _forward_sse_event(self, session_uuid, event_str, run_id):
    # Parse SSE
    event_type, data = parse_sse(event_str)

    # Transform to WebSocket format
    ws_type, ws_data = IIAgentWebSocketAdapter.transform(event_type, data)

    # Emit transformed event
    await self.broadcast_to_session(session_uuid, ws_type, ws_data, run_id)
```

---

## Testing

### Manual Testing Checklist

1. [ ] New chat session shows in UI
2. [ ] Text streaming appears character by character
3. [ ] Thinking/reasoning displays correctly
4. [ ] Tool calls show name and arguments
5. [ ] Tool results display
6. [ ] Token usage shows (if UI supports)
7. [ ] Stream completion works
8. [ ] Errors display correctly
9. [ ] WebSocket reconnection works
10. [ ] Agent sandbox initialization works

### Verification Commands

```bash
# Start backend
cd backend && python -m uvicorn main:app --reload

# Start frontend
cd frontend && npm run dev

# Enable Socket.IO debug in browser console
localStorage.debug = '*'
```

---

## Architecture Diagram

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│                 │     │                      │     │                 │
│  LangGraph      │────▶│  Event Adapter       │────▶│  II-Agent       │
│  (AG-UI Events) │     │  (event_adapter.py)  │     │  Frontend       │
│                 │     │                      │     │                 │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
        │                         │                          │
        │                         │                          │
        ▼                         ▼                          ▼
   AG-UI Events:            Transformation:            II-Agent Events:
   - message_chunk          IIAgentSSEAdapter          - session
   - reasoning_*            IIAgentWebSocketAdapter    - content
   - tool_call_*                                       - thinking
   - tool_result                                       - tool_call
   - error                                             - tool_result
                                                       - usage
                                                       - complete
                                                       - error
```

---

## Future Enhancements

1. **HITL Support**: Add Human-in-the-Loop interrupt handling in frontend
2. **Token Usage Display**: Frontend component for usage statistics
3. **Streaming Tool Arguments**: Currently accumulated; could stream incrementally
4. **Error Recovery UI**: Better error handling and retry in frontend
5. **Metrics Dashboard**: Real-time monitoring of event throughput
