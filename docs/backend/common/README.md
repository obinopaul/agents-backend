# Common Module

The `common/` module contains shared utilities, base classes, and cross-cutting concerns used throughout the application.

---

## Directory Structure

```
common/
├── __init__.py           # Package initialization
├── context.py            # Request context variables
├── dataclasses.py        # Data class definitions
├── enums.py              # Enumeration types
├── i18n.py               # Internationalization
├── log.py                # Logging configuration
├── model.py              # Base SQLAlchemy models & mixins
├── pagination.py         # Pagination utilities
├── queue.py              # Async queue utilities
├── schema.py             # Base Pydantic schemas
│
├── exception/            # Exception handling
│   ├── __init__.py
│   ├── errors.py         # Custom exception classes
│   └── exception_handler.py  # Global exception handlers
│
├── response/             # Response formatting
│   ├── __init__.py
│   ├── response_code.py  # HTTP status codes
│   └── response_schema.py  # Response schemas
│
├── security/             # Security subsystem
│   ├── __init__.py
│   ├── jwt.py            # JWT token management
│   ├── rbac.py           # Role-based access control
│   └── permission.py     # Permission utilities
│
└── socketio/             # WebSocket integration
    ├── __init__.py
    ├── server.py         # Socket.IO server
    └── actions.py        # Event handlers
```

---

## Module Overview

| File/Directory | Purpose |
|----------------|---------|
| [model.py](./models.md) | Base SQLAlchemy models and mixin classes |
| [schema.py](./schemas.md) | Base Pydantic schemas |
| [enums.py](./enums.md) | Application-wide enumerations |
| [exception/](./exception/README.md) | Exception handling and custom errors |
| [response/](./response/README.md) | Standardized API responses |
| [security/](./security/README.md) | JWT, RBAC, and permissions |
| [socketio/](./socketio/README.md) | WebSocket server and events |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         COMMON MODULE                                │
│                 (Shared Across All Application)                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    │                             │                             │
    ▼                             ▼                             ▼
┌─────────────┐          ┌─────────────────┐          ┌─────────────┐
│   Models    │          │   Utilities     │          │   Security  │
│ ─────────── │          │ ─────────────── │          │ ─────────── │
│ • MappedBase│          │ • context       │          │ • jwt       │
│ • Base      │          │ • log           │          │ • rbac      │
│ • Mixins    │          │ • pagination    │          │ • permission│
│ • id_key    │          │ • queue         │          │             │
└─────────────┘          │ • i18n          │          └─────────────┘
                         └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────┐          ┌─────────────────┐          ┌─────────────┐
│  Schemas    │          │   Exception     │          │  Response   │
│ ─────────── │          │ ─────────────── │          │ ─────────── │
│ • SchemaBase│          │ • errors        │          │ • codes     │
│ • Custom    │          │ • handlers      │          │ • schemas   │
└─────────────┘          └─────────────────┘          └─────────────┘
```

---

## Base Models (model.py)

### Model Inheritance Hierarchy

```
                    ┌─────────────────────┐
                    │   DeclarativeBase   │   SQLAlchemy base
                    │     (SQLAlchemy)    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     MappedBase      │   + AsyncAttrs
                    │                     │   + Auto tablename
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │DataClassBase│     │  Mixins     │     │  Custom     │
   │             │     │ ─────────── │     │  Models     │
   │+ MappedAs   │     │ DateTimeMixin│    │             │
   │  Dataclass  │     │ UserMixin   │     │             │
   └──────┬──────┘     └─────────────┘     └─────────────┘
          │
          ▼
   ┌─────────────┐
   │    Base     │   + DateTimeMixin
   │             │   (most models inherit from this)
   └─────────────┘
```

### Key Components

| Class | Description |
|-------|-------------|
| `MappedBase` | Root declarative base with auto-tablename |
| `DataClassBase` | Adds dataclass integration |
| `Base` | Standard base with DateTimeMixin |
| `DateTimeMixin` | Adds `created_time`, `updated_time` |
| `UserMixin` | Adds `created_by`, `updated_by` |
| `id_key` | Primary key type (autoincrement or snowflake) |

---

## Enumerations (enums.py)

| Enum | Type | Values |
|------|------|--------|
| `StatusType` | IntEnum | `disable=0`, `enable=1` |
| `MethodType` | StrEnum | `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS` |
| `MenuType` | IntEnum | `directory`, `menu`, `button`, `embedded`, `link` |
| `DataBaseType` | StrEnum | `mysql`, `postgresql` |
| `PrimaryKeyType` | StrEnum | `autoincrement`, `snowflake` |
| `LoginLogStatusType` | IntEnum | `fail=0`, `success=1` |
| `FileType` | StrEnum | `image`, `video` |
| `PluginType` | StrEnum | `zip`, `git` |

---

## Quick Usage Examples

### Using Base Model

```python
from backend.common.model import Base, id_key

class User(Base):
    """User table"""
    __tablename__ = "sys_user"
    
    id: Mapped[id_key]
    username: Mapped[str]
    email: Mapped[str]
    # created_time and updated_time inherited from Base
```

### Using Enums

```python
from backend.common.enums import StatusType, MethodType

if user.status == StatusType.enable:
    print("User is active")

if request.method == MethodType.POST:
    validate_body(request)
```

### Using Context

```python
from backend.common.context import ctx

# In route handler
current_user_id = ctx.user_id
current_permission = ctx.permission
```

---

## Subdirectory Documentation

| Directory | Documentation |
|-----------|---------------|
| `exception/` | [Exception Handling](./exception/README.md) |
| `response/` | [Response Formatting](./response/README.md) |
| `security/` | [Security System](./security/README.md) |
| `socketio/` | [WebSocket Integration](./socketio/README.md) |

---

## Related Documentation

- [Core Configuration](../core/README.md) - Settings used by common module
- [Database Layer](../database/README.md) - Model integration with database

---

*Last Updated: December 2024*
