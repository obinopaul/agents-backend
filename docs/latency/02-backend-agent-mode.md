# Backend Agent Mode (Socket.IO) Latency Analysis

## Overview
- Endpoint: Socket.IO `query` event
- Protocol: Socket.IO (WebSocket)

## Critical Path
1. `query_handler.handle()`:
   - Pre-streaming checks (3-4 DB queries + billing check)
2. Sandbox initialization:
   - Cold start: 30-60s (Docker + `start-services.sh`)
   - Warm start: 1-5s (Reuse existing container)
3. `_run_agent_with_sandbox`:
   - MCP setup (tool registration)
   - Token-by-token streaming
4. Event emission: `message_chunk`

## Latency Hotspots

### 1. Sandbox Cold Start: 30-60s
- **Root cause**: Sequential service starts with hardcoded sleeps
- **Location**: `sandbox.start()` → `docker-compose up` → `start-services.sh`
- **Code path**: 
  ```
  backend/docker/sandbox/start-services.sh
  ├── sleep 2  # After tmux session
  ├── sleep 1  # After node server
  ├── sleep 1  # After Python server
  └── sleep 1  # After browser
  ```

### 2. Pre-streaming Checks: 100-300ms
- **Location**: `query_handler.handle()` (before streaming)
- **Code**: Multiple DB queries and billing check
- **Queries**:
  - Get user session
  - Get agent configuration
  - Check billing/quota
  - Create message record

### 3. MCP Tool Registration: 1-5s
- **Location**: `SandboxConnection.initialize()`
- **Cause**: Synchronous tool registration for each tool

## Recommendations
1. Implement sandbox pre-warming pool
2. Parallelize service starts in sandbox
3. Defer non-critical pre-streaming checks
4. Cache tool registrations
