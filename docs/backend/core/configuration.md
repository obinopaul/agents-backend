# Configuration Reference

This document provides a comprehensive reference for all configuration settings in `backend/core/conf.py`.

---

## Overview

The `Settings` class uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to manage configuration. Settings are loaded from:

1. Environment variables
2. `.env` file in the backend directory
3. Default values defined in the class

```python
from backend.core.conf import settings

# Access any setting
print(settings.FASTAPI_TITLE)
print(settings.DATABASE_HOST)
```

---

## Configuration Loading

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CONFIGURATION HIERARCHY                          │
│              (Higher priority overrides lower)                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
   │ Environment │        │  .env File  │        │  Defaults   │
   │  Variables  │        │             │        │  in Class   │
   │  (highest)  │        │  (medium)   │        │  (lowest)   │
   └─────────────┘        └─────────────┘        └─────────────┘
```

---

## Settings Categories

### Environment

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ENVIRONMENT` | `Literal['dev', 'prod']` | **Required** | Current environment mode |

**Environment-Aware Behavior:**

When `ENVIRONMENT=prod`:
- `FASTAPI_OPENAPI_URL` → `None` (disable OpenAPI docs)
- `FASTAPI_STATIC_FILES` → `False` (disable static file serving)
- `CELERY_BROKER` → `'rabbitmq'` (use RabbitMQ instead of Redis)

---

### FastAPI Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `FASTAPI_API_V1_PATH` | `str` | `'/api/v1'` | API version 1 prefix |
| `FASTAPI_TITLE` | `str` | `'FastAPI'` | Application title |
| `FASTAPI_DESCRIPTION` | `str` | `'FastAPI Best Architecture'` | API description |
| `FASTAPI_DOCS_URL` | `str` | `'/docs'` | Swagger UI path |
| `FASTAPI_REDOC_URL` | `str` | `'/redoc'` | ReDoc path |
| `FASTAPI_OPENAPI_URL` | `str \| None` | `'/openapi'` | OpenAPI schema path |
| `FASTAPI_STATIC_FILES` | `bool` | `True` | Enable static file serving |

---

### Database Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DATABASE_TYPE` | `Literal['mysql', 'postgresql']` | **Required** | Database engine type |
| `DATABASE_HOST` | `str` | **Required** | Database server host |
| `DATABASE_PORT` | `int` | **Required** | Database server port |
| `DATABASE_USER` | `str` | **Required** | Database username |
| `DATABASE_PASSWORD` | `str` | **Required** | Database password |
| `DATABASE_ECHO` | `bool \| Literal['debug']` | `False` | Log SQL statements |
| `DATABASE_POOL_ECHO` | `bool \| Literal['debug']` | `False` | Log pool checkouts |
| `DATABASE_SCHEMA` | `str` | `'fba'` | Database schema/name |
| `DATABASE_CHARSET` | `str` | `'utf8mb4'` | Character set (MySQL) |
| `DATABASE_PK_MODE` | `Literal['autoincrement', 'snowflake']` | `'autoincrement'` | Primary key strategy |

**Database Connection URL Format:**

```
# MySQL
mysql+asyncmy://user:password@host:port/database?charset=utf8mb4

# PostgreSQL
postgresql+asyncpg://user:password@host:port/database
```

---

### Redis Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `REDIS_HOST` | `str` | **Required** | Redis server host |
| `REDIS_PORT` | `int` | **Required** | Redis server port |
| `REDIS_PASSWORD` | `str` | **Required** | Redis password |
| `REDIS_DATABASE` | `int` | **Required** | Redis database number |
| `REDIS_TIMEOUT` | `int` | `5` | Connection timeout (seconds) |

---

### Snowflake ID Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `SNOWFLAKE_DATACENTER_ID` | `int \| None` | `None` | Datacenter ID (0-31) |
| `SNOWFLAKE_WORKER_ID` | `int \| None` | `None` | Worker ID (0-31) |
| `SNOWFLAKE_REDIS_PREFIX` | `str` | `'fba:snowflake'` | Redis key prefix |
| `SNOWFLAKE_HEARTBEAT_INTERVAL_SECONDS` | `int` | `30` | Heartbeat interval |
| `SNOWFLAKE_NODE_TTL_SECONDS` | `int` | `60` | Node TTL |

---

