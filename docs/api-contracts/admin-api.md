# Admin API Reference

> Complete API documentation for admin, user management, and system endpoints.

---

## Quick Reference

| Category | Base Path | Description |
|----------|-----------|-------------|
| [Auth](#authentication) | `/api/v1/admin/auth` | Login, logout, register |
| [Users](#user-management) | `/api/v1/admin/users` | User CRUD, profiles |
| [Roles](#role-management) | `/api/v1/admin/roles` | Role permissions |
| [Depts](#department-management) | `/api/v1/admin/depts` | Departments |
| [Menus](#menu-management) | `/api/v1/admin/menus` | Navigation menus |
| [OAuth2](#oauth2-social-login) | `/api/v1/oauth2` | Social login |

---

## Authentication

### Login

**`POST /api/v1/admin/auth/login`**

```json
{
  "username": "admin",
  "password": "password123"
}
```

**Response:**
```json
{
  "code": 200,
  "msg": "Success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "access_token_expire_time": "2024-12-29T00:00:00Z",
    "session_uuid": "abc-123-def",
    "user": {
      "id": 1,
      "uuid": "user-uuid",
      "username": "admin",
      "nickname": "Administrator",
      "email": "admin@example.com",
      "avatar": null,
      "phone": null,
      "roles": [{"id": 1, "name": "admin"}],
      "dept": {"id": 1, "name": "HQ"}
    }
  }
}
```

---

### Logout

**`POST /api/v1/admin/auth/logout`**

Headers: `Authorization: Bearer {token}`

---

### Token Refresh

**`POST /api/v1/admin/auth/token/refresh`**

Uses HTTP-only cookie for refresh token.

**Response:**
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "access_token_expire_time": "2024-12-29T00:00:00Z"
  }
}
```

---

### Register

**`POST /api/v1/admin/auth/register`**

```json
{
  "username": "newuser",
  "password": "SecurePass123!",
  "email": "user@example.com",
  "nickname": "New User"
}
```

---

### Get Captcha

**`GET /api/v1/admin/auth/captcha`**

**Response:**
```json
{
  "code": 200,
  "data": {
    "image": "data:image/png;base64,...",
    "captcha_key": "captcha-uuid"
  }
}
```

---

## User Management

### Get Current User

**`GET /api/v1/admin/users/me`**

Headers: `Authorization: Bearer {token}`

**Response:**
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "uuid": "user-uuid",
    "username": "admin",
    "nickname": "Administrator",
    "email": "admin@example.com",
    "phone": null,
    "avatar": null,
    "status": 1,
    "is_superuser": true,
    "is_multi_login": false,
    "roles": [...],
    "dept": {...},
    "created_time": "2024-01-01T00:00:00Z"
  }
}
```

---

### List Users

**`GET /api/v1/admin/users`**

Query params:
- `page`: Page number (default: 1)
- `size`: Page size (default: 20)
- `username`: Filter by username
- `status`: Filter by status (1=active, 0=inactive)
- `dept_id`: Filter by department

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "size": 20,
    "pages": 5
  }
}
```

---

### Create User

**`POST /api/v1/admin/users`**

```json
{
  "username": "newuser",
  "password": "SecurePass123!",
  "nickname": "New User",
  "email": "user@example.com",
  "phone": "1234567890",
  "dept_id": 1,
  "role_ids": [2, 3]
}
```

---

### Update User

**`PUT /api/v1/admin/users/{user_id}`**

```json
{
  "nickname": "Updated Name",
  "email": "newemail@example.com",
  "status": 1
}
```

---

### Delete User

**`DELETE /api/v1/admin/users/{user_id}`**

---

### Update Avatar

**`PUT /api/v1/admin/users/avatar`**

Content-Type: `multipart/form-data`

```
file: <image file>
```

---

### Reset Password

**`PUT /api/v1/admin/users/{user_id}/password/reset`**

```json
{
  "new_password": "NewSecurePass123!"
}
```

---

## Role Management

### List Roles

**`GET /api/v1/admin/roles`**

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "name": "admin",
      "data_scope": 1,
      "status": 1,
      "remark": "Administrator role",
      "menus": [...]
    }
  ]
}
```

---

### Create Role

**`POST /api/v1/admin/roles`**

```json
{
  "name": "editor",
  "data_scope": 2,
  "menu_ids": [1, 2, 3],
  "remark": "Content editor role"
}
```

---

### Get Role Menus

**`GET /api/v1/admin/roles/{role_id}/menus`**

**Response:**
```json
{
  "code": 200,
  "data": [
    {"id": 1, "name": "Dashboard"},
    {"id": 2, "name": "Users"}
  ]
}
```

---

## Department Management

### Department Tree

**`GET /api/v1/admin/depts/tree`**

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "name": "Headquarters",
      "parent_id": null,
      "children": [
        {"id": 2, "name": "Engineering", "children": []},
        {"id": 3, "name": "Sales", "children": []}
      ]
    }
  ]
}
```

---

### Create Department

**`POST /api/v1/admin/depts`**

```json
{
  "name": "New Department",
  "parent_id": 1,
  "sort": 10,
  "leader": "John Doe",
  "phone": "1234567890",
  "email": "dept@example.com"
}
```

---

## Menu Management

### Menu Tree

**`GET /api/v1/admin/menus/tree`**

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "name": "System",
      "path": "/system",
      "component": "Layout",
      "icon": "setting",
      "type": 0,
      "children": [
        {
          "id": 2,
          "name": "Users",
          "path": "/system/users",
          "component": "system/users/index",
          "type": 1
        }
      ]
    }
  ]
}
```

