# Core Backend API Contracts

> **Base URL:** `http://localhost:8000/api/v1`
>
> **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [User Management](#2-user-management)
3. [Role Management](#3-role-management)
4. [Department Management](#4-department-management)
5. [Menu & Permissions](#5-menu--permissions)
6. [OAuth2 Social Login](#6-oauth2-social-login)
7. [Email Plugin](#7-email-plugin)
8. [System Configuration](#8-system-configuration)
9. [Database & Credits](#9-database--credits)
10. [Middleware Stack](#10-middleware-stack)

---

## 1. Authentication

Authentication uses **JWT (JSON Web Tokens)** stored in Redis with configurable expiration.

### Token Configuration (from `.env`)

| Setting | Default | Description |
|---------|---------|-------------|
| `TOKEN_EXPIRE_SECONDS` | 86400 (1 day) | Access token lifetime |
| `TOKEN_REFRESH_EXPIRE_SECONDS` | 604800 (7 days) | Refresh token lifetime |
| `TOKEN_SECRET_KEY` | required | Secret for signing tokens |

### POST `/auth/login`

Authenticate user and receive JWT tokens.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123",
  "uuid": "optional-captcha-uuid",
  "captcha": "optional-captcha-code"
}
```

**Response:**
```json
{
  "code": 200,
  "msg": "Success",
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 86400,
    "refresh_token": "eyJ...",
    "session_uuid": "abc123"
  }
}
```

**Rate Limited:** 5 requests per minute

---

### POST `/auth/refresh`

Get new access token using refresh token.

**Headers:** `Authorization: Bearer <refresh_token>`

**Response:**
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJ...",
    "expires_in": 86400
  }
}
```

---

### POST `/auth/logout`

Invalidate tokens and end session.

**Headers:** `Authorization: Bearer <access_token>`

**Response:** `{"code": 200, "msg": "Success"}`

---

### GET `/auth/codes`

Get all permission codes for current user.

**Headers:** `Authorization: Bearer <access_token>`

**Response:**
```json
{
  "code": 200,
  "data": ["sys:user:add", "sys:user:edit", "sys:role:view"]
}
```

---

## 2. User Management

All endpoints require `Authorization: Bearer <token>` header.

### GET `/admin/users/me`

Get current authenticated user info.

**Response:**
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "uuid": "abc123",
    "username": "admin",
    "nickname": "Administrator",
    "email": "admin@example.com",
    "phone": "1234567890",
    "avatar": "https://...",
    "status": 1,
    "is_superuser": true,
    "is_staff": true,
    "join_time": "2024-01-01T00:00:00Z",
    "last_login_time": "2024-12-21T10:00:00Z",
    "dept": "IT Department",
    "roles": ["Admin", "Developer"]
  }
}
```

---

### GET `/admin/users`

List all users with pagination.

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `dept` | int | Filter by department ID |
| `username` | string | Filter by username |
| `phone` | string | Filter by phone |
| `status` | int | Filter by status (0=disabled, 1=active) |
| `page` | int | Page number |
| `size` | int | Page size |

---

### GET `/admin/users/{id}`

Get user by ID.

---

### POST `/admin/users`

Create new user. **Requires: Superuser**

**Request:**
```json
{
  "username": "newuser",
  "password": "Password123",
  "nickname": "New User",
  "email": "user@example.com",
  "phone": "1234567890",
  "dept_id": 1,
  "roles": [1, 2]
}
```

---

### PUT `/admin/users/{id}`

Update user. **Requires: Superuser**

**Request:**
```json
{
  "username": "updateduser",
  "nickname": "Updated Name",
  "email": "new@example.com",
  "dept_id": 2,
  "roles": [1, 3]
}
```

---

### PUT `/admin/users/me/password`

Change current user's password.

**Request:**
```json
{
  "old_password": "currentpass",
  "new_password": "newpass123",
  "confirm_password": "newpass123"
}
```

---

### PUT `/admin/users/{id}/password`

Reset user password. **Requires: Superuser**

**Request:**
```json
{
  "password": "newpassword123"
}
```

---

### DELETE `/admin/users/{id}`

Delete user. **Requires: Permission `sys:user:del`**

---

## 3. Role Management

### GET `/admin/roles`

List all roles with pagination.

**Query:** `?name=Admin&status=1`

---

### GET `/admin/roles/all`

Get all roles (no pagination).

---

### GET `/admin/roles/{id}`

Get role details with relationships.

---

### POST `/admin/roles`

Create role. **Requires: Permission `sys:role:add`**

**Request:**
```json
{
  "name": "Editor",
  "code": "editor",
  "sort": 1,
  "status": 1,
  "remark": "Content editor role"
}
```

---

### PUT `/admin/roles/{id}`

Update role. **Requires: Permission `sys:role:edit`**

---

### PUT `/admin/roles/{id}/menus`

Assign menus to role. **Requires: Permission `sys:role:menu:edit`**

**Request:**
```json
{
  "menus": [1, 2, 3, 4, 5]
}
```

---

### PUT `/admin/roles/{id}/scopes`

Assign data scopes to role. **Requires: Permission `sys:role:scope:edit`**

**Request:**
```json
{
  "data_scopes": [1, 2]
}
```

---

### DELETE `/admin/roles`

Batch delete roles. **Requires: Permission `sys:role:del`**

**Request:**
```json
{
  "pks": [1, 2, 3]
}
```

---

## 4. Department Management

### GET `/admin/depts`

Get department tree structure.

---

### GET `/admin/depts/{id}`

Get department details.

---

### POST `/admin/depts`

Create department. **Requires: Permission `sys:dept:add`**

**Request:**
```json
{
  "name": "Engineering",
  "parent_id": 0,
  "sort": 1,
  "leader": "John Doe",
  "phone": "1234567890",
  "email": "eng@company.com",
  "status": 1
}
```

---

### PUT `/admin/depts/{id}`

Update department. **Requires: Permission `sys:dept:edit`**

---

### DELETE `/admin/depts/{id}`

Delete department. **Requires: Permission `sys:dept:del`**

---

## 5. Menu & Permissions

### GET `/admin/menus`

Get menu tree structure.

---

### GET `/admin/menus/{id}`

Get menu details.

---

### POST `/admin/menus`

Create menu/permission. **Requires: Permission `sys:menu:add`**

**Request:**
```json
{
  "title": "User Management",
  "name": "UserManagement",
  "parent_id": 0,
  "type": 1,
  "icon": "user",
  "path": "/admin/users",
  "component": "views/admin/user/index",
  "perms": "sys:user:view",
  "sort": 1,
  "status": 1
}
```

**Menu Types:**
| Type | Description |
|------|-------------|
| 0 | Directory |
| 1 | Menu |
| 2 | Button/Permission |

---

## 6. OAuth2 Social Login

### GitHub

#### GET `/oauth2/github`

Get GitHub authorization URL.

**Response:**
```json
{
  "code": 200,
  "data": "https://github.com/login/oauth/authorize?client_id=...&state=..."
}
```

#### GET `/oauth2/github/callback`

GitHub OAuth callback (handles automatically).

**Redirects to:** `{OAUTH2_FRONTEND_LOGIN_REDIRECT_URI}?access_token=...&session_uuid=...`

---

### Google

#### GET `/oauth2/google`

Get Google authorization URL.

#### GET `/oauth2/google/callback`

Google OAuth callback.

---

### Linux.do

#### GET `/oauth2/linux-do`

Get Linux.do authorization URL.

#### GET `/oauth2/linux-do/callback`

Linux.do OAuth callback.

---

### Configuration (.env)

```env
OAUTH2_GITHUB_CLIENT_ID=your_client_id
OAUTH2_GITHUB_CLIENT_SECRET=your_client_secret
OAUTH2_GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/oauth2/github/callback

OAUTH2_GOOGLE_CLIENT_ID=your_client_id
OAUTH2_GOOGLE_CLIENT_SECRET=your_client_secret
OAUTH2_GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/oauth2/google/callback

OAUTH2_FRONTEND_LOGIN_REDIRECT_URI=http://localhost:3000/oauth/callback
OAUTH2_FRONTEND_BINDING_REDIRECT_URI=http://localhost:3000/oauth/binding
```

---

## 7. Email Plugin

### POST `/email/captcha`

Send email verification code.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "recipients": "user@example.com"
}
```

Or multiple recipients:
```json
{
  "recipients": ["user1@example.com", "user2@example.com"]
}
```

**How it works:**
1. Generates 6-digit code
2. Stores in Redis with prefix `fba:email:captcha:{ip}`
3. Sends email using configured SMTP

### Configuration (.env)

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your@email.com
EMAIL_PASSWORD=your_app_password
EMAIL_USE_TLS=True
EMAIL_FROM=noreply@example.com

EMAIL_CAPTCHA_REDIS_PREFIX=fba:email:captcha
EMAIL_CAPTCHA_EXPIRE_SECONDS=300
```

---

## 8. System Configuration

### GET `/config/all`

Get all system configurations.

**Query:** `?type=system`

---

### GET `/config/{id}`

Get configuration by ID.

---

### GET `/config`

Get configurations with pagination.

**Query:** `?name=site_name&type=system`

---

### POST `/config`

Create configuration. **Requires: Permission `sys:config:add`**

**Request:**
```json
{
  "name": "site_name",
  "key": "SITE_NAME",
  "value": "My Application",
  "type": "system",
  "remark": "Application name"
}
```

---

### PUT `/config/{id}`

Update configuration. **Requires: Permission `sys:config:edit`**

---

### DELETE `/config`

Batch delete configurations. **Requires: Permission `sys:config:del`**

---

## 9. Database & Credits

### Database Configuration (.env)

```env
DATABASE_TYPE=postgresql        # postgresql or mysql
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
DATABASE_SCHEMA=fba             # Use 'postgres' for Supabase
```

### User Credits System

Credits are stored directly in the `sys_user` table:

| Column | Type | Description |
|--------|------|-------------|
| `credits` | float | Main credit balance |
| `bonus_credits` | float | Bonus credits (used first) |

**How Credits Work:**

1. **Storage:** Each user has `credits` and `bonus_credits` columns
2. **Deduction:** When AI is used, credits are calculated based on tokens
3. **Priority:** Bonus credits are used before regular credits
4. **Tracking:** `agent_session_metrics` table tracks usage per session

### Credit Calculation Formula

```python
# Per 1000 tokens
input_cost = input_tokens * 0.01   # $0.01 per 1K input
output_cost = output_tokens * 0.03  # $0.03 per 1K output
total_credits = input_cost + output_cost
```

### Giving Users Credits

**Option 1: API (Update User)**
```bash
curl -X PUT http://localhost:8000/api/v1/admin/users/123 \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"credits": 100.0, "bonus_credits": 10.0}'
```

**Option 2: Direct SQL**
```sql
UPDATE sys_user SET credits = 100.0, bonus_credits = 10.0 WHERE id = 123;
```

**Option 3: Default for New Users**
Configure in `backend/app/admin/service/user_service.py` or via migration.

---

## 10. Middleware Stack

### JWT Authentication Middleware

Validates `Authorization: Bearer <token>` header on all protected routes.

**Excluded Paths:**
- `/api/v1/auth/login`
- `/api/v1/monitors/redis`
- `/api/v1/monitors/server`

### Access Log Middleware

Logs all requests with:
- Request path, method
- Response status
- Duration

### Opera Log Middleware

Audit trail for operations:
- User ID, IP address
- Operation type
- Request/Response data
- Timestamp

### I18n Middleware

Detects language from `Accept-Language` header.

Supported: `en-US`, `zh-CN`

### State Middleware

Manages per-request context (user ID, IP, trace ID).

---

## Response Format

All API responses follow this structure:

```json
{
  "code": 200,
  "msg": "Success",
  "data": { ... }
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized (invalid/missing token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Internal Server Error |

---

## Quick Test Commands

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.data.access_token')

# 2. Get current user
curl http://localhost:8000/api/v1/admin/users/me \
  -H "Authorization: Bearer $TOKEN"

# 3. List all users
curl http://localhost:8000/api/v1/admin/users \
  -H "Authorization: Bearer $TOKEN"

# 4. List all roles
curl http://localhost:8000/api/v1/admin/roles/all \
  -H "Authorization: Bearer $TOKEN"
```
