# Backend Documentation

This section provides comprehensive documentation for the `backend/` directory, covering all modules, components, and their interactions.

---

## Directory Structure

```
backend/
│
├── main.py                               # Application entry point
├── cli.py                                # Command-line interface (16+ commands)
├── run.py                                # Uvicorn server runner
├── __init__.py                           # Package version info
│
├── core/                                 # Core configuration & app factory
│   ├── conf.py                           # Global settings (299 config options)
│   ├── registrar.py                      # FastAPI app registration
│   └── path_conf.py                      # Path constants
│
├── database/                             # Database layer
│   ├── db.py                             # Async SQLAlchemy engine & session
│   └── redis.py                          # Redis client configuration
│
├── common/                               # Shared utilities & base classes
│   ├── model.py                          # Base SQLAlchemy models & mixins
│   ├── schema.py                         # Base Pydantic schemas
│   ├── enums.py                          # Enumerations (StatusType, MethodType...)
│   ├── log.py                            # Logging configuration
│   ├── pagination.py                     # Pagination utilities
│   ├── context.py                        # Request context
│   ├── i18n.py                           # Internationalization
│   ├── queue.py                          # Async queue utilities
│   ├── dataclasses.py                    # Data class definitions
│   ├── exception/                        # Exception handling
│   │   ├── errors.py                     # Custom exception classes
│   │   └── exception_handler.py          # Global exception handlers
│   ├── response/                         # Response formatting
│   │   ├── response_code.py              # HTTP status codes
│   │   └── response_schema.py            # Response schemas
│   ├── security/                         # Security subsystem
│   │   ├── jwt.py                        # JWT token management
│   │   ├── rbac.py                       # Role-based access control
│   │   └── permission.py                 # Permission utilities
│   └── socketio/                         # WebSocket integration
│       ├── server.py                     # Socket.IO server
│       └── actions.py                    # Socket.IO event handlers
│
├── app/                                  # Application modules
│   ├── router.py                         # Main router aggregation
│   ├── admin/                            # Admin module
│   │   ├── api/                          # REST endpoints (22 files)
│   │   ├── crud/                         # Database operations (10 files)
│   │   ├── model/                        # SQLAlchemy models (11 files)
│   │   ├── schema/                       # Pydantic schemas (12 files)
│   │   ├── service/                      # Business logic (12 files)
│   │   ├── tests/                        # Unit tests
│   │   └── utils/                        # Admin utilities
│   └── task/                             # Celery task module
│       ├── celery.py                     # Celery app configuration
│       ├── database.py                   # Task result database
│       ├── api/                          # Task API endpoints
│       ├── crud/                         # Task CRUD operations
│       ├── model/                        # Task models
│       ├── schema/                       # Task schemas
│       ├── service/                      # Task services
│       ├── tasks/                        # Task definitions
│       └── utils/                        # Task utilities
│
├── middleware/                           # HTTP middleware stack
│   ├── access_middleware.py              # Request/response logging
│   ├── i18n_middleware.py                # Language detection
│   ├── jwt_auth_middleware.py            # JWT authentication
│   ├── opera_log_middleware.py           # Operation audit logging
│   └── state_middleware.py               # Request state initialization
│
├── plugin/                               # Plugin system
│   ├── tools.py                          # Plugin discovery & routing
│   ├── code_generator/                   # Code generation plugin
│   ├── oauth2/                           # OAuth2 plugin (GitHub, Google, Linux-DO)
│   ├── email/                            # Email sending plugin
│   ├── dict/                             # Dictionary plugin
│   ├── config/                           # Dynamic config plugin
│   └── notice/                           # Notification plugin
│
├── ptc-agent/                            # AI Agent framework (PTC)
│   ├── agent/                            # Agent implementation
│   │   ├── agent.py                      # Main agent logic
│   │   ├── graph.py                      # LangGraph workflow
│   │   ├── backends/                     # LLM backends
│   │   ├── middleware/                   # Agent middleware
│   │   ├── prompts/                      # Prompt templates
│   │   ├── subagents/                    # Specialized subagents
│   │   └── tools/                        # Agent tools
│   ├── core/                             # Core components
│   │   ├── sandbox.py                    # Daytona sandbox (76KB)
│   │   ├── mcp_registry.py               # MCP integration
│   │   ├── session.py                    # Session management
│   │   ├── security.py                   # Security controls
│   │   └── tool_generator.py             # Dynamic tool generation
│   ├── config/                           # Agent configuration
│   ├── ii-agent/                         # II-Agent subproject
│   ├── utils/                            # Agent utilities
│   └── tests/                            # Agent tests
│
├── utils/                                # Utility functions (19 files)
│   ├── snowflake.py                      # Snowflake ID generation
│   ├── serializers.py                    # MsgSpec JSON serialization
│   ├── encrypt.py                        # Encryption helpers
│   ├── timezone.py                       # Timezone utilities
│   ├── file_ops.py                       # File operations
│   ├── dynamic_config.py                 # Dynamic configuration
│   ├── health_check.py                   # Health check utilities
│   ├── server_info.py                    # Server information
│   └── ...                               # Other utilities
│
├── locale/                               # i18n translations
│   ├── en-US.json                        # English translations
│   └── zh-CN.yml                         # Chinese translations
│
├── alembic/                              # Database migrations
│   ├── env.py                            # Migration environment
│   └── script.py.mako                    # Migration template
│
├── scripts/                              # Development scripts
│   ├── export.sh                         # Export utilities
│   ├── format.sh                         # Code formatting
│   └── lint.sh                           # Linting
│
├── sql/                                  # SQL initialization
│   └── ...                               # SQL scripts
│
└── static/                               # Static files
    └── ...                               # Assets
```

