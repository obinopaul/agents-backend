# Backend Socket.IO API Contract

**Version**: 1.0.0
**Protocol**: Socket.IO v4
**Endpoint**: `/ws/socket.io`

---

## 1. Connection & Authentication

**Handshake Auth**:
```json
{
  "token": "working_jwt_token"
}
```

**Transport**: Websocket (preferred) or Polling.

---

## 2. Agent Types

The system supports two categories of agents. The `agent_type` field determines backend routing.

### 2.1 No-Sandbox Agents
Routes to light-weight chat logic.
- `chat`: General conversational AI (fast, cheap)

### 2.2 Sandbox Agents
Routes to heavy-weight agent logic with full code execution environment.
- `general`: Standard agent
- `deep_research`: Web research specialist
- `academic`: Paper writing specialist
- `dev`: Coding specialist
- `design`: UI/UX specialist
- `data_scientist`: Data analysis specialist
- `slides`: Presentation generator
- `documents`: Document/LaTeX generator
- `quant`: Financial analysis specialist
- `excalidraw`: Diagram generator

---

## 3. Client Events (Commands)

### 3.1 `join_session`
Joins a specific session room to receive broadcasts.
```json
{
  "session_uuid": "string (uuid)"
}
```

### 3.2 `chat_message`
Main message payload to trigger agent generation.
```json
{
  "command": "query",
  "session_uuid": "string (uuid)",
  "content": {
    "message": "string (user input)",
    "files": ["string (file_id)"],
    "agent_type": "string (enum from Section 2)",
    "model_id": "string (optional)",
    "locale": "string (default: en-US)"
  }
}
```

### 3.3 `awake_sandbox`
Request connection details for a sandbox (VS Code / MCP).
```json
{
  "command": "awake_sandbox",
  "session_uuid": "string (uuid)"
}
```

### 3.4 `enhance_prompt`
Enhance a user's prompt using LLM.
```json
{
  "command": "enhance_prompt",
  "content": {
    "prompt": "string (raw prompt)"
  }
}
```

---

## 4. Server Events (Responses)

All events are emitted to the `chat_event` channel.

### 4.1 Status Updates
```json
{
  "type": "status_update",
  "content": {
    "status": "running" | "idle",
    "run_id": "string (uuid)"
  }
}
```

### 4.2 Message Content
Streaming text deltas.
```json
{
  "type": "message_chunk",
  "content": {
    "content": "string (delta)",
    "role": "assistant",
    "id": "string (message_id)"
  }
}
```

### 4.3 Tool Execution (Sandbox)
```json
{
  "type": "tool_call_start",
  "content": {
    "toolCallId": "string",
    "toolCallName": "string (e.g., execute_code)"
  }
}
```
```json
{
  "type": "tool_call_args",
  "content": {
    "toolCallId": "string",
    "delta": "string (json fragment)"
  }
}
```

### 4.4 Sandbox Connection Info (Response to `awake_sandbox`)
```json
{
  "type": "sandbox_awake",
  "content": {
    "vscode_url": "https://...",
    "mcp_url": "https://...",
    "excalidraw_url": "https://...",
    "latex_url": "https://..."
  }
}
```

---

## 5. Error Handling

Errors are emitted to the `error` channel or `chat_event` with type `error`.

```json
{
  "type": "error",
  "content": {
    "message": "string (error description)",
    "code": "string (error code)"
  }
}
```
