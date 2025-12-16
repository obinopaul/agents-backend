# Agents Backend Documentation

> **Enterprise-Level FastAPI Backend Architecture with AI Agent Integration**

Welcome to the comprehensive documentation for the Agents Backend project. This documentation provides detailed explanations of every component, architecture patterns, implementation guides, and extension references.

---

## 📋 Table of Contents

| Section | Description |
|---------|-------------|
| [Architecture Overview](./architecture-overview.md) | System design, data flow, and component interactions |
| [Getting Started](./getting-started.md) | Installation, configuration, and first run |
| [Backend Documentation](./backend/README.md) | Complete backend module reference |

---

## 🏗️ Project Structure

```
agents-backend/
│
├── backend/                          # Main application code
│   ├── main.py                       # Application entry point
│   ├── cli.py                        # Command-line interface
│   ├── run.py                        # Uvicorn server runner
│   │
│   ├── core/                         # Core configuration & app factory
│   │   ├── conf.py                   # Settings (env, database, redis, jwt...)
│   │   ├── registrar.py              # FastAPI app registration
│   │   └── path_conf.py              # Path constants
│   │
│   ├── database/                     # Database layer
│   │   ├── db.py                     # SQLAlchemy async engine & session
│   │   └── redis.py                  # Redis client configuration
│   │
│   ├── common/                       # Shared utilities & base classes
│   │   ├── model.py                  # Base SQLAlchemy models
│   │   ├── schema.py                 # Base Pydantic schemas
│   │   ├── enums.py                  # Enumerations
│   │   ├── exception/                # Exception handling
│   │   ├── response/                 # Response formatting
│   │   ├── security/                 # JWT, RBAC, permissions
│   │   └── socketio/                 # WebSocket integration
│   │
│   ├── app/                          # Application modules
│   │   ├── admin/                    # Admin module (users, roles, menus...)
│   │   │   ├── api/                  # REST API endpoints
│   │   │   ├── crud/                 # Database operations
│   │   │   ├── model/                # SQLAlchemy models
│   │   │   ├── schema/               # Pydantic schemas
│   │   │   └── service/              # Business logic
│   │   └── task/                     # Celery background tasks
│   │
│   ├── middleware/                   # HTTP middleware stack
│   │   ├── access_middleware.py      # Access logging
│   │   ├── i18n_middleware.py        # Internationalization
│   │   ├── jwt_auth_middleware.py    # JWT authentication
│   │   ├── opera_log_middleware.py   # Operation logging
│   │   └── state_middleware.py       # Request state
│   │
│   ├── plugin/                       # Plugin system
│   │   ├── code_generator/           # Auto-generate CRUD code
│   │   ├── oauth2/                   # GitHub, Google, Linux-DO OAuth
│   │   ├── email/                    # Email sending
│   │   ├── dict/                     # System dictionaries
│   │   ├── config/                   # Dynamic configuration
│   │   └── notice/                   # Notifications
│   │
│   ├── ptc-agent/                    # AI Agent framework (PTC)
│   │   ├── agent/                    # Agent implementation
│   │   ├── core/                     # Sandbox, MCP, security
│   │   └── config/                   # Agent configuration
│   │
│   ├── utils/                        # Utility functions
│   ├── locale/                       # i18n translations
│   ├── alembic/                      # Database migrations
│   └── scripts/                      # Development scripts
│
├── deploy/                           # Deployment configurations
├── docs/                             # This documentation
├── docker-compose.yml                # Docker orchestration
└── requirements.txt                  # Python dependencies
```

---

## 🎯 Architecture Overview

