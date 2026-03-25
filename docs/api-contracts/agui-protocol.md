# AG-UI Protocol API Contract

> Technical specification for AG-UI Protocol events in the streaming API.

---

## Overview

The AG-UI (Agent-User Interface) Protocol defines a standardized format for streaming events between the backend and frontend. This document specifies the exact event formats, payloads, and lifecycle for all AG-UI protocol events.

---

## Endpoints

| Endpoint | Method | Content-Type | Description |
|----------|--------|--------------|-------------|
| `/agent/chat/stream` | POST | `text/event-stream` | Chat streaming with tools |
| `/agent/agent/stream` | POST | `text/event-stream` | Agent streaming with sandbox |

### Request Format

```typescript
interface StreamRequest {
  messages: Message[];
  thread_id?: string;
  agent_id?: string;
  model_id?: string;
  enable_deep_thinking?: boolean;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string | ContentBlock[];
}

interface ContentBlock {
  type: 'text' | 'image' | 'audio' | 'file';
  // For text
  text?: string;
  // For image
  url?: string;
  data?: string;  // base64
  mime_type?: string;
}
```

### Response Format (SSE)

```
event: <event_type>
data: <json_payload>

event: <event_type>
data: <json_payload>
...
```

---

## Event Types

### Tool Call Events

#### `tool_call_start`

Emitted when a tool call begins.

```typescript
interface ToolCallStartEvent {
  toolCallId: string;
  toolCallName: string;
  thread_id?: string;
  agent?: string;
}
```

**Example:**
```
event: tool_call_start
data: {"toolCallId": "call_abc123", "toolCallName": "web_search", "thread_id": "thread_1"}
```

#### `tool_call_args`

Emitted as tool arguments stream in.

```typescript
interface ToolCallArgsEvent {
  toolCallId: string;
  delta: string;
  thread_id?: string;
}
```

**Example:**
```
event: tool_call_args
data: {"toolCallId": "call_abc123", "delta": "{\"query\": \"weather"}
```

#### `tool_call_end`

Emitted when tool call arguments are complete.

```typescript
interface ToolCallEndEvent {
  toolCallId: string;
  thread_id?: string;
}
```

**Example:**
```
event: tool_call_end
data: {"toolCallId": "call_abc123"}
```

#### `tool_result`

Emitted when tool execution returns a result.

```typescript
interface ToolResultEvent {
  toolCallId: string;
  content: string;
  role: 'tool';
  thread_id?: string;
}
```

**Example:**
```
event: tool_result
data: {"toolCallId": "call_abc123", "content": "The weather in Tokyo is...", "role": "tool"}
```

---

### Reasoning Events

#### `reasoning_start`

Emitted when the model begins a reasoning session.

```typescript
interface ReasoningStartEvent {
  messageId: string;
  thread_id?: string;
}
```

**Example:**
```
event: reasoning_start
data: {"messageId": "reasoning-abc123"}
```

#### `reasoning_message_start`

Emitted when a reasoning message begins.

```typescript
interface ReasoningMessageStartEvent {
  messageId: string;
  role: 'assistant';
  thread_id?: string;
}
```

**Example:**
```
event: reasoning_message_start
data: {"messageId": "reasoning-abc123", "role": "assistant"}
```

#### `reasoning_message_content`

Emitted as reasoning content streams in.

```typescript
interface ReasoningMessageContentEvent {
  messageId: string;
  delta: string;
  thread_id?: string;
}
```

**Example:**
```
event: reasoning_message_content
data: {"messageId": "reasoning-abc123", "delta": "Let me analyze this step by step..."}
```

#### `reasoning_message_end`

Emitted when a reasoning message is complete.

```typescript
interface ReasoningMessageEndEvent {
  messageId: string;
  thread_id?: string;
}
```

**Example:**
```
event: reasoning_message_end
data: {"messageId": "reasoning-abc123"}
```

#### `reasoning_end`

Emitted when the reasoning session is complete.

```typescript
interface ReasoningEndEvent {
  messageId: string;
  thread_id?: string;
}
```

**Example:**
```
event: reasoning_end
data: {"messageId": "reasoning-abc123"}
```

---

### Message Events

#### `message`

Standard text content chunk.

```typescript
interface MessageEvent {
  content: string;
  thread_id?: string;
  agent?: string;
}
```

**Example:**
```
event: message
data: {"content": "Here is the weather information...", "thread_id": "thread_1"}
```

#### `status`

Status updates (start, complete, etc.).

```typescript
interface StatusEvent {
  type: 'start' | 'running' | 'complete' | 'error';
  message?: string;
  thread_id?: string;
}
```

**Example:**
```
event: status
data: {"type": "complete", "thread_id": "thread_1"}
```

