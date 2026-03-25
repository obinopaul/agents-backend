# Frontend Latency Analysis

## Overview
- Framework: React 18 + Redux
- Streaming: SSE (fetch + ReadableStream) and Socket.IO
- State Management: Redux with chat slice

## Critical Path

### Chat Mode (SSE)
1. User sends message → Redux dispatch
2. `chat.service.ts` → `streamChatResponse()`
3. `fetch()` with ReadableStream
4. `parseSSEBlock()` → Token extraction
5. Redux state update → Re-render

### Agent Mode (Socket.IO)
1. User sends message → Redux dispatch
2. `websocket-context.tsx` → `socket.emit("query")`
3. Event listener: `message_chunk`
4. Redux state update → Re-render

## Latency Hotspots

### 1. "THINKING" Animation Blocking: 500-1000ms
- **Location**: Chat component render logic
- **Cause**: Animation prevents content display until complete
- **Impact**: Perceived latency even when tokens arrive

### 2. Redux State Batching: 16-50ms per batch
- **Location**: Chat slice reducers
- **Cause**: React 18 automatic batching during rapid updates
- **Impact**: Token display delayed until batch completes

### 3. Event Normalization Overhead: 1-5ms per event
- **Location**: `normalizeStreamEvent()` in chat.service.ts
- **Cause**: Complex event type detection and transformation
- **Code**: Lines 210-307 in chat.service.ts

## Timing Diagnostic Tool

The frontend includes a timing diagnostic utility:

```typescript
// Enable in browser console
window.__timingDiag = {
  T0: Date.now(),  // Message sent
  T1: null,        // First byte received
  T2: null,        // First token parsed
  T3: null,        // First render
  T4: null,        // Stream complete
  T5: null         // Final render
};
```

### Measurement Points
- **T0 → T1**: Network + backend processing
- **T1 → T2**: SSE parsing overhead
- **T2 → T3**: React render cycle
- **T3 → T4**: Streaming duration
- **T4 → T5**: Final state reconciliation

## Recommendations
1. Remove or minimize "THINKING" animation duration
2. Use `useDeferredValue` for non-critical UI updates
3. Simplify event normalization logic
4. Implement virtual scrolling for long conversations
