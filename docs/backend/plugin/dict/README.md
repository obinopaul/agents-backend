# Dictionary Plugin

The `dict/` plugin provides system dictionary management for key-value data storage.

---

## Directory Structure

```
dict/
├── plugin.toml              # Plugin metadata
├── api/                     # REST endpoints
├── schema/                  # Dict schemas
├── service/                 # Dict service
├── crud/                    # Dict CRUD
└── model/                   # Dict model
```

---

## Features

- **Key-Value Storage**: Store configuration as dictionaries
- **Categorized Dicts**: Group dictionaries by type
- **Caching**: Redis caching for fast lookup
- **Admin Management**: CRUD for dict entries

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sys/dicts` | GET | List dictionaries |
| `/api/v1/sys/dicts/{pk}` | GET | Get dict by ID |
| `/api/v1/sys/dicts` | POST | Create dictionary |
| `/api/v1/sys/dicts/{pk}` | PUT | Update dictionary |
| `/api/v1/sys/dicts/{pk}` | DELETE | Delete dictionary |
| `/api/v1/sys/dicts/type/{type}` | GET | Get dicts by type |

---

## Data Model

```python
class Dict(Base):
    """System dictionary"""
    __tablename__ = "sys_dict"
    
    id: Mapped[id_key]
    type: Mapped[str]      # Dictionary category
    key: Mapped[str]       # Dictionary key
    value: Mapped[str]     # Dictionary value
    label: Mapped[str]     # Display label
    sort: Mapped[int]      # Sort order
    status: Mapped[int]    # Enable/disable
```

---

## Use Cases

- System status codes
- Dropdown options
- Feature flags
- Localized labels

---

*Last Updated: December 2024*