#### `error`

Error events.

```typescript
interface ErrorEvent {
  type: 'error';
  message: string;
  code?: string;
  thread_id?: string;
}
```

**Example:**
```
event: error
data: {"type": "error", "message": "Rate limit exceeded", "code": "RATE_LIMIT"}
```

---

## Event Ordering

### Tool Call Lifecycle

```
1. tool_call_start    (once)
2. tool_call_args     (one or more)
3. tool_call_end      (once)
4. tool_result        (once, after tool execution)
```

### Reasoning Lifecycle

```
1. reasoning_start           (once per session)
2. reasoning_message_start   (once per message)
3. reasoning_message_content (one or more)
4. reasoning_message_end     (once per message)
5. reasoning_end             (once per session)
```

### Concurrent Events

Multiple tool calls and reasoning can occur in the same stream. Use `toolCallId` and `messageId` to correlate events:

```
event: reasoning_start
data: {"messageId": "reasoning-1"}

event: tool_call_start
data: {"toolCallId": "call_1", "toolCallName": "search"}

event: reasoning_message_content
data: {"messageId": "reasoning-1", "delta": "I'll search for..."}

event: tool_call_args
data: {"toolCallId": "call_1", "delta": "{\"query\": \"test\"}"}

event: reasoning_message_end
data: {"messageId": "reasoning-1"}

event: tool_call_end
data: {"toolCallId": "call_1"}

event: reasoning_end
data: {"messageId": "reasoning-1"}

event: tool_result
data: {"toolCallId": "call_1", "content": "..."}
```

---

## Content Block Formats

### Text Block

```json
{
  "type": "text",
  "text": "Your text content here"
}
```

### Image Block (URL)

```json
{
  "type": "image",
  "url": "https://example.com/image.jpg"
}
```

### Image Block (Base64)

```json
{
  "type": "image",
  "data": "iVBORw0KGgoAAAANSUhEUgAAAAE...",
  "mime_type": "image/png"
}
```

### Reasoning Block

Automatically extracted from model output when present:

```json
{
  "type": "reasoning",
  "reasoning": "Let me think about this..."
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Stream started successfully |
| 400 | Invalid request format |
| 401 | Authentication required |
| 403 | Access denied |
| 500 | Internal server error |

### Stream Error Events

When an error occurs during streaming, an error event is sent:

```
event: error
data: {"type": "error", "message": "Tool execution failed", "code": "TOOL_ERROR"}
```

### Recovery

The stream may continue after recoverable errors. Fatal errors will close the connection.

---

## Backend Implementation Reference

### Key Files

| File | Description |
|------|-------------|
| `backend/app/agent/models.py` | Pydantic models for AG-UI events |
| `backend/app/agent/api/v1/agent.py` | Agent streaming endpoint |
| `backend/app/agent/api/v1/chat.py` | Chat streaming endpoint |

### Model Classes

```python
# Import from backend.app.agent.models
from backend.app.agent.models import (
    ToolCall,          # Tool call model with AG-UI methods
    ToolResult,        # Tool result model
    ReasoningState,    # Reasoning session tracker
    ToolCallState,     # Tool call lifecycle tracker
    AgentMessage,      # Message with content blocks
    TextBlock,         # Text content block
    ImageBlock,        # Image content block
    make_ag_ui_event,  # Helper to create events
)
```

### Event Generation

```python
# Tool events
tool_call = ToolCall(tool_call_id="call_1", tool_name="search", tool_input={})
yield make_ag_ui_event("tool_call_start", tool_call.to_ag_ui_start_event())
yield make_ag_ui_event("tool_call_args", tool_call.to_ag_ui_args_event(json.dumps(args)))
yield make_ag_ui_event("tool_call_end", tool_call.to_ag_ui_end_event())

# Tool result
result = ToolResult(tool_call_id="call_1", tool_name="search", output="...")
yield make_ag_ui_event("tool_result", result.to_ag_ui_event())

# Reasoning events
reasoning_state = ReasoningState()
msg_id = reasoning_state.start_reasoning()
yield make_ag_ui_event("reasoning_start", {"messageId": msg_id})
yield make_ag_ui_event("reasoning_message_start", {"messageId": msg_id, "role": "assistant"})
yield make_ag_ui_event("reasoning_message_content", {"messageId": msg_id, "delta": content})
yield make_ag_ui_event("reasoning_message_end", {"messageId": msg_id})
yield make_ag_ui_event("reasoning_end", {"messageId": msg_id})
```

---

## Related API Contracts

- [Agent API](./agent-api.md)
- [Sandbox Server](./sandbox-server.md)
- [Tool Server](./tool-server.md)
