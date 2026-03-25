# Alembic Migrations

The `alembic/` directory manages database schema migrations using Alembic.

---

## Directory Structure

```
alembic/
├── env.py                   # Migration environment configuration
├── script.py.mako           # Migration script template
├── versions/                # Migration scripts
│   ├── 001_initial.py
│   ├── 002_add_user_fields.py
│   └── ...
└── alembic.ini              # Alembic configuration (at backend root)
```

---

## Configuration

### alembic.ini

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic
```

### env.py

The environment file configures async migrations:

```python
from backend.database.db import SQLALCHEMY_DATABASE_URL
from backend.common.model import MappedBase

config.set_main_option("sqlalchemy.url", str(SQLALCHEMY_DATABASE_URL))
target_metadata = MappedBase.metadata
```

---

## Commands

### Create Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add user email field"

# Create empty migration
alembic revision -m "custom migration"
```

### Run Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade by one revision
alembic upgrade +1

# Upgrade to specific revision
alembic upgrade abc123
```

### Rollback

```bash
# Downgrade by one
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade abc123

# Downgrade to beginning
alembic downgrade base
```

### Status

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

---

## Migration Script Example

```python
# versions/002_add_user_email.py
"""add user email field

Revision ID: abc123def456
Revises: 001_initial
Create Date: 2024-12-14 15:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = 'abc123def456'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sys_user', sa.Column('email', sa.String(100), nullable=True))
    op.create_index('ix_sys_user_email', 'sys_user', ['email'])


def downgrade() -> None:
    op.drop_index('ix_sys_user_email', 'sys_user')
    op.drop_column('sys_user', 'email')
```

---

## Best Practices

1. **Always review auto-generated migrations**
2. **Test migrations on development database first**
3. **Keep migrations atomic and reversible**
4. **Use descriptive migration messages**
5. **Backup database before production migrations**

---

*Last Updated: December 2024*
