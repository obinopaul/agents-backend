# Core Module

The `core/` module contains the foundational configuration and application factory for the entire backend system.

---

## Directory Structure

```
core/
├── __init__.py           # Package initialization
├── conf.py               # Global settings (Settings class)
├── registrar.py          # FastAPI app factory
└── path_conf.py          # Path constants
```

---

## Module Overview

| File | Size | Description |
|------|------|-------------|
| `conf.py` | ~300 lines | Global configuration with 100+ settings |
| `registrar.py` | ~220 lines | FastAPI app creation and component registration |
| `path_conf.py` | ~15 lines | Base path and directory constants |

---

## Files Documentation

### [conf.py](./configuration.md) - Global Configuration

The central configuration hub using Pydantic Settings. All environment variables and application settings are defined here.

**Key Features:**
- Loads settings from `.env` file
- Type-safe configuration with Pydantic
- Environment-aware (dev/prod modes)
- Cached singleton pattern

### [registrar.py](./registrar.md) - Application Factory

Creates and configures the FastAPI application instance with all middleware, routes, and lifecycle events.

**Key Features:**
- Lifespan event management
- Middleware registration
- Router aggregation
- Static file serving

### [path_conf.py](./paths.md) - Path Configuration

Defines base paths for the application including static files and upload directories.

---

## Configuration Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION FLOW                            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────┐
                   │    .env file            │
                   │    ─────────────        │
                   │    ENVIRONMENT=dev      │
                   │    DATABASE_HOST=...    │
                   │    REDIS_HOST=...       │
                   │    TOKEN_SECRET_KEY=... │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │    Settings class       │
                   │    (conf.py)            │
                   │    ─────────────        │
                   │    • Load from .env     │
                   │    • Validate types     │
                   │    • Apply defaults     │
                   │    • Environment checks │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │    get_settings()       │
                   │    ─────────────        │
                   │    @lru_cache           │
                   │    Singleton instance   │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │    settings (global)    │
                   │    ─────────────        │
                   │    from backend.core    │
                   │        .conf import     │
                   │        settings         │
                   └─────────────────────────┘
```

---

## Application Factory Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                    register_app() FLOW                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────┐
        │              Create FastAPI Instance         │
        │  ─────────────────────────────────────       │
        │  MyFastAPI(                                  │
        │      title=settings.FASTAPI_TITLE,           │
        │      lifespan=register_init,                 │
        │      ...                                     │
        │  )                                           │
        └────────────────────┬────────────────────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
    ▼                        ▼                        ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ register_   │     │ register_       │     │ register_       │
│ logger()    │     │ static_file()   │     │ socket_app()    │
└─────────────┘     └─────────────────┘     └─────────────────┘
    │                        │                        │
    └────────────────────────┼────────────────────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
    ▼                        ▼                        ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ register_   │     │ register_       │     │ register_       │
│ middleware()│     │ router()        │     │ page()          │
└─────────────┘     └─────────────────┘     └─────────────────┘
                             │
                             ▼
                   ┌─────────────────────┐
                   │ register_exception()│
                   └─────────────────────┘
                             │
                             ▼
                   ┌─────────────────────┐
                   │ Return FastAPI app  │
                   └─────────────────────┘
```

---

## Related Documentation

- [Configuration Reference](./configuration.md) - Complete settings documentation
- [Registrar Reference](./registrar.md) - App factory details
- [Path Configuration](./paths.md) - Directory paths

---

*Last Updated: December 2024*
