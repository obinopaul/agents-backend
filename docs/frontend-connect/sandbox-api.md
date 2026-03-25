# Sandbox API

API endpoints for managing code execution sandboxes.

## Base Path
```
/api/v1/agent/sandboxes
```

---

## Endpoints

### Create Sandbox
```http
POST /sandboxes
Authorization: Bearer <token>
Content-Type: application/json

{
  "template_id": "agents-backend-sandbox"
}
```

**Response:**
```json
{
  "sandbox_id": "sbx_abc123",
  "status": "running",
  "url": "https://sandbox.e2b.dev/sbx_abc123",
  "ports": {
    "mcp_server": 6060,
    "code_server": 9000
  }
}
```

---

### Get Sandbox Status
```http
GET /sandboxes/{sandbox_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "sandbox_id": "sbx_abc123",
  "status": "running",
  "created_at": "2025-01-01T00:00:00Z",
  "user_id": "user_123"
}
```

---

### Run Command
```http
POST /sandboxes/{sandbox_id}/commands
Authorization: Bearer <token>
Content-Type: application/json

{
  "command": "npm run build",
  "background": false
}
```

**Response:**
```json
{
  "stdout": "Build completed successfully",
  "stderr": "",
  "exit_code": 0
}
```

---

### File Operations

**Write File:**
```http
POST /sandboxes/{sandbox_id}/files
Authorization: Bearer <token>
Content-Type: application/json

{
  "path": "/workspace/index.js",
  "content": "console.log('hello')"
}
```

**Read File:**
```http
GET /sandboxes/{sandbox_id}/files?path=/workspace/index.js
Authorization: Bearer <token>
```

---

### Delete Sandbox
```http
DELETE /sandboxes/{sandbox_id}
Authorization: Bearer <token>
```

---

## TypeScript Service Example

```typescript
const sandboxService = {
  async createSandbox(templateId?: string) {
    const { data } = await api.post('/sandboxes', { template_id: templateId })
    return data
  },

  async runCommand(sandboxId: string, command: string, background = false) {
    const { data } = await api.post(`/sandboxes/${sandboxId}/commands`, {
      command,
      background
    })
    return data
  },

  async writeFile(sandboxId: string, path: string, content: string) {
    return api.post(`/sandboxes/${sandboxId}/files`, { path, content })
  },

  async deleteSandbox(sandboxId: string) {
    return api.delete(`/sandboxes/${sandboxId}`)
  }
}
```

---

## Sandbox Architecture

```
┌─────────────────────────────────────────┐
│              E2B Sandbox                │
├─────────────────────────────────────────┤
│  Port 6060: MCP Tool Server             │
│  Port 9000: Code Server (VS Code)       │
│                                         │
│  /workspace   - Project files           │
│  /home/pn     - User home               │
│    ├── .claude/.credentials.json        │
│    └── .codex/auth.json                 │
└─────────────────────────────────────────┘
```

When a sandbox is created, the backend automatically writes:
- Claude Code credentials (if configured)
- Codex authentication (if configured)
