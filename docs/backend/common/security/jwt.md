# JWT Token Management

This document provides detailed documentation for JWT authentication in `backend/common/security/jwt.py`.

---

## Overview

The application uses JSON Web Tokens (JWT) for stateless authentication with Redis-backed session management.

---

## Token Types

| Token | Purpose | Expiry |
|-------|---------|--------|
| Access Token | API authentication | 1 day (configurable) |
| Refresh Token | Generate new access tokens | 7 days (configurable) |

---

## Core Functions

### jwt_encode()

Generates a JWT token from a payload:

```python
def jwt_encode(payload: dict[str, Any]) -> str:
    """
    Encode payload to JWT token.
    
    Args:
        payload: Data to encode (user_id, exp, etc.)
    
    Returns:
        Encoded JWT string
    """
    return jwt.encode(
        payload, 
        settings.TOKEN_SECRET_KEY, 
        algorithm=settings.TOKEN_ALGORITHM
    )
```

---

### jwt_decode()

Decodes and validates a JWT token:

```python
def jwt_decode(token: str) -> dict[str, Any]:
    """
    Decode JWT token.
    
    Args:
        token: JWT string
    
    Returns:
        Decoded payload
    
    Raises:
        TokenError: If token is invalid or expired
    """
```

**Validation Steps:**
1. Verify signature with secret key
2. Check expiration (`exp` claim)
3. Return payload if valid

---

### create_access_token()

Creates an access token for a user:

```python
async def create_access_token(
    user_id: int, 
    *, 
    multi_login: bool, 
    **kwargs
) -> tuple[str, str]:
    """
    Generate access token.
    
    Args:
        user_id: User's database ID
        multi_login: Allow multiple device logins
        **kwargs: Additional token claims
    
    Returns:
        Tuple of (token, session_uuid)
    """
```

**Process:**
```
┌───────────────────────┐
│ Generate session UUID │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Build payload:        │
│ • sub: user_id        │
│ • exp: now + 1 day    │
│ • session: uuid       │
│ • ...kwargs           │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ jwt_encode(payload)   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Store in Redis:       │
│ fba:token:{user_id}   │
│ TTL: 1 day            │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Return (token, uuid)  │
└───────────────────────┘
```

---

### create_refresh_token()

Creates a refresh token:

```python
async def create_refresh_token(
    session_uuid: str, 
    user_id: int, 
    *, 
    multi_login: bool
) -> str:
    """
    Generate refresh token.
    
    Args:
        session_uuid: Session from access token
        user_id: User's database ID
        multi_login: Allow multiple device logins
    
    Returns:
        Refresh token string
    """
```

---

### create_new_token()

Refreshes an access token using a refresh token:

```python
async def create_new_token(
    refresh_token: str,
    session_uuid: str,
    user_id: int,
    *,
    multi_login: bool,
    **kwargs,
) -> tuple[str, str, str]:
    """
    Generate new token pair.
    
    Args:
        refresh_token: Current refresh token
        session_uuid: Current session UUID
        user_id: User's database ID
        multi_login: Allow multiple devices
        **kwargs: Additional claims
    
    Returns:
        Tuple of (new_access_token, new_refresh_token, new_session)
    """
```

---

### revoke_token()

Invalidates a token (logout):

```python
async def revoke_token(user_id: int, session_uuid: str) -> None:
    """
    Revoke user's token.
    
    Args:
        user_id: User's database ID
        session_uuid: Session to revoke
    """
    key = f"{settings.TOKEN_REDIS_PREFIX}:{user_id}"
    await redis_client.delete(key)
```

---

### get_token()

Extracts token from request:

```python
def get_token(request: Request) -> str | None:
    """
    Extract Bearer token from Authorization header.
    
    Args:
        request: FastAPI request object
    
    Returns:
        Token string or None
    """
    authorization = request.headers.get("Authorization")
    scheme, token = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer":
        return None
    return token
```

---

### get_current_user()

Loads user from database:

```python
async def get_current_user(db: AsyncSession, pk: int) -> User:
    """
    Load user by ID.
    
    Args:
        db: Database session
        pk: User primary key
    
    Returns:
        User model instance
    
    Raises:
        AuthorizationError: If user not found or inactive
    """
```

---

### jwt_authentication()

Main authentication function:

```python
async def jwt_authentication(token: str) -> dict[str, Any]:
    """
    Authenticate request with JWT.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        TokenError: If token invalid/expired/revoked
    """
```

**Authentication Flow:**
```
┌───────────────────────┐
│ jwt_decode(token)     │  Decode and verify signature
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Check expiration      │  Verify not expired
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Verify in Redis       │  Token not revoked
│ fba:token:{user_id}   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Return payload        │  user_id, session, etc.
└───────────────────────┘
```

---

### superuser_verify()

Verifies superuser status:

```python
async def superuser_verify(request: Request, _token: str = DependsJwtAuth) -> None:
    """
    Verify user is superuser.
    
    Raises:
        AuthorizationError: If not superuser
    """
    if not request.user.is_superuser:
        raise errors.AuthorizationError(msg='Only superusers allowed')
```

---

## Dependency Injection

### DependsJwtAuth

Basic JWT validation:

```python
DependsJwtAuth = Depends(HTTPBearer())

# Usage
@router.get("/protected")
async def route(_: str = DependsJwtAuth):
    pass
```

### DependsSuperUser

Superuser requirement:

```python
DependsSuperUser = Depends(superuser_verify)

# Usage
@router.delete("/admin/reset")
async def route(_: str = DependsSuperUser):
    pass
```

---

## Token Payload Structure

```python
{
    "sub": 1,                      # User ID
    "exp": 1702598400,             # Expiration timestamp
    "iat": 1702512000,             # Issued at timestamp
    "session": "uuid-string",      # Session identifier
    "multi_login": True,           # Multi-device flag
    # ... additional claims
}
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `TOKEN_SECRET_KEY` | Required | JWT signing key |
| `TOKEN_ALGORITHM` | `HS256` | JWT algorithm |
| `TOKEN_EXPIRE_SECONDS` | `86400` | Access token TTL (1 day) |
| `TOKEN_REFRESH_EXPIRE_SECONDS` | `604800` | Refresh token TTL (7 days) |
| `TOKEN_REDIS_PREFIX` | `fba:token` | Redis key prefix |

---

## Error Handling

| Error | Cause |
|-------|-------|
| `TokenError` | Invalid signature, expired, or revoked |
| `AuthorizationError` | User not found or inactive |

---

## Related Documentation

- [RBAC](./rbac.md) - Role-based access control
- [Security Overview](./README.md) - Security architecture

---

*Last Updated: December 2024*
