<div align="center">

<img alt="Agents Backend Logo" width="320" src="https://wu-clan.github.io/picx-images-hosting/logo/fba.png">

# Agents Backend

**Enterprise-Grade AI Agent & Backend Platform**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.123%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1.0%2B-green)](https://langchain.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0%2B-%23336791)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-%232496ED?logo=docker&logoColor=white)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> ⚠️ **BETA** - This project is under active development. Features may change, and some components are still being refined. Contributions and feedback are welcome!

*The unified, production-ready platform combining high-performance FastAPI with advanced Agentic AI capabilities*

**[🚀 Get Started](#-get-started-in-60-seconds) • [🔌 FastAPI](#-fastapi-backend---full-stack-architecture) • [🤖 Agents](#-agentic-ai-system---production-grade-orchestration) • [📦 Sandbox](#-sandbox-execution-environment---dual-architecture) • [🛠 Tools](#-tool-server---comprehensive-integrations)**

</div>

---

## 📋 Table of Contents

- [Get Started in 60 Seconds](#-get-started-in-60-seconds)
- [Demo](#-demo)
- [FastAPI Backend - Full Stack Architecture](#-fastapi-backend---full-stack-architecture)
  - [Core Services Layer](#core-services-layer)
  - [CRUD Operations](#crud-operations)
  - [Middleware Stack](#middleware-stack)
  - [Plugin System](#plugin-system)
  - [API Endpoints](#api-endpoints)
- [Agentic AI System](#-agentic-ai-system---production-grade-orchestration)
  - [LangGraph Architecture](#langgraph-architecture)
  - [Content Generators](#content-generators)
  - [RAG Pipeline](#rag-pipeline---multiple-vector-stores)
- [Sandbox Execution Environment](#-sandbox-execution-environment---dual-architecture)
  - [Agent Infra Sandbox (Local)](#1-agent-infra-sandbox-local-development)
  - [Sandbox Server (Production)](#2-sandbox-server-production-grade)
- [Tool Server](#-tool-server---comprehensive-integrations)
  - [Browser Automation](#browser-automation-tools)
  - [Slide System](#slide-system-powerpoint)
  - [Web & Search Integrations](#web--search-integrations)
  - [MCP Integration](#mcp-model-context-protocol)
- [Configuration](#-configuration)
- [License](#-license)

---

## 🚀 Get Started in 60 Seconds

### Option 1: Docker (Recommended)

```bash
# 1️⃣ Clone the repository
git clone https://github.com/obinopaul/agents-backend.git && cd agents-backend

# 2️⃣ Set up environment variables
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys (OpenAI, E2B, Tavily, etc.)

# 3️⃣ Start everything with one command
docker-compose up -d --build
```

### Option 2: Local Development

```bash
# 1️⃣ Install dependencies
pip install -r requirements.txt

# 2️⃣ Start PostgreSQL & Redis
docker-compose up -d fba_postgres fba_redis

# 3️⃣ Run migrations & start server
cd backend && alembic upgrade head
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**🎉 Access Your Services:**

| Service | URL | Description |
|---------|-----|-------------|
| **Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API documentation |
| **ReDoc** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative API docs |
| **Agent API** | `/api/v1/agent/chat` | Streaming chat with AI agents |
| **Sandbox API** | `/api/v1/agent/sandbox` | Code execution environment |

---

## 🎬 Demo

<div align="center">

![Agents Backend Demo](https://via.placeholder.com/900x500?text=Demo+GIF+Coming+Soon)

*Watch the agent autonomously research, code, and execute tasks in the secure sandbox*

</div>

---

## 🔌 FastAPI Backend - Full Stack Architecture

This is not a simple REST API template. It's a **production-grade enterprise backend** with complete authentication, authorization, audit logging, and plugin architecture.

### System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Application                             │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│  Middleware │   Routers   │  Services   │    CRUD     │      Models         │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────────────┤
│ JWT Auth    │ /api/v1/    │ Business    │ Type-Safe   │ SQLAlchemy ORM      │
│ Access Log  │   admin/    │ Logic       │ Database    │ Async Sessions      │
│ Opera Log   │   agent/    │ Transaction │ Operations  │ Alembic Migrations  │
│ I18n        │   task/     │ Management  │             │                     │
│ State       │             │             │             │                     │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
    ┌──────────┐             ┌──────────┐             ┌──────────┐
    │PostgreSQL│             │  Redis   │             │ Celery   │
    │ Database │             │  Cache   │             │ Workers  │
    └──────────┘             └──────────┘             └──────────┘
```

### Core Services Layer

The business logic resides in dedicated service classes with transaction management.

| Service | Description | Code Path |
|---------|-------------|-----------|
| `auth_service` | JWT authentication, login/logout, token refresh | [`backend/app/admin/service/auth_service.py`](backend/app/admin/service/auth_service.py) |
| `user_service` | User management, registration, profile updates | [`backend/app/admin/service/user_service.py`](backend/app/admin/service/user_service.py) |
| `role_service` | RBAC role management, permissions assignment | [`backend/app/admin/service/role_service.py`](backend/app/admin/service/role_service.py) |
| `menu_service` | Dynamic menu permissions, UI access control | [`backend/app/admin/service/menu_service.py`](backend/app/admin/service/menu_service.py) |
| `dept_service` | Department/organization structure management | [`backend/app/admin/service/dept_service.py`](backend/app/admin/service/dept_service.py) |
| `data_scope_service` | Row-level security, data access policies | [`backend/app/admin/service/data_scope_service.py`](backend/app/admin/service/data_scope_service.py) |
| `data_rule_service` | Custom data filtering rules | [`backend/app/admin/service/data_rule_service.py`](backend/app/admin/service/data_rule_service.py) |
| `login_log_service` | Track user login history | [`backend/app/admin/service/login_log_service.py`](backend/app/admin/service/login_log_service.py) |
| `opera_log_service` | Audit trail for all operations | [`backend/app/admin/service/opera_log_service.py`](backend/app/admin/service/opera_log_service.py) |
| `plugin_service` | Dynamic plugin management | [`backend/app/admin/service/plugin_service.py`](backend/app/admin/service/plugin_service.py) |
| `password_history_service` | Password policy enforcement | [`backend/app/admin/service/user_password_history_service.py`](backend/app/admin/service/user_password_history_service.py) |

---

### CRUD Operations

Type-safe database operations with SQLAlchemy 2.0 async.

| CRUD Module | Operations | Code Path |
|-------------|------------|-----------|
| `crud_user` | Create, Read, Update, Delete, Search, Filter | [`backend/app/admin/crud/crud_user.py`](backend/app/admin/crud/crud_user.py) |
| `crud_role` | Role CRUD with permission relationships | [`backend/app/admin/crud/crud_role.py`](backend/app/admin/crud/crud_role.py) |
| `crud_dept` | Department hierarchy operations | [`backend/app/admin/crud/crud_dept.py`](backend/app/admin/crud/crud_dept.py) |
| `crud_menu` | Menu/permission tree management | [`backend/app/admin/crud/crud_menu.py`](backend/app/admin/crud/crud_menu.py) |
| `crud_data_scope` | Data access scope configuration | [`backend/app/admin/crud/crud_data_scope.py`](backend/app/admin/crud/crud_data_scope.py) |
| `crud_data_rule` | Custom filtering rules | [`backend/app/admin/crud/crud_data_rule.py`](backend/app/admin/crud/crud_data_rule.py) |
| `crud_login_log` | Login audit records | [`backend/app/admin/crud/crud_login_log.py`](backend/app/admin/crud/crud_login_log.py) |
| `crud_opera_log` | Operation audit records | [`backend/app/admin/crud/crud_opera_log.py`](backend/app/admin/crud/crud_opera_log.py) |

---

### Middleware Stack

Production-grade middleware for security, logging, and internationalization.

| Middleware | Purpose | Key Features | Code Path |
|------------|---------|--------------|-----------|
| **JWT Authentication** | Token-based auth | Access/refresh tokens, auto-renewal, blacklisting | [`jwt_auth_middleware.py`](backend/middleware/jwt_auth_middleware.py) |
| **Access Logging** | Request/response logging | Timing, status codes, error tracking | [`access_middleware.py`](backend/middleware/access_middleware.py) |
| **Operation Audit** | User action audit trail | IP tracking, user agent, action metadata | [`opera_log_middleware.py`](backend/middleware/opera_log_middleware.py) |
| **I18n** | Internationalization | Multi-language support, locale detection | [`i18n_middleware.py`](backend/middleware/i18n_middleware.py) |
| **State Management** | Request state | Context variables, request tracking | [`state_middleware.py`](backend/middleware/state_middleware.py) |

---

### Plugin System

Extensible architecture for additional functionality.

| Plugin | Description | Features | Code Path |
|--------|-------------|----------|-----------|
| **OAuth2** | Social login | GitHub, Google, Linux.do SSO | [`backend/plugin/oauth2/`](backend/plugin/oauth2/) |
| **Email** | Email notifications | SMTP, templates, async sending | [`backend/plugin/email/`](backend/plugin/email/) |
| **Code Generator** | Auto-generate CRUD | Model → API endpoints generation | [`backend/plugin/code_generator/`](backend/plugin/code_generator/) |
| **Config** | Dynamic configuration | Runtime config changes, feature flags | [`backend/plugin/config/`](backend/plugin/config/) |
| **Dictionary** | System dictionaries | Key-value lookups, enums | [`backend/plugin/dict/`](backend/plugin/dict/) |
| **Notice** | System notifications | Announcements, alerts, user messaging | [`backend/plugin/notice/`](backend/plugin/notice/) |

---

### API Endpoints

#### Agent Module (`/api/v1/agent`)

| Endpoint | Method | Description | Code Path |
|----------|--------|-------------|-----------|
| `/chat` | `POST` | Streaming multi-agent chat with tool calling | [`chat.py`](backend/app/agent/api/v1/chat.py) |
| `/chat/models` | `GET` | List available LLM models (OpenAI, Anthropic, etc.) | [`chat.py`](backend/app/agent/api/v1/chat.py) |
| `/generation/podcast` | `POST` | Generate audio podcasts from content | [`generation.py`](backend/app/agent/api/v1/generation.py) |
| `/generation/ppt` | `POST` | Generate PowerPoint presentations | [`generation.py`](backend/app/agent/api/v1/generation.py) |
| `/generation/prose` | `POST` | Generate long-form prose content | [`generation.py`](backend/app/agent/api/v1/generation.py) |
| `/tts` | `POST` | Text-to-speech conversion | [`tts.py`](backend/app/agent/api/v1/tts.py) |
| `/rag/upload` | `POST` | Upload documents for RAG retrieval | [`rag.py`](backend/app/agent/api/v1/rag.py) |
| `/rag/query` | `POST` | Query RAG knowledge base | [`rag.py`](backend/app/agent/api/v1/rag.py) |
| `/mcp/servers` | `GET` | List MCP servers | [`mcp.py`](backend/app/agent/api/v1/mcp.py) |
| `/mcp/tools` | `GET` | List available MCP tools | [`mcp.py`](backend/app/agent/api/v1/mcp.py) |
| `/config` | `GET/PUT` | Agent configuration management | [`config.py`](backend/app/agent/api/v1/config.py) |

#### Sandbox Endpoints (`/api/v1/agent/sandbox`)

| Endpoint | Method | Description | Code Path |
|----------|--------|-------------|-----------|
| `/` | `POST` | Create new sandbox instance | [`sandbox.py`](backend/app/agent/api/v1/sandbox.py) |
| `/{sandbox_id}` | `GET` | Get sandbox status & metadata | [`sandbox.py`](backend/app/agent/api/v1/sandbox.py) |
| `/{sandbox_id}` | `DELETE` | Delete sandbox instance | [`sandbox.py`](backend/app/agent/api/v1/sandbox.py) |
| `/{sandbox_id}/execute` | `POST` | Execute Python/Bash code | [`sandbox.py`](backend/app/agent/api/v1/sandbox.py) |
| `/{sandbox_id}/files` | `GET/POST` | List/upload files | [`sandbox.py`](backend/app/agent/api/v1/sandbox.py) |
| `/{sandbox_id}/urls` | `GET` | Get VS Code & MCP preview URLs | [`sandbox.py`](backend/app/agent/api/v1/sandbox.py) |

#### Credits & Billing (`/api/v1/agent/credits`)

| Endpoint | Method | Description | Code Path |
|----------|--------|-------------|-----------|
| `/balance` | `GET` | Get user credit balance | [`credits.py`](backend/app/agent/api/v1/credits.py) |
| `/usage` | `GET` | Get credit usage history | [`credits.py`](backend/app/agent/api/v1/credits.py) |

#### Admin Module (`/api/v1/admin`)

<details>
<summary><strong>📋 Full Admin API Reference</strong></summary>

##### Authentication (`/auth`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | `POST` | User authentication with captcha |
| `/logout` | `POST` | Invalidate JWT tokens |
| `/register` | `POST` | User registration |
| `/captcha` | `GET` | Generate login captcha |
| `/refresh` | `POST` | Refresh access token |

##### System (`/sys`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users` | `GET/POST/PUT/DELETE` | User management |
| `/roles` | `GET/POST/PUT/DELETE` | Role-based access control |
| `/menus` | `GET/POST/PUT/DELETE` | Permission menus |
| `/depts` | `GET/POST/PUT/DELETE` | Department structure |
| `/data-scopes` | `GET/POST` | Data access policies |
| `/data-rules` | `GET/POST` | Custom data filtering |

##### Monitoring (`/monitor`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server` | `GET` | Server resource metrics |
| `/redis` | `GET` | Redis status & metrics |

##### Logs (`/log`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/opera` | `GET` | Operation audit logs |
| `/login` | `GET` | Login history |

</details>

---

## 🤖 Agentic AI System - Production-Grade Orchestration

The heart of the platform is a sophisticated **multi-agent orchestration system** built on **LangChain** and **LangGraph**.

### LangGraph Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph State Machine                             │
│                        (Directed Acyclic Graph)                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│     ┌─────────┐      ┌─────────────┐      ┌────────────┐                   │
│     │  START  │ ───► │   Router    │ ───► │   Agent    │                   │
│     └─────────┘      │    Node     │      │   Nodes    │                   │
│                      └─────────────┘      └────────────┘                   │
│                            │                    │                           │
│              ┌─────────────┼─────────────┬─────┴───────┐                   │
│              ▼             ▼             ▼             ▼                   │
│        ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│        │ Research │  │   Code   │  │  Content │  │   Tool   │             │
│        │   Node   │  │   Node   │  │   Node   │  │  Caller  │             │
│        └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
│              │             │             │             │                   │
│              └─────────────┴─────────────┴─────────────┘                   │
│                                    │                                        │
│                                    ▼                                        │
│                             ┌──────────┐                                   │
│                             │   END    │                                   │
│                             └──────────┘                                   │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Graph Components

| Component | Description | Size | Code Path |
|-----------|-------------|------|-----------|
| **Graph Builder** | Constructs the agent workflow DAG | 2.7KB | [`backend/src/graph/builder.py`](backend/src/graph/builder.py) |
| **Node Definitions** | All agent nodes (research, code, content, tools) | **56.8KB** | [`backend/src/graph/nodes.py`](backend/src/graph/nodes.py) |
| **Checkpointing** | State persistence for long-running workflows | 15.5KB | [`backend/src/graph/checkpoint.py`](backend/src/graph/checkpoint.py) |
| **Type Definitions** | State schemas and message types | 1.3KB | [`backend/src/graph/types.py`](backend/src/graph/types.py) |
| **Graph Utilities** | Helper functions for graph operations | 3.6KB | [`backend/src/graph/utils.py`](backend/src/graph/utils.py) |

### Agent Modules

| Agent | Purpose | Key Capabilities | Code Path |
|-------|---------|------------------|-----------|
| **Research Agent** | Information gathering | Web search, RAG retrieval, synthesis | [`backend/src/agents/`](backend/src/agents/) |
| **Code Agent** | Code writing & execution | Python, Bash, sandbox integration | [`backend/src/agents/`](backend/src/agents/) |
| **Content Agent** | Content generation | Podcasts, PPT, prose | [`backend/src/agents/`](backend/src/agents/) |
| **Crawler Agent** | Web scraping | BeautifulSoup, Firecrawl, Jina | [`backend/src/crawler/`](backend/src/crawler/) |
| **Prompt Enhancer** | Prompt improvement | Expand, clarify, optimize prompts | [`backend/src/prompt_enhancer/`](backend/src/prompt_enhancer/) |

---

### Content Generators

| Generator | Output Format | Features | Code Path |
|-----------|---------------|----------|-----------|
| **Podcast** | Audio (MP3/WAV) | Multi-voice dialogue, music, effects | [`backend/src/podcast/`](backend/src/podcast/) |
| **PPT Generator** | PowerPoint (.pptx) | Templates, charts, images | [`backend/src/ppt/`](backend/src/ppt/) |
| **Prose Generator** | Long-form text | Chapters, sections, coherent narrative | [`backend/src/prose/`](backend/src/prose/) |

---

### RAG Pipeline - Multiple Vector Stores

Production-grade Retrieval-Augmented Generation with support for **6 vector databases**.

| Vector Store | Type | Features | Code Path |
|--------------|------|----------|-----------|
| **Milvus** | Self-hosted / Zilliz Cloud | High-performance, scalable | [`backend/src/rag/milvus.py`](backend/src/rag/milvus.py) |
| **Qdrant** | Self-hosted / Cloud | Fast, efficient | [`backend/src/rag/qdrant.py`](backend/src/rag/qdrant.py) |
| **Dify** | Managed platform | Easy integration | [`backend/src/rag/dify.py`](backend/src/rag/dify.py) |
| **RagFlow** | Open-source | Document processing | [`backend/src/rag/ragflow.py`](backend/src/rag/ragflow.py) |
| **VikingDB** | ByteDance | Enterprise-grade | [`backend/src/rag/vikingdb_knowledge_base.py`](backend/src/rag/vikingdb_knowledge_base.py) |
| **Moi** | Custom implementation | Flexible | [`backend/src/rag/moi.py`](backend/src/rag/moi.py) |

### LLM Providers

| Provider | Models | Use Cases |
|----------|--------|-----------|
| **OpenAI** | GPT-4o, GPT-4o-mini, o1, o3-mini | General chat, code, reasoning |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus | Long-context, analysis |
| **Google** | Gemini 2.0, Gemini 1.5 Pro | Multimodal, long-context |
| **Custom** | Via LangChain adapters | Self-hosted models |

---

## 📦 Sandbox Execution Environment - Dual Architecture

The platform includes **two sandbox systems** for different use cases.

### 1. Agent Infra Sandbox (Local Development)

A containerized local sandbox for development and testing.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Infra Sandbox (Docker)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│   │   Python    │   │   Browser   │   │    File     │              │
│   │   Runtime   │   │  (Playwright)│   │   System    │              │
│   └─────────────┘   └─────────────┘   └─────────────┘              │
│                                                                      │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │                    LangChain Tools                          │   │
│   │  • session.py (11.5KB) - Session management                │   │
│   │  • session_tools.py (29KB) - 40+ integrated tools          │   │
│   │  • toolkit.py (4.8KB) - Tool registration                  │   │
│   │  • client.py (5.4KB) - API client                          │   │
│   └────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

| Component | Description | Code Path |
|-----------|-------------|-----------|
| **Session Manager** | Manages sandbox sessions and state | [`session.py`](backend/src/sandbox/agent_infra_sandbox/langchain_tools/session.py) |
| **Session Tools** | 40+ pre-integrated tools (**29KB**) | [`session_tools.py`](backend/src/sandbox/agent_infra_sandbox/langchain_tools/session_tools.py) |
| **Toolkit** | Tool registration and discovery | [`toolkit.py`](backend/src/sandbox/agent_infra_sandbox/langchain_tools/toolkit.py) |
| **Docker Compose** | Container orchestration | [`docker-compose.yaml`](backend/src/sandbox/agent_infra_sandbox/docker-compose.yaml) |

**Start locally:**
```bash
cd backend/src/sandbox/agent_infra_sandbox
docker-compose up -d
```

---

### 2. Sandbox Server (Production-Grade)

Enterprise sandbox with session management, lifecycle control, and cloud providers.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Sandbox Server Architecture                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ┌─────────────────────┐                            │
│                          │  Sandbox Controller │                            │
│                          │   (12.5KB lifecycle)│                            │
│                          └─────────────────────┘                            │
│                                    │                                         │
│              ┌─────────────────────┼─────────────────────┐                  │
│              ▼                     ▼                     ▼                  │
│     ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐        │
│     │   E2B Cloud     │   │    Daytona      │   │  Local Docker   │        │
│     │   (13.5KB)      │   │    (42.7KB)     │   │                 │        │
│     └─────────────────┘   └─────────────────┘   └─────────────────┘        │
│              │                     │                     │                  │
│              └─────────────────────┼─────────────────────┘                  │
│                                    ▼                                         │
│                    ┌───────────────────────────────┐                        │
│                    │      Core Components          │                        │
│                    ├───────────────────────────────┤                        │
│                    │ • PTCSandbox (76KB)          │                        │
│                    │ • MCP Registry (25KB)        │                        │
│                    │ • Tool Generator (30KB)      │                        │
│                    │ • Session Manager (6.7KB)    │                        │
│                    │ • Security (10KB)            │                        │
│                    └───────────────────────────────┘                        │
│                                    │                                         │
│                    ┌───────────────┴───────────────┐                        │
│                    ▼                               ▼                        │
│            ┌──────────────┐                ┌──────────────┐                 │
│            │  VS Code     │                │     MCP      │                 │
│            │  Server      │                │   Server     │                 │
│            │  (Browser)   │                │   (SSE)      │                 │
│            └──────────────┘                └──────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Sandbox Providers

| Provider | Description | Features | Code Path |
|----------|-------------|----------|-----------|
| **E2B** | Cloud-based isolation | Persistent, secure, VS Code | [`e2b.py`](backend/src/sandbox/sandbox_server/sandboxes/e2b.py) |
| **Daytona** | Managed dev environments | Git integration, custom images (**42KB**) | [`daytona.py`](backend/src/sandbox/sandbox_server/sandboxes/daytona.py) |
| **Sandbox Factory** | Provider abstraction | Switch via `SANDBOX_PROVIDER` env | [`sandbox_factory.py`](backend/src/sandbox/sandbox_server/sandboxes/sandbox_factory.py) |

#### Core Components

| Component | Description | Size | Code Path |
|-----------|-------------|------|-----------|
| **PTCSandbox** | Programmatic Tool Calling sandbox | **76KB** | [`core/sandbox.py`](backend/src/sandbox/sandbox_server/core/sandbox.py) |
| **MCP Registry** | Tool registration and discovery | **25KB** | [`core/mcp_registry.py`](backend/src/sandbox/sandbox_server/core/mcp_registry.py) |
| **Tool Generator** | Generate Python functions from MCP tools | **30KB** | [`core/tool_generator.py`](backend/src/sandbox/sandbox_server/core/tool_generator.py) |
| **Session Manager** | Sandbox session lifecycle | 6.7KB | [`core/session.py`](backend/src/sandbox/sandbox_server/core/session.py) |
| **Security** | Auth, encryption, sandboxing | 10KB | [`core/security.py`](backend/src/sandbox/sandbox_server/core/security.py) |

#### Lifecycle Management

| Component | Description | Code Path |
|-----------|-------------|-----------|
| **Queue Scheduler** | Message queue for sandbox operations | [`lifecycle/queue.py`](backend/src/sandbox/sandbox_server/lifecycle/queue.py) |
| **Sandbox Controller** | Create, stop, delete, timeout handling | [`lifecycle/sandbox_controller.py`](backend/src/sandbox/sandbox_server/lifecycle/sandbox_controller.py) |

#### Sandbox Templates

| Template | Purpose | Code Path |
|----------|---------|-----------|
| **Code Server** | VS Code in browser | [`docker/sandbox/start-services.sh`](backend/docker/sandbox/start-services.sh) |
| **Cloud Code** | Google Cloud Shell compatible | [`docker/sandbox/`](backend/docker/sandbox/) |
| **Claude Template** | Claude-optimized environment | [`docker/sandbox/claude_template.json`](backend/docker/sandbox/claude_template.json) |
| **Codex Config** | OpenAI Codex integration | [`docker/sandbox/codex_config.toml`](backend/docker/sandbox/codex_config.toml) |

---

## 🛠 Tool Server - Comprehensive Integrations

The Tool Server is a **standalone server** that provides tools to agents via MCP (Model Context Protocol).

### Tool Server Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Tool Server                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Tool Categories                              │   │
│  ├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤   │
│  │ Browser  │   Web    │  Slides  │   Shell  │   File   │    Media     │   │
│  │  (12)    │   (7)    │   (5)    │   (9)    │   (9)    │    (3)       │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Integrations                                  │   │
│  ├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤   │
│  │ Web Visit│Image Gen │Image Srch│Video Gen │Web Search│   Storage    │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     MCP Server (SSE)                                 │   │
│  │  • client.py - MCP client connection                                │   │
│  │  • server.py - MCP server implementation                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Browser Automation Tools

Full Playwright-based browser control for BrowserUse-style automation.

| Tool | Description | Code Path |
|------|-------------|-----------|
| `click` | Click elements by selector | [`browser/click.py`](backend/src/tool_server/tools/browser/click.py) |
| `navigate` | Navigate to URLs | [`browser/navigate.py`](backend/src/tool_server/tools/browser/navigate.py) |
| `enter_text` | Type text into inputs | [`browser/enter_text.py`](backend/src/tool_server/tools/browser/enter_text.py) |
| `enter_text_multiple` | Fill multiple form fields | [`browser/enter_text_multiple_fields.py`](backend/src/tool_server/tools/browser/enter_text_multiple_fields.py) |
| `scroll` | Scroll pages | [`browser/scroll.py`](backend/src/tool_server/tools/browser/scroll.py) |
| `drag` | Drag and drop elements | [`browser/drag.py`](backend/src/tool_server/tools/browser/drag.py) |
| `dropdown` | Select from dropdowns | [`browser/dropdown.py`](backend/src/tool_server/tools/browser/dropdown.py) |
| `press_key` | Keyboard input | [`browser/press_key.py`](backend/src/tool_server/tools/browser/press_key.py) |
| `tab` | Tab management | [`browser/tab.py`](backend/src/tool_server/tools/browser/tab.py) |
| `view` | Screenshot/view page | [`browser/view.py`](backend/src/tool_server/tools/browser/view.py) |
| `wait` | Wait for elements/time | [`browser/wait.py`](backend/src/tool_server/tools/browser/wait.py) |

---

### Slide System (PowerPoint)

Complete PowerPoint manipulation toolkit.

| Tool | Description | Size | Code Path |
|------|-------------|------|-----------|
| `slide_write` | Create new slides from scratch | **31KB** | [`slide_system/slide_write_tool.py`](backend/src/tool_server/tools/slide_system/slide_write_tool.py) |
| `slide_patch` | Modify existing slides | **27KB** | [`slide_system/slide_patch.py`](backend/src/tool_server/tools/slide_system/slide_patch.py) |
| `slide_edit` | Edit slide content | 8.7KB | [`slide_system/slide_edit_tool.py`](backend/src/tool_server/tools/slide_system/slide_edit_tool.py) |

---

### Web & Search Integrations

#### Web Visit Providers

| Provider | Description | Code Path |
|----------|-------------|-----------|
| **BeautifulSoup** | HTML parsing | [`web_visit/beautifulsoup.py`](backend/src/tool_server/integrations/web_visit/beautifulsoup.py) |
| **Firecrawl** | Advanced web scraping | [`web_visit/firecrawl.py`](backend/src/tool_server/integrations/web_visit/firecrawl.py) |
| **Jina** | AI-powered extraction | [`web_visit/jina.py`](backend/src/tool_server/integrations/web_visit/jina.py) |
| **Gemini** | Google Gemini vision | [`web_visit/gemini.py`](backend/src/tool_server/integrations/web_visit/gemini.py) |
| **Tavily** | AI search + extraction | [`web_visit/tavily.py`](backend/src/tool_server/integrations/web_visit/tavily.py) |

#### Web Search Providers

| Provider | Description | Code Path |
|----------|-------------|-----------|
| **DuckDuckGo** | Privacy-focused search | [`web_search/duckduckgo.py`](backend/src/tool_server/integrations/web_search/duckduckgo.py) |
| **SerpAPI** | Google/Bing via API | [`web_search/serpapi.py`](backend/src/tool_server/integrations/web_search/serpapi.py) |

#### Image Search Providers

| Provider | Description | Code Path |
|----------|-------------|-----------|
| **DuckDuckGo** | Image search | [`image_search/duckduckgo.py`](backend/src/tool_server/integrations/image_search/duckduckgo.py) |
| **SerpAPI** | Google Images via API | [`image_search/serpapi.py`](backend/src/tool_server/integrations/image_search/serpapi.py) |

#### Image Generation

| Provider | Description | Code Path |
|----------|-------------|-----------|
| **DuckDuckGo** | Free image generation | [`image_generation/duckduckgo.py`](backend/src/tool_server/integrations/image_generation/duckduckgo.py) |
| **Vertex AI** | Google Imagen | [`image_generation/vertex.py`](backend/src/tool_server/integrations/image_generation/vertex.py) |

---

### Core Tools (Standalone)

| Tool | Description | Code Path |
|------|-------------|-----------|
| **Bash** | Execute shell commands | [`tools/bash.py`](backend/src/tools/bash.py) |
| **Code Execution** | Python with artifacts | [`tools/code_execution.py`](backend/src/tools/code_execution.py) |
| **File Operations** | Read/write/search files | [`tools/file_ops.py`](backend/src/tools/file_ops.py) |
| **Grep** | Pattern matching | [`tools/grep.py`](backend/src/tools/grep.py) |
| **Glob** | File pattern matching | [`tools/glob.py`](backend/src/tools/glob.py) |
| **Python REPL** | Interactive Python | [`tools/python_repl.py`](backend/src/tools/python_repl.py) |
| **Tavily Search** | AI web search | [`tools/tavily.py`](backend/src/tools/tavily.py) |
| **InfoQuest Search** | Custom search tool | [`tools/infoquest_search/`](backend/src/tools/infoquest_search/) |
| **TTS** | Text-to-speech | [`tools/tts.py`](backend/src/tools/tts.py) |
| **Think** | Internal reasoning | [`tools/think.py`](backend/src/tools/think.py) |
| **Crawl** | Web page crawling | [`tools/crawl.py`](backend/src/tools/crawl.py) |
| **Retriever** | RAG document retrieval | [`tools/retriever.py`](backend/src/tools/retriever.py) |

---

### MCP (Model Context Protocol)

Connect multiple MCP servers to enable agents to use external tools.

| Component | Description | Code Path |
|-----------|-------------|-----------|
| **MCP Client** | Connect to MCP servers via SSE | [`mcp/client.py`](backend/src/tool_server/mcp/client.py) |
| **MCP Server** | Expose tools via MCP protocol | [`mcp/server.py`](backend/src/tool_server/mcp/server.py) |
| **MCP Tool** | Base MCP tool implementation | [`tools/mcp_tool.py`](backend/src/tool_server/tools/mcp_tool.py) |

**MCP Architecture:**
```
┌─────────────────┐     SSE      ┌─────────────────┐
│  Agent Graph    │ ────────────►│   MCP Server    │
│  (LangGraph)    │◄──────────── │  (Tool Server)  │
└─────────────────┘              └─────────────────┘
         │                                │
         │                                │
         ▼                                ▼
┌─────────────────┐              ┌─────────────────┐
│    Sandbox      │              │ External MCP    │
│  (E2B/Daytona)  │              │   Servers       │
└─────────────────┘              └─────────────────┘
```

---

## ⚙️ Configuration

### Required Environment Variables

```bash
# ═══════════════════════════════════════════════════════════════
#                         CORE SETTINGS
# ═══════════════════════════════════════════════════════════════
ENVIRONMENT=dev                    # 'dev' or 'prod'

# ═══════════════════════════════════════════════════════════════
#                          DATABASE
# ═══════════════════════════════════════════════════════════════
DATABASE_TYPE=postgresql
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password

# ═══════════════════════════════════════════════════════════════
#                            REDIS
# ═══════════════════════════════════════════════════════════════
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_USERNAME=default            # For Redis 6+ ACL

# ═══════════════════════════════════════════════════════════════
#                          SECURITY
# ═══════════════════════════════════════════════════════════════
TOKEN_SECRET_KEY=your-secret-key

# ═══════════════════════════════════════════════════════════════
#                        AI PROVIDERS
# ═══════════════════════════════════════════════════════════════
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
TAVILY_API_KEY=tvly-...

# ═══════════════════════════════════════════════════════════════
#                          SANDBOX
# ═══════════════════════════════════════════════════════════════
SANDBOX_PROVIDER=e2b              # 'e2b' or 'daytona'
E2B_API_KEY=e2b_...
DAYTONA_API_KEY=...
DAYTONA_API_URL=https://app.daytona.io/api

# ═══════════════════════════════════════════════════════════════
#                        INTEGRATIONS
# ═══════════════════════════════════════════════════════════════
SERPAPI_API_KEY=...               # For web/image search
FIRECRAWL_API_KEY=...             # For web scraping
```

See [`.env.example`](backend/.env.example) for complete reference.

---

## 📚 Documentation

- [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI
- [Agent System Guide](docs/agent-system.md) - Deep dive into agent architecture
- [Sandbox Guide](backend/src/sandbox/sandbox_server/README.md) - Sandbox server documentation
- [Agent Infra Sandbox](backend/src/sandbox/agent_infra_sandbox/langchain_tools/README.md) - Local sandbox guide

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**⭐ Star this repo if you find it useful!**

[![Stargazers over time](https://starchart.cc/obinopaul/agents-backend.svg?variant=adaptive)](https://starchart.cc/obinopaul/agents-backend)

</div>
