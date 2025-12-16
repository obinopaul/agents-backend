# Application Registrar

The `registrar.py` module is the application factory that creates and configures the FastAPI instance with all components.

---

## Overview

The registrar follows the **Application Factory Pattern**, centralizing all FastAPI configuration in one place.

```python
from backend.core.registrar import register_app

app = register_app()  # Returns fully configured FastAPI instance
```

---

## Source Code Reference

**File:** `backend/core/registrar.py`  
**Lines:** ~220

---

## Main Functions

### register_app()

Creates and returns the fully configured FastAPI application.

```python
def register_app() -> FastAPI:
    """Register FastAPI application"""
    
    app = MyFastAPI(
        title=settings.FASTAPI_TITLE,
        version=__version__,
        description=settings.FASTAPI_DESCRIPTION,
        docs_url=settings.FASTAPI_DOCS_URL,
        redoc_url=settings.FASTAPI_REDOC_URL,
        openapi_url=settings.FASTAPI_OPENAPI_URL,
        default_response_class=MsgSpecJSONResponse,
        lifespan=register_init,
    )
    
    # Register all components
    register_logger()
    register_socket_app(app)
    register_static_file(app)
    register_middleware(app)
    register_router(app)
    register_page(app)
    register_exception(app)
    
    return app
```

---

### register_init() - Lifespan Context Manager

Manages application startup and shutdown events:

```python
@asynccontextmanager
async def register_init(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager"""
    
    # ═══════════════════════════════════════
    #              STARTUP
    # ═══════════════════════════════════════
    
    # 1. Create database tables (if not exist)
    await create_tables()
    
    # 2. Open Redis connection
    await redis_client.open()
    
    # 3. Initialize rate limiter
    await FastAPILimiter.init(
        redis=redis_client,
        prefix=settings.REQUEST_LIMITER_REDIS_PREFIX,
        http_callback=http_limit_callback,
    )
    
    # 4. Initialize Snowflake node
    await snowflake.init()
    
    # 5. Start operation log consumer task
    create_task(OperaLogMiddleware.consumer())
    
    yield  # Application runs here
    
    # ═══════════════════════════════════════
    #             SHUTDOWN
    # ═══════════════════════════════════════
    
    # 1. Release Snowflake node
    await snowflake.shutdown()
    
    # 2. Close Redis connection
    await redis_client.aclose()
```

**Startup Flow Diagram:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION STARTUP                             │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│  create_tables()      │    Create SQLAlchemy tables if not exist
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  redis_client.open()  │    Open async Redis connection
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  FastAPILimiter.init()│    Initialize rate limiting with Redis
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  snowflake.init()     │    Register Snowflake worker node
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  OperaLogMiddleware   │    Start async consumer for operation logs
│  .consumer()          │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  SERVER READY ✓       │
└───────────────────────┘
```

---

### register_logger()

Configures application logging:

```python
def register_logger() -> None:
    """Register logging"""
    setup_logging()      # Configure loguru
    set_custom_logfile() # Set up file handlers
```

---

### register_static_file()

Mounts static file directories:

```python
def register_static_file(app: FastAPI) -> None:
    """Register static file serving"""
    
    # Upload directory (always mounted)
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    app.mount('/static/upload', StaticFiles(directory=UPLOAD_DIR), name='upload')
    
    # Static assets (disabled in production)
    if settings.FASTAPI_STATIC_FILES:
        app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
```

**Static File Paths:**

| URL Path | Directory | Description |
|----------|-----------|-------------|
| `/static/upload/` | `backend/static/upload/` | User uploads |
| `/static/` | `backend/static/` | Static assets (dev only) |

---

### register_middleware()

Registers the middleware stack in execution order:

```python
def register_middleware(app: FastAPI) -> None:
    """Register middleware (execution order: bottom to top)"""
    
    # 6. Opera log (captures request/response)
    app.add_middleware(OperaLogMiddleware)
    
    # 5. State (initializes request.state)
    app.add_middleware(StateMiddleware)
    
    # 4. JWT auth (validates token, loads user)
    app.add_middleware(
        AuthenticationMiddleware,
        backend=JwtAuthMiddleware(),
        on_error=JwtAuthMiddleware.auth_exception_handler,
    )
    
    # 3. I18n (detects language)
    app.add_middleware(I18nMiddleware)
    
    # 2. Access log (logs request timing)
    app.add_middleware(AccessMiddleware)
    
    # 1. Context (request ID)
    app.add_middleware(
        ContextMiddleware,
        plugins=[RequestIdPlugin(validate=True)],
        default_error_response=MsgSpecJSONResponse(
            content={'code': 400, 'msg': 'BAD_REQUEST', 'data': None},
            status_code=400,
        ),
    )
