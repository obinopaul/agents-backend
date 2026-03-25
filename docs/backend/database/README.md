# Database Module

The `database/` module provides the data persistence layer using SQLAlchemy (async) and Redis.

---

## Directory Structure

```
database/
├── __init__.py           # Package exports
├── db.py                 # Async SQLAlchemy engine & sessions
└── redis.py              # Redis client singleton
```

---

## Module Overview

| File | Size | Description |
|------|------|-------------|
| `db.py` | ~115 lines | Async database engine, session factory, dependency injection |
| `redis.py` | ~77 lines | Redis client with connection management |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────┴─────────────────────┐
            │                                           │
            ▼                                           ▼
┌─────────────────────────────────┐    ┌─────────────────────────────────┐
│         SQLAlchemy (db.py)      │    │         Redis (redis.py)        │
├─────────────────────────────────┤    ├─────────────────────────────────┤
│                                 │    │                                 │
│  ┌───────────────────────────┐  │    │  ┌───────────────────────────┐  │
│  │     AsyncEngine           │  │    │  │      RedisCli             │  │
│  │  ─────────────────────    │  │    │  │  ─────────────────────    │  │
│  │  • Connection pooling     │  │    │  │  • Async operations       │  │
│  │  • MySQL/PostgreSQL       │  │    │  │  • Health checks          │  │
│  │  • Echo/debug modes       │  │    │  │  • Key prefix utilities   │  │
│  └───────────────────────────┘  │    │  └───────────────────────────┘  │
│                                 │    │                                 │
│  ┌───────────────────────────┐  │    │  Usage:                         │
│  │   async_sessionmaker      │  │    │  • Token storage               │
│  │  ─────────────────────    │  │    │  • Session caching             │
│  │  • AsyncSession factory   │  │    │  • Rate limiting               │
│  │  • Auto-flush disabled    │  │    │  • Celery broker (dev)         │
│  │  • Expire on commit off   │  │    │  • Operation log queue         │
│  └───────────────────────────┘  │    │                                 │
│                                 │    │                                 │
└─────────────────────────────────┘    └─────────────────────────────────┘
```

---

## Files Documentation

### [db.py - SQLAlchemy](./sqlalchemy.md)

Async SQLAlchemy database engine and session management.

**Key Features:**
- MySQL and PostgreSQL support
- Async engine with connection pooling
- Session factory with dependency injection
- Table creation utilities

### [redis.py - Redis](./redis.md)

Redis client singleton for caching and queues.

**Key Features:**
- Async Redis client
- Connection health checking
- Key prefix operations
- Singleton pattern

---

## Quick Usage

### Database Session

```python
from backend.database.db import CurrentSession

@router.get("/items")
async def get_items(db: CurrentSession):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

### Redis Client

```python
from backend.database.redis import redis_client

# Set value
await redis_client.set("key", "value", ex=3600)

# Get value
value = await redis_client.get("key")

# Delete by prefix
await redis_client.delete_prefix("fba:token:")
```

---

## Configuration

### Database Settings (from conf.py)

```python
DATABASE_TYPE = "postgresql"  # or "mysql"
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_USER = "postgres"
DATABASE_PASSWORD = "password"
DATABASE_SCHEMA = "fba"
```

### Redis Settings (from conf.py)

```python
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = ""
REDIS_DATABASE = 0
REDIS_TIMEOUT = 5
```

---

## Initialization Flow

```
APPLICATION STARTUP
        │
        ▼
┌───────────────────────┐
│   create_tables()     │    Creates all SQLAlchemy tables
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  redis_client.open()  │    Verifies Redis connection
└───────────────────────┘
```

---

## Related Documentation

- [SQLAlchemy Reference](./sqlalchemy.md) - Detailed engine and session docs
- [Redis Reference](./redis.md) - Redis client utilities
- [Configuration](../core/configuration.md) - Database and Redis settings

---

*Last Updated: December 2024*
