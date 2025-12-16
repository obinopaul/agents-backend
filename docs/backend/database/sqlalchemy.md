# SQLAlchemy Configuration

This document provides detailed documentation for the async SQLAlchemy setup in `backend/database/db.py`.

---

## Overview

The database layer uses **SQLAlchemy 2.0** with async support for non-blocking database operations.

---

## Supported Databases

| Database | Driver | Connection String |
|----------|--------|-------------------|
| PostgreSQL | `asyncpg` | `postgresql+asyncpg://user:pass@host:port/db` |
| MySQL | `asyncmy` | `mysql+asyncmy://user:pass@host:port/db?charset=utf8mb4` |

---

## Connection URL Creation

```python
def create_database_url(*, unittest: bool = False) -> URL:
    """Create SQLAlchemy database URL"""
    url = URL.create(
        drivername='mysql+asyncmy' if DATABASE_TYPE == 'mysql' else 'postgresql+asyncpg',
        username=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        database=settings.DATABASE_SCHEMA if not unittest else f'{settings.DATABASE_SCHEMA}_test',
    )
    
    # MySQL-specific: add charset
    if DATABASE_TYPE == 'mysql':
        url.update_query_dict({'charset': settings.DATABASE_CHARSET})
    
    return url
```

---

## Async Engine Configuration

```python
engine = create_async_engine(
    url,
    echo=settings.DATABASE_ECHO,           # Log SQL statements
    echo_pool=settings.DATABASE_POOL_ECHO, # Log pool checkouts
    future=True,                            # Use 2.0 style
    
    # Connection Pool Settings
    pool_size=10,           # Base number of connections
    max_overflow=20,        # Extra connections under load
    pool_timeout=30,        # Wait time for connection
    pool_recycle=3600,      # Recycle connections every hour
    pool_pre_ping=True,     # Verify connections before use
    pool_use_lifo=False,    # FIFO connection usage
)
```

### Pool Configuration Guide

| Setting | Low Traffic | Medium Traffic | High Traffic |
|---------|-------------|----------------|--------------|
| `pool_size` | 5 | 10 | 20+ |
| `max_overflow` | 10 | 20 | 40+ |
| `pool_timeout` | 60 | 30 | 15 |
| `pool_recycle` | 7200 | 3600 | 1800 |
| `pool_pre_ping` | False | True | True |
| `pool_use_lifo` | False | False | True |

---

## Session Factory

```python
db_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,        # Explicit flush control
    expire_on_commit=False, # Keep data after commit
)
```

**Why these settings?**

- `autoflush=False`: Prevents unexpected database writes during reads
- `expire_on_commit=False`: Avoids lazy loading issues after commit

---

## Dependency Injection

### get_db() - Standard Session

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (no auto-commit)"""
    async with async_db_session() as session:
        yield session

# Type alias for injection
CurrentSession = Annotated[AsyncSession, Depends(get_db)]
```

**Usage:**

```python
from backend.database.db import CurrentSession

@router.get("/users/{user_id}")
async def get_user(user_id: int, db: CurrentSession):
    user = await db.get(User, user_id)
    return user
```

### get_db_transaction() - Session with Transaction

```python
async def get_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """Get session with automatic transaction management"""
    async with async_db_session.begin() as session:
        yield session
    # Auto-commits on success, auto-rollbacks on exception

# Type alias for injection
CurrentSessionTransaction = Annotated[AsyncSession, Depends(get_db_transaction)]
```

**Usage:**

```python
from backend.database.db import CurrentSessionTransaction

@router.post("/users")
async def create_user(data: CreateUserSchema, db: CurrentSessionTransaction):
    user = User(**data.model_dump())
    db.add(user)
    # No explicit commit needed - auto-commits on function return
    return user
```

---

## Session Usage Patterns

### Pattern 1: Read Operations

```python
async def get_users(db: CurrentSession):
    result = await db.execute(
        select(User).where(User.status == 1)
    )
    return result.scalars().all()
```

### Pattern 2: Write with Manual Commit

```python
async def create_user(db: CurrentSession, data: CreateUserSchema):
    user = User(**data.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

### Pattern 3: Transaction with Auto-Commit

```python
async def transfer_funds(db: CurrentSessionTransaction, from_id: int, to_id: int, amount: float):
    from_account = await db.get(Account, from_id)
    to_account = await db.get(Account, to_id)
    
    from_account.balance -= amount
    to_account.balance += amount
    
    # Auto-commits if no exception raised
```

### Pattern 4: Explicit Transaction Block

```python
async def complex_operation(db: CurrentSession):
    async with db.begin():
        # Multiple operations
        await db.execute(update(User).where(...).values(...))
        await db.execute(insert(Log).values(...))
        # Auto-commits at end of block
```

---

## Table Management

### Create Tables

```python
async def create_tables() -> None:
    """Create all tables defined in MappedBase"""
    async with async_engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)
```

### Drop Tables

```python
async def drop_tables() -> None:
    """Drop all tables (CAUTION: Data loss!)"""
    async with async_engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.drop_all)
```

---

## UUID Compatibility

```python
def uuid4_str() -> str:
    """Generate UUID as string for database compatibility"""
    return str(uuid4())
```

Use this when the database engine doesn't natively support UUID types.

---

## Connection Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        REQUEST HANDLING                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────┐
                   │   Depends(get_db)       │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │  async_db_session()     │
                   │  (session factory)      │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │   Connection Pool       │
                   │  ─────────────────      │
                   │  [conn1][conn2][...]    │
                   │       │                 │
                   │       ▼                 │
                   │   Acquire connection    │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │     AsyncSession        │
                   │  ─────────────────      │
                   │  • Execute queries      │
                   │  • Track changes        │
                   │  • Buffer operations    │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │     ROUTE HANDLER       │
                   │  ─────────────────      │
                   │  async def handler(     │
                   │      db: CurrentSession │
                   │  ):                     │
                   │      ...                │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │   Session closes        │
                   │   Connection returns    │
                   │   to pool               │
                   └─────────────────────────┘
```

---

## Global Instances

```python
# Database connection URL
SQLALCHEMY_DATABASE_URL = create_database_url()

# Async engine and session factory (singletons)
async_engine, async_db_session = create_async_engine_and_session(SQLALCHEMY_DATABASE_URL)

# Dependency injection type aliases
CurrentSession = Annotated[AsyncSession, Depends(get_db)]
CurrentSessionTransaction = Annotated[AsyncSession, Depends(get_db_transaction)]
```

---

## Error Handling

```python
try:
    async with async_db_session() as session:
        result = await session.execute(query)
except SQLAlchemyError as e:
    log.error(f"Database error: {e}")
    raise
```

---

## Related Documentation

- [Redis Configuration](./redis.md) - Cache and session storage
- [Base Models](../common/models.md) - SQLAlchemy model mixins
- [Configuration](../core/configuration.md) - Database settings

---

*Last Updated: December 2024*
