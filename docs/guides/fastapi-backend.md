# FastAPI Backend - Complete Reference

This document provides comprehensive documentation for the FastAPI backend architecture, services, and API endpoints.

## System Architecture

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

---

## Core Services Layer

The business logic resides in dedicated service classes with transaction management.

| Service | Description | Code Path |
|---------|-------------|-----------|
| `auth_service` | JWT authentication, login/logout, token refresh | [`backend/app/admin/service/auth_service.py`](../../backend/app/admin/service/auth_service.py) |
| `user_service` | User management, registration, profile updates | [`backend/app/admin/service/user_service.py`](../../backend/app/admin/service/user_service.py) |
| `role_service` | RBAC role management, permissions assignment | [`backend/app/admin/service/role_service.py`](../../backend/app/admin/service/role_service.py) |
| `menu_service` | Dynamic menu permissions, UI access control | [`backend/app/admin/service/menu_service.py`](../../backend/app/admin/service/menu_service.py) |
| `dept_service` | Department/organization structure management | [`backend/app/admin/service/dept_service.py`](../../backend/app/admin/service/dept_service.py) |
| `data_scope_service` | Row-level security, data access policies | [`backend/app/admin/service/data_scope_service.py`](../../backend/app/admin/service/data_scope_service.py) |
| `data_rule_service` | Custom data filtering rules | [`backend/app/admin/service/data_rule_service.py`](../../backend/app/admin/service/data_rule_service.py) |
| `login_log_service` | Track user login history | [`backend/app/admin/service/login_log_service.py`](../../backend/app/admin/service/login_log_service.py) |
| `opera_log_service` | Audit trail for all operations | [`backend/app/admin/service/opera_log_service.py`](../../backend/app/admin/service/opera_log_service.py) |
| `plugin_service` | Dynamic plugin management | [`backend/app/admin/service/plugin_service.py`](../../backend/app/admin/service/plugin_service.py) |

---

## CRUD Operations

Type-safe database operations with SQLAlchemy 2.0 async.

| CRUD Module | Operations | Code Path |
|-------------|------------|-----------|
| `crud_user` | Create, Read, Update, Delete, Search, Filter | [`backend/app/admin/crud/crud_user.py`](../../backend/app/admin/crud/crud_user.py) |
| `crud_role` | Role CRUD with permission relationships | [`backend/app/admin/crud/crud_role.py`](../../backend/app/admin/crud/crud_role.py) |
| `crud_dept` | Department hierarchy operations | [`backend/app/admin/crud/crud_dept.py`](../../backend/app/admin/crud/crud_dept.py) |
| `crud_menu` | Menu/permission tree management | [`backend/app/admin/crud/crud_menu.py`](../../backend/app/admin/crud/crud_menu.py) |
| `crud_data_scope` | Data access scope configuration | [`backend/app/admin/crud/crud_data_scope.py`](../../backend/app/admin/crud/crud_data_scope.py) |
| `crud_data_rule` | Custom filtering rules | [`backend/app/admin/crud/crud_data_rule.py`](../../backend/app/admin/crud/crud_data_rule.py) |
| `crud_login_log` | Login audit records | [`backend/app/admin/crud/crud_login_log.py`](../../backend/app/admin/crud/crud_login_log.py) |
| `crud_opera_log` | Operation audit records | [`backend/app/admin/crud/crud_opera_log.py`](../../backend/app/admin/crud/crud_opera_log.py) |

---

## Middleware Stack

Production-grade middleware for security, logging, and internationalization.

| Middleware | Purpose | Key Features | Code Path |
|------------|---------|--------------|-----------|
| **JWT Authentication** | Token-based auth | Access/refresh tokens, auto-renewal, blacklisting | [`jwt_auth_middleware.py`](../../backend/middleware/jwt_auth_middleware.py) |
| **Access Logging** | Request/response logging | Timing, status codes, error tracking | [`access_middleware.py`](../../backend/middleware/access_middleware.py) |
| **Operation Audit** | User action audit trail | IP tracking, user agent, action metadata | [`opera_log_middleware.py`](../../backend/middleware/opera_log_middleware.py) |
| **I18n** | Internationalization | Multi-language support, locale detection | [`i18n_middleware.py`](../../backend/middleware/i18n_middleware.py) |
| **State Management** | Request state | Context variables, request tracking | [`state_middleware.py`](../../backend/middleware/state_middleware.py) |

---

## Plugin System

Extensible architecture for additional functionality.