---

## Entry Points

### main.py - Application Entry

The main entry point that bootstraps the FastAPI application:

```python
# Simplified flow
from backend.core.registrar import register_app
from backend.plugin.tools import get_plugins, install_requirements

# 1. Detect and install plugin dependencies
for plugin in get_plugins():
    install_requirements(plugin)

# 2. Create and configure FastAPI app
app = register_app()
```

**Key Actions:**
1. Detects all plugins in `plugin/` directory
2. Installs plugin-specific requirements
3. Calls `register_app()` to create the FastAPI instance

---

### cli.py - Command Line Interface

Provides 16+ CLI commands for development and administration:

```bash
# Database commands
python cli.py init-db          # Initialize database
python cli.py drop-db          # Drop all tables
python cli.py migrate          # Run migrations

# User management
python cli.py create-superuser # Create superuser
python cli.py reset-password   # Reset user password

# Development
python cli.py run              # Run development server
python cli.py shell            # Interactive Python shell
```

---

### run.py - Uvicorn Runner

Simple script to run the server with Uvicorn:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development mode
    )
```

---

## Module Documentation

| Module | Description | Documentation |
|--------|-------------|---------------|
| **core/** | Configuration, app factory, paths | [Core Documentation](./core/README.md) |
| **database/** | SQLAlchemy & Redis setup | [Database Documentation](./database/README.md) |
| **common/** | Shared utilities, security, exceptions | [Common Documentation](./common/README.md) |
| **app/admin/** | Admin module (users, roles, menus) | [Admin Documentation](./app/admin/README.md) |
| **app/task/** | Celery background tasks | [Task Documentation](./app/task/README.md) |
| **middleware/** | HTTP middleware stack | [Middleware Documentation](./middleware/README.md) |
| **plugin/** | Plugin system | [Plugin Documentation](./plugin/README.md) |
| **ptc-agent/** | AI Agent framework | [PTC-Agent Documentation](./ptc-agent/README.md) |
| **utils/** | Utility functions | [Utils Documentation](./utils/README.md) |
| **locale/** | Internationalization | [Locale Documentation](./locale/README.md) |
| **alembic/** | Database migrations | [Alembic Documentation](./alembic/README.md) |

---

## Configuration

### Environment Variables

Configuration is managed through `.env` file. Copy from `.env.example`:

```bash
cp .env.example .env
```

Key configuration categories:

| Category | Variables | Description |
|----------|-----------|-------------|
| **Environment** | `ENVIRONMENT` | `dev` or `prod` |
| **Database** | `DATABASE_TYPE`, `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD` | Primary database |
| **Redis** | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DATABASE` | Cache & sessions |
| **Token** | `TOKEN_SECRET_KEY` | JWT signing key |
| **Celery** | `CELERY_BROKER`, `CELERY_RABBITMQ_*` | Task queue |
| **OAuth2** | `OAUTH2_GITHUB_*`, `OAUTH2_GOOGLE_*` | OAuth providers |
| **Email** | `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_HOST` | SMTP configuration |

See [Configuration Reference](./core/configuration.md) for the complete list of 100+ settings.

---

