# Backend Chat Mode (SSE) Latency Analysis

## Overview
- Endpoint: `POST /agent/api/v1/chat/stream`
- Protocol: Server-Sent Events (SSE)

## Critical Path
1. Request received by FastAPI
2. Auth middleware (JWT validation)
3. `chat_stream` handler
4. `_astream_workflow_generator`:
   - Pre-streaming DB writes (3-4 queries)
   - Triple event emission (AG-UI, II-Agent, message_chunk)
   - Token-by-token streaming
5. SSE response construction

## Latency Hotspots
1. **Pre-streaming DB Writes**: 100-300ms
   - Location: `chat_stream` -> `_astream_workflow_generator` (before first yield)
   - Code: `session.add()` x3 + `session.commit()`
2. **Triple Event Emission**: 1-5ms per token
   - Location: `_astream_workflow_generator` loop
   - Code: `emit("AG-UI", ...)`, `emit("II-Agent", ...)`, `emit("message_chunk", ...)`
3. **Redis Pub/Sub Overhead**: 0.5-2ms per emit
   - Root cause: Single-process deployment still uses Redis

## Recommendations
1. Defer non-critical DB writes until after streaming
2. Consolidate event emission to single protocol
3. Bypass Redis for single-process deployments