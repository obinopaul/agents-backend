# Sandbox Server Integration API Contract

## Overview

The sandbox server provides secure, isolated code execution environments integrated with the FastAPI backend. It supports **E2B** (primary) and **Daytona** (alternative) providers for remote sandboxes.

**Last Verified:** 2024-12-26 | **All 10 Core Tests Passed** ✅

---

## Quick Start

### 1. Prerequisites

| Requirement | Description |
|-------------|-------------|
| Python 3.12+ | Runtime environment |
| Redis | Message queue for sandbox lifecycle |
| PostgreSQL | Database for sandbox state |
| E2B Account | [Sign up at e2b.dev](https://e2b.dev) |

### 2. Environment Setup

Add to `backend/.env`:

```bash
# E2B Configuration (Required)
E2B_API_KEY=e2b_xxxxxxxxxxxxxxxxxxxx
E2B_TEMPLATE_ID=vg6mdf4wgu5qoijamwb5

# Optional: Sandbox Ports (Default shown)
SANDBOX_MCP_SERVER_PORT=6060
SANDBOX_CODE_SERVER_PORT=9000

# Optional: Daytona Alternative Provider
DAYTONA_API_KEY=your_daytona_key
DAYTONA_SERVER_URL=https://app.daytona.io/api
```

### 3. Start the Backend Server

```powershell
cd "c:\Users\pault\Documents\3. AI and Machine Learning\2. Deep Learning\1c. App\Projects\agents-backend"
$env:PYTHONIOENCODING='utf-8'
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Create Test User (First Time Only)

```bash
cd backend
python tests/live/create_test_user.py
# Creates: sandbox_test / TestPass123!
```

### 5. Run Comprehensive Tests

```bash
cd backend/tests/live
python test_sandbox_comprehensive.py
```

---

## Authentication

All sandbox endpoints require **JWT authentication**.

### Step 1: Obtain Token

**Endpoint**: `POST /api/v1/auth/login/swagger`

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login/swagger?username=sandbox_test&password=TestPass123!"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Step 2: Use Token

Include in all subsequent requests:
```
Authorization: Bearer <access_token>
```

---

## API Endpoints

> [!IMPORTANT]
> **Base Path**: `/agent/sandboxes/sandboxes` (Note: NOT `/api/v1/agent/...`)

### Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/create` | Create new sandbox |
| `GET` | `/{sandbox_id}/status` | Get sandbox status |
| `GET` | `/{sandbox_id}/info` | Get sandbox details |
| `GET` | `/{sandbox_id}/urls` | Get MCP and VSCode URLs |
| `POST` | `/run-cmd` | Execute shell command |
| `POST` | `/write-file` | Write file to sandbox |
| `POST` | `/read-file` | Read file from sandbox |
| `POST` | `/expose-port` | Expose a port |
| `POST` | `/schedule-timeout` | Set sandbox timeout |
| `POST` | `/{sandbox_id}/pause` | Pause sandbox |
| `DELETE` | `/{sandbox_id}` | Delete sandbox |

---

### Create Sandbox

```bash
POST /agent/sandboxes/sandboxes/create
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": "user-123",
  "sandbox_template_id": "vg6mdf4wgu5qoijamwb5"  // Optional
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "sandbox_id": "29ef1923-20e4-4e41-9d76-1fffafbaaaeb",
    "provider_sandbox_id": "i4isp1t4pd05ulp7qgdop",
    "status": "running",
    "mcp_url": "https://6060-i4isp1t4pd05ulp7qgdop.e2b.app",
    "vscode_url": "https://9000-i4isp1t4pd05ulp7qgdop.e2b.app"
  }
}
```

---

### Run Command

```bash
POST /agent/sandboxes/sandboxes/run-cmd
Authorization: Bearer <token>
Content-Type: application/json

{
  "sandbox_id": "29ef1923-20e4-4e41-9d76-1fffafbaaaeb",
  "command": "echo 'Hello' && pwd && python3 --version",
  "background": false
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "output": "Hello\n/home/user\nPython 3.12.0\n",
    "message": "Command executed successfully"
  }
}
```

---

### Write File

```bash
POST /agent/sandboxes/sandboxes/write-file
Authorization: Bearer <token>
Content-Type: application/json

{
  "sandbox_id": "29ef1923-20e4-4e41-9d76-1fffafbaaaeb",
  "file_path": "/home/user/test.py",
  "content": "print('Hello World')"
}
```

---

### Read File

```bash
POST /agent/sandboxes/sandboxes/read-file
Authorization: Bearer <token>
Content-Type: application/json

{
  "sandbox_id": "29ef1923-20e4-4e41-9d76-1fffafbaaaeb",
  "file_path": "/home/user/test.py"
}
```

---

### Delete Sandbox

```bash
DELETE /agent/sandboxes/sandboxes/{sandbox_id}
Authorization: Bearer <token>
```

---

## E2B Template Deployment

### Deploy New Template

```bash
# Install E2B CLI
npm install -g @e2b/cli

# Login
e2b auth login

# Build template (from project root)
e2b template build -d backend/e2b.Dockerfile -n agents-sandbox

# Note the template ID in output: vg6mdf4wgu5qoijamwb5
```

### Update Existing Template

```bash
e2b template build -d backend/e2b.Dockerfile vg6mdf4wgu5qoijamwb5
```

### Template Features

| Component | Description |
|-----------|-------------|
| Python 3.12 | Runtime with all tool_server dependencies |
| Node.js 24 | JavaScript/TypeScript execution |
| Playwright | Browser automation |
| MCP Server | Tool server on port 6060 |
| Code-Server | VS Code IDE on port 9000 |
| Obfuscated tool_server | Protected by PyArmor |

---

## Python Client Example

```python
import asyncio
import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"

async def sandbox_demo():
    client = httpx.AsyncClient(
        timeout=120.0,
        http2=False,  # Required
        headers={
            'User-Agent': 'SandboxClient/1.0',
            'X-Request-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        }
    )
    
    # 1. Login
    r = await client.post(
        f'{BASE_URL}/api/v1/auth/login/swagger',
        params={'username': 'sandbox_test', 'password': 'TestPass123!'}
    )
    token = r.json()['access_token']
    client.headers['Authorization'] = f'Bearer {token}'
    
    # 2. Create sandbox
    r = await client.post(
        f'{BASE_URL}/agent/sandboxes/sandboxes/create',
        json={'user_id': 'demo'}
    )
    sandbox_id = r.json()['data']['sandbox_id']
    print(f"Created: {sandbox_id}")
    
    # 3. Run command
    r = await client.post(
        f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
        json={'sandbox_id': sandbox_id, 'command': 'python3 --version'}
    )
    print(f"Output: {r.json()['data']['output']}")
    
    # 4. Cleanup
    await client.delete(f'{BASE_URL}/agent/sandboxes/sandboxes/{sandbox_id}')
    print("Deleted")
    
    await client.aclose()

asyncio.run(sandbox_demo())
```

---

## Required HTTP Headers

| Header | Required | Description |
|--------|----------|-------------|
| `User-Agent` | ✅ | Client identifier |
| `X-Request-ID` | ✅ | Valid UUID |
| `Authorization` | ✅ | `Bearer <token>` |
| `Content-Type` | ✅ | `application/json` |

---

## Test Files

**Location:** `backend/tests/live/`

| File | Purpose |
|------|---------|
| `test_sandbox_comprehensive.py` | Full test suite (10 tests) |
| `create_test_user.py` | Create test credentials |
| `test_sandbox_authenticated.py` | Legacy test |

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Token 无效` | Invalid/missing JWT | Login to get valid token |
| `500 on create` | E2B_API_KEY not set | Add to `backend/.env` |
| `500 on create` | Server using old env | Restart uvicorn server |
| `404 on endpoints` | Wrong base path | Use `/agent/sandboxes/sandboxes` |

### E2B Build Errors

| Error | Solution |
|-------|----------|
| `ResolutionImpossible` | Use `e2b-requirements.txt` (fixed) |
| `google-cloud-storage conflict` | Downgraded to 2.18.2 (fixed) |
| `Template not found` | Deploy template first |

---

## Configuration Summary

```bash
# backend/.env - Required Settings

# E2B (Primary Provider)
E2B_API_KEY=e2b_xxxxxxxxxxxxxxxxxxxx
E2B_TEMPLATE_ID=vg6mdf4wgu5qoijamwb5

# Redis (Required for lifecycle queue)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DATABASE=0

# Database (Required for sandbox state)
DATABASE_URL=postgresql://user:pass@localhost/db
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   FastAPI       │────▶│  SandboxService  │────▶│  E2B Cloud      │
│   /agent/...    │     │  (Controller)    │     │  (Provider)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│   PostgreSQL    │     │     Redis        │
│   (State DB)    │     │  (Queue/Cache)   │
└─────────────────┘     └──────────────────┘
```

---

## Current Status

| Component | Status |
|-----------|--------|
| E2B Template | ✅ `vg6mdf4wgu5qoijamwb5` deployed |
| Create Sandbox | ✅ Working |
| Run Command | ✅ Working |
| File Operations | ✅ Read/Write working |
| Port Exposure | ✅ MCP & VSCode URLs |
| Delete Sandbox | ✅ Working |
| Authentication | ✅ JWT via `/api/v1/auth/login/swagger` |
