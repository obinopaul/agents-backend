# Standalone Scripts Guide

This guide explains how to write Python scripts that interact directly with the backend database models outside of the FastAPI application context.

## Quick Start

```python
#!/usr/bin/env python
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

async def main():
    # CRITICAL: Load all models before importing individual models
    from backend import load_all_models
    load_all_models()
    
    # Now you can import models
    from backend.app.admin.model.user import User
    from backend.database.db import async_db_session
    
    async with async_db_session() as session:
        # Your database operations here
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

## Why `load_all_models()` is Required

SQLAlchemy models in this project use relationships (e.g., `User.api_keys`). When you import a single model like `User`, SQLAlchemy tries to resolve these relationships but may fail if the related models (like `APIKey`) haven't been imported yet.

**Error you'll see without it:**

```text
expression 'APIKey' failed to locate a name ('APIKey')
```

The `load_all_models()` function (defined in `backend/__init__.py`) imports all models at once, ensuring SQLAlchemy can resolve all relationships.

## Model Field Gotchas

### User Model - `salt` Field

The `User` model has a `salt` field that must be explicitly passed, even though it's optional:

```python
# ❌ This will fail
new_user = User(username="test", nickname="Test", password="hash")

# ✅ This works
new_user = User(
    username="test",
    nickname="Test", 
    password="hash",
    salt=None  # Must be explicitly passed
)
```

**Why?** The field is defined as `Mapped[bytes | None]` but without a `default=None` in the column definition. SQLAlchemy's dataclass-style models require all non-defaulted fields to be passed.

## Example: Creating a User

See the complete example at [`backend/tests/create_test_user.py`](../../backend/tests/create_test_user.py).

Key points:

1. Call `load_all_models()` first
2. Use `async_db_session()` for database operations
3. Hash passwords with `pwdlib` (bcrypt embeds salt in hash)
4. Pass `salt=None` explicitly to User constructor

## Common Patterns

### Database Session

```python
from backend.database.db import async_db_session

async with async_db_session() as session:
    # session is an AsyncSession
    result = await session.execute(query)
    await session.commit()
```

### Querying Users

```python
from sqlalchemy import select
from backend.app.admin.model.user import User

async with async_db_session() as session:
    stmt = select(User).where(User.username == "admin")
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
```

### Password Hashing

```python
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

hasher = PasswordHash((BcryptHasher(),))
hashed = hasher.hash("plaintext_password")
# Result: $2b$12$... (bcrypt hash with embedded salt)
```

## Related Documentation

- [Environment Variables](./environment-variables.md) - Database configuration
- [Database Schema](../api-contracts/database.md) - Table definitions
- [API Endpoints](./api-endpoints.md) - REST API reference
