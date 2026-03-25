# Admin Module

The `app/admin/` module implements the core administrative functionality including user management, role-based access control, menu system, and system monitoring.

---

## Directory Structure

```
admin/
├── __init__.py              # Package initialization
│
├── api/                     # REST endpoints (22 files)
│   └── v1/
│       ├── auth.py          # Authentication endpoints
│       ├── user.py          # User management
│       ├── role.py          # Role management
│       ├── menu.py          # Menu management
│       ├── dept.py          # Department management
│       └── ...              # Other endpoints
│
├── schema/                  # Pydantic schemas (12 files)
│   ├── user.py              # User DTOs
│   ├── role.py              # Role DTOs
│   ├── menu.py              # Menu DTOs
│   └── ...
│
├── service/                 # Business logic (12 files)
│   ├── user.py              # User service
│   ├── role.py              # Role service
│   ├── menu.py              # Menu service
│   └── ...
│
├── crud/                    # Database operations (10 files)
│   ├── user.py              # User CRUD
│   ├── role.py              # Role CRUD
│   ├── menu.py              # Menu CRUD
│   └── ...
│
├── model/                   # SQLAlchemy models (11 files)
│   ├── user.py              # User model
│   ├── role.py              # Role model
│   ├── menu.py              # Menu model
│   └── ...
│
├── tests/                   # Unit tests
│   └── ...
│
└── utils/                   # Admin utilities
    └── ...
```

---

## Pseudo 3-Tier Architecture Pattern

Each resource follows a consistent layered structure:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLIENT REQUEST                                    │
│                 POST /api/v1/auth/login                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                                │
│                      api/v1/auth.py                                  │
│  ─────────────────────────────────────                              │
│  @router.post("/login")                                              │
│  async def login(obj: AuthLoginSchema, db: CurrentSession):          │
│      return await auth_service.login(db, obj)                        │
│                                                                     │
│  Responsibilities:                                                   │
│  • HTTP routing and method handling                                  │
│  • Request validation (via Pydantic schemas)                         │
│  • Response formatting                                               │
│  • Dependency injection                                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                              │
│                    service/auth_service.py                           │
│  ─────────────────────────────────────                              │
│  class AuthService:                                                  │
│      async def login(self, db, obj):                                 │
│          user = await user_crud.get_by_username(db, obj.username)    │
│          if verify_password(obj.password, user.password):            │
│              token = create_access_token(user.id)                    │
│              return {"access_token": token}                          │
│                                                                     │
│  Responsibilities:                                                   │
│  • Business rule enforcement                                         │
│  • Transaction orchestration                                         │
│  • Cross-cutting concerns                                            │
│  • Service-to-service coordination                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                                 │
│                      crud/user.py                                    │
│  ─────────────────────────────────────                              │
│  class CRUDUser(CRUDBase):                                           │
│      async def get_by_username(self, db, username):                  │
│          result = await db.execute(                                  │
│              select(User).where(User.username == username)           │
│          )                                                          │
│          return result.scalars().first()                             │
│                                                                     │
│  Responsibilities:                                                   │
│  • Database queries (SQLAlchemy)                                     │
│  • ORM operations                                                    │
│  • Query optimization                                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA MODEL LAYER                                  │
│                      model/user.py                                   │
│  ─────────────────────────────────────                              │
│  class User(Base):                                                   │
│      __tablename__ = "sys_user"                                      │
│      id: Mapped[id_key]                                              │
│      username: Mapped[str]                                           │
│      password: Mapped[str]                                           │
│      ...                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Resources

### Users (`sys_user`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sys/users` | GET | List users with pagination |
| `/api/v1/sys/users/{pk}` | GET | Get user by ID |
| `/api/v1/sys/users` | POST | Create user |
| `/api/v1/sys/users/{pk}` | PUT | Update user |
| `/api/v1/sys/users/{pk}` | DELETE | Delete user |

