# Additional System APIs

> **Base URL:** `http://localhost:8000/api/v1`
>
> All endpoints require `Authorization: Bearer <token>` header.

---

## Table of Contents

1. [Logs](#1-logs)
2. [Monitors](#2-monitors)
3. [Task Scheduler](#3-task-scheduler)
4. [Dictionary Plugin](#4-dictionary-plugin)
5. [Notice Plugin](#5-notice-plugin)
6. [Code Generator Plugin](#6-code-generator-plugin)

---

## 1. Logs

### Login Logs

Track all login attempts.

#### GET `/admin/login-logs`

Get login logs with pagination.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `username` | string | Filter by username |
| `status` | int | Filter by status (0=failed, 1=success) |
| `ip` | string | Filter by IP address |

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "username": "admin",
        "ip": "192.168.1.100",
        "location": "Local",
        "browser": "Chrome 120",
        "os": "Windows 10",
        "status": 1,
        "msg": "Login successful",
        "login_time": "2024-12-21T10:00:00Z"
      }
    ],
    "total": 100
  }
}
```

#### DELETE `/admin/login-logs`

Batch delete login logs. **Requires:** `log:login:del`

**Request:**
```json
{
  "pks": [1, 2, 3]
}
```

#### DELETE `/admin/login-logs/all`

Clear all login logs. **Requires:** `log:login:clear`

---

### Operation Logs

Audit trail of system operations.

#### GET `/admin/opera-logs`

Get operation logs with pagination.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `username` | string | Filter by username |
| `status` | int | Filter by status |
| `ip` | string | Filter by IP |

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "username": "admin",
        "method": "POST",
        "title": "Create User",
        "path": "/api/v1/admin/users",
        "ip": "192.168.1.100",
        "status": 1,
        "response_code": 200,
        "cost_time": 125,
        "created_at": "2024-12-21T10:00:00Z"
      }
    ],
    "total": 500
  }
}
```

#### DELETE `/admin/opera-logs`

Batch delete operation logs. **Requires:** `log:opera:del`

#### DELETE `/admin/opera-logs/all`

Clear all operation logs. **Requires:** `log:opera:clear`

---

## 2. Monitors

### Online Users

#### GET `/monitors/online`

Get online users.

**Query:** `?username=admin`

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "session_uuid": "abc123",
      "username": "admin",
      "nickname": "Administrator",
      "ip": "192.168.1.100",
      "location": "Local",
      "browser": "Chrome 120",
      "os": "Windows 10",
      "login_time": "2024-12-21T10:00:00Z"
    }
  ]
}
```

#### DELETE `/monitors/online/{session_uuid}`

Kick a user offline. **Requires:** `sys:online:del`

---

### Redis Status

#### GET `/monitors/redis`

Get Redis server statistics.

**Response:**
```json
{
  "code": 200,
  "data": {
    "version": "7.0.0",
    "uptime_in_seconds": 86400,
    "connected_clients": 5,
    "used_memory": "10.5MB",
    "used_memory_peak": "15.2MB",
    "total_connections_received": 1000,
    "total_commands_processed": 50000
  }
}
```

---

### Server Status

#### GET `/monitors/server`

Get server system information.

**Response:**
```json
{
  "code": 200,
  "data": {
    "cpu_percent": 25.5,
    "memory_percent": 45.2,
    "disk_percent": 60.0,
    "platform": "Windows 10",
    "python_version": "3.12.0",
    "hostname": "server-01"
  }
}
```

---

## 3. Task Scheduler

Background job scheduling using APScheduler.

### GET `/tasks/schedulers`

List all scheduled tasks.

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "id": "cleanup_logs",
      "name": "Daily Log Cleanup",
      "trigger": "cron",
      "next_run_time": "2024-12-22T00:00:00Z",
      "job_state": "running"
    }
  ]
}
```

---

### POST `/tasks/schedulers`

Create a scheduled task.

**Request:**
```json
{
  "id": "my_task",
  "name": "My Custom Task",
  "func": "backend.tasks.my_task_function",
  "trigger": "interval",
  "minutes": 30
}
```

---

### PUT `/tasks/schedulers/{task_id}/pause`

Pause a scheduled task.

---

### PUT `/tasks/schedulers/{task_id}/resume`

Resume a paused task.

---

### DELETE `/tasks/schedulers/{task_id}`

Delete a scheduled task.

---

### GET `/tasks/results`

Get task execution results.

---

### POST `/tasks/control/run/{task_id}`

Manually trigger a task.

---

## 4. Dictionary Plugin

System dictionaries for dropdown values, configs, etc.

### Dictionary Types

#### GET `/admin/dict-types`

