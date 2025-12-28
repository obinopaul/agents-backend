# Plugins Guide

> Documentation for the 6 extensible plugins in the Agents Backend.

---

## Plugin Architecture

Plugins are modular extensions located in `backend/plugin/`. Each plugin follows the same structure:

```
backend/plugin/{plugin_name}/
├── __init__.py
├── plugin.toml           # Plugin configuration
├── requirements.txt      # Plugin dependencies
├── api/                  # FastAPI routes
│   ├── router.py
│   └── v1/
├── crud/                 # Database operations
├── model/                # SQLAlchemy models
├── schema/               # Pydantic schemas
└── service/              # Business logic
```

---

## Available Plugins

| Plugin | Purpose | API Prefix |
|--------|---------|------------|
| [oauth2](#oauth2-plugin) | Social login | `/api/v1/oauth2` |
| [email](#email-plugin) | Email notifications | `/api/v1/plugin/email` |
| [config](#config-plugin) | Dynamic configuration | `/api/v1/plugin/config` |
| [notice](#notice-plugin) | System announcements | `/api/v1/plugin/notice` |
| [dict](#dict-plugin) | Data dictionaries | `/api/v1/plugin/dict` |
| [code_generator](#code-generator-plugin) | CRUD code generation | `/api/v1/plugin/gen` |

---

## OAuth2 Plugin

**Purpose:** Social login with GitHub, Google, and LinuxDo.

### Configuration

```bash
# .env
OAUTH2_GITHUB_CLIENT_ID='your-client-id'
OAUTH2_GITHUB_CLIENT_SECRET='your-client-secret'
OAUTH2_GOOGLE_CLIENT_ID='your-client-id'
OAUTH2_GOOGLE_CLIENT_SECRET='your-client-secret'
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/oauth2/github` | Get GitHub auth URL |
| GET | `/api/v1/oauth2/github/callback` | GitHub callback |
| GET | `/api/v1/oauth2/google` | Get Google auth URL |
| GET | `/api/v1/oauth2/google/callback` | Google callback |
| GET | `/api/v1/oauth2/user-social/list` | List linked accounts |
| DELETE | `/api/v1/oauth2/user-social/{id}` | Unlink account |

### Usage

See [Authentication Guide](../frontend-connect/authentication.md) for detailed integration.

---

## Email Plugin

**Purpose:** Send emails for verification, notifications, and password reset.

### Configuration

```bash
# .env
EMAIL_HOST='smtp.gmail.com'
EMAIL_PORT=587
EMAIL_USER='your@email.com'
EMAIL_PASSWORD='your-app-password'
EMAIL_USE_TLS=True
EMAIL_FROM='noreply@example.com'

# Captcha settings
EMAIL_CAPTCHA_REDIS_PREFIX='fba:email:captcha'
EMAIL_CAPTCHA_EXPIRE_SECONDS=300
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/plugin/email/send` | Send email |
| POST | `/api/v1/plugin/email/captcha` | Send verification code |
| POST | `/api/v1/plugin/email/verify` | Verify captcha |

### Usage Example

```python
from backend.plugin.email.service.email_service import email_service

# Send email
await email_service.send(
    to="user@example.com",
    subject="Welcome",
    body="Welcome to Agents Backend!"
)

# Send verification code
await email_service.send_captcha(to="user@example.com")
```

---

## Config Plugin

**Purpose:** Dynamic system configuration stored in the database.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/plugin/config` | Get all configs |
| GET | `/api/v1/plugin/config/{key}` | Get config by key |
| PUT | `/api/v1/plugin/config` | Update configs |

### Usage Example

```python
from backend.plugin.config.service.config_service import config_service

# Get config
site_name = await config_service.get("site_name")

# Set config
await config_service.set("site_name", "My App")
```

### Default Configs

| Key | Description | Type |
|-----|-------------|------|
| `site_title` | Application title | string |
| `site_description` | App description | string |
| `enable_registration` | Allow new users | boolean |
| `enable_captcha` | Require captcha | boolean |
| `max_login_attempts` | Failed login limit | integer |

---

## Notice Plugin

**Purpose:** System announcements and notifications.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/plugin/notice` | List notices |
| GET | `/api/v1/plugin/notice/{id}` | Get notice |
| POST | `/api/v1/plugin/notice` | Create notice |
| PUT | `/api/v1/plugin/notice/{id}` | Update notice |
| DELETE | `/api/v1/plugin/notice/{id}` | Delete notice |

### Notice Types

| Type | Value | Description |
|------|-------|-------------|
| Announcement | 1 | General announcement |
| Maintenance | 2 | Scheduled maintenance |
| Update | 3 | Feature update |
| Alert | 4 | Important alert |

### Usage Example

```python
from backend.plugin.notice.service.notice_service import notice_service

# Create notice
await notice_service.create(
    title="System Maintenance",
    content="Scheduled maintenance on Sunday",
    type=2,
    status=1
)
```

---

## Dict Plugin

**Purpose:** Data dictionaries for dropdowns, enums, and static data.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/plugin/dict/types` | List dict types |
| GET | `/api/v1/plugin/dict/types/{id}` | Get dict type |
| POST | `/api/v1/plugin/dict/types` | Create dict type |
| GET | `/api/v1/plugin/dict/data` | List dict data |
| GET | `/api/v1/plugin/dict/data/{type_code}` | Get data by type |
| POST | `/api/v1/plugin/dict/data` | Create dict data |

### Example: Status Dictionary

```python
# Dict Type
{
    "id": 1,
    "name": "Status",
    "code": "sys_status",
    "status": 1
}

# Dict Data
[
    {"label": "Active", "value": "1", "type_code": "sys_status"},
    {"label": "Inactive", "value": "0", "type_code": "sys_status"}
]
```

### Frontend Usage

```typescript
// Fetch dict data
const response = await api.get('/plugin/dict/data/sys_status');
const statusOptions = response.data.data;

// Use in select
<Select options={statusOptions.map(d => ({ label: d.label, value: d.value }))} />
```

---

## Code Generator Plugin

**Purpose:** Generate CRUD code from database tables.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/plugin/gen/tables` | List database tables |
| GET | `/api/v1/plugin/gen/tables/{name}` | Get table info |
| POST | `/api/v1/plugin/gen/preview` | Preview generated code |
| POST | `/api/v1/plugin/gen/generate` | Generate files |
| GET | `/api/v1/plugin/gen/download/{name}` | Download as zip |

### Generated Files

For a table named `products`:

```
generated/
├── model/
│   └── product.py           # SQLAlchemy model
├── schema/
│   └── product.py           # Pydantic schemas
├── crud/
│   └── crud_product.py      # CRUD operations
├── api/
│   └── product.py           # FastAPI routes
└── service/
    └── product_service.py   # Business logic
```

### Usage

1. Create your database table
2. Call `/api/v1/plugin/gen/tables` to list tables
3. Call `/api/v1/plugin/gen/preview` with table name
4. Review generated code
5. Call `/api/v1/plugin/gen/generate` to create files

---

## Creating Custom Plugins

### 1. Create Plugin Directory

```bash
mkdir -p backend/plugin/my_plugin/{api/v1,crud,model,schema,service}
```

### 2. Add Plugin Config

```toml
# backend/plugin/my_plugin/plugin.toml
[plugin]
name = "my_plugin"
version = "1.0.0"
```

### 3. Define Router

```python
# backend/plugin/my_plugin/api/router.py
from fastapi import APIRouter
from backend.plugin.my_plugin.api.v1 import my_endpoints

v1 = APIRouter(prefix='/api/v1/plugin/my-plugin')
v1.include_router(my_endpoints.router)
```

### 4. Register Plugin

Plugins are auto-discovered. Just ensure they follow the structure.

---

## Plugin Dependencies

Each plugin can have its own `requirements.txt`:

```
# backend/plugin/oauth2/requirements.txt
fastapi-oauth20>=0.0.1
```

Dependencies are installed automatically at startup.

---

## Related Documentation

- [Authentication](../frontend-connect/authentication.md) - OAuth2 integration
- [Admin API](../api-contracts/admin-api.md) - User management
- [Environment Variables](./environment-variables.md) - Plugin configuration
