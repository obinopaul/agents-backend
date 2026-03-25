# Reasoning/Thinking Pipeline Diagnosis Report

## Summary

**80 diagnostic tests** across 5 test files — **ALL PASS**. The core reasoning pipeline 
(StreamBuffer, EventAdapter, agent.py extraction, QueryHandler forwarding, chat.py SSE) 
works correctly in isolation for the **content_blocks path**.

## Test Evidence

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_stream_buffer_reasoning.py` | 21 | ✅ ALL PASS |
| `test_event_adapter_reasoning.py` | 22 | ✅ ALL PASS |
| `test_agent_reasoning_extraction.py` | 16 | ✅ ALL PASS |
| `test_query_handler_reasoning.py` | 10 | ✅ ALL PASS |
| `test_chat_reasoning.py` | 11 | ✅ ALL PASS |

## Root Cause Analysis

### Issue 1: List Content Path Missing Reasoning (CONFIRMED BUG)

**Location**: 
- `agent.py` lines 920-960
- `chat.py` lines 556-588

**Problem**: When a model sends reasoning via `chunk.content` (a list of dicts) instead of 
`chunk.content_blocks`, the reasoning items are **silently dropped**. The list content handler 
only checks for `type='text'` and `type='text_delta'`, but NOT `type='reasoning'`.

**Impact**: Models that deliver reasoning through the `chunk.content` list path (rather than 
the `content_blocks` attribute) will have their thinking completely lost. This depends on:
- Which LangChain version is being used
- Which provider/model is being used  
- Whether the provider adapter uses `content_blocks` or `content` list

**Evidence**: 
- `test_agent_reasoning_extraction.py::TestListContentGap::test_list_content_drops_reasoning` — PASSES (confirms the bug)
- `test_chat_reasoning.py::TestChatListContentGap::test_list_content_reasoning_NOT_handled` — PASSES (confirms same bug in chat.py)

### Issue 2: No-Reasoning Diagnosis (MOST LIKELY ROOT CAUSE)

The **most likely reason** the user sees no thinking in the frontend is that the model being 
used does NOT produce `content_blocks` with reasoning at all. This would happen if:

1. **The LLM doesn't support extended thinking** (e.g., GPT-4o doesn't produce reasoning blocks)
2. **Extended thinking isn't enabled** in the API call (Claude requires `thinking.type = "enabled"`)
3. **LangChain version doesn't support content_blocks** (older versions don't have this attribute)

In this case, NO reasoning events are ever produced by agent.py, so the frontend correctly 
shows nothing.

### Issue 3: Pipeline Works End-to-End When Reasoning IS Produced

The diagnostic output from `test_query_handler_reasoning.py::TestSaveOutput` proves that 
when reasoning events ARE produced, the complete pipeline works:

```
SSE Input: "event: reasoning_message_end\ndata: {\"messageId\": \"r-1\"}"
→ Adapter Output: agent_thinking, {text: "Analyzing the problem step by step.", thinking_id: "r-1"}  
→ Socket.IO: {type: "agent_thinking", content: {text: "...", thinking_id: "..."}, run_id: "..."}
→ Frontend: data.type = "agent_thinking", data.content.text = "Analyzing..."
```

The frontend at `websocket-context.tsx:181` adds `id: Date.now().toString()` to every event, 
so the `uniqBy` deduplication in `messages.ts:23` works correctly.

## Fixes Required

### Fix 1: Add reasoning to list content path in agent.py

```python
# In agent.py, inside `elif isinstance(chunk.content, list) and chunk.content:` block
# After the text_delta handling, add:
elif item_type == 'reasoning':
    reasoning_text = item.get('reasoning') or item.get('thinking') or item.get('text', '')
    if reasoning_text:
        if not reasoning_state.is_active:
            msg_id = reasoning_state.start_reasoning()
            if not adapter.thinking_active:
                yield adapter.thinking_start()
            yield _make_event("reasoning_start", {"messageId": msg_id})
            yield _make_event("reasoning_message_start", {"messageId": msg_id, "role": "assistant"})
        yield adapter.thinking_delta(reasoning_text)
        yield _make_event("reasoning_message_content", {
            "messageId": reasoning_state.message_id,
            "delta": reasoning_text,
        })
```

### Fix 2: Add reasoning to list content path in chat.py

Same fix as above, applied to the list content fallback path in `chat.py`.

### Fix 3 (Optional): Enable Extended Thinking for Claude Models

If using Claude, ensure the model is configured with extended thinking enabled. This is 
typically done via the API configuration, not in the streaming code itself. Check the 
LangChain model configuration to ensure `thinking` parameters are set.

## Architecture Understanding (for reference)

```
MODEL → AIMessageChunk
  └── content_blocks: [{type: "reasoning", ...}, {type: "text", ...}]  ← Primary path (works)
  └── content: [{type: "reasoning", ...}, {type: "text", ...}]         ← Fallback path (BROKEN for reasoning)
  └── content: "plain string"                                           ← Simplest path (no reasoning possible)

AGENT MODE (WebSocket):
  agent.py → SSE events → QueryHandler._forward_sse_event → adapter.process_event
    → StreamBuffer (accumulates reasoning deltas) → broadcast_to_session
    → Socket.IO {type: "agent_thinking", content: {text: "..."}}
    → Frontend handleEvent → addMessage({isThinkMessage: true})

CHAT MODE (SSE):
  chat.py → SSE events (thinking + reasoning_*) → browser
    → chat.service.ts parses "thinking" events
    → StreamCallbacks.onThinking → dispatch thinking message
```
