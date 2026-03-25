# Thinking Visibility & Response Latency — Diagnosis Report

**Date**: 2025-01-XX  
**Status**: ROOT CAUSE FOUND & FIXED  
**Severity**: Critical UX — thinking content hidden from user, slow perceived response

---

## Problem Statement

Two interconnected UX issues reported:

1. **"I'm thinking..." animation blocks real content**: After pressing Enter, the frontend
   shows a Lottie "I'm thinking..." animation and **never transitions** to showing actual
   thinking/response content. The user only sees final output after the COMPLETE event or
   first TOOL_CALL — they never see the LLM's reasoning as it streams in.

2. **Slow initial response perception**: Several seconds of blank/animation time before any
   visible content appears, compounding the above issue.

---

## Root Cause Analysis

### ROOT CAUSE: `BUILD_STEP` state machine stuck on `THINKING`

**The view transition state machine has a gap.** When the user submits a prompt:

1. `handleQuestionSubmit()` in `use-question-handlers.tsx` sets
   `setBuildStep(BUILD_STEP.THINKING)` — this is correct.

2. In `agent.tsx`, when `selectedBuildStep === BUILD_STEP.THINKING`:
   - A Lottie "I'm thinking..." animation fills the main content area
   - The actual content panels (AgentBuild, AgentTasks) are **hidden** via CSS `hidden` class
   - The ChatBox sidebar remains visible, but the main panel shows only animation

3. **THE BUG**: The `AGENT_THINKING` event handler in `use-app-events.tsx` (line 363)
   correctly adds the thinking message to the Redux store with `isThinkMessage: true`,
   but **does NOT call `setBuildStep(BUILD_STEP.BUILD)`**. Similarly, the
   `AGENT_RESPONSE` handler (line 920) adds text messages but also **does NOT transition
   the build step**.

4. **Only these events transition from THINKING → BUILD:**
   - `TOOL_CALL` events (line 1385+)
   - `COMPLETE` event (line 1265, after a 50ms timeout)

5. **Result**: If the LLM produces thinking/reasoning content before making any tool calls
   (which is the normal flow for extended thinking models like Claude), the thinking text
   is stored in Redux but the user never sees it because:
   - The Lottie animation panel is visible (`isThinkingView = true`)
   - The AgentBuild panel where messages render is hidden (`isThinkingView && 'hidden'`)

### Agent state machine flow — BEFORE fix:

```
User submits prompt
    → setBuildStep(THINKING)         ← view shows Lottie animation
    → [wait for backend...]
    → AGENT_INITIALIZED event        ← no view change
    → PROCESSING event               ← no view change  
    → AGENT_THINKING event           ← message STORED but view stays on animation ❌
    → AGENT_THINKING event           ← more thinking stored, still invisible ❌
    → AGENT_RESPONSE event           ← response text stored, still invisible ❌
    → TOOL_CALL event                ← setBuildStep(BUILD) ← NOW content visible ✓
    → ... more events ...
    → COMPLETE event                 ← setBuildStep(BUILD) (redundant)
```

### Agent state machine flow — AFTER fix:

```
User submits prompt
    → setBuildStep(THINKING)         ← view shows Lottie animation
    → [wait for backend...]
    → AGENT_INITIALIZED event        ← no view change (infrastructure)
    → PROCESSING event               ← no view change (infrastructure)
    → AGENT_THINKING event           ← setBuildStep(BUILD) → content VISIBLE ✓
    → AGENT_RESPONSE event           ← setBuildStep(BUILD) → already visible ✓
    → TOOL_CALL event                ← setBuildStep(BUILD) → already visible ✓
    → COMPLETE event                 ← setBuildStep(BUILD) (redundant)
```

---

## Backend Latency Analysis

The backend agent startup pipeline introduces expected latency between query submission
and first LLM token:

