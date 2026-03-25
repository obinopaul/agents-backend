# Agent System Documentation

The Agents Backend integrates a powerful LangChain/LangGraph-based agent system into the main FastAPI application. This system supports advanced capabilities like streaming chat, multi-agent workflows, content generation (podcasts, presentations), and more.

## Architecture

The agent system is built as a modular component within the `backend/app/agent` directory, fully integrated with the main application's infrastructure:

- **Router**: `backend/app/agent/api/router.py` exposes all endpoints under `/api/v1/agent`.
- **Authentication**: Uses the main project's JWT authentication (`DependsJwtAuth`).
- **Configuration**: Centralized in `backend/core/conf.py` (Pydantic settings) and `.env`.
- **Database**: Uses the main async PostgreSQL connection for LangGraph checkpointing (memory).
- **Workflows**: Defined in `backend/src/graph` using LangGraph state machines.

## Features

### 1. Streaming Chat (`/api/v1/agent/chat/stream`)
Real-time conversational AI with:
- **Server-Sent Events (SSE)**: Streams tokens, tool calls, and thoughts in real-time.
- **Multi-Agent Coordination**: Planner, Researcher, Coder, and Reviewer agents working together.
- **Deep Thinking**: Optional "reasoning" step for complex queries.
- **Web Search**: Integration with Tavily and other search providers.
- **Memory**: Conversation persistence via thread IDs.

### 2. Content Generation
- **Podcasts** (`/generation/podcast/generate`): Converts text reports into multi-speaker audio scripts and MP3s.
- **Presentations** (`/generation/ppt/generate`): Generates PowerPoint (.pptx) slides from content.
- **Prose** (`/generation/prose/generate`): AI writing assistant for editing, expansion, and fixing text.
- **Prompt Enhancement** (`/generation/prompt/enhance`): Optimizes user prompts for better LLM performance.

### 3. Text-to-Speech (TTS)
- Integration with **Volcengine TTS** for high-quality speech synthesis.

### 4. RAG (Retrieval Augmented Generation)
- Configurable support for **Milvus** or **Qdrant** vector databases.
- Endpoints to manage and query knowledge base resources.

### 5. MCP (Model Context Protocol)
- Support for connecting to MCP servers to dynamically load tools.

## Configuration

To enable these features, configure the following in your `.env` file:

### LLM Providers (Required)
```ini
# At least one provider is required
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
# ... other supported providers (Google, Azure, etc.)
```

### Agent Settings
```ini
AGENT_RECURSION_LIMIT=50             # Max steps in a workflow
AGENT_ENABLE_DEEP_THINKING=true      # Enable reasoning capability
AGENT_ENABLE_WEB_SEARCH=true         # Enable web access
AGENT_MCP_ENABLED=false              # Enable/disable MCP
AGENT_RAG_PROVIDER=milvus            # 'milvus', 'qdrant', or empty
```

### Search & Services (Optional)
```ini
TAVILY_API_KEY=tvly-...              # For web search
VOLCENGINE_TTS_APPID=...             # For TTS
VOLCENGINE_TTS_ACCESS_TOKEN=...
```

## Deployment Architecture

The Agent System is designed as a **modular monolith** integration, meaning it runs **inside the main application process**.

### ❌ No Separate Container
You do **not** need a separate Docker container for the agent. It is NOT a microservice.

### ✅ Unified Runtime
- **Process**: The agent code runs within the same `uvicorn` / `gunicorn` process as your main FastAPI backend.
- **Container**: In Docker, it runs inside the `fba_server` container defined in `docker-compose.yml`.
- **Scaling**: When you scale the `fba_server` container (e.g., `docker-compose up --scale fba_server=3`), you automatically scale the agent capacity.

### Integration Points
1.  **Router**: Agent endpoints (`/api/v1/agent/*`) are registered directly to the main FastAPI `app` instance.
2.  **Dependencies**: Agent libraries (`langchain`, `numpy`, etc.) are installed in the same Python environment as the main app.
3.  **Memory**: Agent state is stored in the **shared PostgreSQL database** (configurable) used by the main app, ensuring state persistence across container restarts.

## Usage Examples

### Streaming Chat (Python Client)

```python
import requests
import json

url = "http://localhost:8000/api/v1/agent/chat/stream"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "messages": [{"role": "user", "content": "Research the latest advancements in solid state batteries."}],
    "thread_id": "unique-conversation-id",
    "enable_web_search": True
}

with requests.post(url, headers=headers, json=data, stream=True) as response:
    for line in response.iter_lines():
        if line:
            print(line.decode('utf-8'))
```

### Generating a Podcast

```bash
curl -X POST "http://localhost:8000/api/v1/agent/generation/podcast/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Full text report content..."}' \
  --output podcast.mp3
```

## Docker Deployment

The agent system runs within the main `fba_server` container. No separate container is needed.
Ensure your `.env` file with API keys is mounted correctly as described in the [Getting Started](getting-started.md) guide.

```bash
# Rebuild to install new agent dependencies
docker-compose up -d --build
```
