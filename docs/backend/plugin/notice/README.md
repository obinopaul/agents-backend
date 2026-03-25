# Notice Plugin

The `notice/` plugin provides user notification functionality.

---

## Directory Structure

```
notice/
├── plugin.toml              # Plugin metadata
├── api/                     # REST endpoints
├── schema/                  # Notice schemas
├── service/                 # Notice service
├── crud/                    # Notice CRUD
└── model/                   # Notice model
```

---

## Features

- **Create Notifications**: System and user notifications
- **Read Status**: Track read/unread status
- **WebSocket Push**: Real-time notifications via Socket.IO
- **User Targeting**: Send to specific users or all

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/notices` | GET | List notifications |
| `/api/v1/notices/{pk}` | GET | Get notice by ID |
| `/api/v1/notices` | POST | Create notice |
| `/api/v1/notices/{pk}/read` | PUT | Mark as read |
| `/api/v1/notices/read-all` | PUT | Mark all as read |
| `/api/v1/notices/{pk}` | DELETE | Delete notice |

---

## Data Model

```python
class Notice(Base):
    """User notification"""
    __tablename__ = "sys_notice"
    
    id: Mapped[id_key]
    title: Mapped[str]      # Notice title
    content: Mapped[str]    # Notice content
    type: Mapped[int]       # Notice type
    user_id: Mapped[int]    # Target user (null = all)
    read: Mapped[bool]      # Read status
```

---

## WebSocket Integration

Notifications can be pushed in real-time via Socket.IO:

```python
from backend.common.socketio.server import sio

# Push notification to user
await sio.emit(
    "notification",
    {"id": notice.id, "title": notice.title},
    room=f"user_{user_id}"
)
```

---

*Last Updated: December 2024*
