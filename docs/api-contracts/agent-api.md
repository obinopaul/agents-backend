# Agent Endpoint API Reference

> **New endpoint for AI agents with sandbox tool support and lazy initialization.**

---

## Endpoint

```
POST /agent/agent/stream
```

**Purpose**: Stream AI agent responses with automatic sandbox creation when tools need it.

**Authentication**: JWT Bearer token required

---

## Quick Start

### 1. Get JWT Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"
```

### 2. Call Agent Endpoint

```bash
curl -X POST http://localhost:8000/agent/agent/stream \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Create a hello.py file"}],
    "session_id": "my-session-123"
  }'
```

---

## Request Schema

```json
{
  "messages": [
    {"role": "user", "content": "Your message"}
  ],
  "thread_id": "__default__",
  "session_id": "optional-session-id",
  "resources": [],
  "max_plan_iterations": 1,
  "max_step_num": 3,
  "max_search_results": 3,
  "auto_accepted_plan": true,
  "enable_background_investigation": true,
  "enable_web_search": true,
  "enable_deep_thinking": false,
  "locale": "en-US"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `messages` | array | ✅ | - | Conversation messages |
| `thread_id` | string | ❌ | `__default__` | Thread ID for continuity |
| `session_id` | string | ❌ | null | Session ID for sandbox reuse |
| `resources` | array | ❌ | `[]` | RAG resources |
| `max_plan_iterations` | int | ❌ | 1 | Max plan iterations (1-10) |
| `max_step_num` | int | ❌ | 3 | Max steps per plan (1-10) |
| `max_search_results` | int | ❌ | 3 | Max search results (1-20) |
| `auto_accepted_plan` | bool | ❌ | true | Auto-accept plans |
| `enable_background_investigation` | bool | ❌ | true | Enable web search background |
| `enable_web_search` | bool | ❌ | true | Enable web search |
| `enable_deep_thinking` | bool | ❌ | false | Enable deep thinking mode |
| `locale` | string | ❌ | `en-US` | User locale |

---

## Response Format (SSE Stream)

The endpoint returns Server-Sent Events (SSE):

### Event Types

| Event | Description |
|-------|-------------|
| `status` | Processing status updates |
| `message` | Agent response chunks |
| `tool` | Tool execution events |
| `warning` | Non-fatal warnings |
| `error` | Error events |

### Example SSE Stream

```
event: status
data: {"type": "processing", "message": "Processing your request..."}

event: status
data: {"type": "sandbox_ready", "sandbox_id": "sbx-abc123", "message": "Environment ready"}

event: status
data: {"type": "mcp_ready", "message": "Tools ready"}

event: message
data: {"type": "chunk", "content": "I'll create ", "thread_id": "abc123"}

event: message
data: {"type": "chunk", "content": "a hello.py file...", "thread_id": "abc123"}

event: tool
data: {"type": "start", "name": "write_file"}

event: tool
data: {"type": "end", "name": "write_file"}

event: status
data: {"type": "complete", "message": "Done", "sandbox_id": "sbx-abc123"}
```

---

## Sandbox Lifecycle

### Lazy Initialization

The sandbox is **NOT** created when:
- User opens a session
- User sends a message

The sandbox **IS** created when:
- The agent endpoint is called
- After "Processing..." is sent

### Session Reuse

If the same `session_id` is used in multiple requests:
1. First request: Creates new sandbox (~1-3 seconds)
2. Subsequent requests: Reuses existing sandbox (instant)

```bash
# First call - creates sandbox
curl -X POST .../agent/agent/stream -d '{"session_id": "sess-123", ...}'

# Second call - reuses sandbox
curl -X POST .../agent/agent/stream -d '{"session_id": "sess-123", ...}'
```

---

## Comparison with Chat Endpoint

| Feature | `/agent/chat/stream` | `/agent/agent/stream` |
|---------|---------------------|----------------------|
| Sandbox | ❌ No | ✅ Yes (lazy) |
| Code execution | ❌ No | ✅ Yes |
| File operations | ❌ No | ✅ Yes |
| Session reuse | ❌ N/A | ✅ Via session_id |
| Best for | Simple chat | Coding tasks |

---

## Error Handling

### Sandbox Creation Error

```json
event: error
data: {"type": "sandbox_error", "message": "Failed to create sandbox: ..."}
```

### Stream Error

```json
event: error
data: {"type": "stream_error", "message": "..."}
```

---

## Python Example

```python
import httpx
import json

async def call_agent():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/agent/agent/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messages": [{"role": "user", "content": "Create hello.py"}],
                "session_id": "my-session"
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(data)
```

---

## TypeScript/JavaScript Example

```typescript
const response = await fetch('/agent/agent/stream', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Create hello.py' }],
    session_id: 'my-session'
  })
});

const reader = response.body?.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  const lines = text.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      console.log(data);
    }
  }
}
```
