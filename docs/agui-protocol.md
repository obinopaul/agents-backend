# AG-UI Protocol Implementation Guide

> Complete guide to the AG-UI (Agent-User Interface) Protocol implementation for streaming events including tool calls, reasoning, multimodal messages, and human-in-the-loop (HITL) interrupts.

---

## Table of Contents

1. [Overview](#overview)
2. [Event Types](#event-types)
3. [Tool Call Events](#tool-call-events)
4. [Reasoning Events](#reasoning-events)
5. [Multimodal Messages](#multimodal-messages)
6. [Human-in-the-Loop (HITL)](#human-in-the-loop-hitl)
7. [Structured Models](#structured-models)
8. [Frontend Integration](#frontend-integration)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The AG-UI Protocol provides a standardized way for AI agents to communicate with frontend applications through Server-Sent Events (SSE). This implementation supports:

| Feature | Description |
|---------|-------------|
| **Tool Calls** | Real-time streaming of tool execution lifecycle |
| **Reasoning** | Model thinking/reasoning content (when supported) |
| **Multimodal** | Image and file content in messages |
| **HITL** | Human-in-the-loop interrupts for approval/edit/reject workflows |
| **LangChain v1** | Full compatibility with LangChain's `content_blocks` format |

### Endpoints

| Endpoint | Streaming Mode | Features |
|----------|---------------|----------|
| `/agent/chat/stream` | `astream` (messages mode) | Chat, tools, reasoning |
| `/agent/agent/stream` | `astream_events` | Chat, tools, reasoning, sandbox |

---

## Event Types

### Tool Events

| Event | Description | Payload |
|-------|-------------|---------|
| `tool_call_start` | Tool execution begins | `{toolCallId, toolCallName}` |
| `tool_call_args` | Tool arguments streaming | `{toolCallId, delta}` |
| `tool_call_end` | Tool execution completes | `{toolCallId}` |
| `tool_result` | Tool output/result | `{toolCallId, content, role: "tool"}` |

### Reasoning Events

| Event | Description | Payload |
|-------|-------------|---------|
| `reasoning_start` | Reasoning session begins | `{messageId}` |
| `reasoning_message_start` | Reasoning message begins | `{messageId, role}` |
| `reasoning_message_content` | Reasoning content delta | `{messageId, delta}` |
| `reasoning_message_end` | Reasoning message ends | `{messageId}` |
| `reasoning_end` | Reasoning session ends | `{messageId}` |

### Message Events

| Event | Description | Payload |
|-------|-------------|---------|
| `message` | Text content chunk | `{content, thread_id, agent}` |
| `status` | Status updates | `{type, message}` |
| `error` | Error occurred | `{type, message}` |
| `interrupt` | Workflow interrupted | `{content, options}` |

---

## Tool Call Events

### Lifecycle

The tool call lifecycle follows this order:

```
tool_call_start → tool_call_args (multiple) → tool_call_end → tool_result
```

### Example SSE Stream

```
event: tool_call_start
data: {"toolCallId": "call_abc123", "toolCallName": "web_search", "thread_id": "thread_1"}

event: tool_call_args
data: {"toolCallId": "call_abc123", "delta": "{\"query\": \"weather"}

event: tool_call_args
data: {"toolCallId": "call_abc123", "delta": " in Tokyo\"}"}

event: tool_call_end
data: {"toolCallId": "call_abc123"}

event: tool_result
data: {"toolCallId": "call_abc123", "content": "The weather in Tokyo is...", "role": "tool"}
```

### Backend Implementation

The tool events are generated from LangChain's streaming events:

```python
# In agent.py - using astream_events
elif event_type == "on_tool_start":
    tool_call = ToolCall(
        tool_call_id=event.get("run_id"),
        tool_name=event.get("name"),
        tool_input=event.get("data", {}).get("input", {}),
    )
    yield _make_event("tool_call_start", tool_call.to_ag_ui_start_event())

# In chat.py - using astream with messages mode
for tc in message_chunk.tool_calls:
    tool_call = ToolCall.from_langchain(tc)
    yield _make_event("tool_call_start", tool_call.to_ag_ui_start_event())
```

---

## Reasoning Events

### Overview

Reasoning events are **automatically detected** from model output when the model includes thinking/reasoning content. This works with:

- **Anthropic Claude** (with extended thinking enabled)
- **OpenAI o1/o3** (with reasoning tokens)
- **Any model** that returns reasoning in `content_blocks`

### LangChain v1 content_blocks

LangChain v1 standardizes reasoning across providers using `content_blocks`:

```python
# Provider-specific formats are automatically converted:
# Anthropic: <thinking>...</thinking> → {"type": "reasoning", "reasoning": "..."}
# OpenAI: reasoning_content → {"type": "reasoning", "reasoning": "..."}

# Access via AIMessageChunk.content_blocks
for block in chunk.content_blocks:
    if block.get('type') == 'reasoning':
        reasoning_text = block.get('reasoning')
```

### Lifecycle

```
reasoning_start → reasoning_message_start → reasoning_message_content (multiple) → reasoning_message_end → reasoning_end
```

### Example SSE Stream

```
event: reasoning_start
data: {"messageId": "reasoning-abc123"}

event: reasoning_message_start
data: {"messageId": "reasoning-abc123", "role": "assistant"}

event: reasoning_message_content
data: {"messageId": "reasoning-abc123", "delta": "Let me think about this..."}

event: reasoning_message_content
data: {"messageId": "reasoning-abc123", "delta": " First, I need to consider..."}

event: reasoning_message_end
data: {"messageId": "reasoning-abc123"}

event: reasoning_end
data: {"messageId": "reasoning-abc123"}
```

### Enabling Deep Thinking

To trigger reasoning events, enable deep thinking mode:

```json
{
  "messages": [{"role": "user", "content": "Solve this step by step..."}],
  "enable_deep_thinking": true
}
```

> **Note:** Reasoning events only appear if the model actually returns thinking content. Not all models support this, and not all queries trigger reasoning.

---

## Multimodal Messages

### Supported Content Types

| Type | Format | Description |
|------|--------|-------------|
| `text` | `{"type": "text", "text": "..."}` | Text content |
| `image` (URL) | `{"type": "image", "url": "https://..."}` | Image from URL |
| `image` (base64) | `{"type": "image", "data": "...", "mime_type": "image/jpeg"}` | Base64 encoded image |

### Request Format

Multimodal messages use the LangChain v1 content block format:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What do you see in this image?"},
        {"type": "image", "url": "https://example.com/photo.jpg"}
      ]
    }
  ]
}
```

### Base64 Image Example

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image"},
        {
          "type": "image",
          "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==",
          "mime_type": "image/png"
        }
      ]
    }
  ]
}
```

---

## Human-in-the-Loop (HITL)

### Overview

Human-in-the-Loop (HITL) enables agents to pause execution and request human approval, editing, or feedback before proceeding. This is essential for:

- **Plan approval** - Review agent's planned steps before execution
- **Action authorization** - Approve sensitive operations (database writes, API calls)
- **Content review** - Edit or reject generated content
- **Iterative refinement** - Provide feedback to improve agent output

### Interrupt Event

When the agent reaches a decision point requiring human input, it emits an `interrupt` event:

```
event: interrupt
data: {
  "id": "interrupt-abc123",
  "thread_id": "thread-xyz",
  "content": "Review the agent's response. Type feedback or 'ACCEPTED' to finish.",
  "finish_reason": "interrupt",
  "options": [
    {"label": "Accept", "value": "accepted"},
    {"label": "Provide Feedback", "value": "feedback"}
  ]
}
```

### Decision Types

| Type | Description | Use Case |
|------|-------------|----------|
| `approve` | Execute action as-is | Accept plan, authorize operation |
| `edit` | Modify then execute | Change tool arguments, revise content |
| `reject` | Cancel with reason | Block dangerous operation |
| `accepted` | Finish workflow | Accept final output, end conversation |
| `feedback` | Continue with input | Provide refinement instructions |

### Event Format

#### Basic Interrupt (Feedback Mode)

Used when agent needs general feedback or approval:

```json
{
  "id": "interrupt-abc123",
  "thread_id": "thread-xyz",
  "content": "Review the agent's response. Type 'ACCEPTED' to finish.",
  "finish_reason": "interrupt",
  "options": [
    {"label": "Accept", "value": "accepted"},
    {"label": "Provide Feedback", "value": "feedback"}
  ]
}
```

#### Action Request Interrupt

Used when specific actions need approval:

```json
{
  "id": "interrupt-abc123",
  "thread_id": "thread-xyz",
  "content": "Review and approve these actions before execution.",
  "finish_reason": "interrupt",
  "options": [
    {"label": "Approve", "value": "approve"},
    {"label": "Edit", "value": "edit"},
    {"label": "Reject", "value": "reject"}
  ],
  "action_requests": [
    {
      "actionId": "action-1",
      "name": "execute_sql",
      "arguments": {"query": "DELETE FROM users WHERE status = 'inactive'"},
      "description": "Delete inactive users from database"
    }
  ],
  "review_configs": [
    {
      "action_name": "execute_sql",
      "allowedDecisions": ["approve", "edit", "reject"]
    }
  ]
}
```

#### Plan Review Interrupt

Used when agent has planned steps to review:

```json
{
  "id": "interrupt-abc123",
  "thread_id": "thread-xyz",
  "content": "Review and modify the planned steps.",
  "finish_reason": "interrupt",
  "options": [
    {"label": "Approve", "value": "approve"},
    {"label": "Edit", "value": "edit"},
    {"label": "Reject", "value": "reject"}
  ],
  "context": {
    "steps": [
      {"description": "Search for weather data", "status": "enabled"},
      {"description": "Analyze temperature trends", "status": "enabled"},
      {"description": "Generate summary report", "status": "enabled"}
    ]
  }
}
```

### Resuming After Interrupt

To resume the workflow, send a response to the same thread:

#### Simple Feedback Response

```json
{
  "messages": [{"role": "user", "content": "ACCEPTED"}],
  "thread_id": "thread-xyz"
}
```

#### Feedback with Instructions

```json
{
  "messages": [{"role": "user", "content": "Please also include humidity data in the analysis."}],
  "thread_id": "thread-xyz"
}
```

#### Action Decision Response

```json
{
  "messages": [{
    "role": "user",
    "content": {
      "decisions": [
        {"actionId": "action-1", "type": "approve"},
        {"actionId": "action-2", "type": "edit", "args": {"limit": 100}},
        {"actionId": "action-3", "type": "reject", "reason": "Too dangerous"}
      ]
    }
  }],
  "thread_id": "thread-xyz"
}
```

### Backend Implementation

The HITL system uses LangGraph's `interrupt()` function:

```python
from langgraph.types import interrupt, Command

def human_feedback_node(state: GraphState) -> Command:
    """Pause for human feedback."""
    # This triggers an interrupt event
    feedback = interrupt("Review the agent's response. Type 'ACCEPTED' to finish.")
    
    if feedback == "ACCEPTED":
        return Command(goto="__end__")
    else:
        # Continue with feedback
        state["messages"].append(HumanMessage(content=feedback))
        return Command(goto="base")
```

### HITL Models

```python
from backend.app.agent.models import (
    HITLDecisionType,
    ActionRequest,
    ReviewConfig,
    HITLDecision,
    HITLRequest,
    HITLResponse,
    HITLState,
    create_hitl_interrupt_event,
)

# Create from LangGraph interrupt
request = HITLRequest.from_langraph_interrupt(
    "Review the planned steps",
    thread_id="thread-123"
)

# Generate AG-UI event
event = request.to_ag_ui_event("thread-123")

# Handle response
response = HITLResponse(
    interrupt_id="interrupt-abc123",
    feedback="Please add more detail to step 2"
)
resume_value = response.to_langraph_resume()  # Returns "Please add more detail..."
```

### Frontend Handling

```typescript
interface HITLInterruptEvent {
  id: string;
  thread_id: string;
  content: string;
  finish_reason: 'interrupt';
  options: Array<{label: string; value: string}>;
  action_requests?: Array<{
    actionId: string;
    name: string;
    arguments: Record<string, any>;
    description?: string;
  }>;
  context?: {
    steps?: Array<{description: string; status: string}>;
  };
}

function handleInterrupt(event: HITLInterruptEvent) {
  // Show interrupt UI based on options
  if (event.action_requests) {
    // Show action approval UI with approve/edit/reject per action
    showActionApprovalDialog(event.action_requests, event.options);
  } else if (event.context?.steps) {
    // Show plan review UI
    showPlanReviewDialog(event.context.steps, event.options);
  } else {
    // Show simple feedback UI
    showFeedbackDialog(event.content, event.options);
  }
}

async function submitResponse(threadId: string, response: string | object) {
  await fetch('/agent/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      messages: [{role: 'user', content: response}],
      thread_id: threadId
    })
  });
}
```

---

## Structured Models

### Location

All AG-UI protocol models are defined in:

```
backend/app/agent/models.py
```

### Key Models

#### Message Models

```python
from backend.app.agent.models import AgentMessage, ChatMessage, MessageRole

# Simple text message
msg = AgentMessage(role=MessageRole.USER, content="Hello!")

# Multimodal message with structured blocks
msg = AgentMessage(
    role=MessageRole.USER,
    content=[
        TextBlock(text="What's in this image?"),
        ImageBlock(url="https://example.com/photo.jpg")
    ]
)

# Convert to LangChain format
lc_format = msg.to_langchain_format()
```

#### Content Blocks

```python
from backend.app.agent.models import TextBlock, ImageBlock, ReasoningBlock

# Text block
text = TextBlock(text="Hello, world!")

# Image block (URL)
img_url = ImageBlock(url="https://example.com/image.jpg")

# Image block (base64)
img_b64 = ImageBlock(data="base64data...", mime_type="image/jpeg")

# Reasoning block
reasoning = ReasoningBlock(reasoning="Let me think...")
```

#### Tool Call Models

```python
from backend.app.agent.models import ToolCall, ToolResult

# Create from LangChain tool call
tc = ToolCall.from_langchain({
    "id": "call_123",
    "name": "web_search",
    "args": {"query": "weather"}
})

# Generate AG-UI events
start_event = tc.to_ag_ui_start_event()  # {"toolCallId": "...", "toolCallName": "..."}
args_event = tc.to_ag_ui_args_event('{"query": "weather"}')  # {"toolCallId": "...", "delta": "..."}
end_event = tc.to_ag_ui_end_event()  # {"toolCallId": "..."}

# Tool result
result = ToolResult(
    tool_call_id="call_123",
    tool_name="web_search",
    output="Search results..."
)
result_event = result.to_ag_ui_event()  # {"toolCallId": "...", "content": "..."}
```

#### State Tracking

```python
from backend.app.agent.models import ReasoningState, ToolCallState

# Track reasoning across streaming chunks
reasoning_state = ReasoningState()
msg_id = reasoning_state.start_reasoning()  # Returns "reasoning-abc123"
# ... stream reasoning content ...
reasoning_state.end_reasoning()

# Track tool calls
tool_state = ToolCallState()
tool_state.start_tool_call(tool_call)
tool_state.append_args("call_id", '{"query":')
tool_state.append_args("call_id", '"test"}')
completed = tool_state.complete_tool_call("call_id")
```

---

## Frontend Integration

### TypeScript Event Handler

```typescript
interface AGUIEvent {
  type: string;
  toolCallId?: string;
  toolCallName?: string;
  messageId?: string;
  delta?: string;
  content?: string;
}

interface ToolCallTracker {
  id: string;
  name: string;
  args: string;
  result?: string;
  isComplete: boolean;
}

interface ReasoningTracker {
  id: string;
  content: string;
  isComplete: boolean;
}

class AGUIEventHandler {
  private toolCalls: Map<string, ToolCallTracker> = new Map();
  private reasoning: Map<string, ReasoningTracker> = new Map();
  
  handleEvent(eventType: string, data: AGUIEvent): void {
    switch (eventType) {
      // Tool events
      case 'tool_call_start':
        this.toolCalls.set(data.toolCallId!, {
          id: data.toolCallId!,
          name: data.toolCallName!,
          args: '',
          isComplete: false
        });
        break;
        
      case 'tool_call_args':
        const tc = this.toolCalls.get(data.toolCallId!);
        if (tc) tc.args += data.delta || '';
        break;
        
      case 'tool_call_end':
        const tcEnd = this.toolCalls.get(data.toolCallId!);
        if (tcEnd) tcEnd.isComplete = true;
        break;
        
      case 'tool_result':
        const tcResult = this.toolCalls.get(data.toolCallId!);
        if (tcResult) tcResult.result = data.content;
        break;
        
      // Reasoning events
      case 'reasoning_start':
        this.reasoning.set(data.messageId!, {
          id: data.messageId!,
          content: '',
          isComplete: false
        });
        break;
        
      case 'reasoning_message_content':
        const rs = this.reasoning.get(data.messageId!);
        if (rs) rs.content += data.delta || '';
        break;
        
      case 'reasoning_end':
        const rsEnd = this.reasoning.get(data.messageId!);
        if (rsEnd) rsEnd.isComplete = true;
        break;
    }
  }
}
```

### React Hook Example

```typescript
import { useState, useCallback } from 'react';

interface ToolCall {
  id: string;
  name: string;
  args: string;
  result?: string;
  status: 'running' | 'complete';
}

interface ReasoningSession {
  id: string;
  content: string;
  isComplete: boolean;
}

export function useAGUIStream(token: string) {
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [reasoning, setReasoning] = useState<ReasoningSession | null>(null);
  const [response, setResponse] = useState('');
  
  const processEvent = useCallback((eventType: string, data: any) => {
    switch (eventType) {
      case 'tool_call_start':
        setToolCalls(prev => [...prev, {
          id: data.toolCallId,
          name: data.toolCallName,
          args: '',
          status: 'running'
        }]);
        break;
        
      case 'tool_call_args':
        setToolCalls(prev => prev.map(tc => 
          tc.id === data.toolCallId 
            ? { ...tc, args: tc.args + (data.delta || '') }
            : tc
        ));
        break;
        
      case 'tool_call_end':
        setToolCalls(prev => prev.map(tc =>
          tc.id === data.toolCallId
            ? { ...tc, status: 'complete' }
            : tc
        ));
        break;
        
      case 'reasoning_start':
        setReasoning({ id: data.messageId, content: '', isComplete: false });
        break;
        
      case 'reasoning_message_content':
        setReasoning(prev => prev 
          ? { ...prev, content: prev.content + (data.delta || '') }
          : null
        );
        break;
        
      case 'reasoning_end':
        setReasoning(prev => prev ? { ...prev, isComplete: true } : null);
        break;
        
      case 'message':
        setResponse(prev => prev + (data.content || ''));
        break;
    }
  }, []);
  
  const sendMessage = useCallback(async (messages: any[], threadId: string) => {
    const res = await fetch('/agent/chat/stream', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ messages, thread_id: threadId })
    });
    
    const reader = res.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      
      // Parse SSE events
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';
      
      for (const event of events) {
        const lines = event.split('\n');
        let eventType = '';
        let eventData = '';
        
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7);
          if (line.startsWith('data: ')) eventData = line.slice(6);
        }
        
        if (eventType && eventData) {
          processEvent(eventType, JSON.parse(eventData));
        }
      }
    }
  }, [token, processEvent]);
  
  return { sendMessage, response, toolCalls, reasoning };
}
```

---

## Testing

### Unit Tests

Run the unit tests for the structured models:

```bash
# Run with pytest
python -m pytest backend/tests/unit/test_agent_models.py -v

# Or run directly
python backend/tests/unit/test_agent_models.py
```

**Test Coverage (33 tests):**
- Content blocks (TextBlock, ImageBlock, AudioBlock, ReasoningBlock)
- ReasoningState lifecycle (start, end, multiple cycles)
- ToolCall model and AG-UI event generation
- ToolResult model
- ToolCallState lifecycle tracking
- AgentMessage and ChatMessage serialization
- Helper functions (make_ag_ui_event, extract_reasoning_from_content_blocks)

### Integration Tests

Run the comprehensive AG-UI protocol test suite:

```bash
# Run all tests
python backend/tests/live/backend_endpoints/test_agui_protocol.py

# With verbose output
python backend/tests/live/backend_endpoints/test_agui_protocol.py --verbose

# Test specific features
python backend/tests/live/backend_endpoints/test_agui_protocol.py --test-tools
python backend/tests/live/backend_endpoints/test_agui_protocol.py --test-reasoning
python backend/tests/live/backend_endpoints/test_agui_protocol.py --test-multimodal

# Test specific endpoint
python backend/tests/live/backend_endpoints/test_agui_protocol.py --chat-only
python backend/tests/live/backend_endpoints/test_agui_protocol.py --agent-only
```

**Tests Included:**
| Test | Description |
|------|-------------|
| `test_model_serialization` | Validates Pydantic models serialize correctly |
| `test_chat_tool_calls` | Tool events via `/agent/chat/stream` |
| `test_agent_tool_calls` | Tool events via `/agent/agent/stream` |
| `test_chat_reasoning` | Reasoning events with deep thinking mode |
| `test_agent_reasoning` | Reasoning events on agent endpoint |
| `test_chat_multimodal_url` | Image messages with URL |
| `test_chat_multimodal_base64` | Image messages with base64 data |

### Example Test Output

```
======================================================================
🧪 AG-UI Protocol Comprehensive Test Suite
   Base URL: http://127.0.0.1:8000
   Date: 2025-12-30 11:51:52
   Models available: True
======================================================================

📋 Step 1: Authenticating...
   ✅ Got JWT token

📋 Test: Model Serialization
   ✅ All model serializations valid

📋 Test: Chat Stream Tool Calls
   🔔 AG-UI: tool_call_start
      Data: {"toolCallId": "call_abc123", "toolCallName": "web_search"}
   🔔 AG-UI: tool_call_args
      Data: {"toolCallId": "call_abc123", "delta": "{\"query\": \"weather in Tokyo\"}"}
   🔔 AG-UI: tool_call_end
      Data: {"toolCallId": "call_abc123"}
   🔔 AG-UI: tool_result
      Data: {"toolCallId": "call_abc123", "content": "..."}

   ✅ PASSED - chat_tool_calls
   Duration: 34.43s

======================================================================
📊 FINAL SUMMARY
======================================================================
   ✅ model_serialization: 0.00s
   ✅ chat_tool_calls: 34.43s
   ✅ agent_tool_calls: 53.67s
   ✅ chat_reasoning: 15.12s
   ✅ agent_reasoning: 58.41s
   ✅ chat_multimodal_url: 4.79s
   ✅ chat_multimodal_base64: 14.46s

   Total: 7 tests
   Passed: 7
   Failed: 0

   AG-UI Tool Events Covered: {'tool_call_end', 'tool_call_args', 'tool_call_start', 'tool_result'}
======================================================================
```

### Prerequisites for Testing

1. **Backend server running:**
   ```bash
   python backend/run.py
   ```

2. **Test user created:**
   ```bash
   python backend/tests/create_test_user.py
   ```

---

## Troubleshooting

### No Reasoning Events

**Issue:** Reasoning events are not appearing in the stream.

**Possible Causes:**
1. **Model doesn't support reasoning** - Not all models support thinking/reasoning output
2. **Deep thinking not enabled** - Set `enable_deep_thinking: true` in request
3. **Query doesn't trigger reasoning** - Simple queries may not require deep thinking

**Solution:**
- Use a model that supports reasoning (Claude with extended thinking, OpenAI o1/o3)
- Enable deep thinking mode in request
- Use prompts that require step-by-step reasoning

### Tool Call ID is null

**Issue:** `toolCallId` is `null` in some events.

**Cause:** Streaming chunks may arrive before the tool call ID is assigned.

**Solution:** The frontend should handle events with null IDs gracefully and wait for the complete tool call lifecycle.

### Multimodal Not Working

**Issue:** Image content not being processed.

**Possible Causes:**
1. **Wrong content format** - Must use LangChain v1 content blocks format
2. **Invalid base64** - Ensure base64 data is valid and properly encoded
3. **Missing mime_type** - Base64 images require `mime_type` field

**Correct Format:**
```json
{
  "content": [
    {"type": "text", "text": "Describe this"},
    {"type": "image", "url": "https://..."} 
  ]
}
```

### Import Errors

**Issue:** Cannot import from `backend.app.agent.models`.

**Solution:** Ensure you're running from the project root:
```bash
cd /path/to/agents-backend
python -c "from backend.app.agent.models import AgentMessage; print('OK')"
```

---

## File References

| File | Purpose |
|------|---------|
| `backend/app/agent/models.py` | Structured Pydantic models for AG-UI (including HITL) |
| `backend/app/agent/api/v1/agent.py` | Agent endpoint with sandbox |
| `backend/app/agent/api/v1/chat.py` | Chat endpoint |
| `backend/src/graph/nodes.py` | Graph nodes including `human_feedback_node` |
| `backend/tests/unit/test_agent_models.py` | Unit tests for models (including HITL) |
| `backend/tests/live/backend_endpoints/test_agui_protocol.py` | Integration tests |
| `backend/tests/live/backend_endpoints/test_tool_events.py` | Tool events tests |
| `backend/tests/live/backend_endpoints/test_hitl_protocol.py` | HITL protocol tests |

---

## Related Documentation

- [Agent System Overview](../agent-system.md)
- [Getting Started](../getting-started.md)
- [Sandbox Tools](../sandbox-tools.md)
- [MCP Configuration](../mcp-configuration.md)