### Roles (`sys_role`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sys/roles` | GET | List roles |
| `/api/v1/sys/roles/{pk}` | GET | Get role by ID |
| `/api/v1/sys/roles` | POST | Create role |
| `/api/v1/sys/roles/{pk}` | PUT | Update role |
| `/api/v1/sys/roles/{pk}/menus` | PUT | Assign menus to role |

### Menus (`sys_menu`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sys/menus` | GET | List menus (tree structure) |
| `/api/v1/sys/menus/{pk}` | GET | Get menu by ID |
| `/api/v1/sys/menus` | POST | Create menu |
| `/api/v1/sys/menus/{pk}` | PUT | Update menu |

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/login` | POST | User login |
| `/api/v1/auth/logout` | POST | User logout |
| `/api/v1/auth/token/refresh` | POST | Refresh access token |
| `/api/v1/auth/captcha` | GET | Get login captcha |

---

## Model Relationships

```
┌─────────────┐       ┌───────────────────┐       ┌─────────────┐
│    User     │──────▶│    UserRole       │◀──────│    Role     │
├─────────────┤  N:M  ├───────────────────┤  N:M  ├─────────────┤
│ id          │       │ user_id           │       │ id          │
│ username    │       │ role_id           │       │ name        │
│ nickname    │       └───────────────────┘       │ data_scope  │
│ email       │                                   │ status      │
│ is_superuser│       ┌───────────────────┐       └──────┬──────┘
│ is_staff    │       │    RoleMenu       │              │
│ status      │       ├───────────────────┤              │
│ dept_id ────┼──┐    │ role_id ──────────┼──────────────┘
└─────────────┘  │    │ menu_id           │
                 │    └─────────┬─────────┘
                 │              │
                 │              ▼
┌─────────────┐  │    ┌─────────────────┐
│    Dept     │◀─┘    │      Menu       │
├─────────────┤       ├─────────────────┤
│ id          │       │ id              │
│ name        │       │ title           │
│ parent_id   │       │ name            │
│ sort        │       │ parent_id       │
│ status      │       │ type            │
│ leader      │       │ perms           │
└─────────────┘       │ icon            │
                      │ path            │
                      │ component       │
                      │ status          │
                      └─────────────────┘
```

---

## Creating a New Resource

### Step 1: Create Model

```python
# model/article.py
from backend.common.model import Base, id_key

class Article(Base):
    """Article table"""
    __tablename__ = "sys_article"
    
    id: Mapped[id_key]
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"))
    status: Mapped[int] = mapped_column(default=1)
```

### Step 2: Create Schema

```python
# schema/article.py
from pydantic import BaseModel

class ArticleCreate(BaseModel):
    title: str
    content: str

class ArticleUpdate(ArticleCreate):
    status: int | None = None

class ArticleResponse(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    status: int
    created_time: datetime
```

### Step 3: Create CRUD

```python
# crud/article.py
from backend.common.crud import CRUDBase
from backend.app.admin.model.article import Article

class CRUDArticle(CRUDBase[Article]):
    pass

article_crud = CRUDArticle(Article)
```

### Step 4: Create Service

```python
# service/article.py
from backend.app.admin.crud.article import article_crud

class ArticleService:
    async def create(self, db, obj: ArticleCreate, author_id: int):
        return await article_crud.create(db, obj, author_id=author_id)
    
    async def get_list(self, db, page: int, size: int):
        return await article_crud.get_multi(db, page=page, size=size)

article_service = ArticleService()
```

### Step 5: Create API

```python
# api/v1/article.py
from fastapi import APIRouter

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.post("")
async def create_article(obj: ArticleCreate, db: CurrentSession):
    return await article_service.create(db, obj, author_id=1)

@router.get("")
async def list_articles(db: CurrentSession, page: int = 1, size: int = 20):
    return await article_service.get_list(db, page, size)
```

---

## Related Documentation

- [Common Module](../common/README.md) - Base models and schemas
- [Database Layer](../database/README.md) - SQLAlchemy configuration
- [Security](../common/security/README.md) - JWT and RBAC

---

*Last Updated: December 2024*
