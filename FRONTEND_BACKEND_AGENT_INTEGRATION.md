# Frontend-to-Backend Agent Integration Documentation

**II-Agent WebSocket System - Complete Reference**

This document provides a comprehensive mapping of the II-Agent WebSocket-based agent system, showing how the TypeScript frontend communicates with the Python backend via Socket.IO. Every event type, command, and agent feature is documented with code snippets from both sides.

**⚠️ Note:** This documentation covers the **WebSocket Agent System**. For the **SSE Chat System**, see `FRONTEND_BACKEND_CHAT_INTEGRATION.md`.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [WebSocket Connection & Lifecycle](#2-websocket-connection--lifecycle)
3. [Event System - Complete Mapping (25+ Events)](#3-event-system---complete-mapping)
4. [Command System - Complete Mapping (9+ Commands)](#4-command-system---complete-mapping)
5. [Agent Execution Flow](#5-agent-execution-flow)
6. [Event Streaming Architecture](#6-event-streaming-architecture)
7. [Sub-Agent System](#7-sub-agent-system)
8. [Sandbox Integration](#8-sandbox-integration)
9. [Authentication & Security](#9-authentication--security)
10. [State Management](#10-state-management)
11. [UI Components for Agent Features](#11-ui-components-for-agent-features)
12. [Deployment Integration](#12-deployment-integration)
13. [Advanced Features](#13-advanced-features)
14. [Error Handling & Recovery](#14-error-handling--recovery)
15. [Code Examples & Reference](#15-code-examples--reference)
16. [WebSocket vs SSE Comparison](#16-websocket-vs-sse-comparison)
17. [File Reference Index](#17-file-reference-index)
18. [Debugging & Troubleshooting](#18-debugging--troubleshooting)

---

## 1. Architecture Overview

### 1.1 Communication Protocol

**Transport:** Socket.IO (WebSocket with fallback to polling) - **NOT Server-Sent Events**

The II-Agent system uses **two separate communication channels**:

| System | Protocol | Purpose | File |
|--------|----------|---------|------|
| **Chat System** | SSE (Server-Sent Events) | Simple LLM chat responses | See `FRONTEND_BACKEND_CHAT_INTEGRATION.md` |
| **Agent System** | Socket.IO (WebSocket) | Complex agent orchestration, tools, sub-agents | **This document** |

**Why WebSocket for Agents?**

Socket.IO provides:
- ✅ **Bidirectional communication** - Server can push events AND client can send commands
- ✅ **Real-time updates** - Live status, progress, and results
- ✅ **Complex state management** - Agent hierarchy, tool execution, cancellation
- ✅ **Room-based isolation** - Multi-user session separation
- ✅ **Automatic reconnection** - Built-in fallback to long-polling
- ✅ **Event-based architecture** - 25+ specialized event types

### 1.2 Technology Stack

| Layer | Frontend | Backend |
|-------|----------|---------|
| **Language** | TypeScript | Python 3.11+ |
| **Framework** | React 18 | FastAPI |
| **WebSocket** | Socket.IO Client 4.x | python-socketio (AsyncServer) |
| **State Management** | Redux Toolkit | AsyncEventStream (pub/sub) |
| **Agent Orchestration** | Event handlers | AgentController |
| **Sandbox** | - | E2B Sandbox |
| **LLM Integration** | - | Anthropic, OpenAI, Gemini |

### 1.3 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React/TypeScript)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User Action → UI Component                                        │
│       │                                                             │
│       ├─ WebSocketContext.sendMessage()                            │
│       └─ socket.emit('chat_message', {type, content})              │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Socket.IO WebSocket
                             │ auth: {token, session_uuid}
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI/Python)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SocketIOManager.chat_message()                                    │
│       │                                                             │
│       ├─ CommandHandlerFactory.get_handler()                       │
│       │      │                                                      │
│       │      ├─ UserQueryHandler (query)                           │
│       │      ├─ CancelHandler (cancel)                             │
│       │      ├─ SandboxStatusHandler (sandbox_status)              │
│       │      └─ ... 6 more handlers                                │
│       │                                                             │
│       └─ Handler.handle(content, session)                          │
│              │                                                      │
│              └─ AgentController.run_impl()                         │
│                     │                                               │
│                     ├─ Emit: AGENT_INITIALIZED                     │
│                     ├─ Emit: PROCESSING                            │
│                     ├─ Emit: AGENT_THINKING                        │
│                     ├─ Loop: TOOL_CALL → Execute → TOOL_RESULT    │
│                     ├─ Emit: AGENT_RESPONSE                        │
│                     └─ Emit: COMPLETE                              │
│                            │                                        │
│                            └─ AsyncEventStream.publish()           │
│                                   │                                │
│                                   ├─ SocketIOSubscriber            │
│                                   ├─ DatabaseSubscriber            │
│                                   └─ MetricsSubscriber             │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Socket.IO Event Stream
                             │ emit('chat_event', {type, content})
                             │ room: session_id
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Event Processing)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  socket.on('chat_event', (data) => {...})                          │
│       │                                                             │
│       └─ useAppEvents.handleEvent()                                │
│              │                                                      │
│              └─ switch(event.type)                                 │
│                     ├─ AGENT_INITIALIZED → Reset state             │
│                     ├─ TOOL_CALL → Create ActionStep              │
│                     ├─ TOOL_RESULT → Update ActionStep            │
│                     ├─ AGENT_RESPONSE → Add message               │
│                     ├─ SUB_AGENT_COMPLETE → Pop agent stack       │
│                     └─ ... 20+ more event types                   │
│                            │                                        │
│                            └─ Redux dispatch + UI update           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.4 Key Components Map

#### Frontend Components:

**File:** `/frontend/src/contexts/websocket-context.tsx` (298 lines)
- `SocketIOProvider` - WebSocket connection management
- `useSocketIOContext` - Hook for accessing socket instance
- Connection states: CONNECTING, CONNECTED, DISCONNECTED

**File:** `/frontend/src/hooks/use-app-events.tsx` (1300+ lines)
- `useAppEvents()` - Main event handler with 25+ event cases
- Agent context tracking (activeAgentsRef, agentStackRef)
- Sub-agent hierarchy management
- Message state updates

**File:** `/frontend/src/typings/agent.ts` (289 lines)
- `AgentEvent` enum - 25+ event types
- `TOOL` enum - 138+ tool types
- `ActionStep` interface - Tool execution display
- `WebSocketConnectionState` enum

**File:** `/frontend/src/state/slice/agent.ts` (145 lines)
- Agent state management (Redux)
- Build steps, completion status, sandbox state

#### Backend Components:

**File:** `/src/ii_agent/server/socket/socketio.py` (290 lines)
- `SocketIOManager` - Connection, authentication, routing
- Event handlers: connect, disconnect, join_session, chat_message
- Session lifecycle management

**File:** `/src/ii_agent/core/event.py` (63 lines)
- `EventType` enum - 25+ event types
- `RealtimeEvent` model - Event data structure
- `AgentStatus` enum - READY, RUNNING, CANCELLED

**File:** `/src/ii_agent/controller/agent_controller.py` (600+ lines)
- `AgentController` - Main agent execution orchestrator
- `run_impl()` - Agent execution loop with event emission
- Tool execution, thinking, response handling

**File:** `/src/ii_agent/server/socket/command/` (9 handler files)
- Command handler implementations
- Factory pattern for handler dispatch

**File:** `/src/ii_agent/subscribers/` (3 subscriber files)
- `SocketIOSubscriber` - Broadcast to WebSocket rooms
- `DatabaseSubscriber` - Persist events to DB
- `MetricsSubscriber` - Track credits and tokens

### 1.5 Why WebSocket for Agents vs SSE for Chat?

| Feature | WebSocket (Agents) | SSE (Chat) |
|---------|-------------------|-----------|
| **Direction** | Bidirectional | Unidirectional (server→client) |
| **Complexity** | High (multi-turn, tools, sub-agents) | Low (streaming text) |
| **State** | Stateful (agent context, tool state) | Stateless (message stream) |
| **Commands** | 9 command types from client | Request-response only |
| **Events** | 25+ specialized events | 12 streaming events |
| **Cancellation** | Real-time abort with feedback | Stream close only |
| **Sub-agents** | Full hierarchy with nesting | N/A |
| **Tools** | Interactive execution with progress | Tool results in stream |
| **Use Case** | Complex agent workflows | Simple chat responses |

**Decision Matrix:**

- Use **SSE Chat** for: Simple Q&A, streaming text responses, tool-less conversations
- Use **WebSocket Agent** for: Multi-step workflows, browser automation, file editing, sub-agent coordination, real-time progress

---

## 2. WebSocket Connection & Lifecycle

### 2.1 Frontend Socket.IO Client Setup

**File:** `/frontend/src/contexts/websocket-context.tsx`

#### Connection Configuration

```typescript
const connectSocket = useCallback(() => {
    const token = localStorage.getItem(ACCESS_TOKEN)
    if (!token) {
        console.log('WebSocket: No token available, skipping connection')
        dispatch(setWsConnectionState(WebSocketConnectionState.DISCONNECTED))
        return
    }

    const socketOptions: Partial<ManagerOptions & SocketOptions> = {
        auth: { token },                          // JWT authentication
        transports: ['websocket', 'polling'],     // WebSocket with fallback
        timeout: 15000,                           // 15 second connection timeout
        reconnection: false                        // Manual reconnection only
    }

    // Optional: include session_uuid for reconnection
    if (sessionIdRef.current && !isFromNewQuestionRef.current) {
        (socketOptions.auth as Record<string, unknown>).session_uuid =
            sessionIdRef.current
    }

    const socketInstance = io(import.meta.env.VITE_API_URL, socketOptions)

    // Register event handlers...
}, [dispatch])
```

#### Event Handlers Registration

```typescript
// Connection established
socketInstance.on('connect', () => {
    console.log('Socket.IO connection established')
    dispatch(setWsConnectionState(WebSocketConnectionState.CONNECTED))

    // Auto-initialize session for new questions
    if (sessionIdRef.current &&
        !sessionInitializedRef.current &&
        isFromNewQuestionRef.current) {
        setTimeout(() => {
            socketInstance.emit('join_session', {
                session_uuid: sessionIdRef.current
            })
            sessionInitializedRef.current = true
        }, 100)
    }
})

// Main event receiver
socketInstance.on('chat_event', (data) => {
    try {
        handleEventRef.current({ ...data, id: Date.now().toString() })
    } catch (error) {
        console.error('Error handling Socket.IO event:', error)
    }
})

// Connection errors
socketInstance.on('connect_error', (error) => {
    console.log('Socket.IO connection error:', error)
    dispatch(setWsConnectionState(WebSocketConnectionState.DISCONNECTED))
    setSocket(null)
    connectionRef.current = null
})

// Disconnection
socketInstance.on('disconnect', (reason) => {
    console.log('Socket.IO connection closed:', reason)
    dispatch(setWsConnectionState(WebSocketConnectionState.DISCONNECTED))
    sessionInitializedRef.current = false
    setSocket(null)
    connectionRef.current = null
})
```

#### Sending Messages

```typescript
const sendMessage = useCallback(
    (payload: { type: string; content: WebSocketMessageContent }) => {
        if (!socket || !socket.connected) {
            toast.error('Socket.IO connection is not open. Please try again.')
            return false
        }

        // Include session_uuid in payload
        const messageWithSession = sessionIdRef.current
            ? { ...payload, session_uuid: sessionIdRef.current }
            : payload

        socket.emit('chat_message', messageWithSession)
        return true
    },
    [socket]
)
```

#### Session Joining

```typescript
const joinSession = useCallback(() => {
    if (!socket || !socket.connected) {
        console.error('Cannot initialize session: Socket not connected')
        return
    }

    console.log('Joining session...')
    socket.emit('join_session', {
        session_uuid: sessionIdRef.current
    })
    sessionInitializedRef.current = true
}, [socket])
```

### 2.2 Backend Socket.IO Server Setup

**File:** `/src/ii_agent/server/socket/socketio.py`

#### SocketIOManager Initialization

```python
class SocketIOManager:
    """Manages Socket.IO connections and their associated chat sessions."""

    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        self.sid_sesion_map: Dict[str, str] = {}  # socket_id → session_uuid
        self.command_factory = CommandHandlerFactory(sio=sio)

    def init(self):
        """Register all Socket.IO event handlers."""
        self.sio.event(self.connect)
        self.sio.event(self.disconnect)
        self.sio.on("join_session")(self.join_session)
        self.sio.on("chat_message")(self.chat_message)
        self.sio.on("leave_session")(self.leave_session)  # backward compatibility
```

### 2.3 Connection Handshake Sequence

```
┌──────────┐                                    ┌──────────┐
│ Frontend │                                    │ Backend  │
└────┬─────┘                                    └────┬─────┘
     │                                                │
     │ 1. io(url, {auth: {token, session_uuid}})    │
     ├───────────────────────────────────────────────>
     │                                                │
     │         2. Verify JWT token                   │
     │            ┌──────────────────────────────┐   │
     │            │ jwt_handler.verify_access_token() │
     │            └──────────────────────────────┘   │
     │                                                │
     │    3. Save session: {user_id, authenticated}  │
     │                                                │
     │ <──────────── 'connect' event ─────────────────┤
     │              (connection approved)             │
     │                                                │
     │ 4. emit('join_session', {session_uuid})       │
     ├───────────────────────────────────────────────>
     │                                                │
     │         5. Get/create SessionInfo             │
     │            Enter room: str(session_id)        │
     │            Add SID to session tracking        │
     │                                                │
     │ <──── 'chat_event' (CONNECTION_ESTABLISHED) ───┤
     │       data: {                                  │
     │         type: 'connection_established',        │
     │         content: {                             │
     │           message: 'Connected...',             │
     │           workspace_path: '/workspace'         │
     │         }                                      │
     │       }                                        │
     │                                                │
     │ <──── 'chat_event' (SYSTEM) ────────────────────┤
     │       data: {                                  │
     │         type: 'system',                        │
     │         content: {                             │
     │           message: 'Session created',          │
     │           session_id: 'uuid...'                │
     │         }                                      │
     │       }                                        │
     │                                                │
     │        ✓ Ready for commands                   │
     │                                                │
```

### 2.4 Authentication Mechanism

**Backend JWT Verification:**
**File:** `/src/ii_agent/server/socket/socketio.py` (lines 209-251)

```python
async def connect(self, sid, environ, auth):
    """Handle Socket.IO client connection."""
    logger.info(f"Socket.IO client connecting: {sid}")

    # Extract authentication info
    if not auth or "token" not in auth:
        logger.warning(
            f"Socket.IO connection rejected: No authentication token for {sid}"
        )
        return False

    auth_token = auth["token"]
    session_uuid_str = auth.get("session_uuid")

    # Try to authenticate
    try:
        # Verify the access token
        payload = jwt_handler.verify_access_token(auth_token)
        if payload:
            user_id = payload.get("user_id")
            logger.info(f"Socket.IO authenticated for user: {user_id}")

            await self.sio.save_session(
                sid,
                {
                    "user_id": user_id,
                    "session_uuid": session_uuid_str,
                    "authenticated": True,
                },
            )
            self.sid_sesion_map[sid] = session_uuid_str
            return True
        else:
            logger.warning(
                f"Socket.IO connection rejected: Invalid or expired token for {sid}"
            )
            return False
    except Exception as e:
        logger.error(
            f"Socket.IO connection rejected: Error verifying token for {sid}: {e}"
        )
        return False
```

**Authentication Flow:**
1. Client sends JWT token in `auth.token`
2. Backend calls `jwt_handler.verify_access_token()`
3. Token decoded, user_id extracted
4. Session saved with authenticated flag
5. Connection approved (return True) or rejected (return False)

### 2.5 Session Management

**Join Session Handler:**
**File:** `/src/ii_agent/server/socket/socketio.py` (lines 145-188)

```python
async def join_session(self, sid, data):
    """Join the session after connection is fully established."""
    try:
        # Get the stored session data
        session_data = await self.sio.get_session(sid)
        if not session_data or not session_data.get("authenticated"):
            logger.error(f"No valid session data found for {sid}")
            await self.sio.disconnect(sid)
            self.sid_sesion_map.pop(sid, None)
            return

        user_id = session_data.get("user_id")
        session_uuid_str = data.get("session_uuid")
        logger.info(f"Joining session for {session_uuid_str}, user: {user_id}")

        # Get or create session
        session_info: SessionInfo = await session_service.get_or_create_sessison(
            session_uuid=session_uuid_str, user_id=user_id
        )

        # Emit system event
        await self._emit_system_event(
            sid, "Session created", session_id=str(session_info.id)
        )

        logger.info(
            f"New chat session {session_info.id} created for user {user_id}: {sid}"
        )

        # Enter Socket.IO room (for session-based broadcasting)
        await self.sio.enter_room(sid, str(session_info.id))
        self.sid_sesion_map[sid] = str(session_info.id)

        # Add SID to session mapping (for tracking multiple connections)
        await session_store.add_sid_to_session(str(session_info.id), sid)

        logger.info(f"Socket {sid} joined room {session_info.id}")

        # Send handshake event
        await self._handshake(sid, session_info)
    except Exception as e:
        logger.error(f"Error initializing session for {sid}: {e}", exc_info=True)
        await self._emit_error(sid, f"Session initialization failed: {str(e)}")
        await self.sio.disconnect(sid)
```

**Room-Based Broadcasting:**

```
Session UUID: "abc-123-def-456"
        ↓
Socket.IO Room: "abc-123-def-456"
        ↓
Connected Sockets in Room:
  ├─ socket_1 (Browser Tab 1)
  ├─ socket_2 (Browser Tab 2)
  └─ socket_N (Browser Tab N)

When event published:
  sio.emit('chat_event', data, room="abc-123-def-456")
  → All sockets in room receive event
  → Perfect session isolation
```

---

### 2.6 Disconnection & Cleanup

**Disconnect Handler:**
**File:** `/src/ii_agent/server/socket/socketio.py` (lines 262-289)

```python
async def disconnect(self, sid: str):
    """Handle Socket.IO disconnection and cleanup."""
    logger.info(f"Socket.IO client disconnecting: {sid}")
    session_uuid = self.sid_sesion_map.pop(sid, None)

    try:
        if session_uuid:
            await self.sio.leave_room(sid, str(session_uuid))
            # Remove SID from session mapping
            await session_store.remove_sid_from_session(str(session_uuid), sid)
            await self.check_and_cleanup_session(str(session_uuid))

        await self.sio.disconnect(sid)

    except ValueError as e:
        logger.warning(f"Failed to leave room {session_uuid} for socket {sid}: {e}")
        # Continue with cleanup even if leaving room fails
```

**Sandbox Cleanup Strategy:**

```python
async def check_and_cleanup_session(self, session_uuid: str) -> None:
    """Check if session is empty and clean up sandbox if needed."""
    if not session_uuid:
        return
    
    is_empty = await session_store.is_session_empty(session_uuid)
    if is_empty:
        # Check for running tasks
        run_task = await AgentRunTask.find_last_by_session_id_and_status(
            db=db, session_id=session_id, status=RunStatus.RUNNING
        )
        
        if run_task:
            # Calculate time-to-live based on how long task has been running
            running_delta = datetime.now(timezone.utc) - run_task.created_at
            ttl = max(
                2 * 60 * 60,  # Minimum 2 hours
                int(3 * 60 * 60 - running_delta.total_seconds()),  # Up to 3 hours total
            )
            
            # Schedule sandbox cleanup
            await sandbox_service.cleanup_sandbox_for_session(
                session_uuid=session_id, time_til_clean_up=ttl
            )
```

**Cleanup Flow:**
```
1. Client disconnects (tab close, network loss, etc.)
   ↓
2. Remove socket from room
   ↓
3. Remove SID from session tracking
   ↓
4. Check if session has any remaining connections
   ↓
5. If empty AND has running task:
   - Calculate TTL (2-3 hours based on task runtime)
   - Schedule sandbox cleanup
   ↓
6. Sandbox cleaned up after TTL expires
```

---

## 3. Event System - Complete Mapping (25+ Events)

The WebSocket agent system uses **25+ specialized event types** for real-time communication. This section documents every event with complete frontend-backend mapping.

### 3.1 Event Type Overview Table

| # | Event Type | Frontend | Backend | Trigger | Frequency | Critical |
|---|------------|----------|---------|---------|-----------|----------|
| 1 | CONNECTION_ESTABLISHED | ✅ | ✅ | Socket handshake | Once per connection | Yes |
| 2 | AGENT_INITIALIZED | ✅ | ✅ | Agent creation | Once per query | Yes |
| 3 | USER_MESSAGE | ✅ | ✅ | User submits message | Once per query | Yes |
| 4 | PROCESSING | ✅ | ✅ | Query starts | Once per query | No |
| 5 | AGENT_THINKING | ✅ | ✅ | Model reasoning | Many (streaming) | No |
| 6 | TOOL_CALL | ✅ | ✅ | Tool invocation | Once per tool | Yes |
| 7 | TOOL_RESULT | ✅ | ✅ | Tool completion | Once per tool | Yes |
| 8 | TOOL_PROGRESS | ✅ | ✅ | Tool progress | Many (Codex) | No |
| 9 | AGENT_RESPONSE | ✅ | ✅ | LLM text response | Once per turn | Yes |
| 10 | AGENT_RESPONSE_INTERRUPTED | ✅ | ✅ | Cancellation | Once if cancelled | Yes |
| 11 | COMPLETE | ✅ | ✅ | Task completion | Once per query | Yes |
| 12 | STREAM_COMPLETE | ✅ | ✅ | Stream end | Once per query | No |
| 13 | SUB_AGENT_COMPLETE | ✅ | ✅ | Sub-agent done | Once per sub-agent | Yes |
| 14 | STATUS_UPDATE | ✅ | ✅ | Status change | Many | Yes |
| 15 | ERROR | ✅ | ✅ | Error occurs | As needed | Yes |
| 16 | SYSTEM | ✅ | ✅ | System message | As needed | Yes |
| 17 | WORKSPACE_INFO | ✅ | ✅ | Workspace query | Once on request | No |
| 18 | SANDBOX_STATUS | ✅ | ✅ | Sandbox query | Once on request | No |
| 19 | BROWSER_USE | ✅ | ✅ | Browser tool | Future | No |
| 20 | FILE_EDIT | ✅ | ✅ | File edit tool | Future | No |
| 21 | UPLOAD_SUCCESS | ✅ | ✅ | File uploaded | Once per file | Yes |
| 22 | PROMPT_GENERATED | ✅ | ✅ | Prompt enhanced | Once on request | No |
| 23 | PONG | ✅ | ✅ | Ping response | On ping | No |
| 24 | METRICS_UPDATE | ✅ | ✅ | Token usage | Once per turn | No |
| 25 | MODEL_COMPACT | ✅ | ✅ | Context compact | As needed | No |
| 26 | TOOL_CONFIRMATION | ✅ | ✅ | Tool confirm | Future/Reserved | No |

---

### 3.2 Event: CONNECTION_ESTABLISHED

**Purpose:** Notifies client that WebSocket connection is established and session is ready.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:15`

```typescript
export enum AgentEvent {
    CONNECTION_ESTABLISHED = 'connection_established',
    // ... other events
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:15`

```python
class EventType(str, Enum):
    CONNECTION_ESTABLISHED = "connection_established"
    # ... other events
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/socketio.py:191-199`

```python
async def _handshake(self, sid, session_info: SessionInfo):
    """Handle handshake message."""
    await self._emit_chat_event(
        room=str(sid),
        event_type=EventType.CONNECTION_ESTABLISHED,
        content={
            "message": "Connected to Agent WebSocket Server",
            "workspace_path": config.workspace_path,
        },
    )
```

#### Payload Structure

**TypeScript:**
```typescript
{
    type: 'connection_established'
    content: {
        message: string
        workspace_path: string
    }
}
```

**Python:**
```python
RealtimeEvent(
    type=EventType.CONNECTION_ESTABLISHED,
    session_id=session_info.id,
    content={
        "message": "Connected to Agent WebSocket Server",
        "workspace_path": "/workspace/path"
    }
)
```

#### Wire Format
```json
{
    "type": "connection_established",
    "content": {
        "message": "Connected to Agent WebSocket Server",
        "workspace_path": "/home/user/workspace"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/contexts/websocket-context.tsx:147-150`

Socket connection handler (no explicit event handler needed - automatic state update)

#### When Emitted
- After successful `join_session` 
- Before any other events
- Once per WebSocket connection

#### UI Impact
- Confirms connection is ready
- Displays workspace path (if needed)
- Enables chat interface

---

### 3.3 Event: AGENT_INITIALIZED

**Purpose:** Signals that the agent has been initialized and is ready to execute.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:17`

```typescript
export enum AgentEvent {
    AGENT_INITIALIZED = 'agent_initialized',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:17`

```python
class EventType(str, Enum):
    AGENT_INITIALIZED = "agent_initialized"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/command/query_handler.py:66-75`

```python
async def _send_agent_initialized_event(
    self,
    session_info: SessionInfo,
    vscode_url: Optional[str] = None,
) -> None:
    await self.send_event(
        RealtimeEvent(
            type=EventType.AGENT_INITIALIZED,
            session_id=session_info.id,
            content={
                "message": "Agent initialized",
                "vscode_url": vscode_url,
            },
        )
    )
```

#### Payload Structure

**Wire Format:**
```json
{
    "type": "agent_initialized",
    "content": {
        "message": "Agent initialized",
        "vscode_url": "https://sandbox.e2b.dev:12345"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:149-166`

```typescript
case AgentEvent.AGENT_INITIALIZED: {
    // Reset agent tracking for fresh conversation
    dispatch(setAgentInitialized(true))
    
    // Clear tracking state
    activeAgentsRef.current.clear()
    agentStackRef.current = []
    agentStartTimeRef.current = Date.now()
    
    // Set VSCode URL from payload
    const vsCodeUrl = extractString(content, 'vscode_url')
    if (vsCodeUrl) {
        dispatch(setVsCodeUrl(vsCodeUrl))
    }
    
    // Clear fullstack project and deployment state
    dispatch(setFullstackProjectInitialized(false))
    dispatch(setPublished(null))
    break
}
```

#### When Emitted
- After query handler creates AgentController
- Before agent execution starts
- Once per query

#### UI Impact
- Resets conversation state
- Displays "Agent initialized" status
- Shows VSCode IDE link (if sandbox enabled)
- Clears previous agent context

---

### 3.4 Event: USER_MESSAGE

**Purpose:** Records the user's submitted message/query.

#### Backend Emission
**File:** `src/ii_agent/server/socket/command/query_handler.py:267-280`

```python
await self.send_event(
    RealtimeEvent(
        type=EventType.USER_MESSAGE,
        session_id=session_info.id,
        run_id=run_id,
        content={
            "text": content.text,
            "files": content.files,  # File IDs only
        },
    )
)
```

#### Payload Structure

```json
{
    "type": "user_message",
    "content": {
        "text": "Can you help me build a website?",
        "files": ["file_id_1", "file_id_2"]
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:278-299`

```typescript
case AgentEvent.USER_MESSAGE: {
    const text = extractString(content, 'text')
    const files = content.files as string[] | undefined
    
    // Create user message
    const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: text,
        createdAt: new Date().toISOString(),
        files: files,
        parts: [{ type: 'text', text }]
    }
    
    // Add to messages (avoid duplicates)
    dispatch(addMessage(userMessage))
    dispatch(setCompleted(false))
    break
}
```

#### Database Storage
**File:** `src/ii_agent/subscribers/database_subscriber.py`

USER_MESSAGE events are **NOT** saved to database (excluded in filter)

#### When Emitted
- After query command received
- Before agent processing starts
- Once per query

#### UI Impact
- Adds user message bubble to chat
- Displays attached files
- Marks conversation as active

---

### 3.5 Event: PROCESSING

**Purpose:** Signals that the agent has started processing the user's query.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:18`

```typescript
export enum AgentEvent {
    // ...
    PROCESSING = 'processing',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:19`

```python
class EventType(str, Enum):
    # ...
    PROCESSING = "processing"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/command/query_handler.py:78-87`

```python
# Emit PROCESSING event before starting agent execution
await self.sio.emit(
    "chat_event",
    {
        "type": EventType.PROCESSING,
        "content": {},
    },
    room=str(session_info.id),
)
```

#### Payload Structure

```json
{
    "type": "processing",
    "content": {}
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:307-314`

```typescript
case AgentEvent.PROCESSING: {
    const isShareMode = location.pathname?.includes('/share/')
    if (isShareMode) {
        dispatch(setLoading(true))
    }
    dispatch(setStopped(false))
    break
}
```

#### Database Storage
**File:** `src/ii_agent/subscribers/database_subscriber.py`

PROCESSING events are **NOT** saved to database (excluded in filter)

#### When Emitted
- After USER_MESSAGE event
- Before agent starts thinking/tool execution
- Once per query

#### UI Impact
- Sets loading state in share mode
- Marks conversation as active (not stopped)
- Shows processing indicator

---

### 3.6 Event: AGENT_THINKING

**Purpose:** Streams the agent's thinking/reasoning process in real-time.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:19`

```typescript
export enum AgentEvent {
    // ...
    AGENT_THINKING = 'agent_thinking',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:20`

```python
class EventType(str, Enum):
    # ...
    AGENT_THINKING = "agent_thinking"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:159-171`

```python
# During LLM streaming, thinking blocks are emitted
if text_result:
    await self.event_stream.publish(
        RealtimeEvent(
            type=EventType.AGENT_THINKING,
            session_id=self.session_id,
            run_id=self.run_id,
            content={"text": text_result.text},
        )
    )
```

#### Payload Structure

```json
{
    "type": "agent_thinking",
    "content": {
        "text": "I need to analyze the user's request and determine the best approach..."
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:316-335`

```typescript
case AgentEvent.AGENT_THINKING: {
    const currentAgentId =
        agentStackRef.current[agentStackRef.current.length - 1] || mainAgentId.current
    const agentContext = activeAgentsRef.current.get(currentAgentId)

    safeDispatch(
        addMessage({
            id: data.id,
            role: 'assistant',
            content: data.content.text as string,
            timestamp: Date.now(),
            isThinkMessage: true,
            agentContext
        })
    )
    break
}
```

#### Database Storage
Database subscriber saves AGENT_THINKING events with the thinking text content.

#### When Emitted
- During LLM streaming when model generates thinking/reasoning blocks
- Can be emitted multiple times during a single turn
- Associated with current agent context (main or sub-agent)

#### UI Impact
- Displays thinking message in collapsible section
- Marked with special `isThinkMessage` flag
- Shows reasoning process to user
- Associated with current agent in hierarchy

---

### 3.7 Event: TOOL_CALL

**Purpose:** Signals that the agent is invoking a tool with specific parameters.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:20`

```typescript
export enum AgentEvent {
    // ...
    TOOL_CALL = 'tool_call',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:21`

```python
class EventType(str, Enum):
    # ...
    TOOL_CALL = "tool_call"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:273-285`

```python
# For each tool call in the batch
for tool_call in pending_tool_calls:
    try:
        tool = self.tool_manager.get_tool(tool_call.tool_name)
    except ValueError as e:
        logger.warning(f"Tool lookup failed: {str(e)}")
        continue

    await self.event_stream.publish(
        RealtimeEvent(
            type=EventType.TOOL_CALL,
            session_id=self.session_id,
            run_id=self.run_id,
            content={
                "tool_call_id": tool_call.tool_call_id,
                "tool_name": tool_call.tool_name,
                "tool_input": tool_call.tool_input,
                "tool_display_name": tool.display_name,
            },
        )
    )
```

#### Payload Structure

```json
{
    "type": "tool_call",
    "content": {
        "tool_call_id": "toolu_01ABC123",
        "tool_name": "Bash",
        "tool_display_name": "Bash Command",
        "tool_input": {
            "command": "ls -la",
            "description": "List files in current directory"
        }
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:337-498`

This is the most complex handler, managing:

```typescript
case AgentEvent.TOOL_CALL: {
    // 1. Determine current agent context
    const currentAgentId =
        agentStackRef.current[agentStackRef.current.length - 1] || mainAgentId.current
    let agentContext = activeAgentsRef.current.get(currentAgentId)

    // 2. Check if this is a subagent tool call
    const isSubagentTool =
        data.content.tool_name === TOOL.SUB_AGENT ||
        data.content.tool_name === TOOL.SUB_AGENT_RESEARCHER ||
        data.content.tool_name === TOOL.DESIGN_DOCUMENT_AGENT ||
        data.content.tool_name === TOOL.TASK ||
        data.content.tool_name === TOOL.CODEX_AGENT ||
        (data.content.tool_name as string).toString().startsWith(TOOL.SUB_AGENT.toString())

    // 3. Create new agent context for sub-agents
    if (isSubagentTool) {
        const agentName = (data.content.tool_display_name || data.content.tool_name) as string
        const toolCallId = data.content.tool_call_id as string | undefined

        // Generate unique sub-agent ID
        const subagentId = generateSubagentId(parentContext, agentName, toolCallId)

        // Create new agent context
        const newAgentContext: AgentContext = {
            agentId: subagentId,
            agentType: 'subagent',
            agentName: String(agentName),
            parentAgentId: parentContext.agentId,
            nestingLevel: parentContext.nestingLevel + 1,
            startTime: Date.now(),
            status: 'running'
        }

        activeAgentsRef.current.set(subagentId, newAgentContext)
        agentStackRef.current.push(subagentId)
        agentContext = newAgentContext
    }

    // 4. Handle special tools
    if (data.content.tool_name === TOOL.SEQUENTIAL_THINKING) {
        // Display thought as a message
        safeDispatch(addMessage({
            id: data.id,
            role: 'assistant',
            content: (data.content.tool_input as { thought: string }).thought,
            timestamp: Date.now(),
            agentContext
        }))
    } else if (data.content.tool_name === TOOL.MESSAGE_USER) {
        // No-op, content emitted on TOOL_RESULT
    } else {
        // 5. Regular tool call - create action message
        const message: Message = {
            id: data.id,
            role: 'assistant',
            action: {
                type: data.content.tool_name as TOOL,
                data: {
                    ...data.content,
                    agentContext
                }
            },
            timestamp: Date.now(),
            agentContext
        }

        safeDispatch(addMessage(message))
        handleClickAction(message.action)
    }
    break
}
```

#### Database Storage
Database subscriber saves TOOL_CALL events with full tool call details.

#### When Emitted
- After agent decides to use a tool
- Before tool execution starts
- Can be emitted multiple times in a batch

#### UI Impact
- Creates action message with tool icon and parameters
- For sub-agent tools: Creates new agent context and pushes to stack
- For SEQUENTIAL_THINKING: Displays thought as text message
- For MESSAGE_USER: Waits for TOOL_RESULT to display
- Triggers action handler (opens file viewer, browser, etc.)

---

### 3.8 Event: TOOL_RESULT

**Purpose:** Returns the result of tool execution back to the agent and user.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:21`

```typescript
export enum AgentEvent {
    // ...
    TOOL_RESULT = 'tool_result',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:22`

```python
class EventType(str, Enum):
    # ...
    TOOL_RESULT = "tool_result"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:306-311`

```python
# After tool execution completes
if approved_tool_calls:
    tool_results = await self.tool_manager.run_tools_batch(approved_tool_calls)

    for tool_call, tool_result in zip(approved_tool_calls, tool_results):
        await self.add_tool_call_result(tool_call, tool_result)
        # add_tool_call_result emits TOOL_RESULT event internally
```

**File:** `src/ii_agent/controller/agent_controller.py` (add_tool_call_result method)

```python
async def add_tool_call_result(self, tool_call: ToolCall, tool_result: ToolResult):
    """Add tool call result to history and emit event."""
    await self.event_stream.publish(
        RealtimeEvent(
            type=EventType.TOOL_RESULT,
            session_id=self.session_id,
            run_id=self.run_id,
            content={
                "tool_call_id": tool_call.tool_call_id,
                "tool_name": tool_call.tool_name,
                "result": tool_result.user_display_content,
            },
        )
    )
```

#### Payload Structure

```json
{
    "type": "tool_result",
    "content": {
        "tool_call_id": "toolu_01ABC123",
        "tool_name": "Bash",
        "result": "total 48\ndrwxr-xr-x  12 user  staff   384 Jan 24 10:30 .\ndrwxr-xr-x   8 user  staff   256 Jan 23 14:20 .."
    }
}
```

For MESSAGE_USER tool:

```json
{
    "type": "tool_result",
    "content": {
        "tool_call_id": "toolu_01XYZ789",
        "tool_name": "message_user",
        "result": {
            "action": {
                "text": "I've completed the task!",
                "attachments": [
                    {
                        "type": "image",
                        "url": "https://example.com/result.png"
                    }
                ]
            }
        }
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:505-700`

```typescript
case AgentEvent.TOOL_RESULT: {
    const currentAgentId =
        agentStackRef.current[agentStackRef.current.length - 1] || mainAgentId.current
    let agentContext = activeAgentsRef.current.get(currentAgentId)

    // Special handling for MESSAGE_USER tool
    if (data.content.tool_name === TOOL.MESSAGE_USER) {
        const resultPayload = data.content.result as { action?: Record<string, unknown> }
        const action = (resultPayload?.action || {}) as Record<string, unknown>
        const messageText = typeof action.text === 'string' ? action.text : ''

        const attachments = Array.isArray(action.attachments)
            ? normalizeAttachments(action.attachments)
            : []

        const message: Message = {
            id: data.id,
            role: 'assistant',
            timestamp: Date.now(),
            agentContext
        }

        if (messageText) {
            message.content = messageText
        }
        if (attachments.length > 0) {
            message.attachments = attachments
        }

        safeDispatch(addMessage(message))
    } else if (data.content.tool_name === TOOL.BROWSER_USE) {
        // Display browser result as message
        safeDispatch(addMessage({
            id: data.id,
            role: 'assistant',
            content: data.content.result as string,
            timestamp: Date.now(),
            agentContext
        }))
    } else {
        // Regular tool result - update the action message
        const messages = [...messagesRef.current]

        // Find the last message with matching tool call
        let lastToolCallMessageIndex = -1
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].action?.type === data.content.tool_name
                && !messages[i].action?.data?.isResult) {
                lastToolCallMessageIndex = i
                break
            }
        }

        if (lastToolCallMessageIndex !== -1) {
            const lastToolCallMessage = cloneDeep(messages[lastToolCallMessageIndex])

            if (lastToolCallMessage?.action) {
                // Store the result
                lastToolCallMessage.action.data.result = data.content.result
                lastToolCallMessage.action.data.isResult = true

                // Check if this completes a subagent
                const isSubagentCompletingTool =
                    data.content.tool_name === TOOL.SUB_AGENT ||
                    data.content.tool_name === TOOL.SUB_AGENT_RESEARCHER ||
                    // ... other sub-agent tools

                const resultText = typeof data.content.result === 'string'
                    ? data.content.result
                    : JSON.stringify(data.content.result || '')

                const hasCompletionIndicator =
                    resultText.includes('Task completed') ||
                    resultText.includes('Sub agent completed')

                if (isSubagentCompletingTool && hasCompletionIndicator) {
                    // Mark subagent as completed (handled separately)
                    // See SUB_AGENT_COMPLETE event
                }

                // Dispatch the updated message
                safeDispatch(updateMessageAtIndex({
                    index: lastToolCallMessageIndex,
                    message: lastToolCallMessage
                }))
            }
        }
    }
    break
}
```

#### Database Storage
Database subscriber saves TOOL_RESULT events with full result content.

#### When Emitted
- After tool execution completes
- Follows TOOL_CALL event
- Can be emitted multiple times in a batch

#### UI Impact
- For MESSAGE_USER: Creates assistant message with text and attachments
- For BROWSER_USE: Displays result as assistant message
- For regular tools: Updates action message with result data
- Marks action as completed (isResult = true)
- Can trigger sub-agent completion detection

---

### 3.9 Event: AGENT_RESPONSE

**Purpose:** Streams the agent's text response to the user.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:22`

```typescript
export enum AgentEvent {
    // ...
    AGENT_RESPONSE = 'agent_response',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:23`

```python
class EventType(str, Enum):
    # ...
    AGENT_RESPONSE = "agent_response"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:186-193`

```python
# When agent generates a text response block
if text_result:
    await self.event_stream.publish(
        RealtimeEvent(
            type=EventType.AGENT_RESPONSE,
            session_id=self.session_id,
            run_id=self.run_id,
            content={"text": text_result.text},
        )
    )
```

**File:** `src/ii_agent/controller/agent_controller.py:513-527` (with interruption handling)

```python
# Determine event type based on interruption status
if await self.is_interrupted():
    rsp_type = EventType.AGENT_RESPONSE_INTERRUPTED
else:
    rsp_type = EventType.AGENT_RESPONSE

await self.event_stream.publish(
    RealtimeEvent(
        type=rsp_type,
        session_id=self.session_id,
        run_id=self.run_id,
        content={
            "text": text,
            "signature": signature,  # For Gemini thinking blocks
        },
    )
)
```

#### Payload Structure

```json
{
    "type": "agent_response",
    "content": {
        "text": "I've analyzed the code and found several optimization opportunities..."
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx` (handler location varies)

```typescript
case AgentEvent.AGENT_RESPONSE: {
    const currentAgentId =
        agentStackRef.current[agentStackRef.current.length - 1] || mainAgentId.current
    const agentContext = activeAgentsRef.current.get(currentAgentId)

    safeDispatch(
        addMessage({
            id: data.id,
            role: 'assistant',
            content: data.content.text as string,
            timestamp: Date.now(),
            agentContext
        })
    )
    break
}
```

#### Database Storage
Database subscriber saves AGENT_RESPONSE events with the response text.

#### When Emitted
- During LLM streaming when model generates regular text response
- Can be emitted multiple times during a single turn
- Associated with current agent context (main or sub-agent)
- Will be AGENT_RESPONSE_INTERRUPTED if cancellation occurred

#### UI Impact
- Displays assistant message with response text
- Associated with current agent in hierarchy
- Rendered as markdown
- Can include code blocks, lists, formatting

---

### 3.10 Event: COMPLETE

**Purpose:** Signals that the agent task has been completed successfully.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:23`

```typescript
export enum AgentEvent {
    // ...
    COMPLETE = 'complete',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:36`

```python
class EventType(str, Enum):
    # ...
    COMPLETE = "complete"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:324-331`

```python
# When MESSAGE_USER tool with type="result" is executed (task completion)
if not self.is_sub_agent:
    await self.event_stream.publish(
        RealtimeEvent(
            type=EventType.COMPLETE,
            session_id=self.session_id,
            run_id=self.run_id,
            content={"text": "Task completed"},
        )
    )
```

**File:** `src/ii_agent/controller/agent_controller.py:355-362` (max turns reached)

```python
# When agent reaches maximum turns without completion
agent_answer = "Agent did not complete after max turns"
await self.event_stream.publish(
    RealtimeEvent(
        type=EventType.COMPLETE,
        session_id=self.session_id,
        run_id=self.run_id,
        content={"text": agent_answer},
    )
)
```

#### Payload Structure

```json
{
    "type": "complete",
    "content": {
        "text": "Task completed"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.COMPLETE: {
    dispatch(setCompleted(true))
    dispatch(setLoading(false))
    break
}
```

#### Database Storage
Database subscriber saves COMPLETE events.

#### When Emitted
- When MESSAGE_USER tool with type="result" is executed
- When agent reaches maximum turns
- Only for main agent (not sub-agents)
- Followed by STATUS_UPDATE with status="ready"

#### UI Impact
- Sets conversation to completed state
- Stops loading indicators
- Enables new query input
- Shows completion status

---

### 3.11 Event: SUB_AGENT_COMPLETE

**Purpose:** Signals that a sub-agent has completed its task and control is returning to parent agent.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:24`

```typescript
export enum AgentEvent {
    // ...
    SUB_AGENT_COMPLETE = 'sub_agent_complete',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:37`

```python
class EventType(str, Enum):
    # ...
    SUB_AGENT_COMPLETE = "sub_agent_complete"
    # ...
```

#### Backend Emission
**File:** Sub-agent tools emit this when their execution completes

```python
# Emitted by sub-agent controller when it finishes
await self.event_stream.publish(
    RealtimeEvent(
        type=EventType.SUB_AGENT_COMPLETE,
        session_id=self.session_id,
        run_id=self.run_id,
        content={
            "agent_id": self.agent_id,
            "result": "Sub agent completed successfully"
        },
    )
)
```

#### Payload Structure

```json
{
    "type": "sub_agent_complete",
    "content": {
        "agent_id": "main-agent-research-toolu_01ABC",
        "result": "Sub agent completed successfully"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.SUB_AGENT_COMPLETE: {
    const agentId = data.content.agent_id as string | undefined

    if (agentId) {
        const agentContext = activeAgentsRef.current.get(agentId)

        if (agentContext) {
            // Mark agent as completed
            agentContext.status = 'completed'
            agentContext.endTime = Date.now()

            // Remove from agent stack
            const stackIndex = agentStackRef.current.indexOf(agentId)
            if (stackIndex !== -1) {
                agentStackRef.current.splice(stackIndex, 1)
            }
        }
    }
    break
}
```

#### Database Storage
Database subscriber saves SUB_AGENT_COMPLETE events.

#### When Emitted
- When sub-agent finishes execution
- Before control returns to parent agent
- Associated with specific sub-agent ID

#### UI Impact
- Marks sub-agent context as completed
- Records end time for duration calculation
- Removes sub-agent from active stack
- Updates agent hierarchy visualization
- Parent agent becomes active again

---

### 3.12 Event: ERROR

**Purpose:** Reports errors that occur during agent execution.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:25`

```typescript
export enum AgentEvent {
    // ...
    ERROR = 'error',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:26`

```python
class EventType(str, Enum):
    # ...
    ERROR = "error"
    # ...
```

#### Backend Emission
**File:** Multiple locations throughout backend

```python
# Example from query handler
await self._send_error_event(
    str(session_info.id),
    message="Insufficient credits to process this request.",
    error_type="insufficient_credits",
)

# Helper method emits ERROR event
async def _send_error_event(self, room: str, message: str, error_type: str = "error"):
    await self.sio.emit(
        "chat_event",
        {
            "type": EventType.ERROR,
            "content": {
                "message": message,
                "error_type": error_type,
            },
        },
        room=room,
    )
```

#### Payload Structure

```json
{
    "type": "error",
    "content": {
        "message": "Insufficient credits to process this request. Please check your credit balance.",
        "error_type": "insufficient_credits"
    }
}
```

Other error types:
```json
{
    "type": "error",
    "content": {
        "message": "Session not found!",
        "error_type": "unexpected_error"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.ERROR: {
    const errorMessage = data.content.message as string
    const errorType = data.content.error_type as string | undefined

    // Show error toast notification
    toast.error(errorMessage, {
        duration: 5000,
        position: 'top-center'
    })

    // Stop loading state
    dispatch(setLoading(false))
    dispatch(setStopped(true))

    // Handle specific error types
    if (errorType === 'insufficient_credits') {
        // Redirect to credits page
        router.push('/credits')
    }

    break
}
```

#### Database Storage
Database subscriber saves ERROR events for debugging and analytics.

#### When Emitted
- When session validation fails
- When credit check fails
- When tool execution throws exception
- When LLM provider returns error
- When cancellation/interruption occurs with error

#### UI Impact
- Displays error toast notification
- Stops all loading indicators
- Marks conversation as stopped
- May trigger navigation (e.g., to credits page)
- Allows user to retry

---

### 3.13 Event: STATUS_UPDATE

**Purpose:** Updates the agent's current execution status (ready, running, cancelled).

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:26`

```typescript
export enum AgentEvent {
    // ...
    STATUS_UPDATE = 'status_update',
    // ...
}

// Referenced enum
export enum AgentStatus {
    READY = 'ready',
    RUNNING = 'running',
    CANCELLED = 'cancelled'
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:8-11, 16`

```python
class AgentStatus(str, enum.Enum):
    READY = "ready"
    RUNNING = "running"
    CANCELLED = "cancelled"

class EventType(str, Enum):
    # ...
    STATUS_UPDATE = "status_update"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:334-339`

```python
# After COMPLETE event, set status back to READY
await self.event_stream.publish(
    RealtimeEvent(
        type=EventType.STATUS_UPDATE,
        session_id=self.session_id,
        run_id=self.run_id,
        content={"status": AgentStatus.READY},
    )
)
```

**File:** `src/ii_agent/server/socket/socketio.py:206-207` (handshake)

```python
# If there's a running task, notify client
if running_task:
    await self._emit_status_update(str(session_info.id), AgentStatus.RUNNING)
```

**File:** Various cancellation handlers

```python
# When agent is cancelled
await self.event_stream.publish(
    RealtimeEvent(
        type=EventType.STATUS_UPDATE,
        session_id=self.session_id,
        run_id=self.run_id,
        content={"status": AgentStatus.CANCELLED},
    )
)
```

#### Payload Structure

```json
{
    "type": "status_update",
    "content": {
        "status": "ready"
    }
}
```

Possible status values:
- `"ready"` - Agent is idle, ready for new query
- `"running"` - Agent is actively executing
- `"cancelled"` - Agent execution was cancelled

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.STATUS_UPDATE: {
    const status = data.content.status as AgentStatus

    dispatch(setAgentStatus(status))

    if (status === AgentStatus.READY) {
        dispatch(setLoading(false))
        dispatch(setCompleted(true))
    } else if (status === AgentStatus.RUNNING) {
        dispatch(setLoading(true))
        dispatch(setCompleted(false))
    } else if (status === AgentStatus.CANCELLED) {
        dispatch(setLoading(false))
        dispatch(setStopped(true))
    }

    break
}
```

#### Database Storage
Database subscriber saves STATUS_UPDATE events for session tracking.

#### When Emitted
- After COMPLETE event (status: "ready")
- On connection handshake if task running (status: "running")
- When agent is cancelled (status: "cancelled")
- State transitions during execution

#### UI Impact
- Updates agent status indicator
- Controls loading spinner visibility
- Enables/disables query input
- Shows appropriate status badge

---

### 3.14 Event: SYSTEM

**Purpose:** Sends system-level messages and notifications to the user.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:27`

```typescript
export enum AgentEvent {
    // ...
    SYSTEM = 'system',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:27`

```python
class EventType(str, Enum):
    # ...
    SYSTEM = "system"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/socketio.py:164-166`

```python
# On session join
await self._emit_system_event(
    sid, "Session created", session_id=str(session_info.id)
)

# Helper method
async def _emit_system_event(self, room: str, message: str, **kwargs) -> None:
    """Helper method to emit system events."""
    content = {"message": message}
    content.update(kwargs)
    await self._emit_chat_event(room, EventType.SYSTEM, content)
```

#### Payload Structure

```json
{
    "type": "system",
    "content": {
        "message": "Session created",
        "session_id": "550e8400-e29b-41d4-a716-446655440000"
    }
}
```

Other examples:
```json
{
    "type": "system",
    "content": {
        "message": "Sandbox initialized",
        "sandbox_id": "sandbox_abc123"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.SYSTEM: {
    const message = data.content.message as string

    // Display system message in chat
    safeDispatch(
        addMessage({
            id: data.id,
            role: 'system',
            content: message,
            timestamp: Date.now(),
            isSystemMessage: true
        })
    )

    // Extract additional metadata
    if (data.content.session_id) {
        dispatch(setSessionId(data.content.session_id as string))
    }

    break
}
```

#### Database Storage
Database subscriber saves SYSTEM events for audit trail.

#### When Emitted
- On session creation/join
- On sandbox initialization
- On important state changes
- For informational messages
- During debugging/logging

#### UI Impact
- Displays system message in chat (usually styled differently)
- Updates session metadata
- Shows notifications for important events
- Provides context for user actions

---

### 3.15 Event: WORKSPACE_INFO

**Purpose:** Provides workspace path information to the frontend.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:28`

```typescript
export enum AgentEvent {
    // ...
    WORKSPACE_INFO = 'workspace_info',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:18`

```python
class EventType(str, Enum):
    # ...
    WORKSPACE_INFO = "workspace_info"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/command/workspace_info_handler.py:34-40`

```python
# In response to WORKSPACE_INFO command
await self.send_event(
    RealtimeEvent(
        type=EventType.WORKSPACE_INFO,
        session_id=session_info.id,
        content={"path": workspace_path},
    )
)
```

Also emitted during handshake:

**File:** `src/ii_agent/server/socket/socketio.py:192-199`

```python
await self._emit_chat_event(
    room=str(sid),
    event_type=EventType.CONNECTION_ESTABLISHED,
    content={
        "message": "Connected to Agent WebSocket Server",
        "workspace_path": config.workspace_path,
    },
)
```

#### Payload Structure

```json
{
    "type": "workspace_info",
    "content": {
        "path": "/workspace/projects/myapp"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.WORKSPACE_INFO: {
    const workspacePath = data.content.path as string

    dispatch(setWorkspacePath(workspacePath))

    // Show toast notification
    toast.info(`Workspace: ${workspacePath}`, {
        duration: 3000
    })

    break
}
```

#### Database Storage
WORKSPACE_INFO events are **NOT** saved to database (excluded in filter)

#### When Emitted
- On connection handshake
- When WORKSPACE_INFO command is sent
- After sandbox initialization

#### UI Impact
- Stores workspace path in Redux state
- Shows workspace path in UI
- Used for file path resolution
- Displayed in status bar

---

### 3.16 Event: SANDBOX_STATUS

**Purpose:** Reports the current status of the E2B sandbox environment.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:29`

```typescript
export enum AgentEvent {
    // ...
    SANDBOX_STATUS = 'sandbox_status',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:35`

```python
class EventType(str, Enum):
    # ...
    SANDBOX_STATUS = "sandbox_status"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/command/sandbox_status_handler.py:37-46`

```python
# In response to SANDBOX_STATUS command
await self.send_event(
    RealtimeEvent(
        type=EventType.SANDBOX_STATUS,
        session_id=session_info.id,
        content={
            "status": status,
            "vscode_url": vscode_url
        },
    )
)
```

**File:** `src/ii_agent/server/socket/command/awake_sandbox_handler.py:32-42`

```python
# After waking up sandbox
await sandbox_service.wake_up_sandbox_by_session(session_info.id)
await self.send_event(
    RealtimeEvent(
        type=EventType.SANDBOX_STATUS,
        session_id=session_info.id,
        content={
            "status": await sandbox_service.get_sandbox_status_by_session(
                session_info.id
            )
        },
    )
)
```

#### Payload Structure

```json
{
    "type": "sandbox_status",
    "content": {
        "status": "running",
        "vscode_url": "https://vscode-abc123.e2b.dev"
    }
}
```

Possible status values:
- `"running"` - Sandbox is active
- `"stopped"` - Sandbox is stopped
- `"sleeping"` - Sandbox is in sleep mode
- `null` - Sandbox not initialized

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.SANDBOX_STATUS: {
    const status = data.content.status as string | null
    const vscodeUrl = data.content.vscode_url as string | undefined

    dispatch(setSandboxStatus(status))

    if (vscodeUrl) {
        dispatch(setVscodeUrl(vscodeUrl))
    }

    // Show notification for status changes
    if (status === 'running') {
        toast.success('Sandbox is running')
    } else if (status === 'sleeping') {
        toast.info('Sandbox is sleeping')
    } else if (status === 'stopped') {
        toast.warning('Sandbox has stopped')
    }

    break
}
```

#### Database Storage
SANDBOX_STATUS events are **NOT** saved to database (excluded in filter)

#### When Emitted
- When SANDBOX_STATUS command is sent
- After AWAKE_SANDBOX command completes
- During sandbox lifecycle changes

#### UI Impact
- Updates sandbox status indicator
- Shows/hides VSCode IDE link
- Displays status badge
- Shows toast notifications for status changes
- Enables/disables sandbox-dependent features

---

### 3.17 Event: STREAM_COMPLETE

**Purpose:** Signals that an LLM streaming response has completed.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:30`

```typescript
export enum AgentEvent {
    // ...
    STREAM_COMPLETE = 'stream_complete',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:25`

```python
class EventType(str, Enum):
    # ...
    STREAM_COMPLETE = "stream_complete"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py` (after LLM streaming completes)

```python
# After LLM response stream finishes
await self.event_stream.publish(
    RealtimeEvent(
        type=EventType.STREAM_COMPLETE,
        session_id=self.session_id,
        run_id=self.run_id,
        content={},
    )
)
```

#### Payload Structure

```json
{
    "type": "stream_complete",
    "content": {}
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.STREAM_COMPLETE: {
    // Mark streaming as complete
    dispatch(setStreaming(false))
    break
}
```

#### Database Storage
STREAM_COMPLETE events are **NOT** saved to database (excluded in filter, allowed during abort)

#### When Emitted
- After each LLM streaming response completes
- Before tool execution begins
- Can be emitted multiple times during agent execution
- Allowed even when agent is aborted

#### UI Impact
- Stops streaming animation
- Finalizes text rendering
- Allows UI interaction with completed message
- Prepares for next agent action

---

### 3.18 Event: AGENT_RESPONSE_INTERRUPTED

**Purpose:** Indicates that the agent's response was interrupted by cancellation.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:31`

```typescript
export enum AgentEvent {
    // ...
    AGENT_RESPONSE_INTERRUPTED = 'agent_response_interrupted',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:24`

```python
class EventType(str, Enum):
    # ...
    AGENT_RESPONSE_INTERRUPTED = "agent_response_interrupted"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/controller/agent_controller.py:513-527`

```python
# When response is interrupted
if await self.is_interrupted():
    rsp_type = EventType.AGENT_RESPONSE_INTERRUPTED
else:
    rsp_type = EventType.AGENT_RESPONSE

await self.event_stream.publish(
    RealtimeEvent(
        type=rsp_type,
        session_id=self.session_id,
        run_id=self.run_id,
        content={
            "text": text,
            "signature": signature,
        },
    )
)
```

**File:** `src/ii_agent/cron/tasks.py:66-73` (system cleanup)

```python
# When task is interrupted by system timeout
await socketio_subscriber.send_event_to_room(
    session_id=uuid.UUID(task.session_id),
    run_id=task.id,
    type=EventType.AGENT_RESPONSE_INTERRUPTED,
    content={
        "message": "Agent run task was interrupted by system cleanup due to timeout."
    },
)
```

#### Payload Structure

```json
{
    "type": "agent_response_interrupted",
    "content": {
        "text": "I was analyzing the code when...",
        "message": "Agent execution was cancelled by user"
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.AGENT_RESPONSE_INTERRUPTED: {
    const text = data.content.text as string | undefined
    const message = data.content.message as string | undefined

    const currentAgentId =
        agentStackRef.current[agentStackRef.current.length - 1] || mainAgentId.current
    const agentContext = activeAgentsRef.current.get(currentAgentId)

    // Add interrupted message if there's text
    if (text) {
        safeDispatch(
            addMessage({
                id: data.id,
                role: 'assistant',
                content: text,
                timestamp: Date.now(),
                agentContext,
                isInterrupted: true
            })
        )
    }

    // Show interruption notification
    toast.warning(message || 'Agent response was interrupted', {
        duration: 4000
    })

    dispatch(setStopped(true))
    dispatch(setLoading(false))

    break
}
```

#### Database Storage
Database subscriber saves AGENT_RESPONSE_INTERRUPTED events for debugging.

#### When Emitted
- When user cancels agent execution
- When system timeout occurs
- During cleanup of long-running tasks
- Replaces AGENT_RESPONSE when interruption detected

#### UI Impact
- Displays partial response with interrupted indicator
- Shows warning toast notification
- Marks conversation as stopped
- Disables loading indicators
- Allows user to start new query

---

### 3.19 Event: UPLOAD_SUCCESS

**Purpose:** Confirms successful file upload to the sandbox.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:32`

```typescript
export enum AgentEvent {
    // ...
    UPLOAD_SUCCESS = 'upload_success',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:29`

```python
class EventType(str, Enum):
    # ...
    UPLOAD_SUCCESS = "upload_success"
    # ...
```

#### Backend Emission
**File:** File upload handler after successful upload

```python
# After files are uploaded to sandbox
await self.event_stream.publish(
    RealtimeEvent(
        type=EventType.UPLOAD_SUCCESS,
        session_id=self.session_id,
        run_id=self.run_id,
        content={
            "files": [
                {
                    "path": "document.pdf",
                    "saved_path": "/workspace/uploads/document.pdf"
                },
                {
                    "path": "image.png",
                    "saved_path": "/workspace/uploads/image.png"
                }
            ]
        },
    )
)
```

#### Payload Structure

```json
{
    "type": "upload_success",
    "content": {
        "files": [
            {
                "path": "document.pdf",
                "saved_path": "/workspace/uploads/document.pdf"
            },
            {
                "path": "image.png",
                "saved_path": "/workspace/uploads/image.png"
            }
        ]
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:1216-1240`

```typescript
case AgentEvent.UPLOAD_SUCCESS: {
    safeDispatch(setIsUploading(false))

    // Update the uploaded files state
    const newFiles = data.content.files as {
        path: string
        saved_path: string
    }[]

    if (newFiles && Array.isArray(newFiles)) {
        dispatch(addUploadedFiles(newFiles))

        // Show success notification
        toast.success(
            `Successfully uploaded ${newFiles.length} file${newFiles.length > 1 ? 's' : ''}`,
            { duration: 3000 }
        )
    }

    break
}
```

#### Database Storage
Database subscriber saves UPLOAD_SUCCESS events.

#### When Emitted
- After successful file upload to sandbox
- Following file upload command
- Before agent can access uploaded files

#### UI Impact
- Clears uploading state
- Adds files to uploaded files list
- Shows success toast notification
- Enables file access in sandbox
- Updates file explorer if visible

---

### 3.20 Event: PONG

**Purpose:** Response to PING command for connection health check.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:33`

```typescript
export enum AgentEvent {
    // ...
    PONG = 'pong',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:28`

```python
class EventType(str, Enum):
    # ...
    PONG = "pong"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/server/socket/command/ping_handler.py`

```python
# In response to PING command
async def handle(self, content: dict, session_info: SessionInfo):
    """Handle ping command and respond with pong."""
    await self.send_event(
        RealtimeEvent(
            type=EventType.PONG,
            session_id=session_info.id,
            content={"timestamp": time.time()},
        )
    )
```

#### Payload Structure

```json
{
    "type": "pong",
    "content": {
        "timestamp": 1706102400.123
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.PONG: {
    const timestamp = data.content.timestamp as number

    // Calculate round-trip time if we stored ping time
    const latency = Date.now() - (lastPingTime || Date.now())

    dispatch(setConnectionLatency(latency))
    dispatch(setLastPongTime(timestamp))

    // Connection is healthy
    dispatch(setConnectionStatus('connected'))

    break
}
```

#### Database Storage
PONG events are **NOT** saved to database (excluded in filter, allowed during abort)

#### When Emitted
- In response to PING command
- Used for connection health monitoring
- Part of heartbeat mechanism

#### UI Impact
- Updates connection status
- Calculates and displays latency
- Confirms WebSocket connection is alive
- Used for debugging connection issues

---

### 3.21 Event: PROMPT_GENERATED

**Purpose:** Returns an LLM-enhanced version of the user's prompt.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:34`

```typescript
export enum AgentEvent {
    // ...
    PROMPT_GENERATED = 'prompt_generated',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:33`

```python
class EventType(str, Enum):
    # ...
    PROMPT_GENERATED = "prompt_generated"
    # ...
```

#### Backend Emission
**File:** Enhance prompt handler

```python
# After LLM enhances the user's prompt
enhanced_prompt = await enhance_prompt_with_llm(original_prompt)

await self.send_event(
    RealtimeEvent(
        type=EventType.PROMPT_GENERATED,
        session_id=session_info.id,
        content={"result": enhanced_prompt},
    )
)
```

#### Payload Structure

```json
{
    "type": "prompt_generated",
    "content": {
        "result": "Create a responsive React component that displays a product card with image, title, price, and an add-to-cart button. The component should use Tailwind CSS for styling and include hover effects."
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:301-305`

```typescript
case AgentEvent.PROMPT_GENERATED: {
    dispatch(setGeneratingPrompt(false))
    dispatch(setCurrentQuestion(data.content.result as string))
    break
}
```

#### Database Storage
Database subscriber saves PROMPT_GENERATED events.

#### When Emitted
- After ENHANCE_PROMPT command completes
- When user requests prompt improvement
- Before submitting enhanced query

#### UI Impact
- Stops "generating prompt" loading state
- Updates query input with enhanced prompt
- Shows enhanced prompt to user for review
- User can edit before submitting

---

### 3.22 Event: METRICS_UPDATE

**Purpose:** Provides real-time updates on token usage and credits consumed.

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:35`

```typescript
export enum AgentEvent {
    // ...
    METRICS_UPDATE = 'metrics_update',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:38`

```python
class EventType(str, Enum):
    # ...
    METRICS_UPDATE = "metrics_update"
    # ...
```

#### Backend Emission
**File:** `src/ii_agent/subscribers/metrics_subscriber.py`

```python
# Emitted by MetricsSubscriber after tracking usage
await self.socketio_subscriber.send_event_to_room(
    session_id=event.session_id,
    run_id=event.run_id,
    type=EventType.METRICS_UPDATE,
    content={
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "credits_used": credits_consumed
    },
)
```

#### Payload Structure

```json
{
    "type": "metrics_update",
    "content": {
        "input_tokens": 1250,
        "output_tokens": 840,
        "total_tokens": 2090,
        "credits_used": 0.05
    }
}
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx`

```typescript
case AgentEvent.METRICS_UPDATE: {
    const inputTokens = data.content.input_tokens as number
    const outputTokens = data.content.output_tokens as number
    const totalTokens = data.content.total_tokens as number
    const creditsUsed = data.content.credits_used as number

    // Update metrics in Redux
    dispatch(updateMetrics({
        inputTokens,
        outputTokens,
        totalTokens,
        creditsUsed
    }))

    // Update session total usage
    dispatch(incrementSessionTokens(totalTokens))
    dispatch(incrementSessionCredits(creditsUsed))

    break
}
```

#### Database Storage
Metrics are saved to database via MetricsSubscriber (separate from event storage).

#### When Emitted
- After each LLM API call completes
- Includes both input and output token counts
- Tracks cumulative credits consumed
- Real-time updates during agent execution

#### UI Impact
- Updates token usage display
- Shows credits consumed
- Updates usage meters/progress bars
- Warns if approaching credit limit
- Displayed in session details

---

### 3.23 Event: BROWSER_USE (Reserved)

**Purpose:** Reserved for browser automation events (future feature).

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:36`

```typescript
export enum AgentEvent {
    // ...
    BROWSER_USE = 'browser_use',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:30`

```python
class EventType(str, Enum):
    # ...
    BROWSER_USE = "browser_use"
    # ...
```

#### Frontend Handler
**File:** `frontend/src/hooks/use-app-events.tsx:501-503`

```typescript
case AgentEvent.BROWSER_USE:
    // Commented out in original code - reserved for future use
    break
```

#### Status
Event type is defined but not currently emitted by backend. Reserved for future browser automation features.

---

### 3.24 Event: FILE_EDIT (Reserved)

**Purpose:** Reserved for file editing events (future feature).

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:37`

```typescript
export enum AgentEvent {
    // ...
    FILE_EDIT = 'file_edit',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:31`

```python
class EventType(str, Enum):
    # ...
    FILE_EDIT = "file_edit"
    # ...
```

#### Status
Event type is defined but not currently implemented. Reserved for future real-time file editing notifications.

---

### 3.25 Event: TOOL_CONFIRMATION (Reserved)

**Purpose:** Reserved for tool confirmation workflow (future feature).

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:38`

```typescript
export enum AgentEvent {
    // ...
    TOOL_CONFIRMATION = 'tool_confirmation',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:34`

```python
class EventType(str, Enum):
    # ...
    TOOL_CONFIRMATION = "tool_confirmation"
    # ...
```

#### Status
Event type is defined but not currently used. Reserved for future tool confirmation and approval workflow.

---

### 3.26 Event: MODEL_COMPACT (Reserved)

**Purpose:** Reserved for model compaction events (future feature).

#### Frontend Type Definition
**File:** `frontend/src/typings/agent.ts:39`

```typescript
export enum AgentEvent {
    // ...
    MODEL_COMPACT = 'model_compact',
    // ...
}
```

#### Backend Type Definition
**File:** `src/ii_agent/core/event.py:39`

```python
class EventType(str, Enum):
    # ...
    MODEL_COMPACT = "model_compact"
    # ...
```

#### Status
Event type is defined but not currently implemented. Reserved for future conversation history compaction features.

---

### 3.27 Event Filtering During Abort

The backend has a special mechanism for filtering events when the agent is aborted.

**File:** `src/ii_agent/core/event.py:42-53`

```python
@staticmethod
def is_allowed_when_aborted(event_type: "EventType") -> bool:
    return event_type in [
        EventType.STATUS_UPDATE,
        EventType.SYSTEM,
        EventType.ERROR,
        EventType.PONG,
        EventType.STREAM_COMPLETE,
        EventType.CONNECTION_ESTABLISHED,
        EventType.AGENT_RESPONSE_INTERRUPTED,
        EventType.WORKSPACE_INFO,
        EventType.SANDBOX_STATUS,
    ]
```

**Events Allowed During Abort:**
- STATUS_UPDATE
- SYSTEM
- ERROR
- PONG
- STREAM_COMPLETE
- CONNECTION_ESTABLISHED
- AGENT_RESPONSE_INTERRUPTED
- WORKSPACE_INFO
- SANDBOX_STATUS

**Events Blocked During Abort:**
All other events (TOOL_CALL, TOOL_RESULT, AGENT_THINKING, AGENT_RESPONSE, etc.) are filtered out when the agent is in aborted state to prevent stale events from appearing after cancellation.

---

## Event Summary Table

| Event | Purpose | Saved to DB | Allowed When Aborted | Emitted Multiple Times |
|-------|---------|-------------|---------------------|----------------------|
| CONNECTION_ESTABLISHED | WebSocket connected | No | Yes | Once per connection |
| AGENT_INITIALIZED | Agent ready to execute | Yes | No | Once per query |
| USER_MESSAGE | User's query received | No | No | Once per query |
| PROCESSING | Agent started processing | No | No | Once per query |
| AGENT_THINKING | Thinking/reasoning stream | Yes | No | Multiple per turn |
| TOOL_CALL | Tool invocation started | Yes | No | Multiple per turn |
| TOOL_RESULT | Tool execution result | Yes | No | Multiple per turn |
| AGENT_RESPONSE | Agent text response | Yes | No | Multiple per turn |
| AGENT_RESPONSE_INTERRUPTED | Response was cancelled | Yes | Yes | Once when cancelled |
| COMPLETE | Task completed | Yes | No | Once per query |
| SUB_AGENT_COMPLETE | Sub-agent finished | Yes | No | Once per sub-agent |
| STATUS_UPDATE | Agent status changed | Yes | Yes | Multiple |
| ERROR | Error occurred | Yes | Yes | As needed |
| SYSTEM | System notification | Yes | Yes | As needed |
| WORKSPACE_INFO | Workspace path info | No | Yes | Once or on request |
| SANDBOX_STATUS | Sandbox status info | No | Yes | On request |
| STREAM_COMPLETE | LLM stream finished | No | Yes | Multiple per turn |
| UPLOAD_SUCCESS | Files uploaded | Yes | No | Once per upload |
| PONG | Ping response | No | Yes | On ping |
| PROMPT_GENERATED | Enhanced prompt ready | Yes | No | Once per request |
| METRICS_UPDATE | Token usage update | Special | No | Multiple |
| BROWSER_USE | Browser automation | - | - | Reserved |
| FILE_EDIT | File editing | - | - | Reserved |
| TOOL_CONFIRMATION | Tool approval | - | - | Reserved |
| MODEL_COMPACT | History compaction | - | - | Reserved |

---

