# MCP Settings API

API endpoints for configuring MCP tools (Codex, Claude Code, custom servers).

## Base Path
```
/api/v1/agent/user-settings/mcp
```

---

## Endpoints

### List All MCP Settings
```http
GET /user-settings/mcp
Authorization: Bearer <token>
```

**Response:**
```json
{
  "settings": [
    {
      "id": 1,
      "user_id": 123,
      "tool_type": "codex",
      "mcp_config": {...},
      "is_active": true,
      "created_time": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

### Configure Codex
```http
POST /user-settings/mcp/codex
Authorization: Bearer <token>
Content-Type: application/json

{
  "auth_json": {"OPENAI_API_KEY": "sk-..."},
  "apikey": "sk-...",
  "model": "gpt-4o",
  "model_reasoning_effort": "medium",
  "search": false
}
```

**Notes:**
- Provide either `auth_json` OR `apikey` (not both required)
- `model_reasoning_effort`: "low", "medium", "high"
- `search`: Enable web search capability

---

### Configure Claude Code

Claude Code uses OAuth with PKCE. The flow is:

1. Frontend generates PKCE verifier and opens OAuth URL
2. User authorizes in browser
3. User copies authorization code
4. Frontend sends `code#verifier` to backend
5. Backend exchanges for tokens

```http
POST /user-settings/mcp/claude-code
Authorization: Bearer <token>
Content-Type: application/json

{
  "authorization_code": "abc123#verifier456"
}
```

**OAuth URL Construction (Frontend):**
```typescript
const oauthParams = new URLSearchParams({
  code: 'true',
  client_id: '9d1c250a-e61b-44d9-88ed-5944d1962f5e',
  response_type: 'code',
  redirect_uri: 'https://console.anthropic.com/oauth/code/callback',
  scope: 'org:create_api_key user:profile user:inference',
  code_challenge: codeChallenge,  // SHA256 of verifier, base64url encoded
  code_challenge_method: 'S256',
  state: codeVerifier
})

window.open(`https://claude.ai/oauth/authorize?${oauthParams}`, '_blank')
```

---

### Configure Custom MCP Server
```http
POST /user-settings/mcp/custom
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "my-mcp-server",
  "command": "npx",
  "args": ["-y", "@my/mcp-server"],
  "transport": "stdio",
  "env": {"API_KEY": "..."}
}
```

---

### Delete MCP Setting
```http
DELETE /user-settings/mcp/{tool_type}
Authorization: Bearer <token>
```

**Example:** `DELETE /user-settings/mcp/codex`

---

### Toggle Active Status
```http
PATCH /user-settings/mcp/{tool_type}/toggle?is_active=true
Authorization: Bearer <token>
```

---

## TypeScript Service Example

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1/agent',
  headers: { 'Content-Type': 'application/json' }
})

export const settingsService = {
  async getMcpSettings() {
    const { data } = await api.get('/user-settings/mcp')
    return data.settings
  },

  async configureCodex(payload: {
    apikey?: string
    model?: string
    model_reasoning_effort?: string
    search?: boolean
  }) {
    return api.post('/user-settings/mcp/codex', payload)
  },

  async configureClaudeCode(payload: { authorization_code: string }) {
    return api.post('/user-settings/mcp/claude-code', payload)
  },

  async deleteMcpSetting(toolType: string) {
    return api.delete(`/user-settings/mcp/${toolType}`)
  }
}
```
