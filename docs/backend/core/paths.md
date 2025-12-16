# Path Configuration

The `path_conf.py` module defines all base paths and directories used throughout the application.

---

## Overview

All paths are derived from the `BASE_PATH` which points to the `backend/` directory.

---

## Source Code

```python
from pathlib import Path

# Project root directory (backend/)
BASE_PATH = Path(__file__).resolve().parent.parent

# Alembic migration files
ALEMBIC_VERSION_DIR = BASE_PATH / 'alembic' / 'versions'

# Log files directory
LOG_DIR = BASE_PATH / 'log'

# Static assets directory
STATIC_DIR = BASE_PATH / 'static'

# User uploads directory
UPLOAD_DIR = STATIC_DIR / 'upload'

# Plugin directory
PLUGIN_DIR = BASE_PATH / 'plugin'

# Internationalization files
LOCALE_DIR = BASE_PATH / 'locale'
```

---

## Path Diagram

```
agents-backend/
│
└── backend/                      ← BASE_PATH
    │
    ├── alembic/
    │   └── versions/             ← ALEMBIC_VERSION_DIR
    │       ├── 001_initial.py
    │       └── ...
    │
    ├── log/                      ← LOG_DIR
    │   ├── fba_access.log
    │   └── fba_error.log
    │
    ├── static/                   ← STATIC_DIR
    │   ├── favicon.ico
    │   └── upload/               ← UPLOAD_DIR
    │       ├── images/
    │       └── videos/
    │
    ├── plugin/                   ← PLUGIN_DIR
    │   ├── code_generator/
    │   ├── oauth2/
    │   └── ...
    │
    └── locale/                   ← LOCALE_DIR
        ├── en-US.json
        └── zh-CN.yml
```

---

## Path Reference

| Constant | Relative Path | Description |
|----------|---------------|-------------|
| `BASE_PATH` | `backend/` | Project backend root |
| `ALEMBIC_VERSION_DIR` | `backend/alembic/versions/` | Database migration scripts |
| `LOG_DIR` | `backend/log/` | Application log files |
| `STATIC_DIR` | `backend/static/` | Static assets |
| `UPLOAD_DIR` | `backend/static/upload/` | User uploaded files |
| `PLUGIN_DIR` | `backend/plugin/` | Plugin modules |
| `LOCALE_DIR` | `backend/locale/` | i18n translation files |

---

## Usage Examples

```python
from backend.core.path_conf import BASE_PATH, LOG_DIR, UPLOAD_DIR

# Get .env file path
env_file = BASE_PATH / '.env'

# Check if log directory exists
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True)

# Save uploaded file
upload_path = UPLOAD_DIR / 'images' / 'avatar.png'
with open(upload_path, 'wb') as f:
    f.write(file_content)
```

---

## Path Usage in Application

| Module | Uses | Purpose |
|--------|------|---------|
| `core/conf.py` | `BASE_PATH` | Load `.env` file |
| `core/registrar.py` | `STATIC_DIR`, `UPLOAD_DIR` | Mount static files |
| `common/log.py` | `LOG_DIR` | Write log files |
| `common/i18n.py` | `LOCALE_DIR` | Load translations |
| `plugin/tools.py` | `PLUGIN_DIR` | Discover plugins |
| `alembic/env.py` | `ALEMBIC_VERSION_DIR` | Find migrations |

---

## Creating Custom Paths

When adding new directories, follow the pattern:

```python
# In path_conf.py
CUSTOM_DIR = BASE_PATH / 'custom'

# In your code
from backend.core.path_conf import CUSTOM_DIR

# Ensure directory exists before use
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
```

---

*Last Updated: December 2024*
