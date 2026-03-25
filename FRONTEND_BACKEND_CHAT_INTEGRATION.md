# Frontend-to-Backend Chat System Integration Documentation

**II-Agent Chat System - Complete Reference**

This document provides a comprehensive mapping of the II-Agent chat system, showing how the TypeScript frontend communicates with the Python backend via Server-Sent Events (SSE). Every event type, content part, and tool is documented with code snippets from both sides.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Event Type System - Complete Mapping](#2-event-type-system---complete-mapping)
3. [Content Part Types](#3-content-part-types)
4. [SSE Connection & Parsing](#4-sse-connection--parsing)
5. [Authentication Flow](#5-authentication-flow)
6. [Tool System Deep Dive](#6-tool-system-deep-dive)
7. [Message Lifecycle & State Management](#7-message-lifecycle--state-management)
8. [Error Handling & Finish Reasons](#8-error-handling--finish-reasons)
9. [Advanced Features](#9-advanced-features)
10. [Code Examples & Reference Tables](#10-code-examples--reference-tables)
11. [File Reference Index](#11-file-reference-index)
12. [Common Debugging Scenarios](#12-common-debugging-scenarios)

---

## 1. Architecture Overview

### 1.1 Communication Protocol

**Transport:** HTTP with Server-Sent Events (SSE) - **NOT WebSocket**

The system uses standard HTTP POST requests with streaming responses via SSE. This provides:
- Unidirectional server-to-client streaming
- Automatic reconnection support
- Standard HTTP infrastructure compatibility
- Simple authentication via headers

### 1.2 Technology Stack

| Layer | Frontend | Backend |
|-------|----------|---------|
| Language | TypeScript | Python 3.11+ |
| Framework | React 18 | FastAPI |
| State Management | Redux Toolkit | SQLAlchemy (async) |
| HTTP Client | fetch() API | httpx |
| Database | - | PostgreSQL |
| LLM Providers | - | Anthropic, OpenAI, Google Gemini |

### 1.3 Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/TypeScript)                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User Input → ChatService.streamQuery()                            │
│       │                                                             │
│       ├─ Construct ChatQueryPayload                                │
│       ├─ Add JWT Bearer Token                                      │
│       └─ fetch() with Accept: text/event-stream                    │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP POST /v1/chat/conversations
                             │ Content-Type: application/json
                             │ Authorization: Bearer {JWT}
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI/Python)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  router.send_chat_message()                                        │
│       │                                                             │
│       ├─ Verify JWT Token (deps.CurrentUser)                       │
│       ├─ Validate ChatMessageRequest                               │
│       ├─ Create/Get Session                                        │
│       └─ Return StreamingResponse                                  │
│                  │                                                  │
│                  ├─ ChatService.stream_chat_response()             │
│                  │      │                                           │
│                  │      ├─ LLM Provider.stream()                   │
│                  │      ├─ Yield RunResponseEvent objects          │
│                  │      ├─ Execute tools if finish_reason=tool_use │
│                  │      └─ Save messages to DB                     │
│                  │                                                  │
│                  └─ Format as SSE: event: X\ndata: {...}\n\n       │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │ SSE Stream
                             │ text/event-stream
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Stream Processing)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  response.body.getReader()                                         │
│       │                                                             │
│       ├─ Buffer accumulation                                       │
│       ├─ parseSSEBlock() - Extract event & data                    │
│       ├─ normalizeStreamEvent() - Convert to ChatStreamEvent       │
│       └─ onEvent() callback                                        │
│                  │                                                  │
│                  └─ use-chat-transport.tsx                         │
│                         │                                           │
│                         ├─ Handle event (switch statement)          │
│                         ├─ Redux dispatch                           │
│                         └─ UI update                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.4 Key API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/conversations` | POST | Send message, start SSE stream |
| `/v1/chat/conversations/{id}` | GET | Get message history |
| `/v1/chat/conversations/{id}/public` | GET | Public session access (no auth) |
| `/v1/chat/conversations/{id}/stop` | POST | Stop/cancel conversation |
| `/chat/{session_id}/files/{file_id}` | GET | Download file attachment |

---

## 2. Event Type System - Complete Mapping

The system defines **12 ChatStreamEvent types** that flow from backend to frontend via SSE.

### Event Type Overview Table

| Event Type | Frontend Type | Backend EventType | Purpose | Frequency |
|------------|---------------|-------------------|---------|-----------|
| `session` | `'session'` | N/A (router-level) | Session initialization | Once per new session |
| `content_start` | `'content_start'` | `CONTENT_START` | Text streaming begins | Once per message |
| `token` | `'token'` | `CONTENT_DELTA` | Text content chunk | Multiple (streaming) |
| `thinking` | `'thinking'` | `THINKING_DELTA` | Reasoning/thinking | Multiple (o1, Claude) |
| `tool_call_start` | `'tool_call_start'` | `TOOL_USE_START` | Tool invocation start | Once per tool |
| `tool_call_delta` | `'tool_call_delta'` | `TOOL_USE_DELTA` | Tool input streaming | Multiple per tool |
| `tool_call_stop` | `'tool_call_stop'` | `TOOL_USE_STOP` | Tool invocation complete | Once per tool |
| `tool_result` | `'tool_result'` | `TOOL_RESULT` | Tool execution result | Once per tool |
| `usage` | `'usage'` | N/A (router-level) | Token usage stats | Once per LLM turn |
| `complete` | `'complete'` | N/A (router-level) | Message complete | Once per message |
| `done` | `'done'` | N/A (marker) | Stream termination | Once per stream |
| `error` | `'error'` | `ERROR` | Error occurred | As needed |

---

### 2.1 Event: `session`

**Purpose:** Notifies frontend of session creation or connection. Only sent for new sessions.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:15-22`

```typescript
export type ChatStreamEvent =
    | {
          type: 'session'
          session_id: string
          is_new_session?: boolean
          name?: string
          agent_type?: string
          model_id?: string
          created_at?: string
      }
    // ... other event types
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:271-297`

```python
async def event_generator():
    try:
        # Yield session event for new sessions
        if is_new_session:
            session_event = {
                "status": "created",
                "session_id": str(session_metadata.session_id),
                "name": session_metadata.name,
                "agent_type": session_metadata.agent_type,
                "model_id": session_metadata.model_id,
                "created_at": session_metadata.created_at,
            }
            yield f"event: session\ndata: {json.dumps(session_event)}\n\n"
```

#### SSE Wire Format
```
event: session
data: {"status":"created","session_id":"550e8400-e29b-41d4-a716-446655440000","name":"Hello world","agent_type":"chat","model_id":"claude-3-5-sonnet-20241022","created_at":"2025-01-24T10:30:00.000Z"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:189-204`

```typescript
// Handle session event
if (eventName === 'session') {
    const status = readString(record, 'status')
    const sessionId = readString(record, 'session_id')
    if (sessionId) {
        events.push({
            type: 'session',
            session_id: sessionId,
            is_new_session: status === 'created',
            name: readString(record, 'name'),
            agent_type: readString(record, 'agent_type'),
            model_id: readString(record, 'model_id'),
            created_at: readString(record, 'created_at')
        })
    }
    return events
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:170-191`

```typescript
onEvent: (event: ChatStreamEvent) => {
    switch (event.type) {
        case 'session': {
            // Update active session in Redux
            dispatch(setActiveSessionId(event.session_id))

            // Call user callback if provided
            callbacks?.onSession?.({
                sessionId: event.session_id,
                isNewSession: event.is_new_session,
                name: event.name,
                modelId: event.model_id
            })
            break
        }
        // ... other cases
    }
}
```

**When Emitted:**
- Only when a new session is created (no `session_id` in request)
- First event in the stream for new conversations

**Common Use Cases:**
- Update URL with new session ID
- Initialize session-specific state
- Track analytics for new conversations

---

### 2.2 Event: `content_start`

**Purpose:** Signals that text content streaming is about to begin. Allows UI to prepare for token display.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:24-25`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'content_start'
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/models.py:561`

```python
class EventType(str, Enum):
    """Granular event types for streaming."""

    CONTENT_START = "content_start"
    # ...
```

**Backend Event Emission:**
**File:** `src/ii_agent/server/chat/router.py:300-307`

```python
# Convert EventType to SSE format
if event.get("type") == "content_start":
    content_event = {"status": "start"}
    yield f"event: content\ndata: {json.dumps(content_event)}\n\n"
```

#### SSE Wire Format
```
event: content
data: {"status":"start"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:223-236`

```typescript
// Handle content event
if (eventName === 'content') {
    const status = readString(record, 'status')
    if (status === 'start') {
        events.push({ type: 'content_start' })
    } else if (status === 'delta') {
        const delta = readString(record, 'delta')
        if (delta) {
            events.push({ type: 'token', content: delta })
        }
    }
    // Ignore 'stop' status
    return events
}
```

**When Emitted:**
- At the very beginning of LLM text response
- Before the first `token` event
- Once per assistant message

**Common Use Cases:**
- Show typing indicator
- Initialize content accumulator
- Start animation/UI transitions

---

### 2.3 Event: `token`

**Purpose:** Streams individual text chunks (deltas) from the LLM response. This is the primary content delivery mechanism.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:27-29`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'token'
          content: string
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/models.py:562` & `router.py:300-307`

```python
# EventType enum
class EventType(str, Enum):
    CONTENT_DELTA = "content_delta"
    # ...

# Router SSE formatting
if event.get("type") == "content_delta":
    content_event = {
        "status": "delta",
        "delta": event.get("content")
    }
    yield f"event: content\ndata: {json.dumps(content_event)}\n\n"
```

#### SSE Wire Format
```
event: content
data: {"status":"delta","delta":"Hello"}

event: content
data: {"status":"delta","delta":" world"}

event: content
data: {"status":"delta","delta":"!"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:228-233`

```typescript
if (eventName === 'content') {
    const status = readString(record, 'status')
    // ...
    else if (status === 'delta') {
        const delta = readString(record, 'delta')
        if (delta) {
            events.push({ type: 'token', content: delta })
        }
    }
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:199-203`

```typescript
case 'token': {
    // Append to message content
    callbacks?.onToken?.(event.content)
    break
}
```

**When Emitted:**
- Multiple times during LLM response generation
- After `content_start` event
- Can be hundreds of events for long responses

**Common Use Cases:**
- Append to message display in real-time
- Create typewriter effect
- Calculate reading progress

---

### 2.4 Event: `thinking`

**Purpose:** Streams reasoning/thinking content from models that support extended thinking (o1, o3-mini, Claude with thinking enabled). This allows users to see the model's internal reasoning process.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:31-35`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'thinking'
          status: 'delta'
          delta: string
          signature?: string  // For Gemini models
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/models.py:567-569`

```python
class EventType(str, Enum):
    THINKING_START = "thinking_start"
    THINKING_DELTA = "thinking_delta"
    THINKING_STOP = "thinking_stop"
    SIGNATURE_DELTA = "signature_delta"  # Google Gemini signatures
    # ...
```

**Backend Event Emission:**
**File:** `src/ii_agent/server/chat/router.py:309-315`

```python
# Thinking events (delta-only, no start/stop)
elif event_type == "thinking_delta":
    thinking_event = {"status": "delta", "delta": event.get("thinking")}
    # Include signature if present (for o1 models)
    if event.get("signature"):
        thinking_event["signature"] = event.get("signature")
    yield f"event: thinking\ndata: {json.dumps(thinking_event)}\n\n"
```

#### SSE Wire Format
```
event: thinking
data: {"status":"delta","delta":"Let me analyze this problem step by step..."}

event: thinking
data: {"status":"delta","delta":" First, I need to understand the requirements..."}

event: thinking
data: {"status":"delta","delta":" The key insight here is...","signature":"base64_encoded_signature"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:206-221`

```typescript
// Handle thinking event
if (eventName === 'thinking') {
    const status = readString(record, 'status')
    if (status === 'delta') {
        const delta = readString(record, 'delta')
        if (delta) {
            events.push({
                type: 'thinking',
                status: 'delta',
                delta,
                signature: readString(record, 'signature')
            })
        }
    }
    return events
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:194-198`

```typescript
case 'thinking': {
    callbacks?.onThinking?.({
        delta: event.delta,
        signature: event.signature
    })
    break
}
```

**When Emitted:**
- Only for models that support extended thinking (o1, o3-mini, Claude with thinking enabled)
- Multiple times during the thinking phase
- Before the actual content/response

**Common Use Cases:**
- Display thinking process in collapsible section
- Show AI reasoning transparency
- Debug model behavior
- Extract signature for verification (Gemini)

---

### 2.5 Event: `tool_call_start`

**Purpose:** Signals the beginning of a tool invocation. The LLM has decided to call a tool and streaming of the tool input is about to begin.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:37-41`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'tool_call_start'
          id: string
          name: string
          call_type: string  // Usually 'function'
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:318-332`

```python
elif event_type == "tool_use_start":
    tool_call = event.get("tool_call", {})
    tool_event = {
        "status": "start",
        "id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
        "name": tool_call.name if hasattr(tool_call, "name") else tool_call.get("name"),
        "type": tool_call.type if hasattr(tool_call, "type") else tool_call.get("type", "function"),
    }
    yield f"event: tool_call\ndata: {json.dumps(tool_event)}\n\n"
```

#### SSE Wire Format
```
event: tool_call
data: {"status":"start","id":"call_abc123","name":"web_search","type":"function"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:254-265`

```typescript
// Handle tool_call event
if (eventName === 'tool_call') {
    const status = readString(record, 'status')
    const id = readString(record, 'id')
    const name = readString(record, 'name')

    if (status === 'start' && id && name) {
        events.push({
            type: 'tool_call_start',
            id,
            name,
            call_type: readString(record, 'type') ?? 'function'
        })
    }
    // ...
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:208-217`

```typescript
case 'tool_call_start': {
    callbacks?.onToolCallStart?.({
        id: event.id,
        name: event.name,
        callType: event.call_type
    })
    break
}
```

**When Emitted:**
- When LLM decides to invoke a tool
- Before `tool_call_delta` events
- Once per tool invocation

**Common Use Cases:**
- Create placeholder UI for tool execution
- Show tool name badge/icon
- Initialize tool input accumulator
- Track tool invocation metrics

---

### 2.6 Event: `tool_call_delta`

**Purpose:** Streams partial JSON input for the tool call. This allows displaying the tool arguments as they're being generated.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:43-46`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'tool_call_delta'
          id: string
          delta: string  // Partial JSON fragment
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:334-345`

```python
elif event_type == "tool_use_delta":
    tool_call = event.get("tool_call", {})
    tool_event = {
        "status": "delta",
        "id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
        "delta": tool_call.input if hasattr(tool_call, "input") else tool_call.get("input", ""),  # Partial JSON
    }
    yield f"event: tool_call\ndata: {json.dumps(tool_event)}\n\n"
```

#### SSE Wire Format
```
event: tool_call
data: {"status":"delta","id":"call_abc123","delta":"{\"query\""}

event: tool_call
data: {"status":"delta","id":"call_abc123","delta":": \"latest"}

event: tool_call
data: {"status":"delta","id":"call_abc123","delta":" news\""}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:266-274`

```typescript
if (eventName === 'tool_call') {
    const status = readString(record, 'status')
    const id = readString(record, 'id')
    // ...
    else if (status === 'delta' && id) {
        const delta = readString(record, 'delta')
        if (delta) {
            events.push({
                type: 'tool_call_delta',
                id,
                delta
            })
        }
    }
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:218-227`

```typescript
case 'tool_call_delta': {
    callbacks?.onToolCallDelta?.({
        id: event.id,
        delta: event.delta
    })
    break
}
```

**When Emitted:**
- Multiple times during tool input generation
- Between `tool_call_start` and `tool_call_stop`
- Frequency depends on input length

**Common Use Cases:**
- Accumulate JSON fragments
- Show streaming tool input (if parseable)
- Display "..." loading indicator

**Note:** The delta may not be valid JSON until accumulated with previous deltas!

---

### 2.7 Event: `tool_call_stop`

**Purpose:** Signals completion of tool input streaming. Provides the complete, valid JSON input for the tool.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:48-52`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'tool_call_stop'
          id: string
          name: string
          input: string  // Complete JSON string
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:347-361`

```python
elif event_type == "tool_use_stop":
    tool_call = event.get("tool_call", {})
    tool_event = {
        "status": "stop",
        "id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
        "name": tool_call.name if hasattr(tool_call, "name") else tool_call.get("name"),
        "input": tool_call.input if hasattr(tool_call, "input") else tool_call.get("input"),  # Complete JSON
    }
    yield f"event: tool_call\ndata: {json.dumps(tool_event)}\n\n"
```

#### SSE Wire Format
```
event: tool_call
data: {"status":"stop","id":"call_abc123","name":"web_search","input":"{\"query\": \"latest news\"}"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:275-284`

```typescript
if (eventName === 'tool_call') {
    const status = readString(record, 'status')
    const id = readString(record, 'id')
    const name = readString(record, 'name')
    // ...
    else if (status === 'stop' && id && name) {
        const input = readString(record, 'input')
        if (input) {
            events.push({
                type: 'tool_call_stop',
                id,
                name,
                input
            })
        }
    }
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:228-237`

```typescript
case 'tool_call_stop': {
    callbacks?.onToolCallStop?.({
        id: event.id,
        name: event.name,
        input: event.input
    })
    break
}
```

**When Emitted:**
- After all `tool_call_delta` events
- Before backend executes the tool
- Once per tool invocation

**Common Use Cases:**
- Parse and display complete tool input
- Validate tool arguments
- Show "Executing..." status
- Log tool calls for debugging

**Tool Execution Flow:**
```
tool_call_start → tool_call_delta* → tool_call_stop → [backend executes] → tool_result
```

---

### 2.8 Event: `tool_result`

**Purpose:** Provides the result of tool execution. Sent after the backend executes the tool.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:54-59`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'tool_result'
          tool_call_id: string
          name: string
          output: string
          is_error?: boolean
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:374-383`

```python
# Tool result events (from backend execution)
elif event_type == "tool_result":
    result_event = {
        "status": "info",
        "tool_call_id": event.get("tool_call_id"),
        "name": event.get("name"),
        "output": event.get("output"),
        "is_error": event.get("is_error", False),
    }
    yield f"event: tool_result\ndata: {json.dumps(result_event)}\n\n"
```

**Backend Tool Execution:**
**File:** `src/ii_agent/server/chat/service.py:871-934`

```python
async def _execute_tool(
    tool_call_id: str,
    tool_name: str,
    tool_input: str,
    tool_registry: Dict[str, BaseTool],
) -> ToolResult:
    tool = tool_registry.get(tool_name)
    tool_response = await tool.run(
        ToolCallInput(
            id=tool_call_id,
            name=tool_name,
            input=tool_input,
        )
    )
    return ToolResult(
        tool_call_id=tool_call_id,
        name=tool_name,
        output=tool_response.output,
    )
```

#### SSE Wire Format
```
event: tool_result
data: {"status":"info","tool_call_id":"call_abc123","name":"web_search","output":"{\"results\": [...]}","is_error":false}

```

**Error Case:**
```
event: tool_result
data: {"status":"info","tool_call_id":"call_abc123","name":"web_search","output":"Connection timeout","is_error":true}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:289-310`

```typescript
// Handle tool_result event
if (eventName === 'tool_result') {
    const status = readString(record, 'status')
    if (status === 'info') {
        const toolCallId = readString(record, 'tool_call_id')
        const name = readString(record, 'name')
        const output =
            typeof record?.output === 'object'
                ? JSON.stringify(record?.output)
                : readString(record, 'output')

        if (toolCallId && name && output !== undefined) {
            events.push({
                type: 'tool_result',
                tool_call_id: toolCallId,
                name,
                output,
                is_error: record.is_error === true
            })
        }
    }
    return events
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:238-247`

```typescript
case 'tool_result': {
    callbacks?.onToolResult?.({
        toolCallId: event.tool_call_id,
        name: event.name,
        output: event.output,
        isError: event.is_error
    })
    break
}
```

**When Emitted:**
- After backend executes the tool
- After `tool_call_stop` event
- Once per tool invocation

**Common Use Cases:**
- Display tool execution result
- Show success/error status
- Parse structured output (JSON)
- Feed result back to LLM for next turn

**Multi-Turn Tool Loop:**
Backend automatically sends tool results back to the LLM, which may trigger more tool calls, creating a multi-turn loop until the LLM provides a final response with `finish_reason: "end_turn"`.

---

### 2.9 Event: `usage`

**Purpose:** Reports token usage statistics for the current LLM turn. Useful for cost tracking and analytics.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:61-67`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'usage'
          input_tokens: number
          output_tokens: number
          cache_creation_tokens: number
          cache_read_tokens: number
          total_tokens: number
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:385-397`

```python
# Usage events (per LLM turn)
elif event_type == "usage":
    usage = event.get("usage", {})
    usage_event = {
        "status": "info",
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_tokens": usage.get("cache_creation_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }
    yield f"event: usage\ndata: {json.dumps(usage_event)}\n\n"
```

#### SSE Wire Format
```
event: usage
data: {"status":"info","input_tokens":1523,"output_tokens":487,"cache_creation_tokens":0,"cache_read_tokens":1200,"total_tokens":2010}

```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:248-254`

```typescript
case 'usage': {
    callbacks?.onUsage?.({
        inputTokens: event.input_tokens,
        outputTokens: event.output_tokens,
        cacheCreationTokens: event.cache_creation_tokens,
        cacheReadTokens: event.cache_read_tokens,
        totalTokens: event.total_tokens
    })
    break
}
```

**When Emitted:**
- After each LLM turn (may be multiple per conversation if tools are used)
- Before `complete` event
- Once per LLM API call

**Token Types Explained:**
- **input_tokens**: Tokens in the prompt sent to LLM
- **output_tokens**: Tokens generated by LLM
- **cache_creation_tokens**: Tokens written to prompt cache (Anthropic)
- **cache_read_tokens**: Tokens read from prompt cache (cheaper)
- **total_tokens**: input_tokens + output_tokens

**Common Use Cases:**
- Display token count to user
- Calculate API cost
- Track usage quotas
- Analytics and monitoring
- Trigger warnings for high usage

---

### 2.10 Event: `complete`

**Purpose:** Signals that message generation is complete. Provides final metadata including finish reason and message ID.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:69-73`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'complete'
          message_id?: string
          finish_reason?: string
          elapsed_ms?: number
      }
    // ...
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:399-409`

```python
# Complete event (final - only sent when loop exits)
elif event_type == "complete":
    elapsed_ms = int((time.time() - start_time) * 1000)
    complete_event = {
        "status": "done",
        "message_id": str(event.get("message_id")),
        "finish_reason": event.get("finish_reason", "end_turn"),
        "elapsed_ms": elapsed_ms,
        "files": event.get("files"),
    }
    yield f"event: complete\ndata: {json.dumps(complete_event)}\n\n"
```

#### SSE Wire Format
```
event: complete
data: {"status":"done","message_id":"550e8400-e29b-41d4-a716-446655440001","finish_reason":"end_turn","elapsed_ms":3542,"files":null}

```

**With Tool Use:**
```
event: complete
data: {"status":"done","message_id":"...","finish_reason":"tool_use","elapsed_ms":1234,"files":null}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:238-250`

```typescript
// Handle complete event
if (eventName === 'complete') {
    const status = readString(record, 'status')
    if (status === 'done') {
        events.push({
            type: 'complete',
            message_id: readString(record, 'message_id'),
            finish_reason: readString(record, 'finish_reason'),
            elapsed_ms: readNumber(record, 'elapsed_ms')
        })
        events.push({ type: 'done' })  // Also emit done event
    }
    return events
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:255-262`

```typescript
case 'complete': {
    callbacks?.onComplete?.({
        messageId: event.message_id,
        finishReason: event.finish_reason,
        elapsedMs: event.elapsed_ms
    })
    break
}
```

**When Emitted:**
- At the very end of message generation
- After all content, tool execution, and usage events
- Once per assistant message

**Finish Reasons:**
- `end_turn`: Normal completion
- `tool_use`: LLM wants to call tools (triggers another turn)
- `max_tokens`: Hit token limit
- `canceled`: User/system cancellation
- `error`: Error occurred

**Common Use Cases:**
- Store message ID for later reference
- Handle completion logic (stop spinner, etc.)
- Check finish reason for next action
- Log performance metrics (elapsed_ms)

---

### 2.11 Event: `done`

**Purpose:** Final stream termination signal. Indicates the SSE stream is complete and will close.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:75-76`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'done'
      }
```

#### Backend Generation
The `done` event is emitted by the frontend after receiving the `complete` event. There's also a `[DONE]` marker that can be sent:

**File:** `frontend/src/services/chat.service.ts:161-164`

```typescript
if (raw === '[DONE]') {
    events.push({ type: 'done' })
    return events
}
```

#### SSE Wire Format
Option 1 - Implicit (from `complete` event):
```
event: complete
data: {"status":"done",...}

```
Frontend automatically generates `done` event after `complete`.

Option 2 - Explicit marker:
```
data: [DONE]

```

#### Frontend Handling
**File:** `frontend/src/services/chat.service.ts:341-349` & `frontend/src/hooks/use-chat-transport.tsx:263-267`

```typescript
// In parseSSEBlock flushBuffer:
if (event.type === 'done') {
    buffer = ''
    try {
        await reader.cancel()
    } catch {
        // Ignore cancel errors
    }
    return true // Signal stream is done
}

// In event handler:
case 'done': {
    callbacks?.onDone?.()
    break
}
```

**When Emitted:**
- After `complete` event
- Last event in the stream
- Once per request

**Common Use Cases:**
- Clean up stream resources
- Reset loading states
- Invalidate caches
- Navigate or update UI

---

### 2.12 Event: `error`

**Purpose:** Reports errors that occur during streaming. Can be sent at any point if something goes wrong.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:78-80`

```typescript
export type ChatStreamEvent =
    // ...
    | {
          type: 'error'
          message?: string
      }
```

#### Backend Generation
**File:** `src/ii_agent/server/chat/router.py:411-418`

```python
except Exception as e:
    logger.error(f"Chat streaming error: {e}", exc_info=True)
    error_event = {
        "status": "error",
        "error": str(e),
        "code": "streaming_error",
    }
    yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
```

#### SSE Wire Format
```
event: error
data: {"status":"error","error":"Connection to LLM provider failed","code":"streaming_error"}

```

#### Frontend Parsing
**File:** `frontend/src/services/chat.service.ts:313-319`

```typescript
// Handle error event
if (eventName === 'error') {
    const message = readString(record, 'message') ?? readString(record, 'error')
    events.push({ type: 'error', message })
    return events
}
```

#### Frontend Handling
**File:** `frontend/src/hooks/use-chat-transport.tsx:259-262` & `chat.service.ts:414-424`

```typescript
// In event handler:
case 'error': {
    callbacks?.onError?.(event.message)
    break
}

// In stream processing catch block:
catch (error) {
    if ((error as DOMException).name !== 'AbortError') {
        console.error('Chat stream interrupted', error)
        onEvent({
            type: 'error',
            message: error instanceof Error
                ? error.message
                : 'Unexpected streaming error'
        })
    }
}
```

**When Emitted:**
- Any time an error occurs during streaming
- Backend exceptions
- Network failures
- LLM provider errors
- Tool execution failures (may also use `tool_result` with `is_error: true`)

**Common Use Cases:**
- Display error message to user
- Log errors for debugging
- Retry logic
- Fallback handling
- Cancel ongoing operations

**Error Handling Strategy:**
1. Backend catches exceptions and yields error event
2. Frontend displays error to user
3. Stream continues (unless fatal)
4. User can retry or cancel

---

## Event Type Summary Matrix

| Event | When | Frequency | Critical | Contains Data |
|-------|------|-----------|----------|---------------|
| `session` | New session only | Once | Yes | session_id, model_id |
| `content_start` | Before text | Once/msg | No | None |
| `token` | During text | Many | Yes | text delta |
| `thinking` | During reasoning | Many | No | thinking delta |
| `tool_call_start` | Tool begins | Once/tool | Yes | tool id, name |
| `tool_call_delta` | Tool input | Many/tool | No | input delta |
| `tool_call_stop` | Tool input done | Once/tool | Yes | complete input |
| `tool_result` | Tool executed | Once/tool | Yes | tool output |
| `usage` | After LLM turn | Once/turn | Yes | token counts |
| `complete` | Message done | Once/msg | Yes | message_id, finish_reason |
| `done` | Stream end | Once | Yes | None |
| `error` | On error | As needed | Yes | error message |

---

## 3. Content Part Types

Content parts are the building blocks of chat messages. Each message contains an array of `ContentPart` objects representing different types of content (text, reasoning, tool calls, etc.). This section maps the 7 content part types between frontend and backend.

### Content Part Overview Table

| Type | Frontend | Backend | Purpose | Rendered In UI |
|------|----------|---------|---------|----------------|
| `text` | TextPart | TextContent | Plain text content | Message body |
| `reasoning` | ReasoningContent | ReasoningContent | Thinking/reasoning | Collapsible section |
| `tool_call` | ToolCallPart | ToolCall | Tool invocation | Action badge/card |
| `tool_result` | ToolResultPart | ToolResult | Tool output | Expandable result |
| `code_block` | CodeBlockPart | CodeBlockContent | Code interpreter | Code viewer |
| `image_url` | N/A (backend only) | ImageURLContent | Image reference | Image display |
| `binary` | N/A (backend only) | BinaryContent | Binary data | File preview |

---

### 3.1 Content Part: `text`

**Purpose:** Standard text content in messages. The most common content type.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:89-91`

```typescript
export type ContentPart =
    | {
          type: 'text'
          text: string
      }
    // ... other types
```

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:296-300`

```python
class TextContent(BaseContentPart):
    """Plain text content."""

    type: Literal["text"] = "text"
    text: str
```

#### JSON Wire Format
```json
{
    "type": "text",
    "text": "Hello! How can I help you today?"
}
```

#### Database Storage
Stored in `ChatMessage.content` JSONB column as part of the content array:

```json
{
    "content": [
        {"type": "text", "text": "User's question here"},
        {"type": "text", "text": "Assistant's response here"}
    ]
}
```

#### Usage Example
**Backend - Creating text content:**

```python
from ii_agent.server.chat.models import TextContent

text_part = TextContent(text="Hello, world!")
```

**Frontend - Rendering text:**

```typescript
if (part.type === 'text') {
    return <p>{part.text}</p>
}
```

---

### 3.2 Content Part: `reasoning`

**Purpose:** Stores extended thinking/reasoning content from models like o1, o3-mini, or Claude with thinking enabled.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:93-99`

```typescript
export type ContentPart =
    // ...
    | {
          type: 'reasoning'
          id?: string
          thinking: string
          signature?: string        // For verification (Gemini)
          started_at?: number | null
          finished_at?: number | null
      }
    // ...
```

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:303-310`

```python
class ReasoningContent(BaseContentPart):
    """Reasoning/thinking content from models like o1, o3-mini, Claude extended thinking."""

    type: Literal["reasoning"] = "reasoning"
    thinking: str
    signature: str = ""
    started_at: Optional[int] = None
    finished_at: Optional[int] = None
```

#### JSON Wire Format
```json
{
    "type": "reasoning",
    "thinking": "Let me think through this step by step. First, I need to understand...",
    "signature": "base64_encoded_signature",
    "started_at": 1706097600000,
    "finished_at": 1706097615000
}
```

#### Database Storage
```json
{
    "content": [
        {
            "type": "reasoning",
            "thinking": "Detailed reasoning process...",
            "signature": "",
            "started_at": 1706097600000,
            "finished_at": 1706097615000
        },
        {
            "type": "text",
            "text": "Based on my reasoning, the answer is..."
        }
    ]
}
```

#### Usage Example
**Frontend - Rendering reasoning:**

```typescript
if (part.type === 'reasoning') {
    return (
        <Collapsible title="Thinking Process">
            <pre>{part.thinking}</pre>
            {part.signature && <p>Signature: {part.signature}</p>}
        </Collapsible>
    )
}
```

**Backend - Creating reasoning content:**

```python
reasoning_part = ReasoningContent(
    thinking="Let me analyze this problem...",
    signature="abc123...",
    started_at=int(time.time() * 1000),
    finished_at=int(time.time() * 1000) + 5000
)
```

---

### 3.3 Content Part: `tool_call`

**Purpose:** Represents a tool/function invocation by the LLM.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:101-106`

```typescript
export type ContentPart =
    // ...
    | {
          type: 'tool_call'
          id: string
          name: string
          input: string          // JSON string
          finished: boolean
      }
    // ...
```

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:340-351`

```python
class ToolCall(BaseContentPart):
    """Tool/function call made by assistant."""

    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    input: str                              # JSON string
    function_type: str = Field(default="function", alias="function_type")
    finished: bool = True
    provider_executed: bool = False         # Whether provider executed the tool
```

#### JSON Wire Format
```json
{
    "type": "tool_call",
    "id": "call_abc123",
    "name": "web_search",
    "input": "{\"query\": \"latest AI news\"}",
    "finished": true
}
```

#### Database Storage
```json
{
    "role": "assistant",
    "content": [
        {
            "type": "tool_call",
            "id": "call_abc123",
            "name": "web_search",
            "input": "{\"query\": \"latest AI news\"}",
            "function_type": "function",
            "finished": true,
            "provider_executed": false
        }
    ]
}
```

#### Frontend Rendering
**File:** `frontend/src/components/agent/action.tsx`

Tool calls are rendered as action badges/cards showing:
- Tool icon (mapped from TOOL enum)
- Tool name (human-readable)
- Tool input (expandable JSON)

```typescript
// Simplified rendering logic
if (part.type === 'tool_call') {
    const toolInput = JSON.parse(part.input)
    return (
        <ActionCard>
            <Icon name={getIconForTool(part.name)} />
            <ToolName>{humanizeName(part.name)}</ToolName>
            <ExpandableInput input={toolInput} />
        </ActionCard>
    )
}
```

---

### 3.4 Content Part: `tool_result`

**Purpose:** Stores the result/output from a tool execution.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:108-114`

```typescript
export type ContentPart =
    // ...
    | {
          type: 'tool_result'
          tool_call_id: string
          name: string
          content: string
          metadata: string
          is_error: boolean
      }
    // ...
```

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:495-502`

```python
class ToolResult(BaseContentPart):
    """Result from tool execution."""

    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    output: ToolResultContent                    # Union of result content types
    provider_options: Optional[Dict[str, Any]] = None
```

**Backend ToolResultContent Types:**
**File:** `src/ii_agent/server/chat/models.py:437-492`

```python
ToolResultContent = Union[
    TextResultContent,        # {"type": "text", "value": str}
    JsonResultContent,        # {"type": "json", "value": any}
    ExecutionDeniedContent,   # {"type": "execution-denied", "reason": str}
    ErrorTextContent,         # {"type": "error-text", "value": str}
    ErrorJsonContent,         # {"type": "error-json", "value": any}
    ArrayResultContent,       # {"type": "array", "value": [...]}
]
```

#### JSON Wire Format
**Success Case:**
```json
{
    "type": "tool_result",
    "tool_call_id": "call_abc123",
    "name": "web_search",
    "output": {
        "type": "json",
        "value": {
            "results": [
                {"title": "Article 1", "url": "https://..."},
                {"title": "Article 2", "url": "https://..."}
            ]
        }
    }
}
```

**Error Case:**
```json
{
    "type": "tool_result",
    "tool_call_id": "call_abc123",
    "name": "web_search",
    "output": {
        "type": "error-text",
        "value": "Connection timeout after 30s"
    }
}
```

#### Database Storage
```json
{
    "role": "tool",
    "content": [
        {
            "type": "tool_result",
            "tool_call_id": "call_abc123",
            "name": "web_search",
            "output": {
                "type": "json",
                "value": {"results": [...]}
            }
        }
    ]
}
```

#### Frontend Rendering
```typescript
if (part.type === 'tool_result') {
    const output = typeof part.content === 'string' 
        ? JSON.parse(part.content) 
        : part.content
        
    return (
        <ToolResultCard error={part.is_error}>
            <ToolName>{part.name}</ToolName>
            {part.is_error ? (
                <ErrorOutput>{output}</ErrorOutput>
            ) : (
                <SuccessOutput>{formatOutput(output)}</SuccessOutput>
            )}
        </ToolResultCard>
    )
}
```

---

### 3.5 Content Part: `code_block`

**Purpose:** Represents code interpreter execution results.

#### Frontend Type Definition
**File:** `frontend/src/typings/chat.ts:116-122`

```typescript
export type ContentPart =
    // ...
    | {
          type: 'code_block'
          id: string
          content: string                     // The code
          status: string
          outputs?: Array<Record<string, unknown>> | null
          container_id?: string | null
      }
    // ...
```

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:515-524`

```python
class CodeBlockContent(BaseContentPart):
    """Code interpreter execution result."""

    type: Literal["code_block"] = "code_block"
    id: str
    content: str                              # The code
    status: str
    outputs: Optional[List[Dict]] = None      # Execution outputs
    container_id: Optional[str] = None
```

#### JSON Wire Format
```json
{
    "type": "code_block",
    "id": "code_block_123",
    "content": "import pandas as pd\ndf = pd.read_csv('data.csv')\nprint(df.head())",
    "status": "completed",
    "outputs": [
        {
            "type": "stdout",
            "value": "   col1  col2\n0     1     2\n1     3     4"
        }
    ],
    "container_id": "container_abc"
}
```

#### Frontend Rendering
```typescript
if (part.type === 'code_block') {
    return (
        <CodeBlockCard>
            <CodeEditor 
                value={part.content} 
                readonly 
                language="python" 
            />
            {part.outputs && part.outputs.length > 0 && (
                <OutputSection>
                    {part.outputs.map(output => (
                        <Output key={output.type}>
                            {formatOutput(output)}
                        </Output>
                    ))}
                </OutputSection>
            )}
            <Status>{part.status}</Status>
        </CodeBlockCard>
    )
}
```

---

### 3.6 Content Part: `image_url` (Backend Only)

**Purpose:** References images by URL (not directly used in frontend types, converted to other formats).

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:313-318`

```python
class ImageURLContent(BaseContentPart):
    """Image content with URL."""

    type: Literal["image_url"] = "image_url"
    url: str
    detail: Optional[str] = None              # "low", "high", "auto"
```

#### JSON Wire Format
```json
{
    "type": "image_url",
    "url": "https://example.com/image.png",
    "detail": "high"
}
```

**Note:** Typically converted to base64 or file upload for frontend consumption.

---

### 3.7 Content Part: `binary` (Backend Only)

**Purpose:** Stores binary data (images, files) with base64 encoding for transmission to LLM providers.

#### Backend Type Definition
**File:** `src/ii_agent/server/chat/models.py:321-337`

```python
class BinaryContent(BaseContentPart):
    """Binary data (images, files) with base64 encoding."""

    type: Literal["binary"] = "binary"
    path: str
    mime_type: str
    data: bytes

    def to_base64(self, provider: str = "anthropic") -> str:
        """Convert to base64 string with provider-specific format."""
        encoded = base64.b64encode(self.data).decode("utf-8")
        if provider == "openai":
            return f"data:{self.mime_type};base64,{encoded}"
        return encoded
```

#### Usage Example
```python
# Create binary content from file
with open("image.png", "rb") as f:
    binary_part = BinaryContent(
        path="image.png",
        mime_type="image/png",
        data=f.read()
    )

# Convert for OpenAI
openai_format = binary_part.to_base64(provider="openai")
# Returns: "data:image/png;base64,iVBORw0KG..."

# Convert for Anthropic
anthropic_format = binary_part.to_base64(provider="anthropic")
# Returns: "iVBORw0KG..."
```

---

## Content Part Usage in Messages

### Message Structure

Messages are stored with a `content` field containing an array of `ContentPart` objects:

**Backend:**
```python
class Message(BaseModel):
    id: UUID
    role: MessageRole  # user, assistant, tool, system
    parts: List[ContentPart]
    # ... other fields
```

**Frontend:**
```typescript
interface ChatHistoryMessage {
    id: string
    role: 'user' | 'assistant' | 'tool'
    content: ContentPart[]  // Array of content parts
    // ... other fields
}
```

### Example Multi-Part Message

A complex assistant message might contain multiple content parts:

```json
{
    "id": "msg_123",
    "role": "assistant",
    "content": [
        {
            "type": "reasoning",
            "thinking": "I need to search for recent news..."
        },
        {
            "type": "tool_call",
            "id": "call_1",
            "name": "web_search",
            "input": "{\"query\": \"AI news 2025\"}"
        },
        {
            "type": "tool_result",
            "tool_call_id": "call_1",
            "name": "web_search",
            "output": {"type": "json", "value": {"results": [...]}}
        },
        {
            "type": "text",
            "text": "Based on the search results, here's what I found..."
        }
    ]
}
```

---