## Application Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATION STARTUP                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│ Plugin        │        │ FastAPI       │        │ Middleware    │
│ Discovery     │        │ Creation      │        │ Registration  │
└───────┬───────┘        └───────┬───────┘        └───────┬───────┘
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│ Install       │        │ Lifespan      │        │ Router        │
│ Requirements  │        │ Events        │        │ Registration  │
└───────────────┘        └───────┬───────┘        └───────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │     LIFESPAN: STARTUP    │
                   ├─────────────────────────┤
                   │ 1. Create database tables│
                   │ 2. Open Redis connection │
                   │ 3. Initialize rate limiter│
                   │ 4. Initialize Snowflake  │
                   │ 5. Start opera log task  │
                   └─────────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │    SERVER RUNNING        │
                   └─────────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │    LIFESPAN: SHUTDOWN    │
                   ├─────────────────────────┤
                   │ 1. Release Snowflake node│
                   │ 2. Close Redis connection │
                   └─────────────────────────┘
```

---

## Pseudo 3-Tier Architecture Pattern

Each module follows a consistent layered structure:

```
module_name/
├── api/                  # Presentation Layer
│   ├── __init__.py       # Router exports
│   └── v1/
│       ├── __init__.py   # Version router
│       └── resource.py   # Endpoint handlers
│
├── schema/               # Data Transfer Objects
│   ├── __init__.py
│   └── resource.py       # Pydantic schemas
│
├── service/              # Business Logic Layer
│   ├── __init__.py
│   └── resource.py       # Service classes
│
├── crud/                 # Data Access Layer
│   ├── __init__.py
│   ├── base.py           # Base CRUD class
│   └── resource.py       # Resource CRUD
│
└── model/                # Domain Models
    ├── __init__.py
    └── resource.py       # SQLAlchemy models
```

### Layer Responsibilities

| Layer | File Pattern | Responsibility |
|-------|--------------|----------------|
| API | `api/v1/*.py` | HTTP routing, request validation, response formatting |
| Schema | `schema/*.py` | Input validation, output serialization |
| Service | `service/*.py` | Business logic, transaction orchestration |
| CRUD | `crud/*.py` | Database queries, ORM operations |
| Model | `model/*.py` | SQLAlchemy table definitions, relationships |

---

## Quick Reference: Where to Make Changes

This table helps you quickly find which files to edit for common development tasks:

| Goal | File(s) to Edit | Notes |
|------|-----------------|-------|
| **Add new API endpoints** | `app/admin/api/v1/` or `app/task/api/v1/` | Create new router files, register in `__init__.py` |
| **Add new middleware** | `middleware/` + `core/registrar.py` | Create middleware class, add in `register_middleware()` |
| **Change app settings** | `core/conf.py` | Add new settings to `Settings` class |
| **Add database models** | `app/admin/model/` | Create SQLAlchemy model, run migration |
| **Add Pydantic schemas** | `app/admin/schema/` | Create request/response schemas |
| **Add business logic** | `app/admin/service/` | Create service classes |
| **Add database operations** | `app/admin/crud/` | Extend `CRUDBase` for new models |
| **Add Celery tasks** | `app/task/tasks/` | Create task functions with `@celery_app.task` |
| **Add agent capabilities** | `ptc-agent/agent/tools/` | Create new tools for the AI agent |
| **Add CLI commands** | `cli.py` | Add new Click commands |
| **Add plugins** | `plugin/` | Create new plugin directory with API/model/service |
| **Customize error responses** | `common/exception/` | Modify exception handlers |
| **Add translations** | `locale/` | Add keys to `en-US.json` or `zh-CN.yml` |

### Key FastAPI Files

| File | Purpose |
|------|---------|
| `main.py` | Application entry point - creates the FastAPI app |
| `core/registrar.py` | App factory - registers middleware, routers, static files |
| `core/conf.py` | All application settings (299+ config options) |
| `app/router.py` | Main router that combines admin and task routers |
| `run.py` | Uvicorn development server runner |
| `cli.py` | CLI tool for database migrations, user management, etc. |

### API Route Structure

```
/api/v1/
├── auth/           → Login, logout, token refresh, OAuth2
├── sys/            → Users, roles, menus, depts, plugins, files
│   ├── users       → User CRUD, password management
│   ├── roles       → Role CRUD, permissions
│   ├── menus       → Menu tree management
│   ├── depts       → Department hierarchy
│   └── ...
├── log/            → Operation logs, login logs
├── monitor/        → Server stats, Redis info
└── task/           → Celery task management
    ├── control     → Task registration, revocation
    ├── result      → Task result retrieval
    └── scheduler   → Periodic task scheduling
```

---

## Next Steps

1. **[Core Configuration](./core/README.md)** - Settings and app factory
2. **[Database Layer](./database/README.md)** - SQLAlchemy and Redis setup
3. **[Common Module](./common/README.md)** - Shared utilities and security
4. **[Admin Module](./app/admin/README.md)** - User and role management
5. **[Middleware Stack](./middleware/README.md)** - Request processing

---

*Last Updated: December 2024*