### Token/JWT Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `TOKEN_SECRET_KEY` | `str` | **Required** | JWT signing key |
| `TOKEN_ALGORITHM` | `str` | `'HS256'` | JWT algorithm |
| `TOKEN_EXPIRE_SECONDS` | `int` | `86400` | Access token expiry (1 day) |
| `TOKEN_REFRESH_EXPIRE_SECONDS` | `int` | `604800` | Refresh token expiry (7 days) |
| `TOKEN_REDIS_PREFIX` | `str` | `'fba:token'` | Token Redis prefix |
| `TOKEN_EXTRA_INFO_REDIS_PREFIX` | `str` | `'fba:token_extra_info'` | Extra info prefix |
| `TOKEN_ONLINE_REDIS_PREFIX` | `str` | `'fba:token_online'` | Online users prefix |
| `TOKEN_REFRESH_REDIS_PREFIX` | `str` | `'fba:refresh_token'` | Refresh token prefix |
| `TOKEN_REQUEST_PATH_EXCLUDE` | `list[str]` | `['/api/v1/auth/login']` | JWT whitelist paths |
| `TOKEN_REQUEST_PATH_EXCLUDE_PATTERN` | `list[Pattern]` | See code | Regex whitelist patterns |

---

### User Security Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `USER_LOCK_REDIS_PREFIX` | `str` | `'fba:user:lock'` | User lock Redis prefix |
| `USER_LOCK_THRESHOLD` | `int` | `5` | Failed attempts before lock (0 = disabled) |
| `USER_LOCK_SECONDS` | `int` | `300` | Lock duration (5 minutes) |
| `USER_PASSWORD_EXPIRY_DAYS` | `int` | `365` | Password validity (0 = never expires) |
| `USER_PASSWORD_REMINDER_DAYS` | `int` | `7` | Password expiry reminder |
| `USER_PASSWORD_HISTORY_CHECK_COUNT` | `int` | `3` | Previous passwords to check |
| `USER_PASSWORD_MIN_LENGTH` | `int` | `6` | Minimum password length |
| `USER_PASSWORD_MAX_LENGTH` | `int` | `32` | Maximum password length |
| `USER_PASSWORD_REQUIRE_SPECIAL_CHAR` | `bool` | `False` | Require special characters |

---

### Login/Captcha Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `LOGIN_CAPTCHA_ENABLED` | `bool` | `True` | Enable login captcha |
| `LOGIN_CAPTCHA_REDIS_PREFIX` | `str` | `'fba:login:captcha'` | Captcha Redis prefix |
| `LOGIN_CAPTCHA_EXPIRE_SECONDS` | `int` | `300` | Captcha validity (5 minutes) |
| `LOGIN_FAILURE_PREFIX` | `str` | `'fba:login:failure'` | Login failure counter prefix |

---

### JWT/RBAC Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `JWT_USER_REDIS_PREFIX` | `str` | `'fba:user'` | User info cache prefix |
| `RBAC_ROLE_MENU_MODE` | `bool` | `True` | Enable role-menu RBAC |
| `RBAC_ROLE_MENU_EXCLUDE` | `list[str]` | `['sys:monitor:redis', 'sys:monitor:server']` | RBAC excluded permissions |

---

### Cookie Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `COOKIE_REFRESH_TOKEN_KEY` | `str` | `'fba_refresh_token'` | Cookie name |
| `COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS` | `int` | `604800` | Cookie expiry (7 days) |

---

### Data Permission Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DATA_PERMISSION_COLUMN_EXCLUDE` | `list[str]` | `['id', 'sort', 'del_flag', 'created_time', 'updated_time']` | Columns excluded from data filtering |

---

### WebSocket Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `WS_NO_AUTH_MARKER` | `str` | `'internal'` | Internal WebSocket marker |

---

### CORS Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `CORS_ALLOWED_ORIGINS` | `list[str]` | `['http://127.0.0.1:8000', 'http://localhost:5173']` | Allowed origins |
| `CORS_EXPOSE_HEADERS` | `list[str]` | `['X-Request-ID']` | Exposed headers |
| `MIDDLEWARE_CORS` | `bool` | `True` | Enable CORS middleware |

---

### Request Limiter Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `REQUEST_LIMITER_REDIS_PREFIX` | `str` | `'fba:limiter'` | Rate limiter Redis prefix |

---

