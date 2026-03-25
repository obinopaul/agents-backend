# Agent Endpoint - Frontend Integration

> How to connect your frontend to the `/agent/agent/stream` endpoint.

---

## Overview

The agent endpoint provides AI agent responses with sandbox tool support:

| Endpoint | Purpose |
|----------|---------|
| `/agent/chat/stream` | Simple chat (no code execution) |
| `/agent/agent/stream` | Agent with sandbox tools |

---

## Quick Integration

### 1. TypeScript/React Hook

```typescript
import { useState, useCallback } from 'react';

interface AgentMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface AgentEvent {
  type: string;
  content?: string;
  message?: string;
  sandbox_id?: string;
}

export function useAgentStream(token: string) {
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState('');
  const [sandboxId, setSandboxId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('');

  const sendMessage = useCallback(async (
    messages: AgentMessage[],
    sessionId: string
  ) => {
    setIsLoading(true);
    setResponse('');
    setStatus('Connecting...');

    try {
      const res = await fetch('/agent/agent/stream', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messages,
          session_id: sessionId
        })
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // Parse event type
          } else if (line.startsWith('data: ')) {
            const data: AgentEvent = JSON.parse(line.slice(6));
            
            if (data.type === 'processing') {
              setStatus('Processing...');
            } else if (data.type === 'sandbox_ready') {
              setStatus('Sandbox ready');
              setSandboxId(data.sandbox_id || null);
            } else if (data.type === 'chunk') {
              setResponse(prev => prev + (data.content || ''));
            } else if (data.type === 'complete') {
              setStatus('Complete');
            }
          }
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  return { sendMessage, response, isLoading, status, sandboxId };
}
```

### 2. Usage in Component

```tsx
function AgentChat() {
  const { sendMessage, response, isLoading, status, sandboxId } = useAgentStream(token);
  const [input, setInput] = useState('');
  const sessionId = useRef(crypto.randomUUID()).current;

  const handleSubmit = () => {
    sendMessage([{ role: 'user', content: input }], sessionId);
    setInput('');
  };

  return (
    <div>
      <div>Status: {status}</div>
      {sandboxId && <div>Sandbox: {sandboxId}</div>}
      <div>{response}</div>
      <input value={input} onChange={e => setInput(e.target.value)} />
      <button onClick={handleSubmit} disabled={isLoading}>
        Send
      </button>
    </div>
  );
}
```

---

## Event Handling

| Event | UI Action |
|-------|-----------|
| `status.processing` | Show loading spinner |
| `status.sandbox_ready` | Update sandbox indicator |
| `status.mcp_ready` | Show "Tools ready" |
| `message.chunk` | Append to response text |
| `tool.start` | Show tool execution indicator |
| `tool.end` | Hide tool indicator |
| `status.complete` | Hide spinner, enable input |
| `error` | Show error message |

---

## Session Management

### Generate Session ID

```typescript
// Per conversation
const sessionId = crypto.randomUUID();

// Per user (persistent)
const sessionId = `user-${userId}-session`;
```

### Reuse Sessions

Using the same `session_id` across requests:
- **Reuses the same sandbox** (no creation delay)
- **Maintains file state** (files created persist)
- **Reduces latency** for subsequent messages

---

## Error Handling

```typescript
if (data.type === 'error') {
  if (data.type === 'sandbox_error') {
    showError('Could not create coding environment');
  } else {
    showError(data.message);
  }
}
```
