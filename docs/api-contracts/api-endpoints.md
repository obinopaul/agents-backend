# API Endpoints Reference

> Complete reference for all REST API endpoints in the Agents Backend.

---

## Base URL
```
http://localhost:8000/api/v1
```

---

## Health Check

The `/health` endpoint is available at the root path (not under `/api/v1`) for easy integration with load balancers and monitoring systems.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |

### Health Check Example

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-29T13:20:08.419998+00:00",
  "version": "1.11.2",
  "service": "agents-backend"
}
```

---

## Authentication

Most endpoints require JWT authentication:
```http
Authorization: Bearer <access_token>
```

---

## Router Structure


```
/api/v1
├── /admin    (Admin & Auth)
│   ├── /auth/*
│   ├── /sys/*
│   ├── /log/*
│   └── /monitor/*
├── /agent    (Agent AI)
│   ├── /chat/*       ← Simple chat (no sandbox)
│   ├── /agent/*      ← Agent with sandbox (NEW)
│   ├── /generation/*
│   ├── /mcp/*
│   ├── /user-settings/mcp/*
│   ├── /rag/*
│   ├── /tts/*
│   ├── /config
│   ├── /credits/*
│   └── /sandboxes/*
└── /task     (Scheduled Tasks)
```

---

# Admin Endpoints

## Authentication (`/api/v1/admin/auth/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Login with username/password |
| POST | `/logout` | Logout and invalidate token |
| POST | `/token/refresh` | Refresh access token |
| GET | `/captcha` | Get CAPTCHA image |

### Login Example
```http
POST /api/v1/admin/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password123",
  "captcha_id": "abc123",
  "captcha_code": "1234"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "nickname": "Administrator"
  }
}
```

---

## System (`/api/v1/admin/sys/`)

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List users (paginated) |
| GET | `/users/{id}` | Get user by ID |
| POST | `/users` | Create user |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user |

### Roles
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/roles` | List roles |
| POST | `/roles` | Create role |
| PUT | `/roles/{id}` | Update role |
| DELETE | `/roles/{id}` | Delete role |
| GET | `/roles/{id}/menus` | Get role menus |
| PUT | `/roles/{id}/menus` | Update role menus |

### Departments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/depts` | List departments (tree) |
| POST | `/depts` | Create department |
| PUT | `/depts/{id}` | Update department |
| DELETE | `/depts/{id}` | Delete department |

### Menus
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/menus` | List menus (tree) |
| POST | `/menus` | Create menu |
| PUT | `/menus/{id}` | Update menu |
| DELETE | `/menus/{id}` | Delete menu |

---

## Logs (`/api/v1/admin/log/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login-logs` | List login logs |
| GET | `/opera-logs` | List operation logs |
| DELETE | `/login-logs/{id}` | Delete login log |
| DELETE | `/opera-logs/{id}` | Delete operation log |

---

## Monitor (`/api/v1/admin/monitor/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/server` | Get server stats |
| GET | `/redis` | Get Redis info |

---

# Agent Endpoints

## Chat (`/api/v1/agent/chat/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/stream` | Stream AI chat responses (SSE) |

### Stream Chat Example
```http
POST /api/v1/agent/chat/stream
Content-Type: application/json
Authorization: Bearer <token>

{
  "messages": [
    {"role": "user", "content": "Create a React component"}
  ],
  "thread_id": "optional-thread-id",
  "agent_name": "coder",
  "resources": [],
  "mcp_settings": {"servers": {}},
  "enable_web_search": true,
  "enable_deep_thinking": false,
  "locale": "en-US"
}
```

**Response:** Server-Sent Events stream

---

## Generation (`/api/v1/agent/generation/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/podcast` | Generate podcast from content |
| POST | `/ppt` | Generate PowerPoint from content |
| POST | `/prose` | Generate/transform prose |
| POST | `/enhance-prompt` | Enhance a prompt |

### Generate Podcast
```http
POST /api/v1/agent/generation/podcast
Content-Type: application/json

{"content": "Report content here..."}
```
**Response:** MP3 audio file

### Generate PPT
```http
POST /api/v1/agent/generation/ppt
Content-Type: application/json

{
  "content": "Report content...",
  "locale": "en-US"
}
```
**Response:** PPTX file

### Generate Prose
```http
POST /api/v1/agent/generation/prose
Content-Type: application/json

{
  "prompt": "Text to process",
  "option": "improve",  // continue, improve, fix, shorter, longer, zap
  "command": ""
}
```

---

## MCP Management (`/api/v1/agent/mcp/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/servers` | List available MCP servers |
| POST | `/servers` | Add MCP server config |
| DELETE | `/servers/{name}` | Remove MCP server |

---

## User MCP Settings (`/api/v1/agent/user-settings/mcp/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's MCP settings |
| GET | `/codex` | Get Codex config |
| POST | `/codex` | Configure Codex |
| GET | `/claude-code` | Get Claude Code config |
| POST | `/claude-code` | Configure Claude Code (OAuth) |
| POST | `/custom` | Add custom MCP server |
| DELETE | `/{tool_type}` | Delete MCP setting |
| PATCH | `/{tool_type}/toggle` | Toggle active status |

### Configure Codex
```http
POST /api/v1/agent/user-settings/mcp/codex
Content-Type: application/json

{
  "apikey": "sk-...",
  "model": "gpt-4o",
  "model_reasoning_effort": "medium",
  "search": false
}
```

### Configure Claude Code
```http
POST /api/v1/agent/user-settings/mcp/claude-code
Content-Type: application/json

{"authorization_code": "code#verifier"}
```

---

## RAG (`/api/v1/agent/rag/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/resources` | List RAG resources |
| POST | `/resources` | Add RAG resource |
| DELETE | `/resources/{id}` | Delete RAG resource |

---

## TTS (`/api/v1/agent/tts/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/synthesize` | Text-to-speech synthesis |

```http
POST /api/v1/agent/tts/synthesize
Content-Type: application/json

{
  "text": "Hello world",
  "voice": "en-US-Standard-A",
  "speed": 1.0
}
```
**Response:** MP3 audio file

---

## Configuration (`/api/v1/agent/config`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Get agent configuration |

---

## Credits (`/api/v1/agent/credits/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/balance` | Get user's credit balance |
| GET | `/usage` | Get credit usage history |
| POST | `/add` | Add credits (admin only) |

---

## Sandbox (`/api/v1/agent/sandboxes/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Create new sandbox |
| POST | `/connect` | Connect to existing sandbox |
| POST | `/run-command` | Run command in sandbox |
| GET | `/{id}` | Get sandbox status |
| GET | `/{id}/info` | Get sandbox details |
| GET | `/{id}/urls` | Get MCP/VS Code URLs |
| POST | `/{id}/timeout` | Schedule timeout |
| POST | `/{id}/pause` | Pause sandbox |
| DELETE | `/{id}` | Delete sandbox |
| POST | `/{id}/expose-port` | Expose port |
| POST | `/write-file` | Write file to sandbox |
| POST | `/read-file` | Read file from sandbox |
| POST | `/upload-file` | Upload file |
| POST | `/upload-from-url` | Upload from URL |
| POST | `/download-to-presigned` | Download to presigned URL |
| POST | `/{id}/mkdir` | Create directory |

### Create Sandbox
```http
POST /api/v1/agent/sandboxes
Content-Type: application/json

{"template_id": "agents-backend-sandbox"}
```

**Response:**
```json
{
  "sandbox_id": "sbx_abc123",
  "mcp_url": "https://6060-sbx.e2b.app",
  "vscode_url": "https://9000-sbx.e2b.app"
}
```

### Run Command
```http
POST /api/v1/agent/sandboxes/run-command
Content-Type: application/json

{
  "sandbox_id": "sbx_abc123",
  "command": "npm install"
}
```

---

## Slides (`/api/v1/agent/sandboxes/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{id}/slides` | List slides |
| GET | `/{id}/slides/{slide_id}` | Get slide |
| POST | `/{id}/slides` | Create slide |
| PUT | `/{id}/slides/{slide_id}` | Update slide |
| DELETE | `/{id}/slides/{slide_id}` | Delete slide |

---

# Task Endpoints (`/api/v1/task/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/schedulers` | List scheduled tasks |
| POST | `/schedulers` | Create scheduled task |
| PUT | `/schedulers/{id}` | Update task |
| DELETE | `/schedulers/{id}` | Delete task |
| POST | `/schedulers/{id}/run` | Run task now |

---

# Plugin Endpoints

## OAuth2 (`/api/v1/admin/oauth2/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/github/authorize` | Start GitHub OAuth |
| GET | `/github/callback` | GitHub callback |
| GET | `/google/authorize` | Start Google OAuth |
| GET | `/google/callback` | Google callback |

## Code Generator (`/api/v1/admin/gen/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/business` | List code gen configs |
| POST | `/business` | Create config |
| POST | `/business/{id}/generate` | Generate code |

---

# Error Responses

All errors follow this format:
```json
{
  "detail": "Error message",
  "code": "ERROR_CODE"
}
```

| Status | Description |
|--------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |
