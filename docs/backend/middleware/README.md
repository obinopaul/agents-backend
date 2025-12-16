# Middleware Module

The `middleware/` module contains HTTP middleware components that process requests and responses.

---

## Directory Structure

```
middleware/
├── __init__.py              # Package initialization
├── access_middleware.py     # Request/response logging
├── i18n_middleware.py       # Language detection
├── jwt_auth_middleware.py   # JWT authentication
├── opera_log_middleware.py  # Operation audit logging
└── state_middleware.py      # Request state initialization
```

---

## Middleware Execution Order

Middleware executes in a specific order. **Request flows top-to-bottom; response flows bottom-to-top:**

```
                              REQUEST
                                 │
┌────────────────────────────────┼────────────────────────────────┐
│                                │                                │
│   ┌────────────────────────────▼────────────────────────────┐   │
│   │ 1. ContextMiddleware (starlette-context)                │   │
│   │    • Generate/validate X-Request-ID                     │   │
│   │    • Set up context variables                           │   │
│   └────────────────────────────┬────────────────────────────┘   │
│                                │                                │
│   ┌────────────────────────────▼────────────────────────────┐   │
│   │ 2. AccessMiddleware                                     │   │
│   │    • Log request start time                             │   │
│   │    • Record method, path, client IP                     │   │
│   └────────────────────────────┬────────────────────────────┘   │
│                                │                                │
│   ┌────────────────────────────▼────────────────────────────┐   │
│   │ 3. I18nMiddleware                                       │   │
│   │    • Detect Accept-Language header                      │   │
│   │    • Set translation context                            │   │
│   └────────────────────────────┬────────────────────────────┘   │
│                                │                                │
│   ┌────────────────────────────▼────────────────────────────┐   │
│   │ 4. AuthenticationMiddleware (JwtAuthMiddleware)         │   │
│   │    • Extract Bearer token                               │   │
│   │    • Validate JWT signature & expiry                    │   │
│   │    • Load user from Redis/database                      │   │
│   │    • Set request.user and request.auth                  │   │
│   └────────────────────────────┬────────────────────────────┘   │
│                                │                                │
│   ┌────────────────────────────▼────────────────────────────┐   │
│   │ 5. StateMiddleware                                      │   │
│   │    • Initialize request.state attributes                │   │
│   │    • Set up permission context                          │   │
│   └────────────────────────────┬────────────────────────────┘   │
│                                │                                │
│   ┌────────────────────────────▼────────────────────────────┐   │
│   │ 6. OperaLogMiddleware                                   │   │
│   │    • Capture request body                               │   │
│   │    • Queue operation log for async write                │   │
│   └────────────────────────────┬────────────────────────────┘   │
│                                │                                │
└────────────────────────────────┼────────────────────────────────┘
                                 │
                                 ▼
                          ROUTE HANDLER
                                 │
                                 ▼
                              RESPONSE
                          (reverse order)
```

---

## Middleware Components

### 1. ContextMiddleware (External)

**Source:** `starlette-context` library

Sets up request context variables including `X-Request-ID` for request tracing.

```python
app.add_middleware(
    ContextMiddleware,
    plugins=[RequestIdPlugin(validate=True)],
)
```

---

### 2. AccessMiddleware

**File:** `access_middleware.py`

Logs request timing and basic information.

```python
class AccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        log.info(f"{request.method} {request.url.path} - {process_time:.3f}s")
        
        return response
```

**Logged Information:**
- HTTP method
- Request path
- Processing time
- Client IP

---

### 3. I18nMiddleware

**File:** `i18n_middleware.py`

Detects and sets the language for internationalization.

```python
class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get language from Accept-Language header
        lang = request.headers.get("Accept-Language", "zh-CN")
        
        # Set translation context
        set_language(lang)
        
        return await call_next(request)
```

**Language Detection:**
1. `Accept-Language` header
2. Query parameter `?lang=en-US`
3. Default: `zh-CN`

---

### 4. JwtAuthMiddleware

**File:** `jwt_auth_middleware.py`

Handles JWT authentication for protected routes.

```python
class JwtAuthMiddleware(AuthenticationBackend):
    async def authenticate(self, request: Request):
        # Skip whitelisted paths
        if path in settings.TOKEN_REQUEST_PATH_EXCLUDE:
            return None
        
        # Extract and validate token
        token = get_token(request)
        if not token:
            return None
        
        # Validate JWT
        payload = await jwt_authentication(token)
        
        # Load user
        user = await get_current_user(db, payload['sub'])
        
        # Return credentials
        return AuthCredentials(['authenticated']), user
```

**Sets on Request:**
- `request.user` - User model instance
- `request.auth` - AuthCredentials with scopes

---

### 5. StateMiddleware

**File:** `state_middleware.py`

Initializes request state for use by route handlers.

```python
class StateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Initialize state
        request.state.permission = None
        request.state.ip = get_client_ip(request)
        
        return await call_next(request)
```

**State Attributes:**
- `permission` - Current route permission string
- `ip` - Client IP address
- Custom attributes as needed

---

### 6. OperaLogMiddleware

**File:** `opera_log_middleware.py` (~8KB)

Captures and logs all operations for auditing.

```python
class OperaLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Capture request body
        body = await request.body()
        
        response = await call_next(request)
        
        # Queue log entry
        await self.queue_log(request, response, body)
        
        return response
    
    @staticmethod
    async def consumer():
        """Background task to batch-write logs"""
        while True:
            logs = await queue.get_batch(100)
            await opera_log_crud.create_many(logs)
```

**Logged Information:**
- User ID
- Request path and method
- Request body (with sensitive data encrypted)
- Response status
- Processing time
- Client IP
- User agent

**Encryption:**
Sensitive fields are encrypted before logging:
- Passwords
- Tokens
- Personal data

---

## Registration in Registrar

```python
def register_middleware(app: FastAPI) -> None:
    """Register middleware (execution order: bottom to top)"""
    
    # 6. Opera log
    app.add_middleware(OperaLogMiddleware)
    
    # 5. State
    app.add_middleware(StateMiddleware)
    
    # 4. JWT auth
    app.add_middleware(
        AuthenticationMiddleware,
        backend=JwtAuthMiddleware(),
        on_error=JwtAuthMiddleware.auth_exception_handler,
    )
    
    # 3. I18n
    app.add_middleware(I18nMiddleware)
    
    # 2. Access log
    app.add_middleware(AccessMiddleware)
    
    # 1. Context (from starlette-context)
    app.add_middleware(
        ContextMiddleware,
        plugins=[RequestIdPlugin(validate=True)],
    )
```

**Note:** Middleware is added in reverse order because FastAPI builds the stack from bottom to top.

---

## Adding Custom Middleware

```python
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Before request
        print(f"Request: {request.url.path}")
        
        response = await call_next(request)
        
        # After response
        response.headers["X-Custom-Header"] = "value"
        
        return response

# Register in registrar.py
app.add_middleware(CustomMiddleware)
```

---

## Related Documentation

- [Core Registrar](../core/registrar.md) - Where middleware is registered
- [Security](../common/security/README.md) - JWT and RBAC details

---

*Last Updated: December 2024*
