# Plugin System

The `plugin/` module provides an extensible plugin architecture for adding modular functionality to the application.

---

## Directory Structure

```
plugin/
├── __init__.py              # Package initialization
├── tools.py                 # Plugin discovery & routing (~16KB)
│
├── code_generator/          # Code generation plugin
│   ├── plugin.toml          # Plugin metadata
│   ├── requirements.txt     # Dependencies
│   ├── api/                 # REST endpoints
│   ├── crud/                # Database operations
│   ├── model/               # SQLAlchemy models
│   ├── schema/              # Pydantic schemas
│   ├── service/             # Business logic
│   ├── templates/           # Code templates
│   └── utils/               # Utilities
│
├── oauth2/                  # OAuth2 authentication plugin
│   ├── plugin.toml
│   ├── requirements.txt
│   ├── api/
│   ├── crud/
│   ├── model/
│   ├── schema/
│   └── service/
│
├── email/                   # Email sending plugin
│   ├── plugin.toml
│   ├── api/
│   ├── crud/
│   ├── model/
│   ├── schema/
│   └── service/
│
├── dict/                    # Dictionary management plugin
│   └── ...
│
├── config/                  # Dynamic configuration plugin
│   └── ...
│
└── notice/                  # Notification plugin
    └── ...
```

---

## Plugin Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PLUGIN SYSTEM                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PLUGIN DISCOVERY (tools.py)                       │
│  ─────────────────────────────────────────────                      │
│  1. Scan PLUGIN_DIR for subdirectories                               │
│  2. Check for plugin.toml in each directory                          │
│  3. Parse plugin metadata                                            │
│  4. Install requirements.txt if present                              │
│  5. Import plugin router                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│   code_generator    │ │      oauth2         │ │       email         │
│   ───────────────   │ │   ───────────────   │ │   ───────────────   │
│   Auto-generate     │ │   GitHub, Google,   │ │   SMTP sending      │
│   CRUD code         │ │   Linux-DO OAuth    │ │   Email captcha     │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ROUTER INTEGRATION                                │
│  ─────────────────────────────────                                  │
│  build_final_router() aggregates:                                    │
│  • Core app routes (admin, task)                                     │
│  • Plugin routes (auto-discovered)                                   │
│                                                                     │
│  All routes under: /api/v1/...                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Plugin Metadata (plugin.toml)

Each plugin requires a `plugin.toml` file:

```toml
[plugin]
name = "code_generator"
version = "1.0.0"
description = "Automatic code generation for CRUD operations"
author = "FBA Team"
enabled = true

[plugin.dependencies]
# Optional: specify required plugins
requires = []
```

---

## Core Functions (tools.py)

### get_plugins()

Discovers all enabled plugins:

```python
def get_plugins() -> list[str]:
    """
    Scan plugin directory for valid plugins.
    
    Returns:
        List of plugin names
    """
    plugins = []
    for item in PLUGIN_DIR.iterdir():
        if item.is_dir() and (item / 'plugin.toml').exists():
            plugins.append(item.name)
    return plugins
```

### install_requirements()

Installs plugin dependencies:

```python
def install_requirements(plugin_name: str) -> None:
    """
    Install requirements.txt for a plugin.
    
    Args:
        plugin_name: Name of the plugin
    """
    req_file = PLUGIN_DIR / plugin_name / 'requirements.txt'
    if req_file.exists():
        pip_install(req_file)
```

### build_final_router()

Aggregates all routes:

```python
def build_final_router() -> APIRouter:
    """
    Build final API router with all plugins.
    
    Returns:
        Aggregated APIRouter
    """
    router = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)
    
    # Core routes
    from backend.app.router import router as app_router
    router.include_router(app_router)
    
    # Plugin routes
    for plugin in get_plugins():
        plugin_router = import_plugin_router(plugin)
        if plugin_router:
            router.include_router(plugin_router)
    
    return router
```

---

## Available Plugins

