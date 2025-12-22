# Agent System API Contracts

> **Base URL:** `http://localhost:8000/api/v1/agent`
>
> All endpoints require `Authorization: Bearer <token>` header.

---

## Table of Contents

1. [Chat Streaming](#1-chat-streaming)
2. [Credits](#2-credits)
3. [MCP (Model Context Protocol)](#3-mcp-model-context-protocol)
4. [RAG (Retrieval Augmented Generation)](#4-rag-retrieval-augmented-generation)
5. [Content Generation](#5-content-generation)
6. [Text-to-Speech](#6-text-to-speech)
7. [Agent Configuration](#7-agent-configuration)

---

## 1. Chat Streaming

Real-time AI agent conversations using Server-Sent Events (SSE).

### POST `/chat/stream`

Stream AI agent responses in real-time.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
Accept: text/event-stream
```

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Research the latest AI developments"}
  ],
  "thread_id": "unique-conversation-id",
  "model_name": "gpt-4o",
  "resources": [],
  "enable_web_search": true,
  "report_style": "ACADEMIC",
  "enable_deep_thinking": false,
  "enable_clarification": false,
  "max_clarification_rounds": 0,
  "locale": "en-US",
  "mcp_settings": {
    "servers": {
      "my-mcp-server": {
        "transport": "stdio",
        "command": "npx",
        "args": ["my-mcp-tool"],
        "enabled_tools": ["tool1", "tool2"]
      }
    }
  },
  "interrupt_before_tools": []
}
```

**Request Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `messages` | array | ✅ | - | Chat history with role (user/assistant/system) and content |
| `thread_id` | string | ❌ | `__default__` | Conversation thread ID for persistence |
| `resources` | array | ❌ | `[]` | RAG resources to include |
| `max_plan_iterations` | int | ❌ | `1` | Max iterations for planning (1-10) |
| `max_step_num` | int | ❌ | `3` | Max steps per plan (1-10) |
| `max_search_results` | int | ❌ | `3` | Max search results to return (1-20) |
| `auto_accepted_plan` | bool | ❌ | `true` | Auto-accept generated plans |
| `interrupt_feedback` | string | ❌ | `null` | Feedback when resuming interrupted workflows |
| `mcp_settings` | object | ❌ | `null` | MCP server configurations |
| `enable_background_investigation` | bool | ❌ | `true` | Enable background web research |
| `enable_web_search` | bool | ❌ | `true` | Enable web search in research steps |
| `report_style` | string | ❌ | `ACADEMIC` | Output style: ACADEMIC, NEWS, SOCIAL_MEDIA, POPULAR_SCIENCE, STRATEGIC_INVESTMENT |
| `enable_deep_thinking` | bool | ❌ | `false` | Enable extended reasoning mode |
| `enable_clarification` | bool | ❌ | `false` | Enable clarifying questions |
| `max_clarification_rounds` | int | ❌ | `3` | Max clarification rounds (1-10) |
| `locale` | string | ❌ | `en-US` | Language locale |
| `interrupt_before_tools` | array | ❌ | `null` | Tools requiring user confirmation before execution |

**SSE Response Stream:**

```
event: message
data: {"type": "agent", "agent": "coordinator", "content": "Processing request..."}

event: message
data: {"type": "agent", "agent": "researcher", "content": "Searching for information..."}

event: message
data: {"type": "tool_call", "tool": "tavily_search", "args": {"query": "AI developments 2024"}}

event: message
data: {"type": "tool_result", "tool": "tavily_search", "result": "Found 5 articles..."}

event: message
data: {"type": "agent", "agent": "reporter", "content": "# AI Developments\n\n..."}

event: done
data: {"status": "complete", "thread_id": "abc123"}
```

**Multi-Agent Workflow:**

```
┌─────────────┐    ┌────────────┐    ┌─────────────┐
│ Coordinator │───►│ Researcher │───►│   Analyst   │
└─────────────┘    └────────────┘    └─────────────┘
                          │                  │
                          ▼                  ▼
                   ┌────────────┐    ┌─────────────┐
                   │   Coder    │    │  Reporter   │
                   └────────────┘    └─────────────┘
```

**JavaScript Client Example:**

```javascript
async function streamChat(messages, token) {
  const response = await fetch('/api/v1/agent/chat/stream', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({
      messages,
      enable_web_search: true,
      model_name: 'gpt-4o',
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        console.log(data.agent, ':', data.content);
      }
    }
  }
}
```

---

## 2. Credits

Track and manage user AI usage credits.

### GET `/credits/balance`

Get current user's credit balance.

**Response:**
```json
{
  "credits": 100.0,
  "bonus_credits": 10.0,
  "total_available": 110.0
}
```

---

### GET `/credits/usage`

Get credit usage history with pagination.

**Query:** `?page=1&per_page=20`

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "abc123",
      "session_title": "Research on AI",
      "credits": 2.5,
      "updated_at": "2024-12-21T10:00:00Z"
    }
  ],
  "total": 15
}
```

---

## 3. MCP (Model Context Protocol)

Dynamically load tools from MCP-compatible servers.

### POST `/mcp/server/metadata`

Connect to an MCP server and retrieve available tools.

**Requires:** `AGENT_MCP_ENABLED=true` in settings.

**Request (stdio transport):**
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-filesystem"],
  "env": {"HOME": "/home/user"},
  "timeout_seconds": 300
}
```

**Request (http transport):**
```json
{
  "transport": "http",
  "url": "https://mcp-server.example.com",
  "headers": {"Authorization": "Bearer api_key"},
  "timeout_seconds": 300
}
```

**Response:**
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-filesystem"],
  "env": {"HOME": "/home/user"},
  "headers": null,
  "tools": [
    {
      "name": "read_file",
      "description": "Read contents of a file",
      "input_schema": {
        "type": "object",
        "properties": {
          "path": {"type": "string"}
        },
        "required": ["path"]
      }
    },
    {
      "name": "write_file",
      "description": "Write contents to a file",
      "input_schema": {...}
    }
  ]
}
```

---

## 4. RAG (Retrieval Augmented Generation)

Manage knowledge base resources.

### GET `/rag/config`

Get current RAG provider configuration.

**Response:**
```json
{
  "provider": "milvus"
}
```

**Provider options:** `milvus`, `qdrant`, or empty string (disabled)

---

### GET `/rag/resources`

List available RAG resources.

**Query:** `?query=AI+research`

**Response:**
```json
{
  "resources": [
    {
      "id": "doc-123",
      "title": "AI Research Papers",
      "description": "Collection of AI papers",
      "type": "document"
    }
  ]
}
```

---

## 5. Content Generation

AI-powered content transformation.

### POST `/generation/podcast/generate`

Convert text report to podcast audio.

**Request:**
```json
{
  "content": "# Research Report\n\nThis report covers..."
}
```

**Response:** MP3 audio file

---

### POST `/generation/ppt/generate`

Generate presentation slides from content.

**Request:**
```json
{
  "content": "# Presentation Topic\n\nKey points...",
  "locale": "en-US"
}
```

**Response:** PPTX file download

**Headers:** `Content-Disposition: attachment; filename=presentation.pptx`

---

### POST `/generation/prose/generate`

AI writing assistance.

**Request:**
```json
{
  "prompt": "The impact of AI on healthcare...",
  "option": "continue",
  "command": ""
}
```

**Options:**
| Option | Description |
|--------|-------------|
| `continue` | Continue writing from prompt |
| `improve` | Improve the text quality |
| `fix` | Fix grammar and spelling |
| `shorter` | Make text more concise |
| `longer` | Expand on the content |
| `zap` | Complete rewrite |

**Response:** Streaming text

---

### POST `/generation/prompt/enhance`

Enhance a user prompt for better results.

**Request:**
```json
{
  "prompt": "tell me about AI",
  "context": "For a research paper",
  "report_style": "ACADEMIC"
}
```

**Response:**
```json
{
  "result": "Provide a comprehensive analysis of artificial intelligence, including its current state, key developments, applications across industries, ethical considerations, and future trajectory. Focus on peer-reviewed sources and include specific examples."
}
```

---

## 6. Text-to-Speech

Convert text to audio using Volcengine TTS.

### POST `/tts/tts`

Synthesize text to speech.

**Request:**
```json
{
  "text": "Hello, welcome to our platform!",
  "encoding": "mp3",
  "speed_ratio": 1.0,
  "volume_ratio": 1.0,
  "pitch_ratio": 1.0,
  "text_type": "plain",
  "with_frontend": 1,
  "frontend_type": "unitTson"
}
```

**Response:** Audio file (MP3 or WAV)

**Configuration (.env):**
```env
VOLCENGINE_TTS_APPID=your_app_id
VOLCENGINE_TTS_ACCESS_TOKEN=your_access_token
VOLCENGINE_TTS_CLUSTER=volcano_tts
VOLCENGINE_TTS_VOICE_TYPE=zh_female_tianmei
```

---

## 7. Agent Configuration

Get agent system settings.

### GET `/config`

Get complete agent configuration.

**Response:**
```json
{
  "rag": {
    "provider": "milvus"
  },
  "models": [
    {
      "name": "GPT-4o",
      "provider": "openai",
      "model_id": "gpt-4o",
      "is_default": true
    },
    {
      "name": "Claude 3 Sonnet",
      "provider": "anthropic",
      "model_id": "claude-3-sonnet-20240229",
      "is_default": false
    }
  ],
  "recursion_limit": 100,
  "mcp_enabled": true,
  "deep_thinking_enabled": true,
  "clarification_enabled": true,
  "default_report_style": "ACADEMIC"
}
```

---

## Environment Variables

```env
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Agent Settings
AGENT_RECURSION_LIMIT=100
AGENT_MCP_ENABLED=true
AGENT_MCP_TIMEOUT_SECONDS=300
AGENT_ENABLE_DEEP_THINKING=true
AGENT_ENABLE_CLARIFICATION=true
AGENT_DEFAULT_REPORT_STYLE=ACADEMIC

# RAG
AGENT_RAG_PROVIDER=milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Search
TAVILY_API_KEY=tvly-...

# TTS
VOLCENGINE_TTS_APPID=...
VOLCENGINE_TTS_ACCESS_TOKEN=...
```

---

## Quick Test Commands

```bash
# Stream a chat
curl -N -X POST http://localhost:8000/api/v1/agent/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello, world!"}]}'

# Check credits
curl http://localhost:8000/api/v1/agent/credits/balance \
  -H "Authorization: Bearer $TOKEN"

# Get agent config
curl http://localhost:8000/api/v1/agent/config \
  -H "Authorization: Bearer $TOKEN"
```
