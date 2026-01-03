# HITL Architecture - Structured Decision Handling

## Overview

This document describes the Human-in-the-Loop (HITL) architecture with structured decision handling.

## Design Principles

1. **Separation of Concerns**: The tool triggers HITL, the node handles decision logic
2. **Structured Decisions**: Always use approve/edit/reject - not arbitrary options
3. **UI-Ready Data**: The node sends structured data that frontends can render properly
4. **Default to Completion**: Base node routes to `__end__` by default, only to `human_feedback` when explicitly needed

## Architecture

```
base_node → 
    ├── Task complete? → END (default)
    └── Agent called request_human_input? → human_feedback → 
            ├── APPROVE → END
            ├── EDIT (with feedback) → base (loop)
            └── REJECT → END
```

## Components

### 1. Tool: `request_human_input` (Simple)

The tool is intentionally simple - it just passes questions to ask the user:

```python
from backend.src.tools import request_human_input

# Agent calls this when it needs clarification
request_human_input(questions=[
    "What framework do you prefer?",
    "Should I include tests?",
])
```

**Why simple?**
- The tool just triggers HITL routing
- It doesn't decide what decisions are available
- The structured decision logic lives in the node

### 2. Node: `human_feedback_node` (Structured)

The node handles all the structured HITL logic:

```python
# Sends structured interrupt to frontend
hitl_request = {
    "questions": ["What framework?", "Include tests?"],
    "allowed_decisions": ["approve", "edit", "reject"],
    "prompt": "The agent needs your input on the following:",
    "context": {"message_count": 5}
}

response = interrupt(hitl_request)

# Handles structured responses
if response["decision"] == "approve":
    goto = "__end__"  # Accept and finish
elif response["decision"] == "edit":
    # Add feedback to messages and loop back
    messages.append(HumanMessage(content=response["feedback"]))
    goto = "base"
elif response["decision"] == "reject":
    # Add rejection message and end
    messages.append(HumanMessage(content=f"[REJECTED] {response['reason']}"))
    goto = "__end__"
```

### 3. State Fields

```python
class State(MessagesState):
    # HITL control
    needs_human_feedback: bool = False  # Set when HITL is needed
    hitl_questions: Optional[List[str]] = None  # Questions from agent
```

### 4. Detection Marker

The tool returns a marker that the node parses:

```python
HITL_TOOL_MARKER = "[HITL_REQUEST]"

# Tool returns:
"[HITL_REQUEST]{\"questions\": [\"What framework?\", \"Include tests?\"]}"

# Node parses:
needs_feedback, questions = _detect_feedback_request(messages)
```

## Frontend Integration

The frontend receives a structured interrupt event:

```json
{
    "type": "interrupt",
    "data": {
        "questions": ["What framework do you prefer?", "Should I include tests?"],
        "allowed_decisions": ["approve", "edit", "reject"],
        "prompt": "The agent needs your input on the following:",
        "context": {}
    }
}
```

The frontend should render:
1. The questions from the agent
2. Three decision buttons: Approve, Edit, Reject
3. A text field for feedback (required for Edit/Reject)

The frontend sends back:

```json
{
    "decision": "edit",
    "feedback": "Use React and yes, include tests",
    "answers": ["React", "Yes"]
}
```

## Graph Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  START                                                          │
│    │                                                            │
│    ▼                                                            │
│  ┌─────────────────────────┐                                    │
│  │ background_investigator │  (optional web search)             │
│  └───────────┬─────────────┘                                    │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────┐                                    │
│  │         base            │  (main agent execution)            │
│  │  - web_search           │                                                                 │
│  │  - RAG retriever        │                                    │
│  │  - request_human_input  │ ◄── Agent triggers HITL            │
│  │  - MCP tools            │                                    │
│  └───────────┬─────────────┘                                    │
│              │                                                  │
│              ▼                                                  │
│    ┌───────────────────────────┐                                │
│    │  Detect HITL tool marker? │                                │
│    └───────────┬───────────────┘                                │
│                │                                                │
│    ┌───────────┴───────────┐                                    │
│    │ NO                YES │                                    │
│    ▼                       ▼                                    │
│  ┌───────┐    ┌─────────────────┐                               │
│  │  END  │    │ human_feedback  │                               │
│  │       │    │  (structured)   │                               │
│  │ Task  │    └────────┬────────┘                               │
│  │ Done  │             │                                        │
│  └───────┘             ▼                                        │
│              ┌──────────────────┐                               │
│              │ User Decision:   │                               │
│              │ approve/edit/    │                               │
│              │ reject           │                               │
│              └────────┬─────────┘                               │
│                       │                                         │
│        ┌──────────────┼──────────────┐                          │
│        │              │              │                          │
│        ▼              ▼              ▼                          │
│   ┌────────┐    ┌──────────┐   ┌──────────┐                     │
│   │ APPROVE│    │   EDIT   │   │  REJECT  │                     │
│   │   ↓    │    │    ↓     │   │    ↓     │                     │
│   │  END   │    │   base   │   │   END    │                     │
│   └────────┘    │  (loop)  │   └──────────┘                     │
│                 └──────────┘                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Options

```python
@dataclass
class Configuration:
    # If True, always route to human_feedback (legacy behavior)
    always_require_feedback: bool = False
    
    # If True, add request_human_input tool to agent
    enable_feedback_tool: bool = True
```

## Files Changed

1. **backend/src/graph/types.py** - State with `needs_human_feedback` and `hitl_questions`
2. **backend/src/tools/human_feedback.py** - Simple `request_human_input` tool
3. **backend/src/tools/__init__.py** - Exports
4. **backend/src/graph/nodes.py** - Structured `human_feedback_node`, detection logic
5. **backend/app/agent/models.py** - HITL models (`HITLRequest`, `HITLResponse`, etc.)

## Testing

```bash
python -m pytest backend/tests/unit/ -v -k hitl
```
