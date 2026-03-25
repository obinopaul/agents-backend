# Frontend-Backend Event Integration Documentation

## Overview

This document describes the robust event integration layer between the agents-backend (FastAPI/LangGraph) and the II-Agent frontend. The integration ensures seamless communication via WebSocket (Socket.IO) and SSE (Server-Sent Events) protocols.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           II-Agent Frontend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Chat Mode   │  │ Agent Mode  │  │ Tool UI     │  │ Progress    │    │
│  │ (SSE)       │  │ (WebSocket) │  │ Components  │  │ Indicators  │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Event Adapter Layer                              │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐    │
│  │  IIAgentSSEAdapter      │    │  IIAgentWebSocketAdapter        │    │
│  │  - Chat mode events     │    │  - Agent mode events            │    │
│  │  - SSE formatting       │    │  - Socket.IO formatting         │    │
│  └─────────────────────────┘    └─────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Backend Services                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Rate        │  │ Credit      │  │ Query       │  │ LangGraph   │    │
│  │ Limiter     │  │ Checker     │  │ Handler     │  │ Agents      │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Features Implemented

### 1. User Message Event Emission

**Purpose:** Immediately notify the frontend when a user's message is received, allowing instant UI updates.

**Location:** `backend/common/socketio/command/query_handler.py`

**Event Format:**
```json
{
  "type": "user_message",
  "content": {
    "text": "User's message text",
    "files": ["file_id_1", "file_id_2"]
  },
  "run_id": "uuid-string"
}
```

**Behavior:**
- Emitted immediately after the user message is stored in the database
- Emitted BEFORE agent processing begins
- Allows frontend to display the user's message in the chat history without waiting

---

### 2. WebSocket Rate Limiting

**Purpose:** Protect backend resources from abuse and ensure fair usage across users.

**Location:** `backend/common/socketio/rate_limiter.py`

**Architecture:**
```
┌─────────────────────────────────────────────────────┐
│              WebSocketRateLimiter                    │
│  ┌─────────────────┐    ┌─────────────────────┐    │
│  │ RedisRateLimiter │ ←→ │ InMemoryRateLimiter │    │
│  │ (Primary)        │    │ (Fallback)          │    │
│  └─────────────────┘    └─────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Rate Limit Configuration:**

| Scope | Requests | Window | Description |
|-------|----------|--------|-------------|
| `messages` | 100 | 60s | General messages (pings, status) |
| `queries` | 10 | 60s | Agent queries (expensive) |
| `sandbox_ops` | 5 | 60s | Sandbox operations |
| `enhance_prompt` | 20 | 60s | LLM prompt enhancement |
| `file_upload` | 10 | 60s | File upload operations |

**Message Type to Scope Mapping:**
```python
MESSAGE_TYPE_TO_SCOPE = {
    "query": "queries",
    "cancel": "messages",
    "ping": "messages",
    "sandbox_status": "sandbox_ops",
    "awake_sandbox": "sandbox_ops",
    "workspace_info": "messages",
    "enhance_prompt": "enhance_prompt",
    "publish": "queries",
}
```

**Error Response Format:**
```json
{
  "type": "error",
  "content": {
    "message": "Rate limit exceeded. Please wait before sending more messages.",
    "error_type": "rate_limit",
    "retry_after_ms": 5000,
    "limit_type": "per_user",
    "current_usage": {
      "requests": 10,
      "limit": 10,
      "scope": "queries"
    }
  }
}
```

**Configuration (in `backend/core/conf.py`):**
```python
# WebSocket Rate Limiting
WS_RATE_LIMIT_ENABLED: bool = True
WS_RATE_LIMIT_REDIS_PREFIX: str = 'agents_backend:ws:limiter'
```

---

### 3. Tool Display Names

**Purpose:** Provide human-readable names for tools displayed in the frontend UI.

**Location:** `backend/app/agent/event_adapter.py`

**Mapping Examples:**
```python
TOOL_DISPLAY_NAMES = {
    # Common tools
    "web_search": "Searching Web",
    "browser_use": "Using Browser",
    "bash": "Running Command",
    "read": "Reading File",
    "write": "Writing File",
    "edit": "Editing File",

    # MCP tools
    "mcp_codex_execute": "Running Codex",
    "mcp_browser_navigate": "Navigating Browser",

    # Research tools
    "arxiv_search": "Searching arXiv",
    "pubmed_search": "Searching PubMed",

    # And 40+ more...
}
```

**Tool Call Event Format (with display name):**
```json
{
  "type": "tool_call",
  "content": {
    "status": "start",
    "tool_name": "web_search",
    "tool_display_name": "Searching Web",
    "tool_call_id": "tc-123"
  }
}
```

**Humanization Logic:**
1. Check exact match in `TOOL_DISPLAY_NAMES`
2. For MCP tools (`mcp_*`), strip prefix and check again
3. Fall back to title-casing with underscores replaced by spaces

---

### 4. Credit Checking Before Agent Runs

**Purpose:** Validate user has sufficient credits and model access before executing expensive agent operations.

**Location:** `backend/common/socketio/command/query_handler.py`

**Flow:**
```
User Query → Get User UUID → Check Billing Access → Run Agent (if allowed)
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ BillingIntegration │
                           │ - Model access    │
                           │ - Credit balance  │
                           │ - Daily refresh   │
                           └─────────────────┘
