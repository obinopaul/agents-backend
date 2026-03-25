# Frontend Integration Overview

## 1. Unified Architecture

The backend now uses a **Unified Session Architecture** powered by Socket.IO. This means you have a single entry point for both simple chats and advanced agent workflows.

### Connection
- **URL**: `ws://localhost:8000` (or production URL)
- **Path**: `/ws/socket.io`
- **Auth**: JWT token required in handshake auth or headers

### Routing Logic
The backend automatically routes your messages based on the `agent_type` you provide:

| Agent Type | Backend Route | Sandbox? | Use Case |
|------------|---------------|----------|----------|
| `"chat"` | `chat.py` | ❌ No | Simple Q&A, no code execution |
| `"general"`, `"dev"`, etc. | `agent.py` | ✅ Yes | Complex tasks, coding, research |

---

## 2. Socket.IO Events

### Client → Server (Commands)

| Event | Payload | Description |
|-------|---------|-------------|
| `join_session` | `{ "session_uuid": "..." }` | Join a specific chat room |
| `chat_message` | `{ "command": "query", "content": { ... } }` | **Main interface for sending messages** |
| `awake_sandbox` | `{ "command": "awake_sandbox", "session_uuid": "..." }` | Wake up/connect to sandbox, gets ports |
| `sandbox_status` | `{ "command": "sandbox_status", "session_uuid": "..." }` | Check status (running/paused) |
| `enhance_prompt` | `{ "command": "enhance_prompt", "content": { "prompt": "..." } }` | Optimize user prompt via LLM |

### Payload Structure for `chat_message`
```json
{
  "command": "query",
  "session_uuid": "uuid-string",
  "content": {
    "message": "User query here",
    "files": ["file-id-1"],     // Optional attachment IDs
    "agent_type": "dev"         // "chat" or any of the 10 module types
  }
}
```

### Server → Client (Streaming Events)

All processing events are streamed back via the `chat_event` channel.

| Event Type | Payload Data | Triggered By |
|------------|--------------|--------------|
| `processing` | `{ "message": "Processing...", "run_id": "..." }` | Request received |
| `status_update` | `{ "status": "running/idle", "run_id": "..." }` | Task state change |
| `message_chunk` | `{ "content": "delta", "role": "assistant" }` | Streaming text response |
| `tool_call_start` | `{ "toolCallId": "...", "toolCallName": "..." }` | Agent starting a tool |
| `tool_call_args` | `{ "toolCallId": "...", "delta": "..." }` | Streaming tool args |
| `tool_call_end` | `{ "toolCallId": "..." }` | Tool call finished |
| `tool_result` | `{ "toolCallId": "...", "result": "..." }` | Tool execution result |
| `code_execution` | `{ "code": "...", "output": "..." }` | Sandbox code execution |

---

## 3. Agent Types & Modules

The frontend should allow users to select from these 11 types. 

### No-Sandbox Type
- `chat`: Fast, cheap, for general questions.

### Sandbox Types (Advanced)
These will automatically spin up a sandbox environment:
- `general`: Default robust agent
- `deep_research`: For extensive web research
- `academic`: For writing papers/citations
- `dev`: Software engineering
- `design`: UI/UX tasks
- `data_scientist`: Analysis & Python plotting
- `slides`: Powerpoint generation
- `documents`: LaTeX/PDF generation
- `quant`: Financial analysis
- `excalidraw`: Diagram generation

---

## 4. REST API Endpoints

Use these for session management (listing history, etc.), NOT for the actual conversation.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/agent/chat-sessions` | List user's sessions |
| `GET` | `/api/v1/agent/chat-sessions/{uuid}` | Get specific session details |
| `POST` | `/api/v1/agent/chat-sessions` | Create new empty session |
| `DELETE` | `/api/v1/agent/chat-sessions/{uuid}` | Delete session |
| `GET` | `/api/v1/agent/chat-sessions/{uuid}/events` | Get chat history/messages |

---

## 5. Typical Frontend Flow

1. **User lands on page**: 
   - Call `GET /chat-sessions` to list history.
   - User clicks "New Chat" or selects existing.

2. **Session Initialization**:
   - if new: `POST /chat-sessions` → get UUID.
   - Connect Socket.IO.
   - Emit `join_session` with UUID.

3. **User Sends Message**:
   - User types "Analyze this data" + selects "Data Scientist" mode.
   - Emit `chat_message` with `agent_type="data_scientist"`.
   - Backend auto-starts sandbox (if needed) and streams response.

4. **Sandbox Services**:
   - If `agent_type` was a sandbox type, backend emits `sandbox_status`.
   - Frontend calls `awake_sandbox` command to get VS Code / Expo URLs.
   - Backend returns: `{ "vscode_url": "...", "mcp_url": "..." }`.
   - Frontend displays VS Code iframe.