---

### Create Menu

**`POST /api/v1/admin/menus`**

```json
{
  "name": "New Menu",
  "path": "/new-menu",
  "component": "new-menu/index",
  "icon": "star",
  "type": 1,
  "parent_id": 1,
  "sort": 10,
  "perms": "system:menu:list"
}
```

**Menu Types:**
- `0`: Directory
- `1`: Menu
- `2`: Button/Permission

---

## OAuth2 (Social Login)

### Get GitHub Auth URL

**`GET /api/v1/oauth2/github`**

**Response:**
```json
{
  "code": 200,
  "data": "https://github.com/login/oauth/authorize?client_id=xxx&redirect_uri=xxx&state=xxx"
}
```

---

### Get Google Auth URL

**`GET /api/v1/oauth2/google`**

**Response:**
```json
{
  "code": 200,
  "data": "https://accounts.google.com/o/oauth2/auth?client_id=xxx&redirect_uri=xxx&state=xxx"
}
```

---

### List Linked Social Accounts

**`GET /api/v1/oauth2/user-social/list`**

Headers: `Authorization: Bearer {token}`

**Response:**
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "source": "github",
      "sid": "12345678",
      "created_time": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

### Bind Social Account

**`GET /api/v1/oauth2/user-social/{provider}/bind`**

Providers: `github`, `google`, `linux-do`

Redirects to OAuth provider for binding.

---

### Unbind Social Account

**`DELETE /api/v1/oauth2/user-social/{social_id}`**

---

## Login Logs

### List Login Logs

**`GET /api/v1/admin/logs/login`**

Query params:
- `page`, `size`: Pagination
- `username`: Filter by username
- `status`: `0`=fail, `1`=success
- `ip`: Filter by IP

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "username": "admin",
        "ip": "192.168.1.1",
        "os": "Windows 10",
        "browser": "Chrome 120",
        "status": 1,
        "msg": "Login successful",
        "login_time": "2024-12-28T10:00:00Z"
      }
    ],
    "total": 100
  }
}
```

---

## Operation Logs

### List Operation Logs

**`GET /api/v1/admin/logs/opera`**

Query params:
- `page`, `size`: Pagination
- `username`: Filter by username
- `method`: HTTP method (GET, POST, etc.)
- `status`: Response status code

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
        "path": "/api/v1/admin/users",
        "status": 200,
        "response_time": 150,
        "ip": "192.168.1.1",
        "created_time": "2024-12-28T10:00:00Z"
      }
    ],
    "total": 100
  }
}
```

---

## Config Management

### Get System Config

**`GET /api/v1/plugin/config`**

**Response:**
```json
{
  "code": 200,
  "data": {
    "site_title": "Agents Backend",
    "site_description": "AI Agent Platform",
    "enable_registration": true,
    "enable_captcha": true
  }
}
```

---

### Update System Config

**`PUT /api/v1/plugin/config`**

```json
{
  "site_title": "New Title",
  "enable_registration": false
}
```

---

## Notice/Announcements

### List Notices

**`GET /api/v1/plugin/notice`**

**Response:**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "title": "System Maintenance",
        "content": "Scheduled maintenance...",
        "type": 1,
        "status": 1,
        "created_time": "2024-12-28T10:00:00Z"
      }
    ]
  }
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "code": 400,
  "msg": "Error message",
  "data": null
}
```

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Server Error |

---

## Related Documentation

- [Authentication Guide](../frontend-connect/authentication.md) - Frontend auth integration
- [Agent API](./agent-api.md) - Agent chat and sandbox APIs
- [MCP Settings API](../frontend-connect/mcp-settings-api.md) - MCP configuration
