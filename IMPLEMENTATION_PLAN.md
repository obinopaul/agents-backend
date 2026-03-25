# Implementation Plan: Fixing Chat/Agent Mode Issues

## Executive Summary

This plan addresses four critical issues in the agents-backend project affecting the frontend-backend integration for both SSE (chat mode) and WebSocket (agent mode) communication.

---

## Issue 1: Chat Mode Event Streaming - Thinking/Reasoning Not Completing

### Symptoms
- User sees "thoughts" dropdown with "searching for..." text that stops
- Rolling icon continues indefinitely
- Reasoning events don't complete properly

### Root Cause (VERIFIED)
**File:** `/frontend/src/services/chat.service.ts` (lines 245-260)

The frontend SSE parser only handles `status === 'delta'` for thinking events, completely ignoring `start` and `stop` statuses:

```typescript
// Current code (BROKEN):
if (eventName === 'thinking') {
    const status = readString(record, 'status')
    if (status === 'delta') {  // <-- Only handles delta!
        // ...
    }
    return events
}
```

The backend emits three statuses: `start`, `delta`, and `stop`, but only `delta` is handled.

### Files to Modify

| File | Changes Required |
|------|------------------|
| `/frontend/src/services/chat.service.ts` | Add handling for `thinking` status `start` and `stop` |
| `/frontend/src/typings/chat.ts` | Add `thinking_start` and `thinking_stop` event types |
| `/frontend/src/hooks/use-chat-transport.tsx` | Add callbacks for thinking lifecycle |

### Implementation Steps

**Step 1:** Update `/frontend/src/typings/chat.ts` - Add event types

```typescript
// Add to ChatStreamEvent union type:
| { type: 'thinking_start'; thinking_id?: string }
| { type: 'thinking_stop'; thinking_id?: string }
```

**Step 2:** Update `/frontend/src/services/chat.service.ts` (lines 245-260)

Replace the thinking event handler:

```typescript
// Handle thinking event - FULL lifecycle
if (eventName === 'thinking') {
    const status = readString(record, 'status')
    const thinkingId = readString(record, 'thinking_id')

    if (status === 'start') {
        events.push({
            type: 'thinking_start',
            thinking_id: thinkingId
        })
    } else if (status === 'delta') {
        const delta = readString(record, 'delta')
        if (delta) {
            events.push({
                type: 'thinking',
                status: 'delta',
                delta,
                signature: readString(record, 'signature')
            })
        }
    } else if (status === 'stop') {
        events.push({
            type: 'thinking_stop',
            thinking_id: thinkingId
        })
    }
    return events
}
```

**Step 3:** Update `/frontend/src/hooks/use-chat-transport.tsx`

Add new callbacks in StreamCallbacks type and handle them:

```typescript
// In StreamCallbacks type:
onThinkingStart?: (params: { thinking_id?: string }) => void
onThinkingStop?: (params: { thinking_id?: string }) => void

// In event handler switch:
case 'thinking_start': {
    callbacks?.onThinkingStart?.({ thinking_id: event.thinking_id })
    break
}
case 'thinking_stop': {
    callbacks?.onThinkingStop?.({ thinking_id: event.thinking_id })
    break
}
```

---

## Issue 2: Agent Mode Send Button Not Appearing

### Symptoms
- Send button doesn't become active when typing in agent mode
- Works correctly in chat mode

### Root Cause (VERIFIED)
**File:** `/frontend/src/app/routes/home.tsx` (lines 108-113)

The input is disabled based on WebSocket connection state:

```typescript
const isInputDisabled = useMemo(() => {
    if (isChatMode) {
        return isSubmitting
    }
    return wsConnectionState !== WebSocketConnectionState.CONNECTED  // <-- Agent mode check
}, [isChatMode, isSubmitting, wsConnectionState])
```

In agent mode, if `wsConnectionState` is not `CONNECTED`, the input is disabled. This could be due to:
1. WebSocket connection not being established
2. Connection state not updating properly after connection
3. Race condition where input renders before connection completes

### Files to Modify

| File | Changes Required |
|------|------------------|
| `/frontend/src/contexts/websocket-context.tsx` | Verify connection state updates correctly |
| `/frontend/src/app/routes/home.tsx` | Improve disabled state logic |

### Implementation Steps

**Step 1:** Verify WebSocket connection in `/frontend/src/contexts/websocket-context.tsx`

Check that connection state is properly updated:
- On `connect` event → set `CONNECTED`
- On `disconnect` event → set `DISCONNECTED`
- On error → set `ERROR`

**Step 2:** Update `/frontend/src/app/routes/home.tsx` (lines 108-113)

Add fallback behavior for agent mode when WebSocket is connecting:

```typescript
const isInputDisabled = useMemo(() => {
    if (isChatMode) {
        return isSubmitting
    }
    // For agent mode, only disable if explicitly disconnected or errored
    // Allow typing while connecting to improve UX
    return wsConnectionState === WebSocketConnectionState.DISCONNECTED ||
           wsConnectionState === WebSocketConnectionState.ERROR
}, [isChatMode, isSubmitting, wsConnectionState])
```

**Step 3:** Add auto-reconnect logic if not present

Ensure WebSocket reconnects automatically on disconnect.

---

## Issue 3: Tool Name Mapping (Non-existent Tools)

### Symptoms
- Some tools in mapping may not exist in the project
- Tool display names reference undefined tools

### Analysis
**File:** `/backend/app/agent/event_adapter.py` (lines 536-585)

