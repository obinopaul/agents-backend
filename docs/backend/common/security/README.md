# Security Module

The `security/` subdirectory contains authentication and authorization components.

---

## Directory Structure

```
security/
├── __init__.py           # Package exports
├── jwt.py                # JWT token management
├── rbac.py               # Role-based access control
└── permission.py         # Permission utilities
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         REQUEST                                      │
│                   Authorization: Bearer <token>                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    JWT AUTHENTICATION (jwt.py)                       │
│  ───────────────────────────────────────────                        │
│  1. Extract token from Authorization header                          │
│  2. Validate JWT signature and expiry                                │
│  3. Check token exists in Redis                                      │
│  4. Load user from cache or database                                 │
│  5. Set request.user and request.auth                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RBAC VERIFICATION (rbac.py)                       │
│  ───────────────────────────────────────────                        │
│  1. Check path whitelist                                             │
│  2. Verify user has roles assigned                                   │
│  3. Check superuser status (skip remaining checks)                   │
│  4. Verify role menus contain required permission                    │
│  5. Allow or deny access                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       ROUTE HANDLER                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### [jwt.py - JWT Token Management](./jwt.md)

Handles JWT token lifecycle:
- Token creation (access + refresh)
- Token validation
- Token revocation
- User authentication

**Key Functions:**
- `create_access_token()` - Generate access token
- `create_refresh_token()` - Generate refresh token
- `jwt_authentication()` - Validate and authenticate
- `revoke_token()` - Invalidate token

### [rbac.py - Role-Based Access Control](./rbac.md)

Implements permission checking:
- Path whitelist checking
- Role verification
- Menu permission matching
- Superuser bypass

**Key Functions:**
- `rbac_verify()` - Main RBAC check

### [permission.py - Permission Utilities](./permission.md)

Permission helpers and decorators:
- Permission extraction
- Access level checking

---

## Dependency Injection

### DependsJwtAuth

Requires valid JWT token:

```python
from backend.common.security.jwt import DependsJwtAuth

@router.get("/protected")
async def protected_route(_: str = DependsJwtAuth):
    # Token is valid
    return {"message": "authenticated"}
```

### DependsRBAC

Requires valid token AND permissions:

```python
from backend.common.security.rbac import DependsRBAC

@router.get("/admin/users")
async def admin_only(_: str = DependsRBAC):
    # User has required permission
    return {"users": [...]}
```

### DependsSuperUser

Requires superuser privileges:

```python
from backend.common.security.jwt import DependsSuperUser

@router.delete("/system/reset")
async def superuser_only(_: str = DependsSuperUser):
    # Only superusers can access
    return {"status": "reset complete"}
```

---

## Token Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          LOGIN                                       │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Validate credentials  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐         ┌───────────────────────┐
│ create_access_token() │────────▶│ Store in Redis        │
│ create_refresh_token()│         │ fba:token:{user_id}   │
└───────────┬───────────┘         └───────────────────────┘
            │
            ▼
┌───────────────────────┐
│ Return tokens to      │
│ client                │
└───────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                      API REQUEST                                     │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Extract Bearer token  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐         ┌───────────────────────┐
│ jwt_decode(token)     │────────▶│ Verify signature      │
│                       │         │ Check expiry          │
└───────────┬───────────┘         └───────────────────────┘
            │
            ▼
┌───────────────────────┐         ┌───────────────────────┐
│ Check Redis           │────────▶│ Token still valid?    │
│ fba:token:{user_id}   │         │ Not revoked?          │
└───────────┬───────────┘         └───────────────────────┘
            │
            ▼
┌───────────────────────┐
│ Load user object      │
│ Set request.user      │
└───────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                       LOGOUT                                         │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐         ┌───────────────────────┐
│ revoke_token()        │────────▶│ Delete from Redis     │
│                       │         │ fba:token:{user_id}   │
└───────────────────────┘         └───────────────────────┘
```

---

## Redis Keys Used

| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| `fba:token:{user_id}` | Store access token | 1 day |
| `fba:refresh_token:{session}` | Store refresh token | 7 days |
| `fba:token_extra_info:{user_id}` | Token metadata | 1 day |
| `fba:token_online:{user_id}` | Online status | Session |
| `fba:user:{user_id}` | User info cache | Variable |

---

## Related Documentation

- [JWT Reference](./jwt.md) - Token management details
- [RBAC Reference](./rbac.md) - Permission checking details
- [Permission Reference](./permission.md) - Permission utilities

---

*Last Updated: December 2024*