### 1. Code Generator

Automatically generates CRUD code from database table definitions.

**Features:**
- Generate model, schema, crud, service, api files
- Template-based generation
- Download as ZIP file

**Endpoints:**
- `GET /api/v1/gen/tables` - List database tables
- `POST /api/v1/gen/code` - Generate code
- `GET /api/v1/gen/download` - Download generated files

---

### 2. OAuth2

Third-party OAuth2 authentication.

**Supported Providers:**
- GitHub
- Google
- Linux-DO

**Endpoints:**
- `GET /api/v1/oauth2/github/authorize` - Start GitHub OAuth
- `GET /api/v1/oauth2/github/callback` - GitHub callback
- Similar endpoints for Google and Linux-DO

**Configuration:**
```python
OAUTH2_GITHUB_CLIENT_ID = "..."
OAUTH2_GITHUB_CLIENT_SECRET = "..."
OAUTH2_GITHUB_REDIRECT_URI = "http://localhost:8000/api/v1/oauth2/github/callback"
```

---

### 3. Email

Email sending with SMTP.

**Features:**
- Send emails via SMTP
- Email captcha verification
- Template support

**Configuration:**
```python
EMAIL_HOST = "smtp.qq.com"
EMAIL_PORT = 465
EMAIL_SSL = True
EMAIL_USERNAME = "your@email.com"
EMAIL_PASSWORD = "your_password"
```

---

### 4. Dictionary

System dictionary management.

**Features:**
- Key-value dictionary storage
- Categorized dictionaries
- Caching support

---

### 5. Config

Dynamic configuration storage.

**Features:**
- Runtime configuration changes
- Persistent storage in database
- Cache integration

---

### 6. Notice

User notification system.

**Features:**
- Create notifications
- Mark as read
- WebSocket push (with socketio)

---

## Creating a New Plugin

### Step 1: Create Directory Structure

```bash
plugin/
└── my_plugin/
    ├── plugin.toml
    ├── __init__.py
    └── api/
        ├── __init__.py
        └── v1/
            ├── __init__.py
            └── my_resource.py
```

### Step 2: Create plugin.toml

```toml
[plugin]
name = "my_plugin"
version = "1.0.0"
description = "My custom plugin"
enabled = true
```

### Step 3: Create Router

```python
# api/v1/my_resource.py
from fastapi import APIRouter

router = APIRouter(prefix="/my-plugin", tags=["My Plugin"])

@router.get("/hello")
async def hello():
    return {"message": "Hello from my plugin!"}
```

### Step 4: Export Router

```python
# api/v1/__init__.py
from fastapi import APIRouter
from .my_resource import router as my_resource_router

router = APIRouter()
router.include_router(my_resource_router)
```

```python
# api/__init__.py
from .v1 import router
```

### Step 5: Restart Application

The plugin will be automatically discovered and its routes registered.

---

## Plugin File Pattern

Plugins follow the same layered architecture as the main app:

```
my_plugin/
├── api/           # REST endpoints
│   └── v1/
│       └── resource.py
├── schema/        # Pydantic schemas
│   └── resource.py
├── service/       # Business logic
│   └── resource.py
├── crud/          # Database operations
│   └── resource.py
└── model/         # SQLAlchemy models
    └── resource.py
```

---

## Related Documentation

- [Admin Module](../app/admin/README.md) - Core app structure
- [Registrar](../core/registrar.md) - Router registration

---

## Plugin Subdirectory Documentation

| Plugin | Documentation |
|--------|---------------|
| Code Generator | [code-generator/README.md](./code-generator/README.md) |
| OAuth2 | [oauth2/README.md](./oauth2/README.md) |
| Email | [email/README.md](./email/README.md) |
| Dictionary | [dict/README.md](./dict/README.md) |
| Config | [config/README.md](./config/README.md) |
| Notice | [notice/README.md](./notice/README.md) |

---

*Last Updated: December 2024*
