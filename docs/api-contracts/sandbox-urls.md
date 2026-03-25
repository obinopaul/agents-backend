# Sandbox URLs: VS Code, Codex & MCP

This document explains how sandbox URLs are generated and how authentication works.

## Overview

When a sandbox is created via E2B, internal services run on specific ports. These ports are exposed to the internet via E2B's proxy system, generating unique URLs per sandbox.

| Service | Internal Port | Purpose |
|---------|---------------|---------|
| MCP Server | 6060 | Tool server for agent operations (Write, Read, Bash, etc.) |
| VS Code (code-server) | 9000 | Browser-based IDE to view/edit code live |
| Codex SSE | 1324 | Native Codex streaming events (AI coding assistant) |

## How URLs Are Generated

### The `expose_port()` Method

Located in `backend/src/sandbox/sandbox_server/sandboxes/e2b.py`:

```python
async def expose_port(self, port: int) -> str:
    self._ensure_sandbox()
    return f"https://{self._sandbox.get_host(port)}"
```

E2B's SDK method `get_host(port)` returns a hostname in the format:
```
{provider_sandbox_id}-{port}.e2b.dev
```

### Example URLs

For a sandbox with E2B ID `f7d8e9a0-1234-5678-abcd-ef1234567890`:

| Service | URL |
|---------|-----|
| MCP Server | `https://f7d8e9a0-1234-5678-abcd-ef1234567890-6060.e2b.dev` |
| VS Code | `https://f7d8e9a0-1234-5678-abcd-ef1234567890-9000.e2b.dev` |
| Codex SSE | `https://f7d8e9a0-1234-5678-abcd-ef1234567890-1324.e2b.dev` |

## Sandbox IDs Explained

There are **two different IDs** in the system:

### 1. `sandbox_id` (Internal/Application ID)

- **What it is**: Your application's internal identifier
- **Format**: Usually same as `thread_id` from the conversation
- **Purpose**: Maps conversations to sandboxes (1 thread = 1 sandbox)
- **Example**: `test-session-20260104133500` or UUID
- **Stored in**: Database (`sandboxes` table)

### 2. `provider_sandbox_id` (E2B's ID)

- **What it is**: E2B's actual sandbox identifier
- **Format**: E2B-generated UUID
- **Purpose**: Used to connect to E2B's infrastructure
- **Example**: `f7d8e9a0-1234-5678-abcd-ef1234567890`
- **Used for**: URL generation, E2B API calls

### How They Relate

```
Database Record:
┌────────────────────────────────────────────────────────┐
│ sandbox_id (your ID)  →  provider_sandbox_id (E2B ID)  │
│ "my-thread-123"       →  "f7d8e9a0-1234-5678..."       │
└────────────────────────────────────────────────────────┘

When generating URLs, E2B uses provider_sandbox_id:
  https://{provider_sandbox_id}-{port}.e2b.dev
```

## Authentication

### E2B Infrastructure Level

E2B sandboxes are authenticated via the `E2B_API_KEY` environment variable. This key:
- Is required to create, connect, or manage sandboxes
- Is server-side only (never exposed to clients)
- Is configured in `backend/.env`

### Application Level (JWT)

Your application uses JWT tokens to authenticate users:
- Users login via `/api/v1/auth/login/swagger`
- JWT token is passed in `Authorization: Bearer {token}` header
- Sandbox access is controlled by matching `user_id` to sandbox ownership

### VS Code URL Access

The VS Code URL (`https://{sandbox_id}-9000.e2b.dev`) is:
- **Publicly accessible** once exposed (no password by default)
- Authenticated at E2B level (only valid sandbox IDs work)
- Anyone with the URL can view the sandbox workspace

> **Security Note**: In production, you may want to configure code-server password protection.

## Where URLs Are Generated in Code

### In `agent.py` (Agent Stream Endpoint)

```python
# Line 460 - MCP Server
mcp_url = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)

# Line 575 - Codex SSE (if credentials available)
codex_url = await sandbox.expose_port(settings.SANDBOX_CODEX_SSE_PORT)

# Line 614 - VS Code
vscode_url = await sandbox.expose_port(settings.SANDBOX_CODE_SERVER_PORT)
```

### SSE Events Sent to Frontend

| Event Type | Data Fields | When Sent |
|------------|-------------|-----------|
| `status: mcp_ready` | `mcp_url` | After MCP health check passes |
| `status: codex_ready` | `codex_url` | After Codex SSE server starts |
| `status: vscode_ready` | `vscode_url` | After VS Code port exposed |
| `status: complete` | `vscode_url`, `codex_url`, `sandbox_id` | Stream completion |

## Configuration

In `backend/core/conf.py`:

```python
SANDBOX_MCP_SERVER_PORT: int = 6060
SANDBOX_CODE_SERVER_PORT: int = 9000
SANDBOX_CODEX_SSE_PORT: int = 1324
```

## Troubleshooting

### "Cannot connect to VS Code URL"

1. **Sandbox may be paused**: Sandboxes pause after inactivity. Resume by sending a new message.
2. **Sandbox may be deleted**: Check if sandbox still exists in database.
3. **E2B API key invalid**: Verify `E2B_API_KEY` in environment.

### "MCP server not ready"

1. Services take ~10-30 seconds to start after sandbox creation.
2. Check `start-services.sh` executed correctly.
3. Verify MCP health endpoint: `GET {mcp_url}/v1/health`

### "Codex not available"

1. Codex requires user credentials in database (`MCPSetting` with `tool_type=CODEX`).
2. The `sse-http-server` binary must be built in the E2B template.
3. Check `/register-codex` endpoint was called successfully.

## Related Documentation

- [E2B Sandbox](./e2b-sandbox.md) - E2B integration details
- [Sandbox Server](./sandbox-server.md) - Sandbox lifecycle management
- [Tool Server](./tool-server.md) - MCP tool server architecture
