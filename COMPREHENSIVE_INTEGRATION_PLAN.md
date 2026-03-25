# Comprehensive Frontend-Backend Integration Plan

## Executive Summary

This document provides a complete analysis of integrating the II-Agent frontend with your custom LangChain/LangGraph backend. It covers the current state, gap analysis, and a detailed implementation roadmap.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Architecture Overview](#2-architecture-overview)
3. [Gap Analysis](#3-gap-analysis)
4. [Event Protocol Reference](#4-event-protocol-reference)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Detailed Implementation Tasks](#6-detailed-implementation-tasks)
7. [Testing Strategy](#7-testing-strategy)
8. [Risk Assessment](#8-risk-assessment)

---

## 1. Current State Analysis

### 1.1 What You Have Implemented

#### Backend Components (Completed)
| Component | File | Status |
|-----------|------|--------|
| Socket.IO Server | `backend/common/socketio/server.py` | ✅ Done |
| Session Store (Redis) | `backend/common/socketio/session_store.py` | ✅ Done |
| Chat Handler | `backend/common/socketio/handlers.py` | ✅ Done |
| Command Handler Factory | `backend/common/socketio/command/handler_factory.py` | ✅ Done |
| Query Handler | `backend/common/socketio/command/query_handler.py` | ✅ Done |
| Cancel Handler | `backend/common/socketio/command/cancel_handler.py` | ✅ Done |
| Ping Handler | `backend/common/socketio/command/ping_handler.py` | ✅ Done |
| Sandbox Status Handler | `backend/common/socketio/command/sandbox_status_handler.py` | ✅ Done |
| Awake Sandbox Handler | `backend/common/socketio/command/awake_sandbox_handler.py` | ✅ Done |
| Workspace Info Handler | `backend/common/socketio/command/workspace_info_handler.py` | ✅ Done |
| Enhance Prompt Handler | `backend/common/socketio/command/enhance_prompt_handler.py` | ✅ Done |
| Publish Handler | `backend/common/socketio/command/publish_handler.py` | ✅ Done |
| SSE Event Adapter | `backend/app/agent/event_adapter.py` | ✅ Done |
| Chat SSE Endpoint | `backend/app/agent/api/v1/chat.py` | ✅ Done |
| Agent SSE Endpoint | `backend/app/agent/api/v1/agent.py` | ✅ Done |

#### Adapter Implementation (Completed)
| Class | Purpose | Methods |
|-------|---------|---------|
| `IIAgentSSEAdapter` | SSE event transformation | `session_event`, `content_start/delta/stop`, `thinking_start/delta/stop`, `tool_call_start/delta/stop`, `tool_result`, `usage`, `complete`, `error`, `interrupt` |
| `IIAgentWebSocketAdapter` | WebSocket event transformation | `transform()`, `create_agent_initialized_event()`, `create_complete_event()` |

### 1.2 Frontend Expectations (From II-Agent)

The frontend expects two communication channels:

| Channel | Protocol | Use Case | Frontend Handler |
|---------|----------|----------|------------------|
| **WebSocket** | Socket.IO | Agent mode with sandbox | `use-app-events.tsx` |
| **SSE** | HTTP streaming | Chat mode (no sandbox) | `chat.service.ts` |

---

## 2. Architecture Overview

### 2.1 Communication Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (II-Agent React)                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────┐       ┌─────────────────────────────────────┐   │
│  │  CHAT MODE                │       │  AGENT MODE                         │   │
│  │  use-chat-transport.tsx   │       │  use-app-events.tsx                 │   │
│  │                           │       │                                     │   │
│  │  Events (SSE):            │       │  Events (WebSocket):                │   │
│  │  - session                │       │  - agent_initialized                │   │
│  │  - content (start/delta)  │       │  - user_message                     │   │
│  │  - thinking (delta)       │       │  - connection_established           │   │
│  │  - tool_call (lifecycle)  │       │  - processing                       │   │
│  │  - tool_result            │       │  - agent_thinking                   │   │
│  │  - usage                  │       │  - tool_call                        │   │
│  │  - complete               │       │  - tool_result                      │   │
│  │  - error                  │       │  - agent_response                   │   │
│  └────────────┬──────────────┘       │  - complete                         │   │
│               │                       │  - error                            │   │
│               │                       │  - system                           │   │
│               │                       │  - pong                             │   │
│               │                       │  - status_update                    │   │
│               │                       │  - sandbox_status                   │   │
│               │                       │  - upload_success                   │   │
│               │                       │  - prompt_generated                 │   │
│               │                       │  - sub_agent_complete               │   │
│               │                       │  - tool_progress                    │   │
│               │                       │  - model_compact                    │   │
│               │                       └──────────────┬──────────────────────┘   │
│               │                                      │                          │
└───────────────┼──────────────────────────────────────┼──────────────────────────┘
                │                                      │
                │ SSE                                  │ Socket.IO
                │ POST /agent/chat/stream             │ Namespace: /ws
                │                                      │
                ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (Your Project)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────┐       ┌─────────────────────────────────────┐   │
│  │  chat.py                  │       │  SocketIOChatManager               │   │
│  │  _astream_workflow_gen()  │       │  handlers.py                        │   │
│  │                           │       │                                     │   │
│  │  Uses:                    │       │  Command Handlers:                  │   │
│  │  - IIAgentSSEAdapter      │       │  - QueryHandler → _forward_sse()   │   │
│  │  - create_sse_adapter()   │       │  - CancelHandler                   │   │
│  │                           │       │  - PingHandler                     │   │
│  │  Emits SSE events:        │       │  - SandboxStatusHandler            │   │
│  │  event: content           │       │  - AwakeSandboxHandler             │   │
│  │  data: {...}              │       │  - WorkspaceInfoHandler            │   │
│  │                           │       │  - EnhancePromptHandler            │   │
│  └────────────┬──────────────┘       │  - PublishProjectHandler           │   │
│               │                       │                                     │   │
│               │                       │  Uses:                              │   │
│               │                       │  - IIAgentWebSocketAdapter         │   │
│               │                       │  - transform_sse_to_websocket()    │   │
│               │                       └──────────────┬──────────────────────┘   │
│               │                                      │                          │
│               └──────────────────────┬───────────────┘                          │
│                                      │                                          │
│                                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                    LangGraph Agent Execution                              │  │
│  │                                                                           │  │
│  │  ModuleRegistry → graph.astream_events()                                 │  │
│  │                                                                           │  │
│  │  Modules: general, deep_research, academic, design, dev,                 │  │
│  │           data_scientist, slides, documents, quant, excalidraw           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Gap Analysis

### 3.1 Missing Events in Your Implementation

Based on comparing II-Agent's expected events vs your current implementation:

#### WebSocket Events - Missing or Incomplete

| Event | Status | Issue |
|-------|--------|-------|
| `user_message` | ⚠️ Partial | Not emitted after receiving user input |
| `agent_thinking` | ⚠️ Partial | Need to verify reasoning is being transformed |
| `sub_agent_complete` | ❌ Missing | Not emitted when sub-agents complete |
| `tool_progress` | ❌ Missing | Not emitted for long-running tools |
| `model_compact` | ❌ Missing | Not emitted when context is compacted |
| `browser_use` | ❌ Missing | Not emitted for browser tool actions |
| `file_edit` | ❌ Missing | Not emitted for file modification actions |
| `upload_success` | ⚠️ Partial | Need to verify file upload events |
| `workspace_info` | ⚠️ Partial | Need to verify workspace info is emitted |

#### SSE Events - Status

| Event | Status | Notes |
|-------|--------|-------|
| `session` | ✅ Done | Via adapter.session_event() |
| `content` | ✅ Done | Via adapter.content_start/delta/stop() |
| `thinking` | ✅ Done | Via adapter.thinking_start/delta/stop() |
| `tool_call` | ✅ Done | Via adapter.tool_call_start/delta/stop() |
| `tool_result` | ✅ Done | Via adapter.tool_result() |
| `usage` | ✅ Done | Via adapter.usage() |
| `complete` | ✅ Done | Via adapter.complete() |
| `error` | ✅ Done | Via adapter.error() |
| `interrupt` | ✅ Done | Via adapter.interrupt() (HITL) |

### 3.2 Missing Features

| Feature | Priority | Description |
|---------|----------|-------------|
| **Rate Limiting** | High | No rate limiter for WebSocket/SSE |
| **Event Deduplication** | Medium | Same event may be sent twice (original + transformed) |
| **User Message Echo** | High | Frontend expects USER_MESSAGE event after query |
| **Sub-agent Tracking** | Medium | No tracking of sub-agent hierarchy |
| **Credit Checking** | High | Need credit validation before agent runs |
| **Metrics Tracking** | Medium | Token usage not being tracked/persisted |
| **Run Task Tracking** | Medium | AgentRunTask not being created in DB |

### 3.3 Event Format Differences

Some events need additional fields to match II-Agent expectations:

```python
# Current tool_call event
{
    "tool_name": "...",
    "tool_call_id": "...",
    "tool_input": "..."
}

# II-Agent expects
{
    "tool_name": "...",
    "tool_display_name": "...",  # Human-readable name
    "tool_call_id": "...",
    "tool_input": {...}  # Parsed JSON object
}
```

---

## 4. Event Protocol Reference

### 4.1 WebSocket Events (Agent Mode)

#### Client → Server Events

| Event | Payload | Handler |
|-------|---------|---------|
| `join_session` | `{ session_uuid }` | `SocketIOChatManager.join_session()` |
| `leave_session` | `{ session_uuid }` | `SocketIOChatManager.leave_session()` |
| `chat_message` | `{ type, content, session_uuid }` | `CommandHandlerFactory.get_handler()` |

#### Server → Client Events (via `chat_event`)

| Type | Content | When Emitted |
|------|---------|--------------|
| `connection_established` | `{ message, session_id, workspace_path }` | After join_session |
| `system` | `{ message, session_id }` | Session created/joined |
| `processing` | `{ message, run_id, requires_sandbox }` | Query received |
| `user_message` | `{ text, file_ids? }` | After user sends message |
| `agent_initialized` | `{ session_id, sandbox_id, vscode_url, ... }` | Sandbox ready |
| `agent_thinking` | `{ status, text, thinking_id }` | Reasoning in progress |
| `tool_call` | `{ status, tool_name, tool_call_id, tool_input }` | Tool execution |
| `tool_result` | `{ tool_call_id, tool_name, result, is_error }` | Tool completed |
| `agent_response` | `{ text, message_id }` | Response text |
| `complete` | `{ status: "done", finish_reason }` | Stream finished |
| `status_update` | `{ status, message }` | Status change |
| `sandbox_status` | `{ status, vscode_url }` | Sandbox state change |
| `error` | `{ message, code }` | Error occurred |
| `pong` | `{}` | Response to ping |
| `prompt_generated` | `{ result }` | Prompt enhancement done |
| `sub_agent_complete` | `{ text }` | Sub-agent finished |
| `upload_success` | `{ files: [{path, saved_path}] }` | Files uploaded |
| `workspace_info` | `{ workspace_path, ... }` | Workspace details |

### 4.2 SSE Events (Chat Mode)

Format: `event: <type>\ndata: <json>\n\n`

| Event | Data Structure |
|-------|----------------|
| `session` | `{ status: "created"\|"existing", session_id, model_id, message_id }` |
| `content` | `{ status: "start"\|"delta"\|"stop", message_id, delta? }` |
| `thinking` | `{ status: "start"\|"delta"\|"stop", thinking_id, delta?, signature? }` |
| `tool_call` | `{ status: "start"\|"delta"\|"stop", id, name?, delta?, input?, type? }` |
| `tool_result` | `{ status: "info", tool_call_id, name, output, is_error }` |
| `usage` | `{ status: "info", input_tokens, output_tokens, total_tokens, ... }` |
| `complete` | `{ status: "done", message_id, finish_reason, elapsed_ms }` |
| `error` | `{ status: "error", error, code, message_id }` |
| `interrupt` | `{ status: "interrupt", id, content, options, context? }` |

---

## 5. Implementation Roadmap

### Phase 1: Critical Event Flow (Week 1)

| Task | Priority | Effort |
|------|----------|--------|
| 1.1 Add USER_MESSAGE event emission | P0 | 2h |
| 1.2 Verify session event emission | P0 | 1h |
| 1.3 Add complete event at end of streams | P0 | 2h |
| 1.4 Fix tool_call field names | P0 | 3h |
| 1.5 Add rate limiter middleware | P0 | 4h |

### Phase 2: State Management (Week 2)

| Task | Priority | Effort |
|------|----------|--------|
| 2.1 Implement AgentRunTask creation | P1 | 4h |
| 2.2 Add credit checking before runs | P1 | 4h |
| 2.3 Implement metrics tracking | P1 | 4h |
| 2.4 Add token usage persistence | P1 | 3h |
| 2.5 Remove duplicate event emission | P2 | 2h |

### Phase 3: Advanced Features (Week 3)

| Task | Priority | Effort |
|------|----------|--------|
| 3.1 Add sub_agent_complete events | P2 | 4h |
| 3.2 Add tool_progress events | P2 | 4h |
| 3.3 Add browser_use events | P2 | 2h |
| 3.4 Add file_edit events | P2 | 2h |
| 3.5 Add model_compact events | P3 | 2h |

### Phase 4: Frontend Integration (Week 4)

| Task | Priority | Effort |
|------|----------|--------|
| 4.1 Update frontend API_URL | P0 | 1h |
| 4.2 Test SSE chat flow end-to-end | P0 | 4h |
| 4.3 Test WebSocket agent flow end-to-end | P0 | 4h |
| 4.4 Fix any event parsing issues | P1 | Variable |
| 4.5 Test sandbox URLs in iframe | P1 | 2h |

---

## 6. Detailed Implementation Tasks

### 6.1 Task 1.1: Add USER_MESSAGE Event

**File:** `backend/common/socketio/command/query_handler.py`

**Current:**
```python
async def handle(self, content, session_uuid, user_id, sid):
    # ... validate and process
    await self.broadcast_to_session(
        session_uuid=session_uuid,
        event_type='processing',
        content={...}
    )
```

**Required:**
```python
async def handle(self, content, session_uuid, user_id, sid):
    message = content.get('message', '') or content.get('text', '')
    files = content.get('files', [])

    # Emit USER_MESSAGE event (frontend expects this)
    await self.broadcast_to_session(
        session_uuid=session_uuid,
        event_type='user_message',
        content={
            'text': message,
            'file_ids': files,
        },
        run_id=run_id
    )

    # Then emit processing
    await self.broadcast_to_session(
        session_uuid=session_uuid,
        event_type='processing',
        content={...}
    )
```

### 6.2 Task 1.4: Fix Tool Call Field Names

**File:** `backend/app/agent/event_adapter.py`

**Current IIAgentWebSocketAdapter._transform_data:**
```python
if new_type == "tool_call":
    return {
        "status": "start",
        "tool_name": data.get("toolCallName") or data.get("name", ""),
        "tool_call_id": data.get("toolCallId") or data.get("id", ""),
    }
```

**Required:**
```python
if new_type == "tool_call":
    tool_name = data.get("toolCallName") or data.get("name", "")
    return {
        "status": "start",
        "tool_name": tool_name,
        "tool_display_name": _humanize_tool_name(tool_name),  # Add this
        "tool_call_id": data.get("toolCallId") or data.get("id", ""),
    }

def _humanize_tool_name(name: str) -> str:
    """Convert tool_name to human-readable format."""
    # web_search -> Web Search
    # mcp_codex_execute -> Codex Execute
    return name.replace('_', ' ').replace('mcp ', '').title()
```

### 6.3 Task 1.5: Add Rate Limiter

**New File:** `backend/common/socketio/rate_limiter.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict
import asyncio

@dataclass
class RateLimiter:
    """Simple per-session rate limiter for WebSocket messages."""

    max_requests: int = 10  # Max requests per window
    window_seconds: int = 60  # Window size

    _windows: Dict[str, list] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check_rate_limit(self, session_id: str) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        async with self._lock:
            now = datetime.now()
            window_start = now - timedelta(seconds=self.window_seconds)

            # Get or create window
            if session_id not in self._windows:
                self._windows[session_id] = []

            # Clean old requests
            self._windows[session_id] = [
                ts for ts in self._windows[session_id]
                if ts > window_start
            ]

            # Check limit
            if len(self._windows[session_id]) >= self.max_requests:
                return False

            # Record request
            self._windows[session_id].append(now)
            return True

# Global rate limiter
rate_limiter = RateLimiter()
```

**Update in query_handler.py:**
```python
from backend.common.socketio.rate_limiter import rate_limiter

async def handle(self, content, session_uuid, user_id, sid):
    # Check rate limit
    if not await rate_limiter.check_rate_limit(session_uuid):
        await self.send_error(
            room=sid,
            message="Rate limit exceeded. Please wait before sending more messages."
        )
        return

    # ... rest of handler
```

### 6.4 Task 2.2: Add Credit Checking

**Update in query_handler.py:**
```python
from backend.app.agent.service.credit_service import credit_service

async def handle(self, content, session_uuid, user_id, sid):
    # Check credits before running
    async with async_db_session() as db:
        has_credits = await credit_service.check_sufficient_credits(db, user_id)
        if not has_credits:
            await self.send_error(
                room=session_uuid,
                message="Insufficient credits. Please upgrade your plan.",
                error_type="insufficient_credits"
            )
            return

    # ... rest of handler
```

### 6.5 Task 3.1: Sub-agent Complete Events

**Update in _forward_sse_event:**
```python
async def _forward_sse_event(self, session_uuid, event_str, run_id):
    # ... existing code ...

    # Detect sub-agent completion
    if ws_event_type == "agent_response":
        text = ws_data.get("text", "")
        # Check for sub-agent completion markers
        if any(marker in text.lower() for marker in [
            "task completed",
            "sub agent completed",
            "research complete",
            "analysis complete"
        ]):
            # Emit sub_agent_complete event
            await self.broadcast_to_session(
                session_uuid=session_uuid,
                event_type='sub_agent_complete',
                content={'text': text},
                run_id=run_id
            )
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
# tests/test_event_adapter.py
import pytest
from backend.app.agent.event_adapter import IIAgentSSEAdapter, IIAgentWebSocketAdapter

def test_sse_adapter_session_event():
    adapter = IIAgentSSEAdapter(session_id="test-123", model_id="gpt-4")
    event = adapter.session_event(is_new=True)
    assert 'event: session' in event
    assert '"status": "created"' in event
    assert '"session_id": "test-123"' in event

def test_sse_adapter_content_lifecycle():
    adapter = IIAgentSSEAdapter(session_id="test-123")

    start = adapter.content_start()
    assert '"status": "start"' in start
    assert adapter.content_started == True

    delta = adapter.content_delta("Hello")
    assert '"delta": "Hello"' in delta

    stop = adapter.content_stop()
    assert '"status": "stop"' in stop

def test_websocket_adapter_transform():
    # Test message_chunk -> agent_response
    new_type, new_data = IIAgentWebSocketAdapter.transform(
        "message_chunk", {"content": "Hello world"}
    )
    assert new_type == "agent_response"
    assert new_data["text"] == "Hello world"

    # Test tool_call_start -> tool_call
    new_type, new_data = IIAgentWebSocketAdapter.transform(
        "tool_call_start", {"toolCallName": "web_search", "toolCallId": "tc-1"}
    )
    assert new_type == "tool_call"
    assert new_data["status"] == "start"
    assert new_data["tool_name"] == "web_search"
```

### 7.2 Integration Tests

```python
# tests/test_websocket_integration.py
import pytest
import socketio
from backend.main import app

@pytest.fixture
async def sio_client():
    client = socketio.AsyncClient()
    await client.connect(
        "http://localhost:8000/ws",
        auth={"token": "test-jwt-token"}
    )
    yield client
    await client.disconnect()

@pytest.mark.asyncio
async def test_join_session(sio_client):
    events_received = []

    @sio_client.on('chat_event')
    async def handler(data):
        events_received.append(data)

    await sio_client.emit('join_session', {'session_uuid': 'test-session-123'})
    await asyncio.sleep(0.5)

    # Should receive system and connection_established events
    assert len(events_received) >= 2
    types = [e['type'] for e in events_received]
    assert 'system' in types
    assert 'connection_established' in types

@pytest.mark.asyncio
async def test_query_message(sio_client):
    events_received = []

    @sio_client.on('chat_event')
    async def handler(data):
        events_received.append(data)

    await sio_client.emit('join_session', {'session_uuid': 'test-session-456'})
    await asyncio.sleep(0.5)

    await sio_client.emit('chat_message', {
        'type': 'query',
        'content': {
            'message': 'Hello, test message',
            'agent_type': 'chat'
        },
        'session_uuid': 'test-session-456'
    })

    await asyncio.sleep(2)  # Wait for processing

    types = [e['type'] for e in events_received]
    assert 'processing' in types or 'status_update' in types
```

### 7.3 End-to-End Testing Checklist

```markdown
## Chat Mode (SSE) Testing

- [ ] Create new chat session
  - [ ] Verify `session` event with `status: created`
  - [ ] Verify `session_id` is returned

- [ ] Send message
  - [ ] Verify `content` event with `status: start`
  - [ ] Verify streaming `content` deltas
  - [ ] Verify `content` event with `status: stop`

- [ ] Tool usage
  - [ ] Verify `tool_call` event with `status: start`
  - [ ] Verify `tool_call` delta events (arguments)
  - [ ] Verify `tool_call` event with `status: stop`
  - [ ] Verify `tool_result` event

- [ ] Reasoning/Thinking
  - [ ] Verify `thinking` event with `status: start`
  - [ ] Verify streaming `thinking` deltas
  - [ ] Verify `thinking` event with `status: stop`

- [ ] Completion
  - [ ] Verify `usage` event with token counts
  - [ ] Verify `complete` event with `status: done`

## Agent Mode (WebSocket) Testing

- [ ] Connect and join session
  - [ ] Verify Socket.IO connects
  - [ ] Verify `connection_established` event
  - [ ] Verify `system` event with session_id

- [ ] Send query
  - [ ] Verify `user_message` event
  - [ ] Verify `processing` event

- [ ] Sandbox initialization (if applicable)
  - [ ] Verify `agent_initialized` event
  - [ ] Verify `vscode_url` is valid
  - [ ] Verify sandbox iframe loads

- [ ] Agent response
  - [ ] Verify `agent_thinking` events
  - [ ] Verify `tool_call` events
  - [ ] Verify `tool_result` events
  - [ ] Verify `agent_response` events

- [ ] Completion
  - [ ] Verify `complete` event
  - [ ] Verify UI updates properly

- [ ] Cancellation
  - [ ] Send `cancel` message
  - [ ] Verify stream stops
  - [ ] Verify `cancelled` or `agent_response_interrupted` event

- [ ] Ping/Pong
  - [ ] Send `ping` message
  - [ ] Verify `pong` event received
```

---

## 8. Risk Assessment

### 8.1 High Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| Event format mismatch | Frontend doesn't display messages | Thorough testing with actual frontend |
| Missing events | UI incomplete/broken | Follow II-Agent event checklist |
| Rate limiting absent | DoS vulnerability | Implement before production |
| Credit checking absent | Revenue loss | Implement in Phase 2 |

### 8.2 Medium Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| Duplicate events | Minor UI glitches | Remove backward-compat emission later |
| Sub-agent tracking | Sub-agents not shown | Implement in Phase 3 |
| Metrics not tracked | No usage analytics | Implement in Phase 2 |

### 8.3 Low Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| Browser use events | Browser tool not tracked | Future enhancement |
| File edit events | File edits not shown | Future enhancement |
| Model compact events | Context not shown | Future enhancement |

---

## Appendix A: Quick Reference

### Frontend Files to Check

| File | Purpose |
|------|---------|
| `frontend/src/typings/agent.ts` | AgentEvent enum, TOOL enum |
| `frontend/src/typings/chat.ts` | ChatStreamEvent type |
| `frontend/src/hooks/use-app-events.tsx` | WebSocket event handlers |
| `frontend/src/hooks/use-chat-transport.tsx` | SSE event handlers |
| `frontend/src/services/chat.service.ts` | normalizeStreamEvent function |
| `frontend/src/contexts/websocket-context.tsx` | Socket.IO connection |

### Backend Files to Update

| File | Purpose |
|------|---------|
| `backend/app/agent/event_adapter.py` | Event transformation |
| `backend/common/socketio/command/query_handler.py` | Query processing |
| `backend/app/agent/api/v1/chat.py` | SSE streaming |
| `backend/app/agent/api/v1/agent.py` | Agent SSE streaming |

---

*Document Version: 1.0*
*Last Updated: January 25, 2026*