### DateTime Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DATETIME_TIMEZONE` | `str` | `'Asia/Shanghai'` | Application timezone |
| `DATETIME_FORMAT` | `str` | `'%Y-%m-%d %H:%M:%S'` | Datetime format |

---

### File Upload Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `UPLOAD_READ_SIZE` | `int` | `1024` | Upload read buffer size |
| `UPLOAD_IMAGE_EXT_INCLUDE` | `list[str]` | `['jpg', 'jpeg', 'png', 'gif', 'webp']` | Allowed image extensions |
| `UPLOAD_IMAGE_SIZE_MAX` | `int` | `5242880` | Max image size (5 MB) |
| `UPLOAD_VIDEO_EXT_INCLUDE` | `list[str]` | `['mp4', 'mov', 'avi', 'flv']` | Allowed video extensions |
| `UPLOAD_VIDEO_SIZE_MAX` | `int` | `20971520` | Max video size (20 MB) |

---

### Demo Mode Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DEMO_MODE` | `bool` | `False` | Enable demo mode |
| `DEMO_MODE_EXCLUDE` | `set[tuple[str, str]]` | See code | Excluded method/path pairs |

---

### IP Location Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `IP_LOCATION_PARSE` | `Literal['online', 'offline', 'false']` | `'offline'` | IP parsing mode |
| `IP_LOCATION_REDIS_PREFIX` | `str` | `'fba:ip:location'` | IP cache prefix |
| `IP_LOCATION_EXPIRE_SECONDS` | `int` | `86400` | IP cache expiry (1 day) |

---

### Trace ID Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `TRACE_ID_REQUEST_HEADER_KEY` | `str` | `'X-Request-ID'` | Request ID header |
| `TRACE_ID_LOG_LENGTH` | `int` | `32` | Trace ID length (≤ 32) |
| `TRACE_ID_LOG_DEFAULT_VALUE` | `str` | `'-'` | Default trace ID |

---

### Logging Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `LOG_FORMAT` | `str` | See code | Log format string |
| `LOG_STD_LEVEL` | `str` | `'INFO'` | Console log level |
| `LOG_FILE_ACCESS_LEVEL` | `str` | `'INFO'` | Access log file level |
| `LOG_FILE_ERROR_LEVEL` | `str` | `'ERROR'` | Error log file level |
| `LOG_ACCESS_FILENAME` | `str` | `'fba_access.log'` | Access log filename |
| `LOG_ERROR_FILENAME` | `str` | `'fba_error.log'` | Error log filename |

---

### Operation Log Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `OPERA_LOG_ENCRYPT_SECRET_KEY` | `str` | **Required** | Encryption key (hex) |
| `OPERA_LOG_PATH_EXCLUDE` | `list[str]` | See code | Excluded paths |
| `OPERA_LOG_ENCRYPT_TYPE` | `int` | `1` | Encrypt type (0=AES, 1=md5, 2=ItsDangerous, 3=none) |
| `OPERA_LOG_ENCRYPT_KEY_INCLUDE` | `list[str]` | `['password', 'old_password', ...]` | Keys to encrypt |
| `OPERA_LOG_QUEUE_BATCH_CONSUME_SIZE` | `int` | `100` | Batch size |
| `OPERA_LOG_QUEUE_TIMEOUT` | `int` | `60` | Queue timeout (1 minute) |

---

### Plugin Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `PLUGIN_PIP_CHINA` | `bool` | `True` | Use China mirrors |
| `PLUGIN_PIP_INDEX_URL` | `str` | `'https://mirrors.aliyun.com/pypi/simple/'` | pip index URL |
| `PLUGIN_PIP_MAX_RETRY` | `int` | `3` | Max install retries |
| `PLUGIN_REDIS_PREFIX` | `str` | `'fba:plugin'` | Plugin Redis prefix |

---

### I18n Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `I18N_DEFAULT_LANGUAGE` | `str` | `'zh-CN'` | Default language |

---

### Celery Task Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `CELERY_BROKER_REDIS_DATABASE` | `int` | **Required** | Redis database for Celery |
| `CELERY_RABBITMQ_HOST` | `str` | **Required** | RabbitMQ host |
| `CELERY_RABBITMQ_PORT` | `int` | **Required** | RabbitMQ port |
| `CELERY_RABBITMQ_USERNAME` | `str` | **Required** | RabbitMQ username |
| `CELERY_RABBITMQ_PASSWORD` | `str` | **Required** | RabbitMQ password |
| `CELERY_BROKER` | `Literal['rabbitmq', 'redis']` | `'redis'` | Broker type |
| `CELERY_RABBITMQ_VHOST` | `str` | `''` | RabbitMQ vhost |
| `CELERY_REDIS_PREFIX` | `str` | `'fba:celery'` | Celery Redis prefix |
| `CELERY_TASK_MAX_RETRIES` | `int` | `5` | Max task retries |

