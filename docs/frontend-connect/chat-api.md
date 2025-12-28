# Chat Streaming API

API for streaming agent responses using Server-Sent Events (SSE).

## Endpoint
```
POST /api/v1/agent/chat/stream
Authorization: Bearer <token>
Content-Type: application/json
```

---

## Request Body
```json
{
  "message": "Create a React component that fetches data from an API",
  "session_id": "optional-session-id",
  "settings": {
    "model": "gpt-4o",
    "temperature": 0.7,
    "codex_tools": true,
    "claude_code": true
  }
}
```

---

## Response (Server-Sent Events)

The response is a stream of events:

```
event: message
data: {"type": "text", "content": "I'll create a React component..."}

event: message
data: {"type": "tool_call", "tool": "shell", "args": {"command": "npm init -y"}}

event: message
data: {"type": "tool_result", "tool": "shell", "result": "..."}

event: message
data: {"type": "text", "content": "The component has been created."}

event: done
data: {"session_id": "abc123"}
```

---

## TypeScript EventSource Example

```typescript
const streamChat = (message: string, onChunk: (data: any) => void) => {
  const eventSource = new EventSource(
    `/api/v1/agent/chat/stream?message=${encodeURIComponent(message)}`,
    { withCredentials: true }
  )

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onChunk(data)
  }

  eventSource.addEventListener('done', () => {
    eventSource.close()
  })

  eventSource.onerror = (error) => {
    console.error('Stream error:', error)
    eventSource.close()
  }

  return eventSource
}

// Usage
streamChat("Create a hello world app", (data) => {
  if (data.type === 'text') {
    console.log('AI:', data.content)
  } else if (data.type === 'tool_call') {
    console.log('Tool:', data.tool, data.args)
  }
})
```

---

## Using Fetch API with Streams

```typescript
async function streamChatFetch(message: string) {
  const response = await fetch('/api/v1/agent/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message })
  })

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  while (reader) {
    const { done, value } = await reader.read()
    if (done) break
    
    const chunk = decoder.decode(value)
    const lines = chunk.split('\n')
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        console.log('Received:', data)
      }
    }
  }
}
```

---

## Event Types

| Type | Description |
|------|-------------|
| `text` | Text content from the AI |
| `tool_call` | AI is calling a tool |
| `tool_result` | Result from tool execution |
| `human_feedback` | Agent needs user input |
| `error` | Error occurred |
| `done` | Stream complete |
