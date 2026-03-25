# Integration Layer Latency Analysis

## Overview
This document covers latency at the boundary between frontend and backend systems.

## Socket.IO Configuration

### Server Setup
```python
# backend/common/socketio/server.py
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    client_manager=AsyncRedisManager(redis_url)  # Redis pub/sub overhead
)
```

### Redis Pub/Sub Overhead
- **Impact**: 0.5-2ms per emit
- **Cause**: Even single-process deployments route through Redis
- **Recommendation**: Bypass Redis for single-node deployments

## SSE Middleware Issues

### OperaLog Middleware Buffering
- **Location**: `backend/middleware/opera_log_middleware.py`
- **Issue**: Middleware may buffer SSE responses
- **Impact**: Entire response buffered before first byte sent

```python
# Current behavior (problematic)
async def __call__(self, scope, receive, send):
    # ... logs entire response before sending
```

### Recommendation
Exclude streaming endpoints from response logging:
```python
STREAMING_ENDPOINTS = [
    "/agent/api/v1/chat/stream",
    "/agent/api/v1/agent/stream"
]
```

## Connection Lifecycle

### Join Session Flow
```
Client connect
    ↓
join_session event
    ↓
├── Verify JWT (5-20ms)
├── Load user from DB (10-50ms)
├── Create/update session (10-30ms)
└── Join Socket.IO room (1ms)
    ↓
session_joined response
```

**Total overhead**: 26-101ms per connection

### Query Message Flow
```
query event received
    ↓
├── Parse message (1ms)
├── Validate session (5-20ms)
├── Check billing (10-50ms)
├── Create DB records (20-100ms)
└── Initialize sandbox (if needed)
    ↓
First token emitted
```

**Total pre-streaming overhead**: 36-171ms (excluding sandbox)

## Protocol Comparison

| Aspect | SSE (Chat Mode) | Socket.IO (Agent Mode) |
|--------|-----------------|------------------------|
| Connection overhead | Per-request | Persistent |
| Auth per message | Yes | Session-based |
| Bidirectional | No | Yes |
| Redis dependency | No | Yes |
| Typical first-token | 200-500ms | 300-800ms |

## Recommendations
1. Use connection pooling for DB operations
2. Cache session/billing data in Redis with TTL
3. Implement lazy sandbox initialization
4. Consider protocol consolidation
