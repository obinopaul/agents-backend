# API Contracts

This directory contains detailed documentation for all FastAPI endpoints in the Agents Backend.

## Overview

The Agents Backend provides two entry points:

| Entry Point | Purpose | Access |
|-------------|---------|--------|
| **FBA CLI** | Local prototyping & testing | Command-line (`fba agent`, `fba run`) |
| **FastAPI Server** | Production deployment | HTTP API (`POST /api/v1/...`) |

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTS BACKEND                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        FBA CLI (cli.py)                              │   │
│   │   Local command-line tool for testing and prototyping               │   │
│   │                                                                      │   │
│   │   $ fba run      → Start FastAPI server                             │   │
│   │   $ fba agent    → Run Deep Research Agent directly                 │   │
│   │   $ fba init     → Initialize database                              │   │
│   │   $ fba celery   → Start background workers                         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                   ┌────────────────┴────────────────┐                       │
│                   ▼                                 ▼                        │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │     FastAPI Server            │   │    workflow.py (Direct)       │    │
│   │   (Production API)            │   │   (CLI Testing Only)          │    │
│   │                               │   │                               │    │
│   │   POST /api/v1/agent/chat     │   │   run_agent_workflow_async()  │    │
│   │   POST /api/v1/agent/sandbox  │   │   No server needed            │    │
│   │   POST /api/v1/agent/rag      │   │                               │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                   │                                 │                       │
│                   └────────────────┬────────────────┘                       │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    LangGraph Agent (builder.py)                     │   │
│   │         coordinator → planner → researcher → reporter               │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## FBA CLI Commands

The CLI is powered by the `cappa` library and defined in [`backend/cli.py`](../../backend/cli.py).

| Command | Description | Usage |
|---------|-------------|-------|
| `fba run` | Start FastAPI HTTP server | `fba run --host 0.0.0.0 --port 8000` |
| `fba run --no-reload` | Production mode with workers | `fba run --no-reload --workers 4` |
| `fba init` | Initialize DB (drop & recreate tables) | `fba init` |
| `fba agent` | Run Deep Research Agent in terminal | `fba agent --debug` |
| `fba agent --max-step-num N` | Limit steps per plan | `fba agent --max-step-num 5` |
| `fba agent --enable-clarification` | Enable Q&A mode | `fba agent --enable-clarification` |
| `fba celery worker` | Start Celery worker | `fba celery worker -l info` |
| `fba celery beat` | Start Celery scheduler | `fba celery beat` |
| `fba celery flower` | Start Celery monitor UI | `fba celery flower --port 8555` |
| `fba codegen` | Generate CRUD code | `fba codegen` |
| `fba --sql <path>` | Execute SQL script | `fba --sql ./scripts/init.sql` |

## FastAPI Endpoints

When running `fba run`, the following endpoints become available:

### Agent Module (`/api/v1/agent`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/stream` | POST | Streaming multi-agent chat (SSE) |
| `/agent/stream` | POST | **Agent with sandbox tools (SSE)** |
| `/chat/models` | GET | List available LLM models |
| `/sandbox/create` | POST | Create sandbox instance |
| `/sandbox/{id}/status` | GET | Get sandbox status |
| `/sandbox/run-cmd` | POST | Execute shell command |
| `/rag/upload` | POST | Upload documents for RAG |
| `/rag/query` | POST | Query knowledge base |
| `/mcp/servers` | GET | List MCP servers |
| `/tts` | POST | Text-to-speech |

📖 See individual endpoint documentation:
- [Agent API (with Sandbox)](./agent-api.md)
- [Billing API](./billing-api.md)
- [Chat API](./chat-api.md)
- [Sandbox API](./sandbox-api.md)
- [RAG API](./rag-api.md)


### Admin Module (`/api/v1/admin`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | User authentication |
| `/auth/logout` | POST | Invalidate tokens |
| `/sys/users` | CRUD | User management |
| `/sys/roles` | CRUD | Role-based access control |
| `/monitor/server` | GET | Server metrics |

## Data Flow: CLI vs FastAPI

### When using `fba agent` (CLI mode):
```
User Input → cli.py Agent command
           → workflow.py run_agent_workflow_async()
           → builder.py build_graph()
           → Graph executes
           → Output printed to terminal
```

### When using FastAPI (`fba run`):
```
HTTP POST /api/v1/agent/chat/stream
           → chat.py endpoint handler
           → builder.py build_graph_with_memory()
           → Graph executes with checkpointing
           → SSE stream returned to client
           → checkpoint.py saves messages to DB
```

## Checkpointing

Two checkpointing systems exist:

| System | Purpose | Storage |
|--------|---------|---------|
| **LangGraph Checkpointer** | Save graph state for resume | PostgreSQL / MongoDB |
| **ChatStreamManager** | Save all streaming messages | PostgreSQL / MongoDB |

Settings:
- `LANGGRAPH_CHECKPOINT_ENABLED`: Enable LangGraph checkpointing
- `LANGGRAPH_CHECKPOINT_SAVER`: Enable message stream saving
- `LANGGRAPH_CHECKPOINT_DB_URL`: Database connection URL
