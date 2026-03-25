# Latency Optimization Recommendations

## Executive Summary

Based on the comprehensive latency analysis across backend, frontend, and integration layers, this document prioritizes actionable optimizations.

## Priority Matrix

| Issue | Impact | Effort | Priority |
|-------|--------|--------|----------|
| Sandbox cold start | 30-60s | High | Critical |
| Pre-streaming DB writes | 100-300ms | Medium | High |
| Triple event emission | 1-5ms/token | Low | Medium |
| Redis pub/sub bypass | 0.5-2ms/emit | Medium | Medium |
| Frontend "THINKING" | 500-1000ms perceived | Low | High |
| Middleware buffering | Variable | Low | High |

## Critical Priority

### 1. Sandbox Pre-warming Pool
**Current**: Cold start takes 30-60s due to sequential service initialization.

**Solution**:
```python
# backend/app/agent/sandbox/pool.py
class SandboxPool:
    def __init__(self, min_warm: int = 2, max_warm: int = 5):
        self.warm_sandboxes = asyncio.Queue()
        self.min_warm = min_warm
        
    async def get_sandbox(self) -> Sandbox:
        if not self.warm_sandboxes.empty():
            return await self.warm_sandboxes.get()
        return await self._create_warm_sandbox()
    
    async def maintain_pool(self):
        """Background task to maintain minimum warm sandboxes"""
        while True:
            if self.warm_sandboxes.qsize() < self.min_warm:
                sandbox = await self._create_warm_sandbox()
                await self.warm_sandboxes.put(sandbox)
            await asyncio.sleep(10)
```

**Expected improvement**: Cold start → Warm start (30-60s → 1-5s)

## High Priority

### 2. Defer Pre-streaming DB Writes
**Current**: 3-4 DB writes block first token by 100-300ms.

**Solution**:
```python
async def _astream_workflow_generator(...):
    # Start streaming IMMEDIATELY
    async for event in workflow.astream(...):
        yield event
    
    # Defer DB writes to background task
    asyncio.create_task(_persist_conversation(session, messages))
```

**Expected improvement**: 100-300ms reduction in time-to-first-token

### 3. Fix Middleware SSE Buffering
**Current**: OperaLog middleware may buffer entire SSE response.

**Solution**:
```python
# backend/middleware/opera_log_middleware.py
STREAMING_ENDPOINTS = {
    "/agent/api/v1/chat/stream",
    "/agent/api/v1/agent/stream"
}

class OperaLogMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["path"] in STREAMING_ENDPOINTS:
            # Bypass logging for streaming endpoints
            await self.app(scope, receive, send)
            return
        # ... normal logging logic
```

**Expected improvement**: Eliminates buffering delay

### 4. Reduce Frontend Perceived Latency
**Current**: "THINKING" animation adds 500-1000ms perceived delay.

**Solution**:
```typescript
// Show content immediately, animate subtly
const ChatMessage = ({ message }) => {
  const isStreaming = message.status === 'streaming';
  
  return (
    <div className={isStreaming ? 'animate-pulse-subtle' : ''}>
      {message.content || <Skeleton />}
    </div>
  );
};
```

**Expected improvement**: 500-1000ms perceived latency reduction

## Medium Priority

### 5. Protocol Consolidation
**Current**: Triple event emission (AG-UI, II-Agent, message_chunk) per token.

**Solution**: Consolidate to single event protocol:
```python
# Emit single unified event
await sio.emit("message", {
    "type": "chunk",
    "content": token,
    "metadata": {...}
}, room=session_id)
```

**Expected improvement**: 2-10ms/token reduction

### 6. Redis Bypass for Single-Node
**Current**: Even single-process deployments use Redis pub/sub.

**Solution**:
```python
# backend/common/socketio/server.py
if settings.SINGLE_NODE_MODE:
    sio = socketio.AsyncServer(async_mode='asgi')
else:
    sio = socketio.AsyncServer(
        async_mode='asgi',
        client_manager=AsyncRedisManager(redis_url)
    )
```

**Expected improvement**: 0.5-2ms/emit reduction

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 days)
- [ ] Fix middleware SSE buffering
- [ ] Reduce "THINKING" animation
- [ ] Add streaming endpoint exclusions

### Phase 2: Core Optimizations (1 week)
- [ ] Implement deferred DB writes
- [ ] Add connection/session caching
- [ ] Protocol consolidation

### Phase 3: Infrastructure (2-3 weeks)
- [ ] Sandbox pre-warming pool
- [ ] Parallel sandbox service starts
- [ ] Redis bypass for single-node

## Metrics to Track

1. **Time to First Token (TTFT)**: Target < 300ms
2. **Sandbox Cold Start**: Target < 5s (with warm pool)
3. **Streaming Throughput**: Target > 100 tokens/sec
4. **P95 Response Latency**: Target < 2s for typical query

## Verification

Use the test harness in `tests/test_latency.py` to measure improvements:
```bash
pytest tests/test_latency.py -v --tb=short
```
