# Chat Connection Infrastructure Investigation

> **Document Purpose**: Comprehensive investigation of the backend and frontend chat/conversation infrastructure for Step 5 of the Frontend-Backend Integration Plan.
> 
> **Last Updated**: January 23, 2026

---

## Table of Contents

- [1. Architecture Overview](#1-architecture-overview)
- [2. Backend WebSocket Infrastructure](#2-backend-websocket-infrastructure)
  - [2.1 Socket.IO Server Configuration](#21-socketio-server-configuration)
  - [2.2 Chat Manager (handlers.py)](#22-chat-manager-handlerspy)
  - [2.3 Session Store](#23-session-store)
  - [2.4 Command Handlers](#24-command-handlers)
- [3. Backend SSE Streaming](#3-backend-sse-streaming)
  - [3.1 Chat Endpoint (No Sandbox)](#31-chat-endpoint-no-sandbox)
  - [3.2 Agent Endpoint (With Sandbox)](#32-agent-endpoint-with-sandbox)
  - [3.3 AG-UI Protocol Models](#33-ag-ui-protocol-models)
- [4. Backend Agent Modules](#4-backend-agent-modules)
- [5. Backend Sandbox URLs](#5-backend-sandbox-urls)
- [6. Frontend WebSocket Context](#6-frontend-websocket-context)
- [7. Frontend SSE Service](#7-frontend-sse-service)
- [8. Frontend Event Handling](#8-frontend-event-handling)
- [9. Frontend State Management](#9-frontend-state-management)
- [10. Integration Mapping](#10-integration-mapping)
- [11. Event Type Reference](#11-event-type-reference)
- [12. Implementation Checklist](#12-implementation-checklist)

---

## 1. Architecture Overview

The system uses a **dual-transport architecture** for chat functionality:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                        │
│                                                                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐│
│  │  WebSocket (Socket.IO)      │    │  SSE (HTTP Streaming)               ││
│  │  websocket-context.tsx      │    │  chat.service.ts                    ││
│  │                             │    │                                     ││
│  │  Used for: Agent Mode       │    │  Used for: Chat Mode                ││
│  │  Route: /:sessionId         │    │  Route: /chat                       ││
│  │                             │    │                                     ││
│  │  Events:                    │    │  Endpoints:                         ││
│  │  - join_session             │    │  - POST /agent/chat/stream          ││
│  │  - chat_message             │    │  - POST /agent/agent/stream         ││
│  │  - leave_session            │    │                                     ││
│  └──────────────┬──────────────┘    └────────────────┬────────────────────┘│
└─────────────────┼────────────────────────────────────┼──────────────────────┘
                  │                                    │
                  ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                         │
│                                                                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐│
│  │  Socket.IO Server           │    │  FastAPI SSE Endpoints              ││
│  │  backend/common/socketio/   │    │  backend/app/agent/api/v1/          ││
│  │                             │    │                                     ││
│  │  Files:                     │    │  Files:                             ││
│  │  - server.py                │    │  - chat.py (no sandbox)             ││
│  │  - handlers.py              │    │  - agent.py (with sandbox)          ││
│  │  - session_store.py         │    │                                     ││
│  │  - command/*.py             │    │  Generators:                        ││
│  │                             │    │  - _astream_workflow_generator      ││
│  │  Command Handlers:          │    │  - _agent_stream_generator          ││
│  │  - QueryHandler             │    │                                     ││
│  │  - CancelHandler            │    │                                     ││
│  │  - PingHandler              │    │                                     ││
│  │  - SandboxStatusHandler     │    │                                     ││
│  │  - AwakeSandboxHandler      │    │                                     ││
│  │  - WorkspaceInfoHandler     │    │                                     ││
│  │  - EnhancePromptHandler     │    │                                     ││
│  │  - PublishProjectHandler    │    │                                     ││
│  └──────────────┬──────────────┘    └────────────────┬────────────────────┘│
│                 │                                    │                      │
│                 └────────────────┬───────────────────┘                      │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    SessionSandboxManager                              │  │
│  │                    (Cold/Warm Start Pattern)                          │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         E2B SANDBOX                                   │  │
│  │  Ports: MCP(6060), VSCode(9000), Codex(1324), LaTeX(9001),           │  │
│  │         Design(6002), Excalidraw(6003), Graphiti(8500)               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Transport Decision Logic

| Route | Transport | Backend Endpoint | Reason |
|-------|-----------|------------------|--------|
| `/chat` | SSE | `/agent/chat/stream` | Simple Q&A, no sandbox needed |
| `/:sessionId` (agent) | WebSocket | Socket.IO `/ws` namespace | Real-time bidirectional, sandbox control |
| `/:sessionId` (agent) | SSE (via WS) | QueryHandler → SSE generators | WebSocket forwards SSE events |

---

## 2. Backend WebSocket Infrastructure

### 2.1 Socket.IO Server Configuration

**File**: `backend/common/socketio/server.py`

```python
sio = socketio.AsyncServer(
    client_manager=socketio.AsyncRedisManager(
        f'redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DATABASE}',
    ),
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ALLOWED_ORIGINS,
    cors_credentials=True,
    namespaces=['/ws'],  # Primary namespace
)
```

**Key Features**:
- Redis client manager for multi-process scalability
- Single namespace: `/ws`
- JWT-based authentication on connect
- CORS enabled with credentials

**Connection Handler** (server.py):
```python
@sio.event
async def connect(sid, environ, auth) -> bool:
    # Requires auth: { token, session_uuid }
    token = auth.get('token')
    session_uuid = auth.get('session_uuid')
    
    # JWT verification
    await jwt_authentication(token)
    
    # Store in Redis for tracking
    await redis_client.sadd(settings.TOKEN_ONLINE_REDIS_PREFIX, session_uuid)
    return True
```

### 2.2 Chat Manager (handlers.py)

**File**: `backend/common/socketio/handlers.py`

**Class**: `SocketIOChatManager`

This is the main class handling all chat-related Socket.IO events.

#### Event Registration

```python
def init_handlers(self):
    self.sio.on('join_session', namespace='/ws')(self.join_session)
    self.sio.on('leave_session', namespace='/ws')(self.leave_session)
    self.sio.on('chat_message', namespace='/ws')(self.chat_message)
```

#### Event: `join_session`

**Purpose**: Join or create a chat session room

**Client Payload**:
```json
{
    "session_uuid": "uuid-string"  // Optional, creates new if not provided
}
```

**Server Response Events**:
1. `system` event with session_id and session_info
2. `connection_established` event with workspace_path

**Code Flow**:
```python
async def join_session(self, sid: str, data: Dict[str, Any]) -> None:
    # 1. Verify authentication from Socket.IO session
    session_data = await self.sio.get_session(sid, namespace='/ws')
    user_id = session_data.get('user_id')
    
    # 2. Get or create chat session in database
    session, created = await chat_session_service.get_or_create(
        db=db, session_uuid=session_uuid, user_id=user_id
    )
    
    # 3. Emit system event with session info
    await self._emit_system_event(sid, "Session created/joined", session_info=...)
    
    # 4. Join Socket.IO room
    await self.sio.enter_room(sid, session_uuid, namespace='/ws')
    
    # 5. Add to Redis session store
    await session_store.add_sid_to_session(session_uuid, sid)
    
    # 6. Emit connection_established
    await self._emit_chat_event(sid, 'connection_established', {
        'message': 'Connected to Chat Session',
        'session_id': session_uuid,
        'workspace_path': session_info.get('workspace_dir'),
    })
```

#### Event: `chat_message`

**Purpose**: Route incoming messages to command handlers

**Client Payload**:
```json
{
    "session_uuid": "uuid-string",
    "type": "query|cancel|ping|sandbox_status|awake_sandbox|workspace_info|enhance_prompt|publish",
    "content": { /* type-specific content */ }
}
```

**Code Flow**:
```python
async def chat_message(self, sid: str, data: Dict[str, Any]) -> None:
    message_type = data.get('type')
    content = data.get('content', {})
    
    # Route to command handler
    handler = _command_factory.get_handler_by_string(message_type)
    await handler.handle(
        content=content,
        session_uuid=session_uuid,
        user_id=user_id,
        sid=sid
    )
```

#### Helper Methods

```python
async def _emit_chat_event(self, room, event_type, content, namespace='/ws'):
    """Standard format for all chat events"""
    await self.sio.emit('chat_event', {
        'type': event_type,
        'content': content,
    }, room=room, namespace=namespace)

async def _emit_error(self, room, message):
    await self._emit_chat_event(room, 'error', {'message': message})

async def _emit_status_update(self, room, status):
    await self._emit_chat_event(room, 'status_update', {'status': status})

async def broadcast_to_session(self, session_uuid, event_type, content):
    """Broadcast to all clients in a session"""
    await self._emit_chat_event(room=session_uuid, event_type=event_type, content=content)
```

### 2.3 Session Store

**File**: `backend/common/socketio/session_store.py`

**Class**: `RedisSessionStore`

Redis-backed session management with TTL (default 1 hour).

**Redis Key Patterns**:

| Key Pattern | Purpose |
|-------------|---------|
| `chat_session_sids:{session_uuid}` | Set of SIDs in a session |
| `chat_sid_session:{sid}` | SID → session_uuid mapping |

**Key Methods**:

```python
async def add_sid_to_session(self, session_uuid: str, sid: str) -> None:
    """Add a SID to a session's SID set in Redis with TTL."""
    session_key = f"chat_session_sids:{session_uuid}"
    await self.redis.sadd(session_key, sid)
    await self.redis.expire(session_key, self.ttl_seconds)
    
    # Reverse mapping
    sid_key = f"chat_sid_session:{sid}"
    await self.redis.set(sid_key, session_uuid)
    await self.redis.expire(sid_key, self.ttl_seconds)

async def remove_sid_from_session(self, session_uuid: str, sid: str) -> None
async def get_session_sids(self, session_uuid: str) -> Set[str]
async def is_session_empty(self, session_uuid: str) -> bool
async def get_session_for_sid(self, sid: str) -> Optional[str]
```

### 2.4 Command Handlers

**Directory**: `backend/common/socketio/command/`

#### 2.4.1 Base Handler

**File**: `base_handler.py`

```python
class UserCommandType(str, Enum):
    INIT_AGENT = "init_agent"
    QUERY = "query"
    WORKSPACE_INFO = "workspace_info"
    AWAKE_SANDBOX = "awake_sandbox"
    SANDBOX_STATUS = "sandbox_status"
    PING = "ping"
    CANCEL = "cancel"
    ENHANCE_PROMPT = "enhance_prompt"
    PUBLISH_PROJECT = "publish"

class CommandHandler(ABC):
    def __init__(self, sio: socketio.AsyncServer, namespace: str = '/ws'):
        self.sio = sio
        self.namespace = namespace
    
    @abstractmethod
    def get_command_type(self) -> UserCommandType
    
    @abstractmethod
    async def handle(self, content: Dict, session_uuid: str, user_id: int, sid: str) -> None
    
    # Event emission helpers
    async def emit_chat_event(self, room, event_type, content, run_id=None)
    async def emit_to_sid(self, sid, event_type, content, run_id=None)
    async def broadcast_to_session(self, session_uuid, event_type, content, run_id=None)
    async def send_error(self, room, message, error_type="error", run_id=None)
    async def send_status_update(self, room, status, run_id=None)
```

#### 2.4.2 Handler Factory

**File**: `handler_factory.py`

```python
class CommandHandlerFactory:
    def __init__(self, sio: socketio.AsyncServer):
        self._sio = sio
        self._handlers: Dict[UserCommandType, CommandHandler] = {}
        self._initialize_handlers()
    
    def _initialize_handlers(self):
        self._handlers = {
            UserCommandType.PING: PingHandler(self._sio),
            UserCommandType.CANCEL: CancelHandler(self._sio),
            UserCommandType.SANDBOX_STATUS: SandboxStatusHandler(self._sio),
            UserCommandType.AWAKE_SANDBOX: AwakeSandboxHandler(self._sio),
            UserCommandType.WORKSPACE_INFO: WorkspaceInfoHandler(self._sio),
            UserCommandType.QUERY: QueryHandler(self._sio),
            UserCommandType.ENHANCE_PROMPT: EnhancePromptHandler(self._sio),
            UserCommandType.PUBLISH_PROJECT: PublishProjectHandler(self._sio),
        }
    
    def get_handler_by_string(self, command_type_str: str) -> Optional[CommandHandler]:
        command_type = UserCommandType(command_type_str)
        return self._handlers.get(command_type)
```

#### 2.4.3 Query Handler (CRITICAL)

**File**: `query_handler.py`

This is the most important handler - processes user chat messages.

**Content Expected**:
```json
{
    "message": "User's question text",
    "files": ["file-id-1", "file-id-2"],
    "agent_type": "chat|general|deep_research|...",
    "model_id": "claude-sonnet-4@20250514",
    "resources": [],
    "locale": "en-US"
}
```

**Routing Logic**:
```python
async def handle(self, content, session_uuid, user_id, sid):
    agent_type_str = content.get('agent_type', 'general')
    
    # Determine if sandbox is needed
    agent_type = AgentType(agent_type_str)
    requires_sandbox = agent_type.requires_sandbox  # True unless agent_type == 'chat'
    
    if requires_sandbox:
        # Route to agent.py logic (with sandbox)
        await self._run_agent_with_sandbox(...)
    else:
        # Route to chat.py logic (no sandbox)
        await self._run_chat_without_sandbox(...)
```

**Chat (No Sandbox) Flow**:
```python
async def _run_chat_without_sandbox(self, session_uuid, user_id, message, ...):
    from backend.app.agent.api.v1.chat import _astream_workflow_generator
    
    async for event_str in _astream_workflow_generator(
        messages=messages,
        thread_id=session_uuid,
        resources=resources,
        ...
    ):
        # Check for cancellation
        if should_cancel(session_uuid):
            await self.broadcast_to_session(session_uuid, 'cancelled', {...})
            return
        
        # Parse SSE event and forward via Socket.IO
        await self._forward_sse_event(session_uuid, event_str, run_id)
```

**Agent (With Sandbox) Flow**:
```python
async def _run_agent_with_sandbox(self, session_uuid, user_id, message, agent_type, ...):
    from backend.app.agent.api.v1.agent import ModuleRegistry, _agent_stream_generator
    
    # Get agent module graph
    module_type = AgentModuleType(agent_type.value)
    graph = ModuleRegistry.get_graph(module_type)
    
    # Create sandbox manager
    sandbox_manager = SessionSandboxManager(
        user_id=str(user_id),
        session_id=session_uuid,
        ...
    )
    
    async for event_str in _agent_stream_generator(
        graph=graph,
        module_name=agent_type.value,
        messages=messages,
        thread_id=session_uuid,
        sandbox_manager=sandbox_manager,
        ...
    ):
        if should_cancel(session_uuid):
            return
        await self._forward_sse_event(session_uuid, event_str, run_id)
    
    # Emit agent_initialized with sandbox URLs
    if sandbox_manager.is_initialized:
        sandbox, _ = await sandbox_manager.get_sandbox()
        urls = {
            'mcp_url': await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT),
            'vscode_url': await sandbox.expose_port(settings.SANDBOX_CODE_SERVER_PORT),
            'codex_url': await sandbox.expose_port(settings.SANDBOX_CODEX_SSE_PORT),
            'design_url': await sandbox.expose_port(settings.SANDBOX_DESIGN_MCP_PORT),
            'latex_url': await sandbox.expose_port(settings.SANDBOX_LATEX_EDITOR_PORT),
            'excalidraw_url': await sandbox.expose_port(settings.SANDBOX_EXCALIDRAW_PORT),
            'graphiti_url': await sandbox.expose_port(settings.SANDBOX_GRAPHITI_MCP_PORT),
        }
        await self.broadcast_to_session(session_uuid, 'agent_initialized', {
            'sandbox_id': sandbox_manager.sandbox_id,
            **urls
        })
```

**SSE-to-WebSocket Bridge**:
```python
async def _forward_sse_event(self, session_uuid, event_str, run_id):
    """Parse SSE event string and forward via Socket.IO."""
    # SSE format: "event: <type>\ndata: <json>\n\n"
    lines = event_str.strip().split('\n')
    event_type = None
    data = None
    
    for line in lines:
        if line.startswith('event:'):
            event_type = line[6:].strip()
        elif line.startswith('data:'):
            data = json.loads(line[5:].strip())
    
    if event_type and data:
        await self.broadcast_to_session(session_uuid, event_type, data, run_id)
```

#### 2.4.4 Other Handlers Summary

| Handler | File | Command Type | Purpose |
|---------|------|--------------|---------|
| **CancelHandler** | `cancel_handler.py` | `cancel` | Sets cancellation flag for session |
| **PingHandler** | `ping_handler.py` | `ping` | Returns `pong` event with timestamp |
| **SandboxStatusHandler** | `sandbox_status_handler.py` | `sandbox_status` | Returns sandbox running status + vscode_url |
| **AwakeSandboxHandler** | `awake_sandbox_handler.py` | `awake_sandbox` | Wakes paused sandbox, returns URLs |
| **WorkspaceInfoHandler** | `workspace_info_handler.py` | `workspace_info` | Returns workspace directory path |
| **EnhancePromptHandler** | `enhance_prompt_handler.py` | `enhance_prompt` | LLM-based prompt enhancement |
| **PublishProjectHandler** | `publish_handler.py` | `publish` | Deploys project to Vercel |

**Cancel Handler Detail**:
```python
# Global state for cancellation
_running_tasks: Dict[str, bool] = {}

def set_task_running(session_uuid: str, running: bool):
    _running_tasks[session_uuid] = running

def should_cancel(session_uuid: str) -> bool:
    return not _running_tasks.get(session_uuid, True)

class CancelHandler(CommandHandler):
    async def handle(self, content, session_uuid, user_id, sid):
        set_task_running(session_uuid, False)  # Trigger cancellation
        await self.broadcast_to_session(session_uuid, 'cancelled', {
            'message': 'Task cancelled by user'
        })
```

---

## 3. Backend SSE Streaming

### 3.1 Chat Endpoint (No Sandbox)

**File**: `backend/app/agent/api/v1/chat.py`

**Endpoint**: `POST /api/v1/agent/chat/stream`

**Request Model**:
```python
class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: str = "__default__"
    resources: List[Resource] = []
    max_search_results: int = 3
    mcp_settings: Optional[MCPSettings] = None
    enable_background_investigation: bool = True
    enable_web_search: bool = True
    locale: str = "en-US"
```

**Generator Function**:
```python
async def _astream_workflow_generator(
    messages: List[dict],
    thread_id: str,
    resources: List[Resource],
    max_search_results: int,
    mcp_settings: dict,
    enable_background_investigation: bool,
    enable_web_search: bool,
    locale: str = "en-US",
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses using LangGraph workflow.
    Yields SSE-formatted events.
    """
```

**SSE Events Emitted**:

| Event | When | Data |
|-------|------|------|
| `message` | Text content | `{"type": "text", "content": "..."}` |
| `message_start` | Message begins | `{"messageId": "..."}` |
| `message_content` | Content chunk | `{"messageId": "...", "delta": "..."}` |
| `message_end` | Message complete | `{"messageId": "..."}` |
| `reasoning_start` | Thinking begins | `{"messageId": "..."}` |
| `reasoning_message_start` | Reasoning message | `{"messageId": "..."}` |
| `reasoning_message_content` | Reasoning chunk | `{"messageId": "...", "delta": "..."}` |
| `reasoning_message_end` | Reasoning done | `{"messageId": "..."}` |
| `reasoning_end` | All reasoning done | `{"messageId": "..."}` |
| `tool_call_start` | Tool invocation | `{"toolCallId": "...", "toolCallName": "..."}` |
| `tool_call_args` | Tool arguments | `{"toolCallId": "...", "delta": "..."}` |
| `tool_call_end` | Tool call complete | `{"toolCallId": "..."}` |
| `tool_call` | Legacy complete call | `{"id": "...", "name": "...", "args": {...}}` |
| `tool_result` | Tool output | `{"toolCallId": "...", "result": "..."}` |
| `error` | Error occurred | `{"message": "..."}` |
| `interrupt` | HITL pause | `{"interrupt_id": "...", "action_requests": [...]}` |

### 3.2 Agent Endpoint (With Sandbox)

**File**: `backend/app/agent/api/v1/agent.py`

**Endpoint**: `POST /api/v1/agent/agent/stream`

**Request Model**:
```python
class AgentRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: str = "__default__"
    module_type: AgentModuleType = AgentModuleType.GENERAL
    resources: List[Resource] = []
    max_plan_iterations: int = 1
    max_step_num: int = 3
    max_search_results: int = 3
    auto_accepted_plan: bool = True
    interrupt_feedback: Optional[str] = None
    enable_background_investigation: bool = True
    enable_web_search: bool = True
    locale: str = "en-US"
```

**Generator Function**:
```python
async def _agent_stream_generator(
    graph,
    module_name: str,
    messages: List[dict],
    thread_id: str,
    sandbox_manager: SessionSandboxManager,
    resources: List[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: Optional[str],
    enable_background_investigation: bool,
    enable_web_search: bool,
    locale: str,
    db_session: CurrentSession,
    user_api_key: str,
) -> AsyncGenerator[str, None]:
```

**Additional Status Events** (agent-specific):

| Event | Status | Data |
|-------|--------|------|
| `status` | `processing` | `{"message": "Starting agent..."}` |
| `status` | `sandbox_ready` | `{"sandbox_id": "...", "start_type": "cold|warm"}` |
| `status` | `mcp_ready` | `{"mcp_url": "..."}` |
| `status` | `codex_ready` | `{"codex_url": "..."}` |
| `status` | `vscode_ready` | `{"vscode_url": "..."}` |
| `status` | `design_ready` | `{"design_url": "..."}` |
| `status` | `latex_ready` | `{"latex_url": "..."}` |
| `status` | `excalidraw_ready` | `{"excalidraw_url": "..."}` |
| `status` | `graphiti_ready` | `{"graphiti_url": "..."}` |
| `status` | `skills_loaded` | `{"message": "Skills loaded"}` (cold start) |
| `status` | `agent_start` | `{"message": "Agent starting"}` |
| `status` | `complete` | `{"vscode_url": "...", "codex_url": "...", ...}` |

### 3.3 AG-UI Protocol Models

**File**: `backend/app/agent/models.py`

#### Content Block Types

```python
class ContentBlockType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
```

#### Chat Message

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: Union[str, List[ContentBlock], List[Dict[str, Any]]]
    name: Optional[str] = None
```

#### Tool Call

```python
class ToolCall(BaseModel):
    tool_call_id: str
    tool_name: str
    tool_input: Union[Dict[str, Any], str]
    index: Optional[int] = None
    
    def to_ag_ui_start_event(self) -> Dict[str, Any]:
        return {"toolCallId": self.tool_call_id, "toolCallName": self.tool_name}
    
    def to_ag_ui_args_event(self, delta: str) -> Dict[str, Any]:
        return {"toolCallId": self.tool_call_id, "delta": delta}
    
    def to_ag_ui_end_event(self) -> Dict[str, Any]:
        return {"toolCallId": self.tool_call_id}
```

#### Reasoning State

```python
@dataclass
class ReasoningState:
    message_id: Optional[str] = None
    is_active: bool = False
    
    def start_reasoning(self) -> str:
        self.message_id = str(uuid4())
        self.is_active = True
        return self.message_id
    
    def end_reasoning(self) -> Optional[str]:
        if self.is_active:
            self.is_active = False
            return self.message_id
        return None
```

#### HITL (Human-in-the-Loop)

```python
class HITLDecisionType(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    ACCEPTED = "accepted"
    FEEDBACK = "feedback"

class HITLRequest(BaseModel):
    interrupt_id: str
    action_requests: List[ActionRequest]
    review_configs: List[ReviewConfig]
    prompt: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

def create_hitl_interrupt_event(interrupt_value, thread_id) -> str:
    """Generate SSE-formatted HITL interrupt event."""
```

#### Event Helper

```python
def make_ag_ui_event(event_type: str, data: Dict[str, Any]) -> str:
    """Create SSE-formatted event string."""
    json_data = json.dumps(data, default=str, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"
```

---

## 4. Backend Agent Modules

**File**: `backend/app/agent/api/v1/agent.py` (ModuleRegistry)

### AgentType Enum

```python
class AgentType(str, Enum):
    # No-sandbox (routes to chat.py)
    CHAT = "chat"
    
    # With sandbox (routes to agent.py)
    GENERAL = "general"
    DEEP_RESEARCH = "deep_research"
    ACADEMIC = "academic"
    DESIGN = "design"
    DEV = "dev"
    DATA_SCIENTIST = "data_scientist"
    SLIDES = "slides"
    DOCUMENTS = "documents"
    QUANT = "quant"
    EXCALIDRAW = "excalidraw"
    
    @property
    def requires_sandbox(self) -> bool:
        return self != AgentType.CHAT
```

### AgentModuleType Enum

```python
class AgentModuleType(str, Enum):
    GENERAL = "general"
    DEEP_RESEARCH = "deep_research"
    ACADEMIC = "academic"
    DESIGN = "design"
    DEV = "dev"
    DATA_SCIENTIST = "data_scientist"
    SLIDES = "slides"
    DOCUMENTS = "documents"
    QUANT = "quant"
    EXCALIDRAW = "excalidraw"
```

### Module Registry

```python
class ModuleRegistry:
    _loaded_graphs: Dict[str, CompiledGraph] = {}
    _module_info: Dict[str, ModuleInfo] = {
        "general": ModuleInfo(loader=lambda: general_graph, description="Default agent"),
        "deep_research": ModuleInfo(loader=lambda: deep_research_graph, description="Multi-agent research"),
        "academic": ModuleInfo(loader=lambda: academic_graph, description="Academic research"),
        "design": ModuleInfo(loader=lambda: design_graph, description="Design workflow"),
        "dev": ModuleInfo(loader=lambda: dev_graph, description="Software development"),
        "data_scientist": ModuleInfo(loader=lambda: data_science_graph, description="Data science"),
        "slides": ModuleInfo(loader=lambda: slides_graph, description="Presentations"),
        "documents": ModuleInfo(loader=lambda: documents_graph, description="LaTeX/documents"),
        "quant": ModuleInfo(loader=lambda: quant_graph, description="Financial analysis"),
        "excalidraw": ModuleInfo(loader=lambda: excalidraw_graph, description="Diagrams"),
    }
    
    @classmethod
    def get_graph(cls, module_type: AgentModuleType) -> CompiledGraph:
        name = module_type.value
        if name not in cls._loaded_graphs:
            cls._loaded_graphs[name] = cls._module_info[name].loader()  # Lazy load
        return cls._loaded_graphs[name]
```

### Agent Category Mapping (for skills)

```python
def _get_agent_category(agent_type: AgentType) -> str:
    """Map AgentType to skill folder category."""
    mapping = {
        AgentType.GENERAL: "general",
        AgentType.DEV: "general",
        AgentType.DESIGN: "general",
        AgentType.EXCALIDRAW: "general",
        
        AgentType.DEEP_RESEARCH: "scientific",
        AgentType.DATA_SCIENTIST: "scientific",
        AgentType.QUANT: "scientific",
        
        AgentType.ACADEMIC: "academic",
        AgentType.SLIDES: "academic",
        AgentType.DOCUMENTS: "academic",
    }
    return mapping.get(agent_type, "general")
```

---

## 5. Backend Sandbox URLs

### Port Configuration

| Setting | Port | Service | URL Variable |
|---------|------|---------|--------------|
| `SANDBOX_MCP_SERVER_PORT` | 6060 | MCP Tool Server | `mcp_url` |
| `SANDBOX_CODE_SERVER_PORT` | 9000 | VS Code (code-server) | `vscode_url` |
| `SANDBOX_CODEX_SSE_PORT` | 1324 | Codex SSE Server | `codex_url` |
| `SANDBOX_LATEX_EDITOR_PORT` | 9001 | LaTeX AI Editor | `latex_url` |
| `SANDBOX_DESIGN_MCP_PORT` | 6002 | Design MCP (Draw.io) | `design_url` |
| `SANDBOX_EXCALIDRAW_PORT` | 6003 | Excalidraw | `excalidraw_url` |
| `SANDBOX_GRAPHITI_MCP_PORT` | 8500 | Graphiti (Knowledge Graph) | `graphiti_url` |
| `SANDBOX_FALKORDB_WEBUI_PORT` | 3500 | FalkorDB Web UI | (debug only) |

### URL Exposure (in query_handler.py)

```python
sandbox, _ = await sandbox_manager.get_sandbox()

urls = {}
urls['mcp_url'] = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)
urls['vscode_url'] = await sandbox.expose_port(settings.SANDBOX_CODE_SERVER_PORT)
urls['codex_url'] = await sandbox.expose_port(settings.SANDBOX_CODEX_SSE_PORT)
urls['design_url'] = await sandbox.expose_port(settings.SANDBOX_DESIGN_MCP_PORT)
urls['latex_url'] = await sandbox.expose_port(settings.SANDBOX_LATEX_EDITOR_PORT)
urls['excalidraw_url'] = await sandbox.expose_port(settings.SANDBOX_EXCALIDRAW_PORT)
urls['graphiti_url'] = await sandbox.expose_port(settings.SANDBOX_GRAPHITI_MCP_PORT)
```

---

## 6. Frontend WebSocket Context

**File**: `frontend/src/contexts/websocket-context.tsx`

### Provider Structure

```tsx
interface SocketIOContextType {
    socket: Socket | null
    connectSocket: () => void
    sendMessage: (payload: { type: string; content: WebSocketMessageContent }) => boolean
    joinSession: () => void
}

export function SocketIOProvider({ children, handleEvent }: SocketIOProviderProps)
```

### Connection Configuration

```typescript
const socketOptions: Partial<ManagerOptions & SocketOptions> = {
    auth: { token },  // JWT from localStorage
    transports: ['websocket', 'polling'],
    timeout: 15000,
    reconnection: false  // Manual reconnection
}

// Connect to /ws namespace
const socketInstance = io(`${import.meta.env.VITE_API_URL}/ws`, socketOptions)
```

### Event Listeners

```typescript
socketInstance.on('connect', () => {
    dispatch(setWsConnectionState(WebSocketConnectionState.CONNECTED))
    
    // Auto-join session for new questions
    if (sessionIdRef.current && isFromNewQuestionRef.current) {
        socketInstance.emit('join_session', { session_uuid: sessionIdRef.current })
    }
})

socketInstance.on('chat_event', (data) => {
    handleEventRef.current({ ...data, id: Date.now().toString() })
})

socketInstance.on('connect_error', (error) => {
    dispatch(setWsConnectionState(WebSocketConnectionState.DISCONNECTED))
})

socketInstance.on('disconnect', (reason) => {
    dispatch(setWsConnectionState(WebSocketConnectionState.DISCONNECTED))
})
```

### Methods Exposed

```typescript
const joinSession = useCallback(() => {
    socket.emit('join_session', { session_uuid: sessionIdRef.current })
}, [socket])

const sendMessage = useCallback((payload: { type: string; content: WebSocketMessageContent }) => {
    const messageWithSession = sessionIdRef.current
        ? { ...payload, session_uuid: sessionIdRef.current }
        : payload
    
    socket.emit('chat_message', messageWithSession)
    return true
}, [socket])
```

### Usage Example (Agent Mode)

```tsx
// In agent page component
const { sendMessage, joinSession } = useSocketIOContext()

// Join session on mount
useEffect(() => {
    if (sessionId) {
        joinSession()
    }
}, [sessionId])

// Send query
const handleSubmit = () => {
    sendMessage({
        type: 'query',
        content: {
            message: question,
            files: currentMessageFileIds,
            agent_type: selectedAgentType,
            model_id: selectedModelId,
            locale: 'en-US'
        }
    })
}
```

---

## 7. Frontend SSE Service

**File**: `frontend/src/services/chat.service.ts`

### Endpoint Selection

```typescript
// Determine endpoint based on agent type
const endpoint = payload.agent_type && payload.agent_type !== 'chat'
    ? '/agent/agent/stream'   // Sandbox agents
    : '/agent/chat/stream'    // Simple chat
```

### Request Payload

```typescript
interface ChatQueryPayload {
    session_id?: string
    model_id: string
    text: string
    files: string[]
    agent_type?: string  // 'chat' for simple, or agent module type
    tools?: {
        web_search: boolean
        web_visit: boolean
        image_search: boolean
        code_interpreter?: boolean
    }
}

// Sent to backend
{
    messages: [{ role: 'user', content: payload.text }],
    model_id: payload.model_id,
    session_id: payload.session_id,
    thread_id: payload.session_id,
    file_ids: payload.files,
    agent_type: payload.agent_type || 'chat',
    tools: payload.tools ?? {
        web_search: true,
        image_search: true,
        web_visit: true,
        code_interpreter: true
    }
}
```

### SSE Parsing

```typescript
const parseSSEBlock = (block: string): { event?: string; data?: string } | null => {
    let eventName: string | undefined
    const dataLines: string[] = []
    
    for (const rawLine of block.split('\n')) {
        const line = rawLine.trim()
        if (line.startsWith('event:')) {
            eventName = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim())
        }
    }
    
    return { event: eventName, data: dataLines.join('\n') }
}
```

### Event Normalization

```typescript
const normalizeStreamEvent = (eventName: string | undefined, raw: unknown): ChatStreamEvent[] => {
    const events: ChatStreamEvent[] = []
    
    // Handle session event
    if (eventName === 'session') {
        events.push({
            type: 'session',
            session_id: record.session_id,
            is_new_session: record.status === 'created',
            ...
        })
    }
    
    // Handle thinking event
    if (eventName === 'thinking') {
        if (record.status === 'delta') {
            events.push({ type: 'thinking', status: 'delta', delta: record.delta })
        }
    }
    
    // Handle content event
    if (eventName === 'content') {
        if (record.status === 'start') {
            events.push({ type: 'content_start' })
        } else if (record.status === 'delta') {
            events.push({ type: 'token', content: record.delta })
        }
    }
    
    // Handle tool_call event
    if (eventName === 'tool_call') {
        if (record.status === 'start') {
            events.push({ type: 'tool_call_start', id: record.id, name: record.name })
        } else if (record.status === 'delta') {
            events.push({ type: 'tool_call_delta', id: record.id, delta: record.delta })
        } else if (record.status === 'stop') {
            events.push({ type: 'tool_call_stop', id: record.id, name: record.name, input: record.input })
        }
    }
    
    // Handle tool_result, complete, error events...
    
    return events
}
```

### ChatStreamEvent Types

```typescript
type ChatStreamEvent =
    | { type: 'session'; session_id: string; is_new_session?: boolean; ... }
    | { type: 'content_start' }
    | { type: 'token'; content: string }
    | { type: 'thinking'; status: 'delta'; delta: string; signature?: string }
    | { type: 'tool_call_start'; id: string; name: string; call_type: string }
    | { type: 'tool_call_delta'; id: string; delta: string }
    | { type: 'tool_call_stop'; id: string; name: string; input: string }
    | { type: 'tool_result'; tool_call_id: string; name: string; output: string; is_error?: boolean }
    | { type: 'usage'; input_tokens: number; output_tokens: number; total_tokens: number; ... }
    | { type: 'complete'; message_id?: string; finish_reason?: string; elapsed_ms?: number }
    | { type: 'done' }
    | { type: 'error'; message?: string }
```

---

## 8. Frontend Event Handling

**File**: `frontend/src/hooks/use-app-events.tsx`

### handleEvent Function

This function processes all WebSocket `chat_event` data:

```typescript
const handleEvent = useCallback((data: {
    id: string
    type: AgentEvent
    content: Record<string, unknown>
}, ignoreClickAction?: boolean) => {
    switch (data.type) {
        case AgentEvent.AGENT_INITIALIZED:
            // Set vscode_url, reset state
            dispatch(setAgentInitialized(true))
            dispatch(setVscodeUrl(data.content.vscode_url))
            break
            
        case AgentEvent.STATUS_UPDATE:
            // Update loading state
            dispatch(setLoading(data.content.status === 'running'))
            break
            
        case AgentEvent.ERROR:
            toast.error(data.content.message)
            dispatch(setLoading(false))
            break
            
        case AgentEvent.SANDBOX_STATUS:
            dispatch(setSandboxIframeAwake(data.content.status === 'running'))
            dispatch(setVscodeUrl(data.content.vscode_url))
            break
            
        case AgentEvent.SYSTEM:
            if (data.content.session_id) {
                dispatch(setActiveSessionId(data.content.session_id))
                navigate(`/${data.content.session_id}`)
            } else if (data.content.deployment_url) {
                dispatch(setPublished(data.content.deployment_url))
            }
            break
            
        case AgentEvent.USER_MESSAGE:
            dispatch(addMessage({ role: 'user', content: data.content.text }))
            break
            
        case AgentEvent.AGENT_THINKING:
            dispatch(addMessage({ role: 'assistant', content: data.content.text, isThinkMessage: true }))
            break
            
        case AgentEvent.TOOL_CALL:
            // Create action step message
            dispatch(addMessage({
                role: 'assistant',
                action: {
                    type: data.content.tool_name,
                    data: { tool_input: data.content.tool_input }
                }
            }))
            break
            
        case AgentEvent.TOOL_RESULT:
            // Update existing message with result
            dispatch(updateMessage({
                id: data.content.tool_call_id,
                action: { data: { result: data.content.result, isResult: true } }
            }))
            break
            
        case AgentEvent.AGENT_RESPONSE:
            dispatch(addMessage({ role: 'assistant', content: data.content.text }))
            break
            
        case AgentEvent.COMPLETE:
            dispatch(setCompleted(true))
            dispatch(setLoading(false))
            break
            
        case AgentEvent.PONG:
            // Heartbeat response
            break
            
        // ... more cases
    }
}, [dispatch, navigate])
```

### Special Tool Handling

The event handler has special logic for certain tools:

```typescript
// Subagent tools - creates nested agent context
const isSubagentTool = 
    data.content.tool_name === TOOL.SUB_AGENT ||
    data.content.tool_name === TOOL.TASK ||
    data.content.tool_name === TOOL.CODEX_AGENT

// URL extraction from results
if (data.content.tool_name === TOOL.REGISTER_DEPLOYMENT) {
    const urls = extractUrls(data.content.result)
    dispatch(setResultUrl(urls[0]))
}

// Browser URL handling
if (data.content.tool_name === TOOL.BROWSER_NAVIGATE) {
    dispatch(setBrowserUrl(data.content.tool_input.url))
}
```

---

## 9. Frontend State Management

### Redux Store Structure

```
store/
├── messages      # Chat messages array, editing state
├── ui            # Loading, creating session, active tab, mobile visibility
├── agent         # Completed, stopped, result URL, sandbox awake, published URL
├── files         # Uploaded files, current message file IDs
├── workspace     # Workspace info, browser URL, vscode URL, current question
├── settings      # Tool settings, chat tool settings, selected model, available models
├── sessions      # Sessions list, active session ID
├── favorites     # Favorite session IDs
└── user          # User info
```

### Key Slices

**Agent Slice** (`state/slice/agent.ts`):
```typescript
interface AgentState {
    isCompleted: boolean
    isStopped: boolean
    resultUrl: string | null
    isSandboxIframeAwake: boolean
    isAgentInitialized: boolean
    isFullstackProjectInitialized: boolean
    published: string | null
    wsConnectionState: WebSocketConnectionState
    buildStep: BUILD_STEP
    selectedBuildStep: BUILD_STEP | null
}
```

**Workspace Slice** (`state/slice/workspace.ts`):
```typescript
interface WorkspaceState {
    workspaceInfo: string | null
    browserUrl: string | null
    vscodeUrl: string | null
    currentQuestion: string
}
```

**Sessions Slice** (`state/slice/sessions.ts`):
```typescript
interface SessionsState {
    sessions: ISession[]
    activeSessionId: string | null
    isFromNewQuestion: boolean
}
```

### RTK Query APIs

**Session API** (`state/api/session-api.ts`):
```typescript
sessionApi.endpoints.getSessions  // GET /agent/chat-sessions
sessionApi.endpoints.getSession   // GET /agent/chat-sessions/:id
sessionApi.endpoints.deleteSession // DELETE /agent/chat-sessions/:id
```

**User API** (`state/api/user-api.ts`):
```typescript
userApi.endpoints.getCreditBalance  // GET /credits/balance
userApi.endpoints.getCreditUsage    // GET /credits/usage
```

---

## 10. Integration Mapping

### File-to-File Connections

| Backend File | Frontend File | Connection Type |
|--------------|---------------|-----------------|
| `backend/common/socketio/handlers.py` | `frontend/src/contexts/websocket-context.tsx` | Socket.IO events |
| `backend/common/socketio/command/query_handler.py` | `frontend/src/hooks/use-app-events.tsx` | Event handling |
| `backend/app/agent/api/v1/chat.py` | `frontend/src/services/chat.service.ts` | SSE streaming |
| `backend/app/agent/api/v1/agent.py` | `frontend/src/services/chat.service.ts` | SSE streaming (sandbox) |
| `backend/app/agent/api/v1/chat_sessions.py` | `frontend/src/services/session.service.ts` | REST API |

### Event Type Mapping

| Backend Event | Frontend Type | Handler Location |
|---------------|---------------|------------------|
| `agent_initialized` | `AgentEvent.AGENT_INITIALIZED` | `use-app-events.tsx` |
| `connection_established` | `AgentEvent.CONNECTION_ESTABLISHED` | `use-app-events.tsx` |
| `processing` | `AgentEvent.PROCESSING` | `use-app-events.tsx` |
| `status_update` | `AgentEvent.STATUS_UPDATE` | `use-app-events.tsx` |
| `error` | `AgentEvent.ERROR` | `use-app-events.tsx` |
| `system` | `AgentEvent.SYSTEM` | `use-app-events.tsx` |
| `tool_call` | `AgentEvent.TOOL_CALL` | `use-app-events.tsx` |
| `tool_result` | `AgentEvent.TOOL_RESULT` | `use-app-events.tsx` |
| `agent_response` | `AgentEvent.AGENT_RESPONSE` | `use-app-events.tsx` |
| `complete` | `AgentEvent.COMPLETE` | `use-app-events.tsx` |
| `cancelled` | `AgentEvent.AGENT_RESPONSE_INTERRUPTED` | `use-app-events.tsx` |
| `sandbox_status` | `AgentEvent.SANDBOX_STATUS` | `use-app-events.tsx` |
| `pong` | `AgentEvent.PONG` | `use-app-events.tsx` |

### SSE Event Mapping (Chat Mode)

| Backend SSE Event | Frontend ChatStreamEvent | Notes |
|-------------------|--------------------------|-------|
| `session` (status: created) | `{ type: 'session', is_new_session: true }` | Session created |
| `content` (status: delta) | `{ type: 'token', content: delta }` | Text chunk |
| `thinking` (status: delta) | `{ type: 'thinking', delta: delta }` | Reasoning |
| `tool_call` (status: start) | `{ type: 'tool_call_start', id, name }` | Tool start |
| `tool_call` (status: delta) | `{ type: 'tool_call_delta', id, delta }` | Tool args |
| `tool_call` (status: stop) | `{ type: 'tool_call_stop', id, name, input }` | Tool end |
| `tool_result` (status: info) | `{ type: 'tool_result', tool_call_id, output }` | Tool output |
| `usage` (status: info) | `{ type: 'usage', input_tokens, output_tokens }` | Token stats |
| `complete` (status: done) | `{ type: 'complete', message_id }` | Stream done |
| `error` | `{ type: 'error', message }` | Error |

---

## 11. Event Type Reference

### Backend UserCommandType

```python
class UserCommandType(str, Enum):
    INIT_AGENT = "init_agent"
    QUERY = "query"
    WORKSPACE_INFO = "workspace_info"
    AWAKE_SANDBOX = "awake_sandbox"
    SANDBOX_STATUS = "sandbox_status"
    PING = "ping"
    CANCEL = "cancel"
    ENHANCE_PROMPT = "enhance_prompt"
    PUBLISH_PROJECT = "publish"
```

### Frontend AgentEvent

```typescript
enum AgentEvent {
    AGENT_INITIALIZED = 'agent_initialized',
    USER_MESSAGE = 'user_message',
    CONNECTION_ESTABLISHED = 'connection_established',
    WORKSPACE_INFO = 'workspace_info',
    PROCESSING = 'processing',
    AGENT_THINKING = 'agent_thinking',
    TOOL_CALL = 'tool_call',
    TOOL_RESULT = 'tool_result',
    AGENT_RESPONSE = 'agent_response',
    COMPLETE = 'complete',
    ERROR = 'error',
    SYSTEM = 'system',
    PONG = 'pong',
    UPLOAD_SUCCESS = 'upload_success',
    BROWSER_USE = 'browser_use',
    FILE_EDIT = 'file_edit',
    PROMPT_GENERATED = 'prompt_generated',
    AGENT_RESPONSE_INTERRUPTED = 'agent_response_interrupted',
    STATUS_UPDATE = 'status_update',
    SANDBOX_STATUS = 'sandbox_status',
    SUB_AGENT_COMPLETE = 'sub_agent_complete',
    TOOL_PROGRESS = 'tool_progress',
    MODEL_COMPACT = 'model_compact'
}
```

### Frontend TOOL Enum (Selected)

```typescript
enum TOOL {
    // Core tools
    MESSAGE_USER = 'message_user',
    WEB_SEARCH = 'web_search',
    BROWSER_NAVIGATE = 'browser_navigate',
    
    // File operations
    READ = 'Read',
    WRITE = 'Write',
    EDIT = 'Edit',
    LS = 'LS',
    
    // Shell operations
    BASH = 'Bash',
    SHELL_EXEC = 'shell_exec',
    
    // Agent tools
    SUB_AGENT = 'sub_agent',
    TASK = 'Task',
    CODEX_AGENT = 'codex_agent',
    DEEP_RESEARCH = 'deep_research',
    
    // Deployment
    STATIC_DEPLOY = 'static_deploy',
    REGISTER_DEPLOYMENT = 'register_deployment',
    
    // Presentations
    SLIDE_DECK_INIT = 'slide_deck_init',
    SLIDE_WRITE = 'SlideWrite',
    
    // MCP
    MCP_TOOL = 'mcp_tool',
    MCP_CODEX_EXECUTE = 'mcp_codex_execute',
    CLAUDE_CODE = 'mcp_claude_code'
}
```

---

## 12. Implementation Checklist

### Step 5.1: Verify WebSocket Connection ✅

- [ ] Frontend `websocket-context.tsx` connects to `${VITE_API_URL}/ws`
- [ ] Auth includes JWT token from localStorage (`ACCESS_TOKEN`)
- [ ] `join_session` emits with `{ session_uuid }`
- [ ] `chat_message` emits with `{ type, content, session_uuid }`
- [ ] `chat_event` listener dispatches to `handleEvent`

### Step 5.2: Verify SSE Streaming ✅

- [ ] `chat.service.ts` selects correct endpoint based on `agent_type`
- [ ] Request payload matches `ChatRequest` / `AgentRequest` models
- [ ] SSE parsing handles `event:` and `data:` lines
- [ ] `normalizeStreamEvent` maps all event types correctly

### Step 5.3: Verify Event Handling ✅

- [ ] `use-app-events.tsx` handles all `AgentEvent` types
- [ ] State updates dispatch to correct Redux slices
- [ ] Tool calls create proper message structure
- [ ] Session ID updates trigger navigation

### Step 5.4: Verify Command Handlers ✅

- [ ] Backend `QueryHandler` routes to correct generator
- [ ] `_forward_sse_event` correctly parses and emits via Socket.IO
- [ ] Cancellation flag checked in streaming loops
- [ ] Sandbox URLs emitted in `agent_initialized` event

### Step 5.5: Integration Points to Test

| Test Case | Frontend Action | Expected Backend Response |
|-----------|-----------------|---------------------------|
| New session | Navigate to `/`, type question, submit | `system` event with `session_id`, navigate to `/:sessionId` |
| Existing session | Navigate to `/:sessionId` | `join_session` → `connection_established` |
| Chat query (simple) | Submit with `agent_type: 'chat'` | SSE stream via `/chat/stream` |
| Agent query (sandbox) | Submit with `agent_type: 'general'` | WebSocket events via `QueryHandler` |
| Cancel | Click cancel button | `cancel` command → `cancelled` event |
| Ping | Automatic (heartbeat) | `pong` event |
| Sandbox status | Check sandbox | `sandbox_status` event with URLs |

---

## Appendix A: External GitHub Reference

The external ii-agent project provides a reference implementation:

| ii-agent File | Our Equivalent | Notes |
|---------------|----------------|-------|
| `server/socket/socketio.py` | `backend/common/socketio/handlers.py` | SocketIOManager class |
| `server/socket/session_store.py` | `backend/common/socketio/session_store.py` | Redis session store |
| `server/socket/command/query_handler.py` | `backend/common/socketio/command/query_handler.py` | Query processing |
| `server/socket/command/command_handler.py` | `backend/common/socketio/command/base_handler.py` | Base class |
| `server/chat/router.py` | `backend/app/agent/api/v1/chat.py` | SSE streaming |

### Key Differences

1. **Namespace**: We use `/ws`, ii-agent uses default `/`
2. **Event Format**: We use AG-UI Protocol names, ii-agent uses slightly different names
3. **Generator Bridge**: Our `QueryHandler` bridges SSE generators to Socket.IO, ii-agent has separate paths

---

## Appendix B: MCP Configuration

### MCPSettings Schema

```python
class MCPServerConfig(BaseModel):
    transport: str  # 'stdio' or 'http'
    command: Optional[str]  # For stdio transport
    args: Optional[List[str]]  # Command arguments
    url: Optional[str]  # For http transport
    enabled_tools: Optional[List[str]]  # Whitelist
    add_to_agents: Optional[List[str]]  # Agent list

class MCPSettings(BaseModel):
    servers: Optional[dict[str, MCPServerConfig]]
```

### Example MCP Configuration

```json
{
    "servers": {
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-filesystem"],
            "enabled_tools": ["read_file", "write_file"]
        },
        "graphiti": {
            "transport": "http",
            "url": "http://localhost:8500/mcp/"
        }
    }
}
```

---

*Document generated from comprehensive codebase investigation for Step 5 of Frontend-Backend Integration Plan.*