| Plugin | Description | Features | Code Path |
|--------|-------------|----------|-----------|
| **OAuth2** | Social login | GitHub, Google, Linux.do SSO | [`backend/plugin/oauth2/`](../../backend/plugin/oauth2/) |
| **Email** | Email notifications | SMTP, templates, async sending | [`backend/plugin/email/`](../../backend/plugin/email/) |
| **Code Generator** | Auto-generate CRUD | Model → API endpoints generation | [`backend/plugin/code_generator/`](../../backend/plugin/code_generator/) |
| **Config** | Dynamic configuration | Runtime config changes, feature flags | [`backend/plugin/config/`](../../backend/plugin/config/) |
| **Dictionary** | System dictionaries | Key-value lookups, enums | [`backend/plugin/dict/`](../../backend/plugin/dict/) |
| **Notice** | System notifications | Announcements, alerts, user messaging | [`backend/plugin/notice/`](../../backend/plugin/notice/) |

---

## API Endpoints

### Agent Module (`/api/v1/agent`)

| Endpoint | Method | Description | Code Path |
|----------|--------|-------------|-----------|
| `/chat/stream` | `POST` | Streaming multi-agent chat with tool calling | [`chat.py`](../../backend/app/agent/api/v1/chat.py) |
| `/chat/models` | `GET` | List available LLM models | [`chat.py`](../../backend/app/agent/api/v1/chat.py) |
| `/generation/podcast` | `POST` | Generate audio podcasts from content | [`generation.py`](../../backend/app/agent/api/v1/generation.py) |
| `/generation/ppt` | `POST` | Generate PowerPoint presentations | [`generation.py`](../../backend/app/agent/api/v1/generation.py) |
| `/generation/prose` | `POST` | Generate long-form prose content | [`generation.py`](../../backend/app/agent/api/v1/generation.py) |
| `/tts` | `POST` | Text-to-speech conversion | [`tts.py`](../../backend/app/agent/api/v1/tts.py) |
| `/rag/upload` | `POST` | Upload documents for RAG retrieval | [`rag.py`](../../backend/app/agent/api/v1/rag.py) |
| `/rag/query` | `POST` | Query RAG knowledge base | [`rag.py`](../../backend/app/agent/api/v1/rag.py) |
| `/mcp/servers` | `GET` | List MCP servers | [`mcp.py`](../../backend/app/agent/api/v1/mcp.py) |
| `/mcp/tools` | `GET` | List available MCP tools | [`mcp.py`](../../backend/app/agent/api/v1/mcp.py) |
| `/config` | `GET/PUT` | Agent configuration management | [`config.py`](../../backend/app/agent/api/v1/config.py) |

### Sandbox Endpoints (`/api/v1/agent/sandboxes`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/create` | `POST` | Create new sandbox instance |
| `/{sandbox_id}/status` | `GET` | Get sandbox status & metadata |
| `/{sandbox_id}` | `DELETE` | Delete sandbox instance |
| `/run-cmd` | `POST` | Execute shell commands |
| `/read-file` | `POST` | Read file content |
| `/write-file` | `POST` | Write file to sandbox |
| `/{sandbox_id}/urls` | `GET` | Get VS Code & MCP preview URLs |

### Slides Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{sandbox_id}/presentations` | `GET` | List all presentations in sandbox |
| `/{sandbox_id}/presentations/{name}` | `GET` | List slides in a presentation |
| `/{sandbox_id}/slides/{name}/{num}` | `GET` | Get slide HTML for preview |
| `/{sandbox_id}/slides/export` | `POST` | Export presentation to PDF |
| `/{sandbox_id}/slides/download/{name}` | `GET` | Download slides as ZIP archive |

### Credits & Billing (`/api/v1/agent/credits`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/balance` | `GET` | Get user credit balance |
| `/usage` | `GET` | Get credit usage history |

### Admin Module (`/api/v1/admin`)

#### Authentication (`/auth`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | `POST` | User authentication with captcha |
| `/logout` | `POST` | Invalidate JWT tokens |
| `/register` | `POST` | User registration |
| `/captcha` | `GET` | Generate login captcha |
| `/refresh` | `POST` | Refresh access token |

#### System (`/sys`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users` | `GET/POST/PUT/DELETE` | User management |
| `/roles` | `GET/POST/PUT/DELETE` | Role-based access control |
| `/menus` | `GET/POST/PUT/DELETE` | Permission menus |
| `/depts` | `GET/POST/PUT/DELETE` | Department structure |
| `/data-scopes` | `GET/POST` | Data access policies |
| `/data-rules` | `GET/POST` | Custom data filtering |

#### Monitoring (`/monitor`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server` | `GET` | Server resource metrics |
| `/redis` | `GET` | Redis status & metrics |

#### Logs (`/log`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/opera` | `GET` | Operation audit logs |
| `/login` | `GET` | Login history |

---

## Request/Response Examples

### Chat Stream Request

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Research AI trends"}],
    "thread_id": "my-thread-123",
    "max_plan_iterations": 1,
    "max_step_num": 3,
    "enable_background_investigation": true
  }'
```

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "123456", "captcha": "..."}'

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

## Related Documentation

- [CLI Reference](cli-reference.md) - Agents Backend CLI commands
- [Agentic AI System](agentic-ai.md) - LangGraph and agent details
- [Main README](../../README.md) - Project overview