---

### Code Generator Plugin Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `CODE_GENERATOR_DOWNLOAD_ZIP_FILENAME` | `str` | `'fba_generator'` | Generated ZIP filename |

---

### OAuth2 Plugin Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `OAUTH2_GITHUB_CLIENT_ID` | `str` | **Required** | GitHub OAuth client ID |
| `OAUTH2_GITHUB_CLIENT_SECRET` | `str` | **Required** | GitHub OAuth client secret |
| `OAUTH2_GOOGLE_CLIENT_ID` | `str` | **Required** | Google OAuth client ID |
| `OAUTH2_GOOGLE_CLIENT_SECRET` | `str` | **Required** | Google OAuth client secret |
| `OAUTH2_LINUX_DO_CLIENT_ID` | `str` | **Required** | Linux-DO OAuth client ID |
| `OAUTH2_LINUX_DO_CLIENT_SECRET` | `str` | **Required** | Linux-DO OAuth client secret |
| `OAUTH2_STATE_REDIS_PREFIX` | `str` | `'fba:oauth2:state'` | OAuth state prefix |
| `OAUTH2_STATE_EXPIRE_SECONDS` | `int` | `180` | OAuth state expiry (3 min) |
| `OAUTH2_GITHUB_REDIRECT_URI` | `str` | See code | GitHub callback URL |
| `OAUTH2_GOOGLE_REDIRECT_URI` | `str` | See code | Google callback URL |
| `OAUTH2_LINUX_DO_REDIRECT_URI` | `str` | See code | Linux-DO callback URL |
| `OAUTH2_FRONTEND_LOGIN_REDIRECT_URI` | `str` | See code | Frontend login redirect |
| `OAUTH2_FRONTEND_BINDING_REDIRECT_URI` | `str` | See code | Frontend binding redirect |

---

### Email Plugin Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `EMAIL_USERNAME` | `str` | **Required** | SMTP username |
| `EMAIL_PASSWORD` | `str` | **Required** | SMTP password |
| `EMAIL_HOST` | `str` | `'smtp.qq.com'` | SMTP host |
| `EMAIL_PORT` | `int` | `465` | SMTP port |
| `EMAIL_SSL` | `bool` | `True` | Use SSL |
| `EMAIL_CAPTCHA_REDIS_PREFIX` | `str` | `'fba:email:captcha'` | Email captcha prefix |
| `EMAIL_CAPTCHA_EXPIRE_SECONDS` | `int` | `180` | Email captcha expiry (3 min) |

---

## Example .env File

```bash
# Environment
ENVIRONMENT=dev

# Database
DATABASE_TYPE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DATABASE=0

# Security
TOKEN_SECRET_KEY=your-secret-key-here-at-least-32-chars
OPERA_LOG_ENCRYPT_SECRET_KEY=your-hex-key-here

# Celery
CELERY_BROKER_REDIS_DATABASE=1
CELERY_RABBITMQ_HOST=localhost
CELERY_RABBITMQ_PORT=5672
CELERY_RABBITMQ_USERNAME=guest
CELERY_RABBITMQ_PASSWORD=guest

# OAuth2 (optional)
OAUTH2_GITHUB_CLIENT_ID=
OAUTH2_GITHUB_CLIENT_SECRET=
OAUTH2_GOOGLE_CLIENT_ID=
OAUTH2_GOOGLE_CLIENT_SECRET=
OAUTH2_LINUX_DO_CLIENT_ID=
OAUTH2_LINUX_DO_CLIENT_SECRET=

# Email (optional)
EMAIL_USERNAME=
EMAIL_PASSWORD=
```

---

## Generating Secret Keys

```python
import secrets
import os

# For TOKEN_SECRET_KEY
print(secrets.token_urlsafe(32))

# For OPERA_LOG_ENCRYPT_SECRET_KEY
print(os.urandom(32).hex())
```

---

*Last Updated: December 2024*
