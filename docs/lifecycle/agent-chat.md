# Agent Chat Lifecycle

> From chat request to streaming response through LangGraph.

---

## Overview

The agent chat system provides:
- **Streaming responses** via Server-Sent Events (SSE)
- **Multi-agent workflow** using LangGraph
- **Tool execution** via MCP tool server
- **Memory persistence** for conversation history

---

## Complete Flow

```mermaid
flowchart TD
    subgraph Frontend
        A[User types message]
        B[Send ChatRequest]
        Z[Display streaming response]
    end
    
    subgraph Backend API
        C[POST /agent/chat/stream]
        D[JWT Authentication]
        E[Build workflow input]
    end
    
    subgraph LangGraph
        F[Graph Entry]
        G{Agent Node}
        H[Background Investigator]
        I[Base Agent]
        J[Human Feedback]
    end
    
    subgraph Tool Execution
        K[Tool Call Decision]
        L[MCP Tool Server]
        M[Tool Result]
    end
    
    subgraph Response
        N[SSE Stream]
        O[Format chunks]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    
    F --> G
    G --> H
    G --> I
    G --> J
    
    I --> K
    K -->|Yes| L
    L --> M
    M --> I
    K -->|No| N
    
    H --> N
    I --> N
    J --> N
    
    N --> O
    O --> Z
```

---

## Request Structure

```http
POST /api/v1/agent/chat/stream
Authorization: Bearer <token>
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Create a React component"}
  ],
  "thread_id": "session-123",
  "agent_name": "coder",
  "resources": [
    {"uri": "https://docs.example.com", "name": "Docs"}
  ],
  "mcp_settings": {
    "servers": {
      "my-mcp": {"command": "...", "args": [...]}
    }
  },
  "enable_web_search": true,
  "enable_deep_thinking": false,
  "enable_clarification": true,
  "max_clarification_rounds": 2,
  "locale": "en-US",
  "interrupt_before_tools": ["shell_run_command"]
}
```

---

## SSE Response Events

The response is a stream of Server-Sent Events:

### Text Content
```
event: message
data: {"type": "text", "agent": "coder", "content": "I'll create a React..."}
```

### Tool Call
```
event: message
data: {"type": "tool_call", "tool": "file_write", "args": {"path": "...", "content": "..."}}
```

### Tool Result
```
event: message
data: {"type": "tool_result", "tool": "file_write", "result": "File written successfully"}
```

### Interrupt (Human Feedback)
```
event: interrupt
data: {"thread_id": "session-123", "needs_input": true, "prompt": "Should I proceed?"}
```

### Stream Complete
```
event: done
data: {"thread_id": "session-123", "agent": "reporter"}
```

---

## LangGraph Workflow

```mermaid
stateDiagram-v2
    [*] --> BackgroundInvestigator: New message
    
    BackgroundInvestigator --> BaseAgent: Research complete
    
    BaseAgent --> ToolExecution: Need tool
    ToolExecution --> BaseAgent: Tool result
    
    BaseAgent --> HumanFeedback: Need clarification
    HumanFeedback --> BaseAgent: User response
    
    BaseAgent --> Reporter: Task complete
    Reporter --> [*]: Final response
```

**Nodes:**
| Node | Purpose |
|------|---------|
| `BackgroundInvestigator` | Web research if enabled |
| `BaseAgent` | Main reasoning and tool use |
| `HumanFeedback` | Clarification requests |
| `Reporter` | Final response generation |

---

## Tool Execution Flow

```mermaid
sequenceDiagram
    participant Agent as LangGraph Agent
    participant MCP as MCP Client
    participant Server as Tool Server
    participant Tool as Actual Tool
    
    Agent->>Agent: Decide to use tool
    Agent->>MCP: call_tool("shell_run_command", {...})
    MCP->>Server: HTTP POST to /mcp
    Server->>Tool: Execute ShellRunCommand
    Tool->>Tool: Run command in tmux
    Tool-->>Server: ToolResult
    Server-->>MCP: MCP Response
    MCP-->>Agent: Result string
    Agent->>Agent: Continue reasoning
```

---

## Memory & Persistence

### Thread ID
Each conversation has a `thread_id` for:
- **Checkpointing**: Save/resume conversation state
- **Memory**: Retrieve past messages
- **Credits**: Track token usage per session

### Session Metrics
| Column | Purpose |
|--------|---------|
| `session_id` | Links to thread_id |
| `model_name` | LLM used |
| `credits` | Credits consumed |
| `total_prompt_tokens` | Input tokens |
| `total_completion_tokens` | Output tokens |

---

## Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `enable_web_search` | bool | Use Tavily for web research |
| `enable_deep_thinking` | bool | Extended reasoning mode |
| `enable_clarification` | bool | Allow agent to ask questions |
| `max_clarification_rounds` | int | Limit on clarification loops |
| `interrupt_before_tools` | list | Tools requiring confirmation |

---

## Error Handling

| Error | Cause | Response |
|-------|-------|----------|
| 401 | Invalid/missing token | `{"detail": "Unauthorized"}` |
| 400 | Invalid request body | `{"detail": "Validation error"}` |
| 500 | Agent error | SSE event: `{"type": "error", "message": "..."}` |

---

## Code References

| File | Purpose |
|------|---------|
| [chat.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/app/agent/api/v1/chat.py) | Chat endpoint |
| [builder.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/src/graph/builder.py) | LangGraph workflow |
| [nodes.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/src/graph/nodes.py) | Agent nodes |
| [client.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/src/tool_server/mcp/client.py) | MCP client |

---

## Frontend Integration

```typescript
// Using EventSource
const eventSource = new EventSource(
  `/api/v1/agent/chat/stream?...`,
  { withCredentials: true }
)

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  switch (data.type) {
    case 'text':
      appendToChat(data.content)
      break
    case 'tool_call':
      showToolCall(data.tool, data.args)
      break
    case 'tool_result':
      showToolResult(data.result)
      break
  }
}

eventSource.addEventListener('done', () => {
  eventSource.close()
})
```
