# Sandbox API Contracts

> **Base URL:** `http://localhost:8000/api/v1/agent/sandboxes`
>
> All endpoints require `Authorization: Bearer <token>` header.

---

## Overview

The Sandbox API provides secure, isolated execution environments for running code, files, and commands. Each sandbox is a containerized environment with:
- File system access
- Command execution
- Port exposure for services (MCP server, VS Code)
- Timeout management

---

## Table of Contents

1. [Lifecycle Management](#1-lifecycle-management)
2. [Command Execution](#2-command-execution)
3. [File Operations](#3-file-operations)
4. [Port Exposure](#4-port-exposure)
5. [Timeout Management](#5-timeout-management)

---

## 1. Lifecycle Management

### POST `/create`

Create a new sandbox environment.

**Request:**
```json
{
  "user_id": "user-123",
  "sandbox_template_id": "default"
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "sandbox_id": "sandbox-abc123",
    "provider_sandbox_id": "e2b-xyz789",
    "status": "running",
    "message": "Sandbox created successfully",
    "mcp_url": "https://sandbox.e2b.dev:6060",
    "vscode_url": "https://sandbox.e2b.dev:9000"
  }
}
```

**Exposed Ports:**
| Port | Service |
|------|---------|
| 6060 | MCP Tool Server |
| 9000 | VS Code Server |

---

### POST `/connect`

Connect to an existing sandbox (or resume if paused).

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123"
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "sandbox_id": "sandbox-abc123",
    "provider_sandbox_id": "e2b-xyz789",
    "status": "running",
    "message": "Successfully connected to sandbox",
    "mcp_url": "https://sandbox.e2b.dev:6060",
    "vscode_url": "https://sandbox.e2b.dev:9000"
  }
}
```

---

### GET `/{sandbox_id}/status`

Get sandbox status.

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "sandbox_id": "sandbox-abc123",
    "status": "running",
    "provider_sandbox_id": "e2b-xyz789",
    "message": "Status retrieved successfully"
  }
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| `running` | Sandbox is active |
| `paused` | Sandbox is paused (can be resumed) |
| `stopped` | Sandbox has been stopped |

---

### GET `/{sandbox_id}/info`

Get detailed sandbox information.

**Response:**
```json
{
  "code": 200,
  "data": {
    "sandbox_id": "sandbox-abc123",
    "provider_sandbox_id": "e2b-xyz789",
    "user_id": "user-123",
    "template_id": "default",
    "created_at": "2024-12-21T10:00:00Z",
    "status": "running"
  }
}
```

---

### GET `/{sandbox_id}/urls`

Get MCP and VS Code URLs for a sandbox.

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "sandbox_id": "sandbox-abc123",
    "mcp_url": "https://sandbox.e2b.dev:6060",
    "vscode_url": "https://sandbox.e2b.dev:9000"
  }
}
```

---

### POST `/{sandbox_id}/pause`

Pause a sandbox (saves resources).

**Query:** `?reason=manual`

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "message": "Sandbox paused successfully (reason: manual)"
  }
}
```

---

### DELETE `/{sandbox_id}`

Delete a sandbox permanently.

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "message": "Sandbox deleted successfully"
  }
}
```

---

## 2. Command Execution

### POST `/run-cmd`

Execute a command in the sandbox.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "command": "ls -la /workspace",
  "background": false
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "output": "total 24\ndrwxr-xr-x 5 user user 4096 Dec 21 10:00 .\ndrwxr-xr-x 1 root root 4096 Dec 21 10:00 ..\n-rw-r--r-- 1 user user  220 Dec 21 10:00 .bashrc\ndrwxr-xr-x 2 user user 4096 Dec 21 10:00 project\n",
    "message": "Command executed successfully"
  }
}
```

**Background Execution:**

Set `"background": true` for long-running commands that shouldn't block.

---

## 3. File Operations

### POST `/write-file`

Write content to a file.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "file_path": "/workspace/app.py",
  "content": "print('Hello, World!')"
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "message": "File written to /workspace/app.py"
  }
}
```

---

### POST `/read-file`

Read file contents.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "file_path": "/workspace/app.py"
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "content": "print('Hello, World!')"
  }
}
```

---

### POST `/upload-file`

Upload a file using multipart form.

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `sandbox_id` | string | Target sandbox ID |
| `file_path` | string | Destination path in sandbox |
| `file` | file | The file to upload |

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "message": "File uploaded to /workspace/uploaded.txt"
  }
}
```

---

### POST `/upload-file-from-url`

Download a file from URL and upload to sandbox.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "url": "https://example.com/data.csv",
  "file_path": "/workspace/data.csv"
}
```

---

### POST `/download-to-presigned-url`

Download from sandbox and upload to presigned URL.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "sandbox_path": "/workspace/output.pdf",
  "presigned_url": "https://s3.amazonaws.com/bucket/output.pdf?...",
  "format": "binary"
}
```

---

### POST `/create-directory`

Create a directory.

**Query:** `?sandbox_id=abc123&directory_path=/workspace/new_folder&exist_ok=true`

---

## 4. Port Exposure

### POST `/expose-port`

Expose a port from the sandbox to public URL.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "port": 8080
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "url": "https://sandbox-abc123-8080.e2b.dev",
    "message": "Port 8080 exposed successfully"
  }
}
```

---

## 5. Timeout Management

### POST `/schedule-timeout`

Schedule automatic sandbox cleanup.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "timeout_seconds": 3600
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "message": "Timeout scheduled successfully"
  }
}
```

---

## Error Responses

| Code | Exception | Description |
|------|-----------|-------------|
| 401 | `SandboxAuthenticationError` | Authentication failed |
| 404 | `SandboxNotFoundException` | Sandbox not found |
| 408 | `SandboxTimeoutException` | Operation timed out |
| 422 | `SandboxNotInitializedError` | Sandbox not initialized |
| 500 | General Error | Internal server error |

---

## Configuration (.env)

```env
# Sandbox Provider
SANDBOX_PROVIDER=e2b  # or 'daytona'
E2B_API_KEY=your_e2b_api_key

# Default Ports
SANDBOX_MCP_SERVER_PORT=6060
SANDBOX_CODE_SERVER_PORT=9000

# Timeouts
SANDBOX_DEFAULT_TIMEOUT=3600
```

---

## Quick Test Commands

```bash
# Create sandbox
SANDBOX=$(curl -s -X POST http://localhost:8000/api/v1/agent/sandboxes/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test-user"}' | jq -r '.data.sandbox_id')

# Run command
curl -X POST http://localhost:8000/api/v1/agent/sandboxes/run-cmd \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"sandbox_id\":\"$SANDBOX\",\"command\":\"echo Hello World\"}"

# Write file
curl -X POST http://localhost:8000/api/v1/agent/sandboxes/write-file \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"sandbox_id\":\"$SANDBOX\",\"file_path\":\"/workspace/test.txt\",\"content\":\"Test content\"}"

# Delete sandbox
curl -X DELETE "http://localhost:8000/api/v1/agent/sandboxes/$SANDBOX" \
  -H "Authorization: Bearer $TOKEN"
```
