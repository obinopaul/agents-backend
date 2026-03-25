# Architecture Overview

This document provides a comprehensive view of the Agents Backend system architecture, including component interactions, data flow, and design patterns.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Request Lifecycle](#request-lifecycle)
3. [Middleware Pipeline](#middleware-pipeline)
4. [Application Layers](#application-layers)
5. [Database Architecture](#database-architecture)
6. [Plugin System](#plugin-system)
7. [AI Agent Architecture](#ai-agent-architecture)
8. [Security Architecture](#security-architecture)

---

## System Architecture

### High-Level Overview

```
                                    ┌─────────────────────┐
                                    │   Load Balancer     │
                                    │   (Nginx/Traefik)   │
                                    └──────────┬──────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
           ┌────────────────┐         ┌────────────────┐         ┌────────────────┐
           │   FastAPI      │         │   FastAPI      │         │   FastAPI      │
           │   Instance 1   │         │   Instance 2   │         │   Instance N   │
           └───────┬────────┘         └───────┬────────┘         └───────┬────────┘
                   │                          │                          │
                   └──────────────────────────┼──────────────────────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────┐
              │                               │                           │
              ▼                               ▼                           ▼
     ┌─────────────────┐            ┌─────────────────┐         ┌─────────────────┐
     │   PostgreSQL    │            │     Redis       │         │   RabbitMQ      │
     │    / MySQL      │            │   (Cache/Queue) │         │   (Optional)    │
     │  ┌───────────┐  │            │  ┌───────────┐  │         │  ┌───────────┐  │
     │  │  Primary  │  │            │  │  Master   │  │         │  │  Broker   │  │
     │  └───────────┘  │            │  └───────────┘  │         │  └───────────┘  │
     └─────────────────┘            └─────────────────┘         └─────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **FastAPI Instances** | HTTP request handling, API routing, business logic |
| **PostgreSQL/MySQL** | Persistent data storage, ACID transactions |
| **Redis** | Session storage, token caching, rate limiting, task queues |
| **RabbitMQ** | Message broker for Celery tasks (production) |
| **Celery Workers** | Async background task processing |

---

## Request Lifecycle

### Complete Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               CLIENT REQUEST                                     │
│                        POST /api/v1/users  { "name": "..." }                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. UVICORN ASGI SERVER                                                          │
│    ─────────────────────                                                        │
│    • Receives raw HTTP request                                                  │
│    • Parses headers, body                                                       │
│    • Creates ASGI scope                                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 2. STARLETTE MIDDLEWARE STACK                                                   │
│    ────────────────────────────                                                 │
│    Execution order (top to bottom on request, bottom to top on response):       │
│                                                                                 │
│    ┌─────────────────────────────────────────────────────────────────────────┐  │
│    │ ContextMiddleware (starlette-context)                                   │  │
│    │ • Generates/validates X-Request-ID                                      │  │
│    │ • Sets up request context variables                                     │  │
│    └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│    ┌─────────────────────────────────────────────────────────────────────────┐  │
│    │ AccessMiddleware                                                        │  │
│    │ • Logs request start time                                               │  │
│    │ • Records request method, path                                          │  │
│    └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│    ┌─────────────────────────────────────────────────────────────────────────┐  │
│    │ I18nMiddleware                                                          │  │
│    │ • Detects Accept-Language header                                        │  │
│    │ • Sets translation context                                              │  │
│    └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│    ┌─────────────────────────────────────────────────────────────────────────┐  │
│    │ AuthenticationMiddleware (JwtAuthMiddleware)                            │  │
│    │ • Extracts Bearer token from Authorization header                       │  │
│    │ • Validates JWT signature and expiry                                    │  │
│    │ • Loads user from Redis cache or database                               │  │
│    │ • Sets request.user and request.auth                                    │  │
│    └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│    ┌─────────────────────────────────────────────────────────────────────────┐  │
│    │ StateMiddleware                                                         │  │
│    │ • Initializes request.state attributes                                  │  │
│    │ • Sets up permission context                                            │  │
│    └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│    ┌─────────────────────────────────────────────────────────────────────────┐  │
│    │ OperaLogMiddleware                                                      │  │
│    │ • Captures request body (for logging)                                   │  │
│    │ • Queues operation log for async write                                  │  │
│    └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 3. FASTAPI ROUTING                                                              │
│    ──────────────────                                                           │
│    • Matches URL path to route handler                                          │
│    • Resolves path parameters                                                   │
│    • Executes route dependencies (DependsRBAC, DependsJwtAuth)                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 4. REQUEST VALIDATION                                                           │
│    ───────────────────                                                          │
│    • Pydantic schema validates request body                                     │
│    • Path/query parameters validated                                            │
│    • Returns 422 on validation errors                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 5. ROUTE HANDLER (api/)                                                         │
│    ─────────────────────                                                        │
│    • Receives validated request data                                            │
│    • Calls service layer                                                        │
│    • Returns response                                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 6. SERVICE LAYER (service/)                                                     │
│    ─────────────────────────                                                    │
│    • Implements business logic                                                  │
│    • Orchestrates CRUD operations                                               │
│    • Manages transactions                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 7. DATA ACCESS LAYER (crud/)                                                    │
│    ──────────────────────────                                                   │
│    • Executes SQLAlchemy queries                                                │
│    • Handles pagination                                                         │
│    • Returns model instances                                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 8. DATABASE (PostgreSQL/MySQL)                                                  │
│    ─────────────────────────────                                                │
│    • Executes SQL                                                               │
│    • Returns resultset                                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 9. RESPONSE FORMATTING                                                          │
│    ─────────────────────                                                        │
│    • Data serialized via MsgSpec JSON                                           │
│    • Wrapped in standard response format: { code, msg, data }                   │
│    • Response headers set                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               CLIENT RESPONSE                                    │
│                    { "code": 200, "msg": "Success", "data": {...} }             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Middleware Pipeline

### Execution Order

Middleware executes in a specific order. **Request flows top-to-bottom; response flows bottom-to-top:**

```
                                  REQUEST
                                     │
    ┌────────────────────────────────┼────────────────────────────────┐
    │                                │                                │
    │    ┌───────────────────────────▼───────────────────────────┐    │
    │    │              ContextMiddleware                        │    │
    │    │   • X-Request-ID generation/validation                │    │
    │    └───────────────────────────┬───────────────────────────┘    │
    │                                │                                │
    │    ┌───────────────────────────▼───────────────────────────┐    │
    │    │               AccessMiddleware                        │    │
    │    │   • Request timing started                            │    │
    │    └───────────────────────────┬───────────────────────────┘    │
    │                                │                                │
    │    ┌───────────────────────────▼───────────────────────────┐    │
    │    │                I18nMiddleware                         │    │
    │    │   • Language detection                                │    │
    │    └───────────────────────────┬───────────────────────────┘    │
    │                                │                                │
    │    ┌───────────────────────────▼───────────────────────────┐    │
    │    │          AuthenticationMiddleware                     │    │
    │    │   (JwtAuthMiddleware backend)                         │    │
    │    │   • JWT validation                                    │    │
    │    │   • User loading                                      │    │
    │    └───────────────────────────┬───────────────────────────┘    │
    │                                │                                │
    │    ┌───────────────────────────▼───────────────────────────┐    │
    │    │               StateMiddleware                         │    │
    │    │   • Request state initialization                      │    │
    │    └───────────────────────────┬───────────────────────────┘    │
    │                                │                                │
    │    ┌───────────────────────────▼───────────────────────────┐    │
    │    │              OperaLogMiddleware                       │    │
    │    │   • Request body capture                              │    │
    │    │   • Async log queuing                                 │    │
    │    └───────────────────────────┬───────────────────────────┘    │
    │                                │                                │
    └────────────────────────────────┼────────────────────────────────┘
                                     │
                                     ▼
                              ROUTE HANDLER
                                     │
                                     ▼
                                  RESPONSE
```

### Middleware Configuration

Middleware is registered in `core/registrar.py`:

```python
def register_middleware(app: FastAPI) -> None:
    """Register middleware (execution order: bottom to top)"""
    
    # Opera log (last in, first out for response)
    app.add_middleware(OperaLogMiddleware)
    
    # State
    app.add_middleware(StateMiddleware)
    
    # JWT auth
    app.add_middleware(
        AuthenticationMiddleware,
        backend=JwtAuthMiddleware(),
        on_error=JwtAuthMiddleware.auth_exception_handler,
    )
    
    # I18n
    app.add_middleware(I18nMiddleware)
    
    # Access log
    app.add_middleware(AccessMiddleware)
    
    # Context (request ID)
    app.add_middleware(ContextMiddleware, plugins=[RequestIdPlugin()])
```

---

## Application Layers

### Pseudo 3-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    app/                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         API LAYER (api/)                                │    │
│  │  ────────────────────────────────────────                               │    │
│  │                                                                         │    │
│  │  @router.post("/users")                                                 │    │
│  │  async def create_user(                                                 │    │
│  │      request: Request,                                                  │    │
│  │      obj: CreateUserSchema,    ◄─── Request validation                  │    │
│  │      _: str = DependsRBAC      ◄─── Permission check                    │    │
│  │  ) -> ResponseModel:                                                    │    │
│  │      data = await user_service.create(obj)  ◄─── Delegate to service    │    │
│  │      return response_base.success(data=data)                            │    │
│  │                                                                         │    │
│  └───────────────────────────────────┬─────────────────────────────────────┘    │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                       SERVICE LAYER (service/)                          │    │
│  │  ──────────────────────────────────────────                             │    │
│  │                                                                         │    │
│  │  class UserService:                                                     │    │
│  │      async def create(self, obj: CreateUserSchema) -> User:             │    │
│  │          # Business logic                                               │    │
│  │          obj.password = hash_password(obj.password)                     │    │
│  │          # Delegate to CRUD                                             │    │
│  │          return await user_crud.create(db, obj)                         │    │
│  │                                                                         │    │
│  └───────────────────────────────────┬─────────────────────────────────────┘    │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        CRUD LAYER (crud/)                               │    │
│  │  ────────────────────────────────────────                               │    │
│  │                                                                         │    │
│  │  class UserCRUD(CRUDBase[User]):                                        │    │
│  │      async def create(self, db: AsyncSession, obj) -> User:             │    │
│  │          instance = User(**obj.model_dump())                            │    │
│  │          db.add(instance)                                               │    │
│  │          await db.commit()                                              │    │
│  │          return instance                                                │    │
│  │                                                                         │    │
│  └───────────────────────────────────┬─────────────────────────────────────┘    │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        MODEL LAYER (model/)                             │    │
│  │  ─────────────────────────────────────────                              │    │
│  │                                                                         │    │
│  │  class User(Base, IdMixin, DateTimeMixin):                              │    │
│  │      __tablename__ = "sys_user"                                         │    │
│  │                                                                         │    │
│  │      username: Mapped[str]                                              │    │
│  │      email: Mapped[str]                                                 │    │
│  │      password: Mapped[str]                                              │    │
│  │      roles: Mapped[list["Role"]] = relationship(...)                    │    │
│  │                                                                         │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Schema Layer (schema/)

Schemas handle data validation and serialization at API boundaries:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             SCHEMA LAYER                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────┐    ┌────────────────────────────┐              │
│  │    CREATE SCHEMAS          │    │    RESPONSE SCHEMAS        │              │
│  │  ───────────────────       │    │  ──────────────────        │              │
│  │                            │    │                            │              │
│  │  class CreateUserSchema:   │    │  class UserInfoSchema:     │              │
│  │      username: str         │    │      id: int               │              │
│  │      email: EmailStr       │    │      username: str         │              │
│  │      password: str         │    │      email: str            │              │
│  │                            │    │      created_time: datetime│              │
│  └────────────────────────────┘    └────────────────────────────┘              │
│                                                                                 │
│  ┌────────────────────────────┐    ┌────────────────────────────┐              │
│  │    UPDATE SCHEMAS          │    │    QUERY SCHEMAS           │              │
│  │  ───────────────────       │    │  ──────────────────        │              │
│  │                            │    │                            │              │
│  │  class UpdateUserSchema:   │    │  class UserQuerySchema:    │              │
│  │      username: str | None  │    │      username: str | None  │              │
│  │      email: str | None     │    │      status: int | None    │              │
│  │                            │    │      page: int = 1         │              │
│  └────────────────────────────┘    └────────────────────────────┘              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Database Architecture

### Entity Relationship Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ADMIN MODULE ENTITIES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐            │
│  │   sys_user   │────────▶│sys_user_role │◀────────│   sys_role   │            │
│  ├──────────────┤   1:N   ├──────────────┤   N:1   ├──────────────┤            │
│  │ id           │         │ user_id      │         │ id           │            │
│  │ username     │         │ role_id      │         │ name         │            │
│  │ password     │         └──────────────┘         │ code         │            │
│  │ email        │                                  │ status       │            │
│  │ dept_id ─────┼──┐                               └──────┬───────┘            │
│  │ status       │  │                                      │                    │
│  └──────────────┘  │                                      │                    │
│                    │                                      │ 1:N                │
│                    │                                      ▼                    │
│                    │       ┌──────────────┐         ┌──────────────┐           │
│                    │       │sys_role_menu │◀────────│   sys_menu   │           │
│                    │       ├──────────────┤   N:1   ├──────────────┤           │
│                    │       │ role_id      │         │ id           │           │
│                    │       │ menu_id      │         │ title        │           │
│                    │       └──────────────┘         │ path         │           │
│                    │                                │ perms        │           │
│                    │                                │ parent_id    │           │
│                    │                                └──────────────┘           │
│                    │                                                           │
│                    │  N:1                                                      │
│                    ▼                                                           │
│            ┌──────────────┐                                                    │
│            │   sys_dept   │◀────────┐                                          │
│            ├──────────────┤         │                                          │
│            │ id           │         │ parent_id (self-ref)                     │
│            │ name         │─────────┘                                          │
│            │ parent_id    │                                                    │
│            │ sort         │                                                    │
│            └──────────────┘                                                    │
│                                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Database Connection Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ASYNC DATABASE LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                        create_async_engine()                           │     │
│  │  ─────────────────────────────────────────────                         │     │
│  │  • pool_size: 10        (base connections)                             │     │
│  │  • max_overflow: 20     (extra connections under load)                 │     │
│  │  • pool_timeout: 30     (wait time for connection)                     │     │
│  │  • pool_recycle: 3600   (connection lifetime)                          │     │
│  │  • pool_pre_ping: True  (verify connection health)                     │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │                                        │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                        async_sessionmaker()                            │     │
│  │  ───────────────────────────────────────────                           │     │
│  │  • autoflush: False     (explicit control)                             │     │
│  │  • expire_on_commit: False  (keep data after commit)                   │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │                                        │
│                      ┌─────────────────┴─────────────────┐                      │
│                      │                                   │                      │
│                      ▼                                   ▼                      │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐      │
│  │          get_db()               │   │    get_db_transaction()         │      │
│  │  ─────────────────────────      │   │  ─────────────────────────      │      │
│  │  • Yields session               │   │  • Yields session with          │      │
│  │  • Auto closes                  │   │    automatic transaction        │      │
│  │  • Manual commit required       │   │  • Auto commit on success       │      │
│  │                                 │   │  • Auto rollback on error       │      │
│  │  CurrentSession = Depends(...)  │   │  CurrentSessionTransaction =    │      │
│  └─────────────────────────────────┘   │      Depends(...)               │      │
│                                        └─────────────────────────────────┘      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Plugin System

### Plugin Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PLUGIN SYSTEM                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         Plugin Discovery                               │     │
│  │  ─────────────────────────────────────                                 │     │
│  │  1. Scan plugin/ directory for subdirectories                          │     │
│  │  2. Look for plugin.toml in each subdirectory                          │     │
│  │  3. Parse plugin metadata (name, version, dependencies)                │     │
│  │  4. Install requirements.txt if present                                │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                        │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         Plugin Structure                               │     │
│  │  ──────────────────────────────────                                    │     │
│  │                                                                        │     │
│  │  plugin/                                                               │     │
│  │  └── my_plugin/                                                        │     │
│  │      ├── plugin.toml        # Plugin metadata                          │     │
│  │      ├── requirements.txt   # Optional dependencies                    │     │
│  │      ├── __init__.py                                                   │     │
│  │      ├── api/               # API endpoints                            │     │
│  │      │   ├── __init__.py                                               │     │
│  │      │   └── v1/                                                       │     │
│  │      │       ├── __init__.py                                           │     │
│  │      │       └── my_resource.py                                        │     │
│  │      ├── crud/              # Database operations                      │     │
│  │      ├── model/             # SQLAlchemy models                        │     │
│  │      ├── schema/            # Pydantic schemas                         │     │
│  │      └── service/           # Business logic                           │     │
│  │                                                                        │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                        │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         Router Integration                             │     │
│  │  ────────────────────────────────────                                  │     │
│  │                                                                        │     │
│  │  def build_final_router():                                             │     │
│  │      router = APIRouter(prefix="/api/v1")                              │     │
│  │                                                                        │     │
│  │      # Core app routes                                                 │     │
│  │      router.include_router(admin_router)                               │     │
│  │      router.include_router(task_router)                                │     │
│  │                                                                        │     │
│  │      # Plugin routes (auto-discovered)                                 │     │
│  │      for plugin in get_plugins():                                      │     │
│  │          plugin_router = import_plugin_router(plugin)                  │     │
│  │          router.include_router(plugin_router)                          │     │
│  │                                                                        │     │
│  │      return router                                                     │     │
│  │                                                                        │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Available Plugins

| Plugin | Description |
|--------|-------------|
| `code_generator` | Auto-generates api/crud/model/schema/service from table definitions |
| `oauth2` | GitHub, Google, Linux-DO OAuth2 authentication |
| `email` | SMTP email sending with captcha support |
| `dict` | System dictionary management |
| `config` | Dynamic configuration storage |
| `notice` | User notifications system |

---

## AI Agent Architecture

### PTC-Agent Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PTC-AGENT ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                           USER REQUEST                                 │     │
│  │                   "Create a new FastAPI endpoint"                      │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │                                        │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         MAIN AGENT (agent.py)                          │     │
│  │  ─────────────────────────────────────────────                         │     │
│  │  • Processes user request                                              │     │
│  │  • Determines required tools                                           │     │
│  │  • Generates executable code (PTC approach)                            │     │
│  │  • Coordinates subagents                                               │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │                                        │
│                    ┌───────────────────┼───────────────────┐                    │
│                    │                   │                   │                    │
│                    ▼                   ▼                   ▼                    │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐     │
│  │   CODE SUBAGENT      │ │  BROWSER SUBAGENT    │ │  RESEARCH SUBAGENT   │     │
│  │  ─────────────────   │ │  ─────────────────   │ │  ─────────────────   │     │
│  │  • File operations   │ │  • Web browsing      │ │  • Information       │     │
│  │  • Code editing      │ │  • Screenshot        │ │    gathering         │     │
│  │  • Command execution │ │  • Form filling      │ │  • API calls         │     │
│  └──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘     │
│             │                        │                        │                  │
│             └────────────────────────┼────────────────────────┘                  │
│                                      │                                          │
│                                      ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         TOOL EXECUTION                                 │     │
│  │  ─────────────────────────────────────                                 │     │
│  │                                                                        │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │     │
│  │  │ read_file   │  │ write_file  │  │ run_command │  │ browser_nav │    │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │     │
│  │  │ search_code │  │ list_dir    │  │ ask_user    │  │ web_search  │    │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │     │
│  │                                                                        │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │                                        │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         SANDBOX (Daytona)                              │     │
│  │  ───────────────────────────────────────                               │     │
│  │  • Isolated execution environment                                      │     │
│  │  • File system access                                                  │     │
│  │  • Command execution                                                   │     │
│  │  • Security boundaries                                                 │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| **Sandbox** | `core/sandbox.py` | Daytona sandbox for isolated code execution |
| **MCP Registry** | `core/mcp_registry.py` | Model Context Protocol integration |
| **Session** | `core/session.py` | Agent session state management |
| **Security** | `core/security.py` | Execution security and permissions |
| **Tool Generator** | `core/tool_generator.py` | Dynamic tool code generation |

---

## Security Architecture

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────┐        ┌────────────────────┐        ┌───────────────┐  │
│  │      CLIENT        │        │      SERVER        │        │    REDIS      │  │
│  └─────────┬──────────┘        └─────────┬──────────┘        └───────┬───────┘  │
│            │                             │                           │          │
│            │  POST /auth/login           │                           │          │
│            │  {username, password}       │                           │          │
│            ├────────────────────────────▶│                           │          │
│            │                             │                           │          │
│            │                             │  Validate credentials     │          │
│            │                             │  ──────────────────────   │          │
│            │                             │                           │          │
│            │                             │  Generate JWT tokens      │          │
│            │                             │  ──────────────────────   │          │
│            │                             │    access_token (1 day)   │          │
│            │                             │    refresh_token (7 days) │          │
│            │                             │                           │          │
│            │                             │  Store session in Redis   │          │
│            │                             ├──────────────────────────▶│          │
│            │                             │                           │          │
│            │  {access_token,             │                           │          │
│            │   refresh_token}            │                           │          │
│            │◀────────────────────────────┤                           │          │
│            │                             │                           │          │
│            │                             │                           │          │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│            │                             │                           │          │
│            │  GET /api/v1/users          │                           │          │
│            │  Authorization: Bearer xxx  │                           │          │
│            ├────────────────────────────▶│                           │          │
│            │                             │                           │          │
│            │                             │  Validate JWT in Redis    │          │
│            │                             ├──────────────────────────▶│          │
│            │                             │◀──────────────────────────┤          │
│            │                             │                           │          │
│            │                             │  Load user, check RBAC    │          │
│            │                             │  ──────────────────────   │          │
│            │                             │                           │          │
│            │  {users: [...]}             │                           │          │
│            │◀────────────────────────────┤                           │          │
│            │                             │                           │          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### RBAC (Role-Based Access Control)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              RBAC FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         INCOMING REQUEST                               │     │
│  │               GET /api/v1/users  (requires: sys:user:list)             │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │                                        │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    1. PATH WHITELIST CHECK                             │     │
│  │  ─────────────────────────────────────────                             │     │
│  │  If path in TOKEN_REQUEST_PATH_EXCLUDE → ALLOW                         │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │ Not in whitelist                       │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    2. JWT VALIDATION CHECK                             │     │
│  │  ─────────────────────────────────────────                             │     │
│  │  If not request.auth.scopes → DENY (TokenError)                        │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │ Valid token                            │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    3. SUPERUSER CHECK                                  │     │
│  │  ─────────────────────────────                                         │     │
│  │  If request.user.is_superuser → ALLOW                                  │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │ Not superuser                          │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    4. ROLE ASSIGNMENT CHECK                            │     │
│  │  ─────────────────────────────────────────                             │     │
│  │  If no roles assigned or all disabled → DENY                           │     │
│  └─────────────────────────────────────┬──────────────────────────────────┘     │
│                                        │ Has active roles                       │
│                                        ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    5. MENU PERMISSION CHECK                            │     │
│  │  ──────────────────────────────────────────                            │     │
│  │  path_auth_perm = "sys:user:list"                                      │     │
│  │                                                                        │     │
│  │  For each role:                                                        │     │
│  │      For each menu in role.menus:                                      │     │
│  │          If menu.perms contains path_auth_perm → ALLOW                 │     │
│  │                                                                        │     │
│  │  If not found → DENY (AuthorizationError)                              │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

- **[Getting Started](./getting-started.md)** - Installation and first run
- **[Backend Documentation](./backend/README.md)** - Detailed module reference
- **[API Reference](./backend/app/admin/api.md)** - API endpoint documentation

---

*Last Updated: December 2024*