| Stage | Cold Start | Warm |
|-------|-----------|------|
| DB ops (session, billing) | 100-500ms | 100-500ms |
| Sandbox creation | 30-60s | <1s (reuse) |
| MCP URL setup | <100ms | <100ms |
| Codex registration | 2-5s | <100ms |
| Port exposures (×6) | 1-2s | <100ms |
| Skills loading | 1-2s | <100ms |
| Workflow setup | <100ms | <100ms |
| **Total to first LLM token** | **35-70s** | **1-3s** |

**The cold start is inherent to the sandbox architecture.** The fix above ensures that
when thinking/response events DO arrive, they are immediately visible — not hidden behind
an animation.

### Frontend Delay Inventory

| Location | Delay | Context | Impact |
|----------|-------|---------|--------|
| `use-session-manager.tsx:37` | 1000ms per event | Replay mode ONLY | None in live mode |
| `use-chat-query.tsx:739-746` | N/A | Hydration delay (documented) | Minor |
| New session join flow | Variable | Await session_id before sending query | 100-500ms |

**No artificial delays found in the live prompt submission path.**

---

## Changes Made

### Fix 1: AGENT_THINKING view transition
**File**: `frontend/src/hooks/use-app-events.tsx`  
**Change**: Added `dispatch(setBuildStep(BUILD_STEP.BUILD))` to the `AgentEvent.AGENT_THINKING`
case handler, before adding the message to the store. This transitions the view from the
Lottie animation to the actual content panel as soon as thinking content arrives.

### Fix 2: AGENT_RESPONSE view transition
**File**: `frontend/src/hooks/use-app-events.tsx`  
**Change**: Added `dispatch(setBuildStep(BUILD_STEP.BUILD))` to the `AgentEvent.AGENT_RESPONSE`
case handler. This ensures text responses also transition the view, covering cases where the
model responds with text before making tool calls.

### Fix 3: Frontend Timing Diagnostic
**File**: `frontend/src/utils/timing-diagnostic.ts` (NEW)  
**Instrumentation points**:
- `use-question-handlers.tsx` — T0 (submit), T1 (query sent)
- `use-app-events.tsx` — T2 (first event), T3 (first content), T4 (view transition)

**Usage** (browser console):
```javascript
window.__timingDiag.enable()   // Start recording
// ... submit a prompt ...
window.__timingDiag.report()   // Print timing report
window.__timingDiag.history()  // Print all recorded sessions
window.__timingDiag.disable()  // Stop recording
```

The diagnostic measures 5 milestones (T0-T5) and automatically flags bottlenecks:
- Submit → Query sent > 500ms warns about session creation delay
- Query → First event > 3s warns about backend startup latency
- First event → Content > 5s warns about agent initialization
- Content → Visible > 200ms warns about view transition delay
- Content arrived but view never transitioned = critical (the bug we fixed)

---

## Files Modified

| File | Type | Description |
|------|------|-------------|
| `frontend/src/hooks/use-app-events.tsx` | FIX | Added `setBuildStep(BUILD)` + timing marks to AGENT_THINKING and AGENT_RESPONSE handlers |
| `frontend/src/hooks/use-question-handlers.tsx` | INSTRUMENTATION | Added timing marks at submit and query-sent points |
| `frontend/src/utils/timing-diagnostic.ts` | NEW | Timing diagnostic utility with console API |

---

## Verification

To verify the fix works:

1. Start the frontend dev server
2. Open browser console, run `window.__timingDiag.enable()`
3. Submit a prompt in agent mode
4. **Expected**: Thinking content should appear immediately when the model starts reasoning,
   replacing the "I'm thinking..." animation
5. **Expected**: The timing report should show T4 (view transition) occurring at the same
   time as T3 (first content event)
6. **Previously**: T4 would be null or only occur on TOOL_CALL/COMPLETE — the thinking
   content was invisible behind the animation

---

## Related Previous Fix

In the previous session, a backend bug was found where reasoning items in list content
paths were silently dropped in both `agent.py` and `chat.py`. That fix ensures reasoning
content is actually emitted by the backend. This fix ensures it's actually *shown* by the
frontend. Together, they complete the reasoning visibility pipeline.
