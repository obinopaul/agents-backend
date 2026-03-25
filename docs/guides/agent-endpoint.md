# Agent Endpoint Guide

> How to use the `/agent/agent/stream` endpoint for AI-powered code execution.

---

## Overview

The agent endpoint combines LLM reasoning with sandbox tool execution:

```
User Message → Agent Processes → Creates Sandbox (if needed) → Executes Tools → Response
```

---

## When to Use Each Endpoint

| Use Case | Endpoint | Example |
|----------|----------|---------|
| Q&A, explain code | `/agent/chat/stream` | "What does this function do?" |
| Create files, run code | `/agent/agent/stream` | "Create a hello.py file" |
| Web research | `/agent/chat/stream` | "Research Python best practices" |
| Execute shell commands | `/agent/agent/stream` | "Run `pip install requests`" |

---

## Quick Start

### 1. Get JWT Token

```bash
# Using the login endpoint
curl -X POST http://localhost:8000/api/v1/admin/auth/login \
  -d "username=admin&password=password"
```

### 2. Call Agent Endpoint

```bash
curl -X POST http://localhost:8000/agent/agent/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Create hello.py that prints Hello World"}],
    "session_id": "my-session"
  }'
```

### 3. Parse SSE Response

```python
import httpx
import json

async def stream_agent():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/agent/agent/stream",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "messages": [{"role": "user", "content": "Create hello.py"}],
                "session_id": "test-session"
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if data.get("type") == "chunk":
                        print(data["content"], end="")
```

---

## Session-Based Sandbox Reuse

Using the same `session_id` reuses the sandbox:

```bash
# Request 1: Creates sandbox, creates file
curl ... -d '{"session_id": "abc", "messages": [{"content": "Create hello.py"}]}'

# Request 2: REUSES sandbox, runs file
curl ... -d '{"session_id": "abc", "messages": [{"content": "Run hello.py"}]}'
```

Benefits:
- **Faster**: No sandbox creation on subsequent requests
- **Persistent**: Files created in request 1 exist in request 2
- **Efficient**: Reduces E2B container costs

---

## SSE Event Types

| Event | Purpose | Example Data |
|-------|---------|--------------|
| `status` | Progress updates | `{"type": "sandbox_ready"}` |
| `message` | Agent response | `{"type": "chunk", "content": "..."}` |
| `tool` | Tool execution | `{"type": "start", "name": "Bash"}` |
| `error` | Errors | `{"message": "..."}` |

---

## Related Documentation

- [Agent API Reference](../api-contracts/agent-api.md)
- [Frontend Integration](../frontend-connect/agent-api.md)
- [Sandbox Guide](../lifecycle/sandbox.md)
