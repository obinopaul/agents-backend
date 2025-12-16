# Redis Configuration

This document provides detailed documentation for the Redis client in `backend/database/redis.py`.

---

## Overview

The application uses Redis for:
- Token/session storage
- Rate limiting
- Caching user data
- Celery message broker (development)
- Operation log queuing

---

## Redis Client Class

```python
class RedisCli(Redis):
    """Custom Redis client with extended functionality"""
    
    def __init__(self) -> None:
        super().__init__(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DATABASE,
            socket_timeout=settings.REDIS_TIMEOUT,
            socket_connect_timeout=settings.REDIS_TIMEOUT,
            socket_keepalive=True,           # Keep connections alive
            health_check_interval=30,         # Health check every 30s
            decode_responses=True,            # Auto-decode to UTF-8
        )
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `REDIS_HOST` | - | Redis server hostname |
| `REDIS_PORT` | - | Redis server port |
| `REDIS_PASSWORD` | - | Authentication password |
| `REDIS_DATABASE` | - | Database number (0-15) |
| `REDIS_TIMEOUT` | 5 | Socket timeout in seconds |

---

## Connection Management

### Opening Connection

```python
async def open(self) -> None:
    """Initialize and verify Redis connection"""
    try:
        await self.ping()
    except TimeoutError:
        log.error('❌ Redis connection timeout')
        sys.exit()
    except AuthenticationError:
        log.error('❌ Redis authentication failed')
        sys.exit()
    except Exception as e:
        log.error('❌ Redis connection error: {}', e)
        sys.exit()
```

**Lifecycle:**
```
Application Startup
        │
        ▼
┌───────────────────────┐
│  redis_client.open()  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│      ping()           │ ──── Verify connection
└───────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
 Success         Failure
    │               │
    ▼               ▼
 Continue       sys.exit()
```

---

## Utility Methods

### delete_prefix() - Batch Delete by Prefix

```python
async def delete_prefix(
    self, 
    prefix: str, 
    exclude: str | list[str] | None = None, 
    batch_size: int = 1000
) -> None:
    """
    Delete all keys matching a prefix.
    
    Args:
        prefix: Key prefix to match (e.g., "fba:token:")
        exclude: Keys to exclude from deletion
        batch_size: Delete in batches to avoid blocking
    """
```

**Usage:**

```python
# Delete all tokens
await redis_client.delete_prefix("fba:token:")

# Delete all tokens except specific ones
await redis_client.delete_prefix(
    "fba:token:", 
    exclude=["fba:token:admin", "fba:token:superuser"]
)
```

**Implementation:**
```
SCAN keys matching prefix*
        │
        ▼
   For each key:
   ┌────────────────────┐
   │ In exclude set?    │
   └────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
   Yes             No
    │               │
    ▼               ▼
   Skip         Add to batch
                    │
                    ▼
            ┌───────────────┐
            │ Batch full?   │
            └───────┬───────┘
                    │
            ┌───────┴───────┐
            │               │
            ▼               ▼
           Yes             No
            │               │
            ▼               ▼
        DELETE batch    Continue
```

---

### get_prefix() - List Keys by Prefix

```python
async def get_prefix(self, prefix: str, count: int = 100) -> list[str]:
    """
    Get all keys matching a prefix.
    
    Args:
        prefix: Key prefix to match
        count: Batch size for scanning (larger = faster but more resource intensive)
    
    Returns:
        List of matching keys
    """
```

**Usage:**

```python
# Get all active tokens
token_keys = await redis_client.get_prefix("fba:token:")
print(f"Active tokens: {len(token_keys)}")
```

---

## Common Operations

### Basic Key-Value

```python
# Set with expiration
await redis_client.set("key", "value", ex=3600)  # Expire in 1 hour

# Set with expiration (milliseconds)
await redis_client.set("key", "value", px=60000)  # Expire in 1 minute

# Get value
value = await redis_client.get("key")

# Delete key
await redis_client.delete("key")

# Check existence
exists = await redis_client.exists("key")
```

### Hash Operations

```python
# Set hash field
await redis_client.hset("user:1", "name", "John")

# Set multiple fields
await redis_client.hset("user:1", mapping={"name": "John", "age": 30})

# Get field
name = await redis_client.hget("user:1", "name")

# Get all fields
user = await redis_client.hgetall("user:1")
```

### List Operations

```python
# Push to list
await redis_client.rpush("queue", "item1", "item2")

# Pop from list
item = await redis_client.lpop("queue")

# Get list length
length = await redis_client.llen("queue")
```

### Set Operations

```python
# Add to set
await redis_client.sadd("tags", "python", "fastapi")

# Check membership
is_member = await redis_client.sismember("tags", "python")

# Get all members
tags = await redis_client.smembers("tags")
```

---

## Key Prefixes Used in Application

| Prefix | Purpose | TTL |
|--------|---------|-----|
| `fba:token:` | Access tokens | 1 day |
| `fba:refresh_token:` | Refresh tokens | 7 days |
| `fba:user:` | User info cache | Variable |
| `fba:token_online:` | Online users | Session |
| `fba:login:captcha:` | Login captcha | 5 min |
| `fba:login:failure:` | Failed login attempts | Variable |
| `fba:user:lock:` | Locked users | 5 min |
| `fba:oauth2:state:` | OAuth state | 3 min |
| `fba:email:captcha:` | Email captcha | 3 min |
| `fba:ip:location:` | IP geolocation cache | 1 day |
| `fba:limiter:` | Rate limiting | Variable |
| `fba:celery:` | Celery tasks | Variable |
| `fba:snowflake:` | Snowflake node | 60s |

---

## Singleton Pattern

```python
# Global singleton instance
redis_client: RedisCli = RedisCli()
```

**Usage anywhere in the application:**

```python
from backend.database.redis import redis_client

async def some_function():
    await redis_client.set("key", "value")
```

---

## Error Handling

```python
from redis.exceptions import RedisError

try:
    await redis_client.get("key")
except RedisError as e:
    log.error(f"Redis error: {e}")
    # Handle error or return default
```

---

## Connection Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION                                  │
│                                                                     │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│   │   Request   │    │   Request   │    │   Request   │            │
│   │   Handler   │    │   Handler   │    │   Handler   │            │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘            │
│          │                  │                  │                    │
│          └──────────────────┼──────────────────┘                    │
│                             │                                       │
│                             ▼                                       │
│                 ┌───────────────────────┐                           │
│                 │     redis_client      │                           │
│                 │     (RedisCli)        │                           │
│                 │     ─────────────     │                           │
│                 │  • Connection pool    │                           │
│                 │  • Health checks      │                           │
│                 │  • Auto-reconnect     │                           │
│                 └───────────┬───────────┘                           │
│                             │                                       │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              ▼
                 ┌───────────────────────┐
                 │     REDIS SERVER      │
                 │     ─────────────     │
                 │  • Database 0-15      │
                 │  • Key-value store    │
                 │  • Pub/sub            │
                 └───────────────────────┘
```

---

## Best Practices

1. **Use appropriate TTLs**: Always set expiration for temporary data
2. **Use prefixes**: Group related keys with consistent prefixes
3. **Batch operations**: Use pipelines for multiple operations
4. **Handle errors**: Always catch Redis exceptions
5. **Monitor memory**: Use `INFO memory` to check usage

---

## Related Documentation

- [SQLAlchemy Configuration](./sqlalchemy.md) - Primary database
- [Configuration](../core/configuration.md) - Redis settings

---

*Last Updated: December 2024*