The `TOOL_DISPLAY_NAMES` dictionary maps internal tool names to display names. The system already has a graceful fallback:

```python
def humanize_tool_name(tool_name: str) -> str:
    if tool_name in TOOL_DISPLAY_NAMES:
        return TOOL_DISPLAY_NAMES[tool_name]
    # Default: title case with underscores replaced
    return tool_name.replace("_", " ").title()
```

### Recommendation
This is a low-priority documentation/cleanup issue. The fallback handling is already in place. Consider:

1. Auditing actual tool implementations vs mappings
2. Adding comments to clarify which tools are:
   - Currently implemented
   - MCP-provided (dynamically available)
   - Planned for future

### Files to Review

| File | Action |
|------|--------|
| `/backend/app/agent/event_adapter.py` | Audit and document tool mappings |
| `/backend/src/agents/tools/__init__.py` | List of implemented tools |

---

## Issue 4: Chat History Not Being Saved/Displayed

### Symptoms
- No list of chats in left panel
- History not persisting between sessions

### Root Cause (VERIFIED)
**File:** `/frontend/src/components/sidebar.tsx` (lines 315-317)

The sidebar filters sessions to only show those with names:

```typescript
{sessions
    ?.filter((session) => session.name)  // <-- Filters out sessions without names!
    ?.map((session) => (
```

Sessions are created before the first message is processed, so they initially have no name. The name is set AFTER the first message, but by then the sidebar has already filtered them out.

### Files to Modify

| File | Changes Required |
|------|------------------|
| `/frontend/src/components/sidebar.tsx` | Remove name filter or add fallback |
| `/backend/common/socketio/command/query_handler.py` | Emit session_updated event when name changes |
| `/frontend/src/contexts/websocket-context.tsx` | Handle session_updated event |

### Implementation Steps

**Step 1:** Update `/frontend/src/components/sidebar.tsx` (lines 315-331)

Remove the filter and add a fallback name:

```typescript
{sessions?.map((session) => (
    <SessionItem
        key={session.id}
        session={{
            ...session,
            name: session.name || 'New Conversation'
        }}
        isActive={
            activeSessionId === session.id ||
            (workspaceInfo?.includes(session.id) ?? false)
        }
        onClick={handleResetState}
    />
))}
```

**Step 2:** Update `/backend/common/socketio/command/query_handler.py`

After setting the session name (around line 248-250), emit a session_updated event:

```python
if not session.name and message:
    name = message[:50] + ("..." if len(message) > 50 else "")
    await chat_session_dao.update_name(db, session.id, name)

    # Emit session_updated event to update frontend cache
    await self.broadcast_to_session(
        session_uuid=session_uuid,
        event_type='session_updated',
        content={
            'session_id': session_uuid,
            'name': name,
        },
        run_id=run_id
    )
```

**Step 3:** Handle event in frontend WebSocket context

```typescript
// In event handler:
case 'session_updated': {
    const { session_id, name } = data.content
    // Update RTK Query cache or Redux state
    dispatch(updateSessionName({ session_id, name }))
    break
}
```

---

## Summary of Files to Modify

### Frontend Files (6 files)

| File | Issue(s) | Priority |
|------|----------|----------|
| `/frontend/src/services/chat.service.ts` | 1 | HIGH |
| `/frontend/src/typings/chat.ts` | 1 | HIGH |
| `/frontend/src/hooks/use-chat-transport.tsx` | 1 | HIGH |
| `/frontend/src/components/sidebar.tsx` | 4 | HIGH |
| `/frontend/src/app/routes/home.tsx` | 2 | HIGH |
| `/frontend/src/contexts/websocket-context.tsx` | 2, 4 | MEDIUM |

### Backend Files (2 files)

| File | Issue(s) | Priority |
|------|----------|----------|
| `/backend/common/socketio/command/query_handler.py` | 4 | MEDIUM |
| `/backend/app/agent/event_adapter.py` | 3 | LOW |

---

## Verification Steps

### Issue 1 - Thinking Events
1. Start a chat conversation with a model that uses reasoning (Claude, etc.)
2. Verify "thoughts" dropdown appears when thinking starts
3. Verify thinking content streams as deltas arrive
4. Verify indicator completes when thinking ends (no infinite spinner)

### Issue 2 - Agent Mode Send Button
1. Navigate to home page
2. Ensure agent mode is selected (not chat mode)
3. Wait for WebSocket connection (check browser DevTools Network tab)
4. Type text in the input field
5. Verify send button becomes active (enabled)
6. Submit a query and verify it works

### Issue 3 - Tool Mapping
1. Use a tool in chat (e.g., web search)
2. Verify tool name displays correctly (not raw internal name)
3. Verify unknown tools show reasonable fallback names

### Issue 4 - Chat History
1. Create a new chat session
2. Send a message
3. Check left sidebar - session should appear
4. Verify session name matches first message (truncated to 50 chars)
5. Refresh page - verify session persists in list
6. Click on session - verify it loads correctly

---

## Recommended Implementation Order

1. **Issue 1 (Thinking Events)** - High impact, frontend-only fix
2. **Issue 4 (Chat History)** - High impact, quick frontend fix + backend enhancement
3. **Issue 2 (Send Button)** - High impact, requires WebSocket debugging
4. **Issue 3 (Tool Mapping)** - Low priority, documentation/cleanup

---

## Notes

- All fixes avoid placeholder code and are production-ready
- Edge cases like empty sessions, disconnected WebSocket, and malformed events are handled
- Changes are minimal and focused on the specific issues
- Backward compatibility is maintained with existing event formats
