# API Contracts

> Complete API documentation for frontend developers.

---

## Quick Start

```bash
# Start the backend
cd backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Default credentials
Username: admin
Password: admin123

# Get token and test
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.data.access_token')

curl http://localhost:8000/api/v1/admin/users/me \
  -H "Authorization: Bearer $TOKEN"
```

---

## Contract Files

| File | Description | Base URL |
|------|-------------|----------|
| [00_setup_guide.md](00_setup_guide.md) | **Deployment & Setup** (Local + Production) | - |
| [01_fastapi_core.md](01_fastapi_core.md) | Authentication, Users, Roles, Departments, OAuth2, Email | `/api/v1` |
| [02_agent_system.md](02_agent_system.md) | Chat Streaming, Credits, MCP, RAG, Generation, TTS | `/api/v1/agent` |
| [03_sandbox.md](03_sandbox.md) | Sandbox Lifecycle, Commands, Files, Ports | `/api/v1/agent/sandboxes` |
| [04_slides.md](04_slides.md) | Presentations, Slides, PDF Export | `/api/v1/agent/slides` |
| [05_additional_system.md](05_additional_system.md) | Logs, Monitors, Tasks, Dict, Notice, Code Gen | `/api/v1` |
| [06_tool_server.md](06_tool_server.md) | MCP Tool Server (50+ tools) | `http://localhost:6060` |

---

## API Overview

```
/api/v1/
├── auth/                    # Authentication
│   ├── login               # POST - Get JWT tokens
│   ├── logout              # POST - Invalidate session
│   └── refresh             # POST - Refresh access token
│
├── admin/                   # Admin Management
│   ├── users/              # User CRUD
│   ├── roles/              # Role CRUD
│   ├── depts/              # Department CRUD
│   └── menus/              # Menu/Permission CRUD
│
├── oauth2/                  # Social Login
│   ├── github/             # GitHub OAuth
│   ├── google/             # Google OAuth
│   └── linux-do/           # Linux.do OAuth
│
├── email/                   # Email Plugin
│   └── captcha             # POST - Send verification
│
├── config/                  # System Configuration
│
└── agent/                   # AI Agent System
    ├── chat/stream         # POST - SSE streaming chat
    ├── credits/            # Balance & usage
    ├── config              # GET - Agent config
    ├── mcp/                # MCP server tools
    ├── rag/                # RAG resources
    ├── generation/         # Podcast, PPT, Prose
    ├── tts/                # Text-to-speech
    ├── sandboxes/          # Sandbox management
    └── slides/             # Presentation management
```

---

## Authentication

All protected endpoints require:

```
Authorization: Bearer <access_token>
```

**Token Lifecycle:**
- Access Token: 24 hours
- Refresh Token: 7 days

---

## Response Format

```json
{
  "code": 200,
  "msg": "Success",
  "data": { ... }
}
```

---

## Interactive Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
