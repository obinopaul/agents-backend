# Backend Documentation

> Comprehensive documentation for the `backend/` directory.

---

## Directory Structure

```
backend/
│
├── main.py                               # Application entry point
├── cli.py                                # Command-line interface
├── run.py                                # Uvicorn server runner
│
├── core/                                 # Core configuration
│   ├── conf.py                           # Global settings (299 config options)
│   ├── registrar.py                      # FastAPI app registration
│   └── path_conf.py                      # Path constants
│
├── database/                             # Database layer
│   ├── db.py                             # Async SQLAlchemy engine
│   └── redis.py                          # Redis client
│
├── common/                               # Shared utilities
│   ├── model.py                          # Base SQLAlchemy models
│   ├── schema.py                         # Base Pydantic schemas
│   ├── security/                         # JWT, RBAC, permissions
│   ├── exception/                        # Exception handling
│   └── response/                         # Response formatting
│
├── app/                                  # Application modules
│   ├── router.py                         # Main router
│   ├── admin/                            # Admin module (users, roles, menus)
│   ├── agent/                            # Agent module (NEW)
│   │   ├── api/v1/                       # Agent endpoints
│   │   │   ├── chat.py                   # Streaming chat
│   │   │   ├── generation.py             # Podcast, PPT, prose
│   │   │   ├── sandbox.py                # Sandbox management
│   │   │   ├── mcp.py                    # MCP servers
│   │   │   ├── mcp_settings.py           # User MCP configs
│   │   │   ├── rag.py                    # RAG resources
│   │   │   ├── tts.py                    # Text-to-speech
│   │   │   ├── credits.py                # Credit balance
│   │   │   └── config.py                 # Agent config
│   │   ├── model/                        # Database models
│   │   ├── schema/                       # Pydantic schemas
│   │   ├── service/                      # Business logic
│   │   └── crud/                         # CRUD operations
│   └── task/                             # Celery tasks
│
├── middleware/                           # HTTP middleware
│   ├── jwt_auth_middleware.py            # JWT authentication
│   ├── access_middleware.py              # Request logging
│   └── opera_log_middleware.py           # Audit logging
│
├── plugin/                               # Plugin system
│   ├── oauth2/                           # GitHub, Google OAuth
│   ├── code_generator/                   # Code generation
│   ├── email/                            # Email sending
│   └── ...
│
├── src/                                  # Agentic AI System (NEW)
│   ├── graph/                            # LangGraph workflow
│   ├── tool_server/                      # MCP tool server (44+ tools)
│   ├── sandbox/                          # Sandbox providers
│   ├── rag/                              # RAG retrieval
│   ├── llms/                             # LLM configuration
│   ├── prompts/                          # Prompt templates
│   ├── agents/                           # Agent implementations
│   ├── agent_template/                   # Reusable agent template
│   ├── module/                           # Feature modules
│   ├── ptc/                              # Programmatic Tool Calling
│   └── services/                         # Shared services
│
├── utils/                                # Utilities
├── alembic/                              # Database migrations
├── locale/                               # i18n translations
└── scripts/                              # Dev scripts
```

---

## Key Module Documentation

| Module | Description | Documentation |
|--------|-------------|---------------|
| **core/** | Settings, app factory | [Core](./core/README.md) |
| **database/** | SQLAlchemy, Redis | [Database](./database/README.md) |
| **common/** | Utilities, security | [Common](./common/README.md) |
| **app/admin/** | Users, roles, auth | [Admin](./app/admin/README.md) |
| **app/agent/** | AI agent APIs | [Agent](./app/agent/README.md) |
| **middleware/** | HTTP processing | [Middleware](./middleware/README.md) |
| **plugin/** | Extensions | [Plugin](./plugin/README.md) |
| **src/** | AI system | [Src](./src/README.md) |
| **alembic/** | Migrations | [Alembic](./alembic/README.md) |

---

## NEW: `backend/src/` (Agentic AI System)

This is the core AI functionality:

### LangGraph (`src/graph/`)
- **builder.py** - Builds the multi-agent workflow
- **nodes.py** - Agent nodes (investigator, coder, reporter)
- **state.py** - Workflow state definition

### Tool Server (`src/tool_server/`)
- **mcp/** - MCP server and client
- **tools/** - 44+ tools (shell, file, browser, web, media)
- **integrations/** - Web visit, search, etc.

### Sandbox (`src/sandbox/`)
- **sandbox_server/** - Sandbox management service
- **sandboxes/** - E2B, Daytona providers
- **agent_infra_sandbox/** - DeepAgents CLI

### RAG (`src/rag/`)
- **retriever.py** - Document retrieval
- **embeddings/** - Vector embeddings

### Other Modules
| Module | Purpose |
|--------|---------|
| `agents/` | Agent implementations |
| `agent_template/` | Reusable agent template |
| `module/` | Feature modules (podcast, prose, slides) |
| `prompts/` | Prompt templates |
| `llms/` | LLM configuration |
| `ptc/` | Programmatic Tool Calling |

---

## NEW: `backend/app/agent/` Module

The agent module provides API endpoints for AI features:

### Endpoints
| File | Prefix | Purpose |
|------|--------|---------|
| `chat.py` | `/chat` | Streaming chat |
| `generation.py` | `/generation` | Podcast, PPT, prose |
| `sandbox.py` | `/sandboxes` | Sandbox management |
| `mcp.py` | `/mcp` | MCP server management |
| `mcp_settings.py` | `/user-settings/mcp` | User MCP configs |
| `rag.py` | `/rag` | RAG resources |
| `tts.py` | `/tts` | Text-to-speech |
| `credits.py` | `/credits` | Credit balance |

### Database Models
| Model | Table | Purpose |
|-------|-------|---------|
| APIKey | `agent_api_keys` | Tool server auth |
| SessionMetrics | `agent_session_metrics` | Usage tracking |
| MCPSetting | `agent_mcp_settings` | User MCP configs |

---

## Application Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATION STARTUP                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│ Plugin        │        │ FastAPI       │        │ Middleware    │
│ Discovery     │        │ Creation      │        │ Registration  │
└───────────────┘        └───────────────┘        └───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │     LIFESPAN: STARTUP    │
                    ├─────────────────────────┤
                    │ 1. Create database tables│
                    │ 2. Open Redis connection │
                    │ 3. Initialize rate limiter│
                    │ 4. Initialize Snowflake  │
                    └─────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │    SERVER RUNNING        │
                    └─────────────────────────┘
```

---

## 3-Tier Architecture Pattern

Each module follows:

```
module_name/
├── api/v1/             # REST endpoints
├── schema/              # Pydantic schemas
├── service/             # Business logic
├── crud/                # Database operations
└── model/               # SQLAlchemy models
```

---

## Quick Reference

| Goal | Files to Edit |
|------|---------------|
| Add API endpoint | `app/*/api/v1/` |
| Add database model | `app/*/model/` |
| Add agent tool | `src/tool_server/tools/` |
| Add LangGraph node | `src/graph/nodes.py` |
| Add MCP server | `src/tool_server/mcp_integrations/` |
| Add sandbox provider | `src/sandbox/sandbox_server/sandboxes/` |

---

## Related Documentation

- [Lifecycle Docs](../lifecycle/README.md) - Visual workflows
- [API Endpoints](../api-contracts/api-endpoints.md) - All endpoints
- [Database Schema](../api-contracts/database.md) - All tables
- [MCP Configuration](../mcp-configuration.md) - Tool server
- [Sandbox Tools](../sandbox-tools.md) - 44+ tools
