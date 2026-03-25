# Utilities Module

The `utils/` directory contains shared utility functions used throughout the application.

---

## Directory Structure

```
utils/
├── __init__.py              # Package initialization
├── snowflake.py             # Snowflake ID generation
├── serializers.py           # MsgSpec JSON serialization
├── encrypt.py               # Encryption helpers
├── timezone.py              # Timezone utilities
├── file_ops.py              # File operations
├── dynamic_config.py        # Dynamic configuration
├── health_check.py          # Health check utilities
├── server_info.py           # Server information
├── request_parse.py         # Request parsing
├── ip_location.py           # IP geolocation
├── import_parse.py          # Dynamic imports
├── build_tree.py            # Tree structure building
├── format_string.py         # String formatting
├── paginaction.py           # Pagination helpers
├── re_verify.py             # Regex validation
├── demo_site.py             # Demo mode utilities
├── gen_template.py          # Template generation
└── openapi.py               # OpenAPI utilities
```

---

## Key Utilities

### Snowflake ID Generation

```python
# snowflake.py
from backend.utils.snowflake import snowflake

# Generate unique ID
user_id = await snowflake.generate()
# Returns: 7173912345678901234 (64-bit integer)
```

**Features:**
- Distributed ID generation
- Time-ordered IDs
- Worker/datacenter isolation
- Redis-based node registration

---

### JSON Serialization

```python
# serializers.py
from backend.utils.serializers import MsgSpecJSONResponse

# High-performance JSON response
return MsgSpecJSONResponse(content={"data": result})
```

**Benefits:**
- Faster than orjson
- Datetime handling
- Custom encoder support

---

### Encryption

```python
# encrypt.py
from backend.utils.encrypt import hash_password, verify_password

# Hash password
hashed = hash_password("my_password")

# Verify password
is_valid = verify_password("my_password", hashed)
```

---

### Timezone

```python
# timezone.py
from backend.utils.timezone import timezone

# Get current time
now = timezone.now()  # Timezone-aware datetime

# Convert to string
formatted = timezone.strftime(now)  # "2024-12-14 15:30:00"

# Parse string
dt = timezone.strptime("2024-12-14 15:30:00")
```

---

### File Operations

```python
# file_ops.py
from backend.utils.file_ops import save_upload_file, delete_file

# Save uploaded file
path = await save_upload_file(file, "images")

# Delete file
await delete_file(path)
```

---

### IP Location

```python
# ip_location.py
from backend.utils.ip_location import get_ip_location

# Get location from IP
location = await get_ip_location("8.8.8.8")
# Returns: "United States, California, Mountain View"
```

**Modes:**
- `online`: Query external API
- `offline`: Local database lookup
- `false`: Disabled

---

### Tree Building

```python
# build_tree.py
from backend.utils.build_tree import build_tree

# Convert flat list to tree
tree = build_tree(menus, parent_id=0)
```

---

## Related Documentation

- [Configuration](../core/configuration.md) - Settings used by utilities
- [Database](../database/README.md) - Snowflake Redis integration

---

*Last Updated: December 2024*