The project follows a **Pseudo 3-Tier Architecture** inspired by enterprise Java patterns, adapted for Python/FastAPI:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLIENT REQUEST                               │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           MIDDLEWARE STACK                                │
│                                                                          │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │
│   │  Context    │──▶│   Access    │──▶│    I18n     │──▶│  JWT Auth   │  │
│   │ Middleware  │   │ Middleware  │   │ Middleware  │   │ Middleware  │  │
│   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘  │
│                                                               │          │
│   ┌─────────────┐   ┌─────────────┐                          │          │
│   │   State     │◀──│  Opera Log  │◀─────────────────────────┘          │
│   │ Middleware  │   │ Middleware  │                                      │
│   └─────────────┘   └─────────────┘                                      │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (api/)              │  DATA TRANSFER (schema/)       │
│  ─────────────────────────              │  ───────────────────────       │
│  • Route handlers                       │  • Request validation          │
│  • Dependency injection                 │  • Response serialization      │
│  • HTTP status codes                    │  • Pydantic models             │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  BUSINESS LOGIC LAYER (service/)                                         │
│  ───────────────────────────────                                         │
│  • Business rules & workflows                                            │
│  • Transaction orchestration                                             │
│  • Cross-cutting concerns                                                │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  DATA ACCESS LAYER (crud/)                                               │
│  ─────────────────────────                                               │
│  • SQLAlchemy async operations                                           │
│  • Query building                                                        │
│  • Pagination support                                                    │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  DATABASE LAYER (model/)               │  CACHE LAYER                    │
│  ──────────────────────                │  ───────────                    │
│  ┌─────────────────────┐               │  ┌─────────────────────┐        │
│  │  PostgreSQL / MySQL │               │  │       Redis         │        │
│  │  (Primary Storage)  │               │  │  (Sessions, Cache)  │        │
│  └─────────────────────┘               │  └─────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Layer Mapping (Java → Python)

| Workflow | Java | This Project |
|----------|------|--------------|
| View | Controller | `api/` |
| Data Transfer | DTO | `schema/` |
| Business Logic | Service + Impl | `service/` |
| Data Access | DAO / Mapper | `crud/` |
| Model | Entity | `model/` |

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd agents-backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp backend/.env.example backend/.env
# Edit .env with your database and Redis settings

# 5. Initialize database
# Ensure PostgreSQL/MySQL and Redis are running
cd backend
alembic upgrade head

# 6. Start the server
python run.py
# or: uvicorn backend.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API documentation.

---

## 📚 Documentation Sections

### Core System

| Document | Description |
|----------|-------------|
| [Backend Overview](./backend/README.md) | Complete backend module guide |
| [Core Configuration](./backend/core/README.md) | Settings, app factory, paths |
| [Database Layer](./backend/database/README.md) | SQLAlchemy & Redis setup |

### Security & Authentication

| Document | Description |
|----------|-------------|
| [Security Overview](./backend/common/security/README.md) | Authentication & authorization |
| [JWT Authentication](./backend/common/security/jwt.md) | Token management |
| [RBAC System](./backend/common/security/rbac.md) | Role-based access control |

### Application Modules

| Document | Description |
|----------|-------------|
| [Admin Module](./backend/app/admin/README.md) | Users, roles, menus, departments |
| [Task Module](./backend/app/task/README.md) | Celery background tasks |
| [Plugin System](./backend/plugin/README.md) | Extensible plugins |

### AI Agent Framework

| Document | Description |
|----------|-------------|
| [PTC-Agent Overview](./backend/ptc-agent/README.md) | AI agent architecture |
| [Agent Implementation](./backend/ptc-agent/agent/README.md) | Tools, middleware, prompts |
| [Core Components](./backend/ptc-agent/core/README.md) | Sandbox, MCP, security |

---

## 🔧 Technology Stack

| Category | Technology |
|----------|------------|
| **Framework** | FastAPI 0.100+ |
| **Database** | PostgreSQL 16+ / MySQL 8+ |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Cache** | Redis |
| **Validation** | Pydantic v2 |
| **Auth** | JWT (python-jose) |
| **Tasks** | Celery + RabbitMQ/Redis |
| **WebSocket** | Socket.IO |
| **Migrations** | Alembic |
| **Linting** | Ruff |

---

## 📖 How to Use This Documentation

1. **New to the project?** Start with [Getting Started](./getting-started.md)
2. **Understanding architecture?** Read [Architecture Overview](./architecture-overview.md)
3. **Working on a feature?** Navigate to the relevant module in [Backend Documentation](./backend/README.md)
4. **Extending the system?** Check the "How to Extend" sections in each module doc
5. **Adding plugins?** See [Plugin System](./backend/plugin/README.md)

---

## 🔗 External References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Redis Documentation](https://redis.io/docs/)

---

*Last Updated: December 2024*