```

**Middleware Execution Order:**

```
REQUEST ──┐
          │
          ▼
    ┌─────────────────┐
    │ 1. Context      │  ← First to execute on request
    ├─────────────────┤
    │ 2. Access       │
    ├─────────────────┤
    │ 3. I18n         │
    ├─────────────────┤
    │ 4. JWT Auth     │
    ├─────────────────┤
    │ 5. State        │
    ├─────────────────┤
    │ 6. Opera Log    │  ← Last to execute on request
    └─────────────────┘
          │
          ▼
     ROUTE HANDLER
          │
          ▼
    ┌─────────────────┐
    │ 6. Opera Log    │  ← First to execute on response
    ├─────────────────┤
    │ 5. State        │
    ├─────────────────┤
    │ 4. JWT Auth     │
    ├─────────────────┤
    │ 3. I18n         │
    ├─────────────────┤
    │ 2. Access       │
    ├─────────────────┤
    │ 1. Context      │  ← Last to execute on response
    └─────────────────┘
          │
          ▼
     RESPONSE ──┘
```

---

### register_router()

Aggregates and registers all API routes:

```python
def register_router(app: FastAPI) -> None:
    """Register routes"""
    
    # Add demo mode dependency if enabled
    dependencies = [Depends(demo_site)] if settings.DEMO_MODE else None
    
    # Build final router (includes plugins)
    router = build_final_router()
    app.include_router(router, dependencies=dependencies)
    
    # Ensure unique route names
    ensure_unique_route_names(app)
    
    # Simplify OpenAPI operation IDs
    simplify_operation_ids(app)
```

---

### register_page()

Enables pagination support:

```python
def register_page(app: FastAPI) -> None:
    """Register pagination support"""
    add_pagination(app)  # fastapi-pagination
```

---

### register_socket_app()

Mounts Socket.IO for WebSocket support:

```python
def register_socket_app(app: FastAPI) -> None:
    """Register Socket.IO application"""
    from backend.common.socketio.server import sio
    
    socket_app = socketio.ASGIApp(
        socketio_server=sio,
        other_asgi_app=app,
        socketio_path='/ws/socket.io',
    )
    app.mount('/ws', socket_app)
```

**WebSocket Endpoint:** `ws://host:port/ws/socket.io`

---

## CORS Configuration

The registrar includes a custom FastAPI subclass that handles CORS:

```python
class MyFastAPI(FastAPI):
    if settings.MIDDLEWARE_CORS:
        def build_middleware_stack(self) -> ASGIApp:
            return CORSMiddleware(
                super().build_middleware_stack(),
                allow_origins=settings.CORS_ALLOWED_ORIGINS,
                allow_credentials=True,
                allow_methods=['*'],
                allow_headers=['*'],
                expose_headers=settings.CORS_EXPOSE_HEADERS,
            )
```

---

## Complete Registration Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        register_app()                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    │                             │                             │
    ▼                             ▼                             ▼
┌─────────────┐          ┌─────────────────┐          ┌─────────────┐
│ Create      │          │ Set lifespan    │          │ Set default │
│ MyFastAPI   │          │ = register_init │          │ response    │
│ instance    │          │                 │          │ class       │
└──────┬──────┘          └─────────────────┘          └─────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Component Registration                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. register_logger()                                               │
│     └── Setup loguru logging                                        │
│                                                                     │
│  2. register_socket_app(app)                                        │
│     └── Mount Socket.IO at /ws                                      │
│                                                                     │
│  3. register_static_file(app)                                       │
│     └── Mount /static and /static/upload                            │
│                                                                     │
│  4. register_middleware(app)                                        │
│     └── Add 6 middleware in order                                   │
│                                                                     │
│  5. register_router(app)                                            │
│     └── Include all API routes + plugins                            │
│                                                                     │
│  6. register_page(app)                                              │
│     └── Enable pagination                                           │
│                                                                     │
│  7. register_exception(app)                                         │
│     └── Add global exception handlers                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────┐
                   │  Return FastAPI app     │
                   └─────────────────────────┘
```

---

## Related Documentation

- [Configuration](./configuration.md) - Settings used by registrar
- [Middleware](../middleware/README.md) - Registered middleware details
- [Plugin System](../plugin/README.md) - How plugins are discovered and routed

---

*Last Updated: December 2024*
