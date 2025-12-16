# Role-Based Access Control (RBAC)

This document provides detailed documentation for RBAC in `backend/common/security/rbac.py`.

---

## Overview

RBAC enforces authorization by checking if the authenticated user's roles have the required menu permissions for the requested endpoint.

---

## RBAC Verification Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      INCOMING REQUEST                                │
│              GET /api/v1/admin/users (requires: sys:user:list)       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: PATH WHITELIST CHECK                                        │
│ ─────────────────────────────                                       │
│ Is path in TOKEN_REQUEST_PATH_EXCLUDE?                              │
│ Does path match TOKEN_REQUEST_PATH_EXCLUDE_PATTERN?                 │
│                                                                     │
│ YES ────────────────────────────────────────────────────▶  ALLOW    │
│  NO │                                                               │
└─────┼───────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: JWT AUTHENTICATION CHECK                                    │
│ ────────────────────────────────                                    │
│ Does request.auth.scopes exist?                                     │
│                                                                     │
│  NO ────────────────────────────────────────────────────▶  DENY     │
│      (TokenError)                                                   │
│ YES │                                                               │
└─────┼───────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: SUPERUSER CHECK                                             │
│ ───────────────────────                                             │
│ Is request.user.is_superuser == True?                               │
│                                                                     │
│ YES ────────────────────────────────────────────────────▶  ALLOW    │
│  NO │                                                               │
└─────┼───────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: ROLE ASSIGNMENT CHECK                                       │
│ ─────────────────────────────                                       │
│ Does user have any active roles?                                    │
│                                                                     │
│  NO ────────────────────────────────────────────────────▶  DENY     │
│      (AuthorizationError: "User has no roles")                      │
│ YES │                                                               │
└─────┼───────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: MENU ASSIGNMENT CHECK                                       │
│ ─────────────────────────────                                       │
│ Do any of user's roles have menus assigned?                         │
│                                                                     │
│  NO ────────────────────────────────────────────────────▶  DENY     │
│      (AuthorizationError: "User has no menus")                      │
│ YES │                                                               │
└─────┼───────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: STAFF PERMISSION CHECK (for write operations)               │
│ ────────────────────────────────────────────────────────            │
│ If method is POST/PUT/DELETE/PATCH:                                 │
│   Is request.user.is_staff == True?                                 │
│                                                                     │
│  NO ────────────────────────────────────────────────────▶  DENY     │
│      (AuthorizationError: "User not staff")                         │
│ YES │                                                               │
└─────┼───────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: PERMISSION STRING CHECK                                     │
│ ───────────────────────────────                                     │
│                                                                     │
│ path_auth_perm = "sys:user:list"  (from route definition)           │
│                                                                     │
│ IF path_auth_perm is None ─────────────────────────────▶  ALLOW     │
│    (optional permission)                                            │
│                                                                     │
│ IF path_auth_perm in RBAC_ROLE_MENU_EXCLUDE ───────────▶  ALLOW     │
│    (excluded from checking)                                         │
│                                                                     │
│ For each role in user.roles:                                        │
│   For each menu in role.menus:                                      │
│     If menu.perms contains path_auth_perm ──────────────▶  ALLOW    │
│                                                                     │
│ If not found ──────────────────────────────────────────▶  DENY      │
│    (AuthorizationError)                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Main Function

### rbac_verify()

```python
async def rbac_verify(request: Request, _token: str = DependsJwtAuth) -> None:
    """
    RBAC permission verification.
    
    Args:
        request: FastAPI request object
        _token: JWT token (validated by DependsJwtAuth)
    
    Raises:
        TokenError: No valid authentication
        AuthorizationError: Permission denied
    """
```

---

## Permission String Format

Permissions follow a hierarchical format:

```
{module}:{resource}:{action}

Examples:
  sys:user:list     - List users
  sys:user:add      - Create user
  sys:user:edit     - Update user
  sys:user:del      - Delete user
  sys:role:list     - List roles
  sys:menu:add      - Create menu
```

---

## Database Relationships

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│    User     │──────▶│   UserRole       │◀──────│    Role     │
├─────────────┤  1:N  ├──────────────────┤  N:1  ├─────────────┤
│ id          │       │ user_id          │       │ id          │
│ username    │       │ role_id          │       │ name        │
│ is_superuser│       └──────────────────┘       │ status      │
│ is_staff    │                                  └──────┬──────┘
└─────────────┘                                         │
                                                        │ 1:N
                                                        ▼
                      ┌──────────────────┐       ┌─────────────┐
                      │   RoleMenu       │◀──────│    Menu     │
                      ├──────────────────┤  N:1  ├─────────────┤
                      │ role_id          │       │ id          │
                      │ menu_id          │       │ title       │
                      └──────────────────┘       │ perms       │
                                                 │ status      │
                                                 └─────────────┘
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `TOKEN_REQUEST_PATH_EXCLUDE` | `['/api/v1/auth/login']` | Paths to skip auth |
| `TOKEN_REQUEST_PATH_EXCLUDE_PATTERN` | Regex patterns | Regex path whitelist |
| `RBAC_ROLE_MENU_MODE` | `True` | Enable role-menu RBAC |
| `RBAC_ROLE_MENU_EXCLUDE` | `['sys:monitor:*']` | Skip permission check |

---

## Dependency Injection

```python
DependsRBAC = Depends(rbac_verify)

# Usage in routes
@router.get("/users", dependencies=[Depends(rbac_verify)])
async def list_users():
    pass

# Or with parameter
@router.get("/users")
async def list_users(_: str = DependsRBAC):
    pass
```

---

## Setting Route Permissions

Permissions are set via the `dependencies` parameter or custom metadata:

```python
from backend.common.security.rbac import DependsRBAC

@router.get(
    "/users",
    summary="List users",
    dependencies=[DependsRBAC],
)
async def list_users():
    """
    Permission: sys:user:list
    """
    pass
```

The permission string is typically stored and matched via:
1. Route path mapping in database menus
2. Context variable `ctx.permission`

---

## Casbin Alternative

When `RBAC_ROLE_MENU_MODE = False`, the system falls back to Casbin RBAC:

```python
if not settings.RBAC_ROLE_MENU_MODE:
    casbin_rbac = import_module_cached('backend.plugin.casbin_rbac.rbac')
    await casbin_rbac.casbin_verify(request)
```

---

## Error Messages

| Error | Message |
|-------|---------|
| No roles | "User has no roles assigned" |
| No menus | "User has no menus assigned" |
| Not staff | "User cannot perform admin operations" |
| No permission | "Authorization failed" (generic) |

---

## Example Authorization Check

```python
# User with roles: ["editor", "viewer"]
# Editor role menus: [perms="content:post:list,content:post:edit"]
# Viewer role menus: [perms="content:post:list"]

# Request: GET /api/v1/posts (requires: content:post:list)
# Result: ALLOWED (both roles have this permission)

# Request: POST /api/v1/posts (requires: content:post:add)
# Result: DENIED (neither role has this permission)
```

---

## Related Documentation

- [JWT Authentication](./jwt.md) - Token validation
- [Security Overview](./README.md) - Security architecture

---

*Last Updated: December 2024*
