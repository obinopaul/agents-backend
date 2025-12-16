# App Module

The `app/` directory contains the main application modules that implement business functionality.

---

## Directory Structure

```
app/
├── __init__.py              # Package initialization
├── router.py                # Main router aggregation
│
├── admin/                   # Admin module (core functionality)
│   ├── api/                 # REST endpoints (22 files)
│   ├── schema/              # Pydantic schemas (12 files)
│   ├── service/             # Business logic (12 files)
│   ├── crud/                # Database operations (10 files)
│   ├── model/               # SQLAlchemy models (11 files)
│   ├── tests/               # Unit tests
│   └── utils/               # Admin utilities
│
└── task/                    # Celery task module
    ├── celery.py            # Celery app configuration
    ├── database.py          # Task result database
    ├── api/                 # Task API endpoints
    ├── crud/                # Task CRUD
    ├── model/               # Task models
    ├── schema/              # Task schemas
    ├── service/             # Task services
    ├── tasks/               # Task definitions
    └── utils/               # Task utilities
```

---

## Module Overview

| Module | Description | Documentation |
|--------|-------------|---------------|
| **admin/** | Core admin functionality (users, roles, menus) | [Admin Documentation](./admin/README.md) |
| **task/** | Celery background task system | [Task Documentation](./task/README.md) |

---

## Router Aggregation

The `router.py` file aggregates all module routes:

```python
# app/router.py
from fastapi import APIRouter
from backend.app.admin.api import router as admin_router
from backend.app.task.api import router as task_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(task_router)
```

---

## Related Documentation

- [Admin Module](./admin/README.md) - User, role, menu management
- [Task Module](./task/README.md) - Celery tasks

---

*Last Updated: December 2024*