List all dictionary types.

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "name": "User Status",
        "code": "sys_user_status",
        "status": 1,
        "remark": "User account status options"
      }
    ]
  }
}
```

#### POST `/admin/dict-types`

Create dictionary type. **Requires:** `sys:dict:type:add`

```json
{
  "name": "Order Status",
  "code": "order_status",
  "status": 1,
  "remark": "E-commerce order statuses"
}
```

#### PUT `/admin/dict-types/{id}`

Update dictionary type. **Requires:** `sys:dict:type:edit`

#### DELETE `/admin/dict-types`

Batch delete dictionary types. **Requires:** `sys:dict:type:del`

---

### Dictionary Data

#### GET `/admin/dict-data`

List dictionary data (key-value pairs).

**Query:** `?type_id=1` or `?type_code=sys_user_status`

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "type_id": 1,
        "label": "Active",
        "value": "1",
        "sort": 1,
        "status": 1
      },
      {
        "id": 2,
        "type_id": 1,
        "label": "Disabled",
        "value": "0",
        "sort": 2,
        "status": 1
      }
    ]
  }
}
```

#### POST `/admin/dict-data`

Create dictionary data. **Requires:** `sys:dict:data:add`

#### PUT `/admin/dict-data/{id}`

Update dictionary data. **Requires:** `sys:dict:data:edit`

#### DELETE `/admin/dict-data`

Batch delete dictionary data. **Requires:** `sys:dict:data:del`

---

## 5. Notice Plugin

System-wide notifications.

### GET `/admin/notices`

List all notices.

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "title": "System Maintenance",
        "content": "Scheduled maintenance on Sunday...",
        "type": "announcement",
        "status": 1,
        "created_at": "2024-12-21T10:00:00Z"
      }
    ]
  }
}
```

---

### POST `/admin/notices`

Create notice. **Requires:** `sys:notice:add`

```json
{
  "title": "New Feature Released",
  "content": "We have released a new AI assistant...",
  "type": "announcement",
  "status": 1
}
```

---

### PUT `/admin/notices/{id}`

Update notice. **Requires:** `sys:notice:edit`

---

### DELETE `/admin/notices`

Batch delete notices. **Requires:** `sys:notice:del`

---

## 6. Code Generator Plugin

Generate CRUD code from database tables.

### GET `/code-generation/businesses`

List all business entities (tables).

---

### GET `/code-generation/businesses/{id}/columns`

Get table columns for code generation.

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "column_name": "id",
      "column_type": "bigint",
      "is_pk": true,
      "is_required": true,
      "python_type": "int"
    },
    {
      "column_name": "name",
      "column_type": "varchar(64)",
      "is_pk": false,
      "is_required": true,
      "python_type": "str"
    }
  ]
}
```

---

### POST `/code-generation/gen/{business_id}`

Generate code for a business entity.

**Response:** ZIP file containing:
- `model.py` - SQLAlchemy model
- `schema.py` - Pydantic schemas
- `service.py` - Business logic
- `api.py` - FastAPI routes
- `crud.py` - CRUD operations

---

### POST `/code-generation/gen/{business_id}/preview`

Preview generated code without downloading.

---

### POST `/code-generation/import-tables`

Import database tables as business entities.

```json
{
  "table_names": ["products", "orders", "customers"]
}
```

---

## Environment Variables

```env
# Task Scheduler
APSCHEDULER_ENABLED=true
APSCHEDULER_JOBSTORES_TYPE=redis

# Code Generator
CODE_GEN_TEMPLATE_PATH=backend/plugin/code_generator/templates
CODE_GEN_OUTPUT_PATH=backend/generated

# Notice
NOTICE_DEFAULT_DISPLAY_DAYS=7
```

---

## Summary: All APIs in This Project

| Category | Base Path | Endpoints |
|----------|-----------|-----------|
| **Auth** | `/auth` | login, logout, refresh, codes |
| **Users** | `/admin/users` | CRUD, password, permissions |
| **Roles** | `/admin/roles` | CRUD, menus, scopes |
| **Depts** | `/admin/depts` | Tree CRUD |
| **Menus** | `/admin/menus` | Permission CRUD |
| **Logs** | `/admin/login-logs`, `/admin/opera-logs` | List, delete, clear |
| **Monitors** | `/monitors` | online, redis, server |
| **Tasks** | `/tasks` | Scheduler CRUD, control |
| **OAuth2** | `/oauth2` | GitHub, Google, Linux.do |
| **Email** | `/emails` | Captcha |
| **Config** | `/admin/configs` | System config CRUD |
| **Dict** | `/admin/dict-types`, `/admin/dict-data` | Dictionary CRUD |
| **Notice** | `/admin/notices` | Notification CRUD |
| **Code Gen** | `/code-generation` | Generate, preview, import |
| **Agent Chat** | `/agent/chat` | SSE streaming |
| **Credits** | `/agent/credits` | Balance, usage |
| **MCP** | `/agent/mcp` | Server metadata |
| **RAG** | `/agent/rag` | Config, resources |
| **Generation** | `/agent/generation` | Podcast, PPT, prose |
| **TTS** | `/agent/tts` | Text-to-speech |
| **Sandbox** | `/agent/sandboxes` | Lifecycle, files, commands |
| **Slides** | `/agent/slides` | Presentations, export |