```

**Checks Performed:**
1. **User Account Exists:** Validates user UUID can be retrieved
2. **Model Access:** Verifies subscription tier allows requested model
3. **Credit Balance:** Ensures sufficient credits for operation

**Error Event Format (billing_error):**
```json
{
  "type": "billing_error",
  "content": {
    "message": "Insufficient credits. Required: $0.50, Available: $0.25",
    "error_type": "insufficient_credits",
    "details": {
      "tier_name": "free",
      "error_type": "insufficient_credits"
    }
  },
  "run_id": "uuid"
}
```

**Error Types:**
- `no_account`: User has no billing account
- `model_access_denied`: Subscription doesn't include requested model
- `insufficient_credits`: Not enough credits for operation

**Fail-Open Behavior:**
If the billing system encounters an error (not a validation failure), the operation is allowed to proceed. This prevents blocking users due to temporary system issues.

---

### 5. Sub-Agent Complete Events

**Purpose:** Notify frontend when sub-agents (specialized workers) complete their tasks.

**Location:**
- Detection: `backend/app/agent/api/v1/agent.py`
- Transformation: `backend/app/agent/event_adapter.py`

**Sub-Agent Detection Logic:**
```python
is_subagent = (
    "subagent" in chain_name.lower() or
    "compiled" in chain_name.lower() or
    any("subagent" in tag.lower() for tag in chain_tags) or
    chain_name in ["planner", "analyzer", "coder", "executor",
                   "verifier", "researcher", "debugger", "reviewer"]
)
```

**Event Format:**
```json
{
  "type": "sub_agent_complete",
  "content": {
    "text": "Analysis complete: Found 3 key insights...",
    "chain_name": "analyzer",
    "thread_id": "session-uuid"
  },
  "run_id": "uuid"
}
```

**Use Cases:**
- Deep research modules with multiple specialized agents
- Data scientist workflows with planner/coder/executor agents
- Academic research with parallel analysis sub-agents

---

### 6. Tool Progress Events

**Purpose:** Provide progress updates for long-running tool operations.

**Location:** `backend/app/agent/event_adapter.py`

**Event Format:**
```json
{
  "type": "tool_progress",
  "content": {
    "status": "progress",
    "tool_call_id": "tc-123",
    "tool_name": "web_search",
    "tool_display_name": "Searching Web",
    "progress_percentage": 50,
    "status_message": "Processing result 5/10",
    "current_step": 5,
    "total_steps": 10,
    "metadata": {}
  },
  "run_id": "uuid"
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `tool_call_id` | string | Identifier for the tool invocation |
| `tool_name` | string | Internal tool name |
| `tool_display_name` | string | Human-readable name |
| `progress_percentage` | int | 0-100 completion percentage |
| `status_message` | string | Human-readable status |
| `current_step` | int? | Current step number |
| `total_steps` | int? | Total number of steps |
| `metadata` | object? | Tool-specific additional data |

**Tools Recommended for Progress Events:**
- `web_search`: Multi-page search results
- `browser_use`: Multi-step browser automation
- `deep_research`: Long-running research operations
- `data_scientist`: Data analysis workflows
- `video_generate`: Video generation tasks

---

### 7. Complete Event Enhancement

**Purpose:** Provide comprehensive completion information including timing and usage statistics.

**Location:** `backend/app/agent/event_adapter.py`

**Event Format:**
```json
{
  "type": "complete",
  "content": {
    "status": "done",
    "message_id": "msg-uuid",
    "finish_reason": "end_turn",
    "elapsed_ms": 5234,
    "usage": {
      "input_tokens": 1500,
      "output_tokens": 800,
      "total_tokens": 2300
    }
  },
  "run_id": "uuid"
}
```

**Finish Reasons:**
| Reason | Description |
|--------|-------------|
| `end_turn` | Normal completion |
| `tool_use` | Stopped to use a tool |
| `interrupt` | Human-in-the-loop interrupt |
| `max_tokens` | Hit token limit |
| `cancelled` | User cancelled |

---

## Event Type Reference

### Full Event Type Mapping

**AG-UI Protocol → II-Agent WebSocket:**

| AG-UI Event | II-Agent Event | Description |
|-------------|----------------|-------------|
| `message_chunk` | `agent_response` | Streaming text response |
| `message` | `agent_response` | Complete text message |
| `reasoning_start` | `agent_thinking` | Start of reasoning |
| `reasoning_message_content` | `agent_thinking` | Reasoning content |
| `reasoning_end` | `agent_thinking` | End of reasoning |
| `tool_call_start` | `tool_call` | Tool invocation start |
| `tool_call_args` | `tool_call` | Tool arguments (streaming) |
| `tool_call_end` | `tool_call` | Tool invocation end |
| `tool_result` | `tool_result` | Tool execution result |
| `tool_progress` | `tool_progress` | Tool progress update |
| `status` | `status_update` | Status change |
| `error` | `error` | Error occurred |
| `interrupt` | `interrupt` | HITL interrupt |
| `complete` | `complete` | Stream complete |
| `sub_agent_complete` | `sub_agent_complete` | Sub-agent finished |

---

## Configuration

### Environment Variables

```bash
# Rate Limiting
WS_RATE_LIMIT_ENABLED=true
WS_RATE_LIMIT_REDIS_PREFIX=agents_backend:ws:limiter

# Billing (affects credit checking)
BILLING_ENABLED=true
ENV=production  # Set to 'local' to disable billing checks
```

### Redis Configuration

The rate limiter uses Redis for distributed rate limiting. If Redis is unavailable, it falls back to in-memory limiting.

```python
# Redis key pattern for rate limits
f"agents_backend:ws:limiter:{scope}:{identifier}"

# Example keys:
# agents_backend:ws:limiter:queries:user:123
# agents_backend:ws:limiter:messages:session:abc-def
```

---

## Integration Guide

### Frontend Event Handling

```typescript
// Example event handler for II-Agent frontend
socket.on('chat_event', (event) => {
  const { type, content, run_id } = event;

  switch (type) {
    case 'user_message':
      // Display user message immediately
      addMessage({ role: 'user', content: content.text });
      break;

    case 'agent_response':
      // Stream agent response
      appendToCurrentMessage(content.text);
      break;

    case 'tool_call':
      if (content.status === 'start') {
        showToolIndicator(content.tool_display_name);
      }
      break;

    case 'tool_progress':
      updateToolProgress(content.tool_call_id, content.progress_percentage);
      break;

    case 'tool_result':
      hideToolIndicator(content.tool_call_id);
      break;

    case 'billing_error':
      showBillingError(content.message, content.error_type);
      break;

    case 'complete':
      finalizeMessage(content.usage);
      break;

    case 'error':
      if (content.error_type === 'rate_limit') {
        showRateLimitWarning(content.retry_after_ms);
      } else {
        showError(content.error);
      }
      break;
  }
});
```

### Sending Messages

```typescript
// Send a query message
socket.emit('chat_message', {
  session_uuid: sessionId,
  type: 'query',
  content: {
    message: 'Analyze this data...',
    files: ['file-uuid-1'],
    agent_type: 'data_scientist',
    model_id: 'gpt-4',
    locale: 'en-US'
  }
});
```

---

## File Reference

| File | Purpose |
|------|---------|
| `backend/common/socketio/command/query_handler.py` | Main query handling, user message emission, credit checking |
| `backend/common/socketio/rate_limiter.py` | Rate limiting implementation |
| `backend/common/socketio/handlers.py` | Socket.IO event routing |
| `backend/app/agent/event_adapter.py` | Event transformation (AG-UI ↔ II-Agent) |
| `backend/app/agent/api/v1/agent.py` | Agent streaming, sub-agent detection |
| `backend/app/agent/api/v1/chat.py` | Chat mode streaming |
| `backend/src/billing/credits/integration.py` | Billing integration |

---

## Troubleshooting

### Rate Limit Issues

**Symptom:** User receives rate limit errors frequently
**Solution:**
1. Check Redis connectivity
2. Verify rate limit configuration in `rate_limiter.py`
3. Consider increasing limits for specific scopes

### Missing Events

**Symptom:** Frontend doesn't receive certain events
**Solution:**
1. Check EVENT_TYPE_MAP in `event_adapter.py`
2. Verify _transform_data handles the event type
3. Check WebSocket connection status

### Billing Check Failures

**Symptom:** All operations fail with billing errors
**Solution:**
1. Verify user has credit_accounts entry in database
2. Check BILLING_ENABLED setting
3. Review BillingIntegration logs

### Sub-Agent Events Not Firing

**Symptom:** Sub-agent completions not detected
**Solution:**
1. Verify `subgraphs=True` in astream_events call
2. Check chain names match detection patterns
3. Review agent module subagent definitions

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-25 | Initial implementation |

---

## Authors

Implementation by Claude Code (Anthropic)

---

## License

MIT License - See repository root for details.
