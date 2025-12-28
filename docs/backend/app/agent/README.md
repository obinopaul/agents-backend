# Agent Module (`app/agent/`)

> AI agent APIs for chat, generation, sandbox, and more.

---

## Overview

The agent module provides REST APIs for AI functionality:

| Endpoint Group | Purpose |
|----------------|---------|
| `/chat/stream` | Streaming AI chat |
| `/generation/*` | Content generation |
| `/sandboxes/*` | Sandbox management |
| `/mcp/*` | MCP server management |
| `/user-settings/mcp/*` | User MCP configs |
| `/rag/*` | RAG resources |
| `/tts/*` | Text-to-speech |
| `/credits/*` | Credit balance |

---

## Directory Structure

```
app/agent/
├── api/
│   ├── router.py          # v1 router aggregation
│   └── v1/
│       ├── chat.py        # Streaming chat endpoint
│       ├── generation.py  # Podcast, PPT, prose
│       ├── sandbox.py     # Sandbox CRUD
│       ├── mcp.py         # MCP server management
│       ├── mcp_settings.py # User MCP configs
│       ├── rag.py         # RAG resources
│       ├── tts.py         # Text-to-speech
│       ├── credits.py     # Credit balance
│       ├── config.py      # Agent configuration
│       └── slides.py      # Slide management
│
├── model/
│   ├── __init__.py
│   ├── agent_models.py    # APIKey, SessionMetrics
│   └── mcp_setting.py     # MCPSetting
│
├── schema/
│   └── mcp_setting.py     # Pydantic schemas
│
├── crud/
│   └── crud_mcp_setting.py # CRUD operations
│
└── service/
    └── mcp_setting_service.py # Business logic
```

---

## Database Models

### `agent_api_keys`
API keys for tool server authentication.

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT | Primary key |
| `user_id` | BIGINT | Owner |
| `api_key` | VARCHAR(256) | sk_... token |
| `name` | VARCHAR(128) | Label |
| `is_active` | BOOLEAN | Active status |

### `agent_session_metrics`
Usage tracking per chat session.

| Column | Type | Description |
|--------|------|-------------|
| `session_id` | VARCHAR(64) | Chat session |
| `user_id` | BIGINT | Owner |
| `credits` | FLOAT | Credits used |
| `total_prompt_tokens` | INT | Input tokens |
| `total_completion_tokens` | INT | Output tokens |

### `agent_mcp_settings`
User MCP tool configurations.

| Column | Type | Description |
|--------|------|-------------|
| `tool_type` | VARCHAR(64) | codex, claude_code, custom:... |
| `mcp_config` | JSONB | MCP server config |
| `auth_json` | JSONB | Credentials |
| `is_active` | BOOLEAN | Enabled |

---

## Key Endpoints

### Chat Stream
```http
POST /api/v1/agent/chat/stream
```
Streams AI responses using Server-Sent Events.

### Generate Podcast
```http
POST /api/v1/agent/generation/podcast
```
Converts text to podcast audio.

### Create Sandbox
```http
POST /api/v1/agent/sandboxes
```
Creates isolated execution environment.

### Configure Codex
```http
POST /api/v1/agent/user-settings/mcp/codex
```
Saves Codex API key for sandbox use.

---

## Related Documentation

- [API Endpoints](../../api-contracts/api-endpoints.md) - Full reference
- [Agent Chat Lifecycle](../../lifecycle/agent-chat.md)
- [Sandbox Lifecycle](../../lifecycle/sandbox.md)
- [MCP User Settings](../../lifecycle/mcp-user-settings.md)
