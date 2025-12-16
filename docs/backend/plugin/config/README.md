# Config Plugin

The `config/` plugin provides dynamic configuration management.

---

## Directory Structure

```
config/
├── plugin.toml              # Plugin metadata
├── api/                     # REST endpoints
├── schema/                  # Config schemas
├── service/                 # Config service
├── crud/                    # Config CRUD
└── model/                   # Config model
```

---

## Features

- **Runtime Configuration**: Change settings without restart
- **Database Storage**: Persist configuration in database
- **Cache Integration**: Redis caching for performance
- **Type Validation**: Validate config values

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sys/configs` | GET | List configurations |
| `/api/v1/sys/configs/{pk}` | GET | Get config by ID |
| `/api/v1/sys/configs` | POST | Create config |
| `/api/v1/sys/configs/{pk}` | PUT | Update config |
| `/api/v1/sys/configs/{pk}` | DELETE | Delete config |
| `/api/v1/sys/configs/key/{key}` | GET | Get config by key |

---

## Data Model

```python
class Config(Base):
    """System configuration"""
    __tablename__ = "sys_config"
    
    id: Mapped[id_key]
    name: Mapped[str]      # Config name
    key: Mapped[str]       # Config key (unique)
    value: Mapped[str]     # Config value
    type: Mapped[str]      # Value type (string/int/bool/json)
    remark: Mapped[str]    # Description
```

---

## Usage

```python
from backend.plugin.config.service import config_service

# Get config value
value = await config_service.get_value("site.name")

# Update config
await config_service.update_by_key("site.name", "New Site Name")
```

---

*Last Updated: December 2024*
