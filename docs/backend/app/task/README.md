# Task Module (Celery)

The `app/task/` module implements background task processing using Celery.

---

## Directory Structure

```
task/
├── __init__.py              # Package initialization
├── celery.py                # Celery app configuration
├── database.py              # Task result database
│
├── api/                     # Task API endpoints
│   └── v1/
│       └── task.py          # Task management endpoints
│
├── schema/                  # Task schemas
│   └── task.py              # Task DTOs
│
├── service/                 # Task services
│   └── task.py              # Task service layer
│
├── crud/                    # Task CRUD
│   └── task.py              # Task database operations
│
├── model/                   # Task models
│   └── task.py              # Task SQLAlchemy model
│
├── tasks/                   # Task definitions
│   ├── __init__.py
│   ├── email.py             # Email tasks
│   └── example.py           # Example tasks
│
└── utils/                   # Task utilities
    └── ...
```

---

## Celery Configuration

```python
# task/celery.py
from celery import Celery
from backend.core.conf import settings

# Broker selection based on environment
if settings.CELERY_BROKER == "rabbitmq":
    broker_url = f"amqp://{settings.CELERY_RABBITMQ_USERNAME}:{settings.CELERY_RABBITMQ_PASSWORD}@{settings.CELERY_RABBITMQ_HOST}:{settings.CELERY_RABBITMQ_PORT}/{settings.CELERY_RABBITMQ_VHOST}"
else:
    broker_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.CELERY_BROKER_REDIS_DATABASE}"

celery_app = Celery(
    "fba_tasks",
    broker=broker_url,
    backend=f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.CELERY_BROKER_REDIS_DATABASE}",
    include=["backend.app.task.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.DATETIME_TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TASK FLOW                                         │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐       ┌───────────────────────┐
│   API Request         │       │   Scheduled Task      │
│   POST /tasks         │       │   (Celery Beat)       │
└───────────┬───────────┘       └───────────┬───────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   Message Broker      │
                │   ─────────────────   │
                │   Redis (dev)         │
                │   RabbitMQ (prod)     │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   Celery Worker       │
                │   ─────────────────   │
                │   • Pick up task      │
                │   • Execute           │
                │   • Store result      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   Result Backend      │
                │   ─────────────────   │
                │   Redis               │
                └───────────────────────┘
```

---

## Creating Tasks

### Simple Task

```python
# tasks/example.py
from backend.app.task.celery import celery_app

@celery_app.task(name="example.add")
def add(x: int, y: int) -> int:
    """Simple addition task"""
    return x + y
```

### Async Task

```python
# tasks/email.py
from backend.app.task.celery import celery_app
from backend.plugin.email.service import email_service

@celery_app.task(
    name="email.send",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_email(self, to: str, subject: str, body: str):
    """Send email with retry support"""
    try:
        email_service.send(to=to, subject=subject, body=body)
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Task with Progress

```python
@celery_app.task(bind=True, name="data.process")
def process_data(self, data: list):
    """Task with progress updates"""
    total = len(data)
    for i, item in enumerate(data):
        # Process item
        process(item)
        
        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={"current": i + 1, "total": total}
        )
    
    return {"processed": total}
```

---

## Running Celery

### Development

```bash
# Start worker
celery -A backend.app.task.celery worker --loglevel=info

# Start beat (scheduler)
celery -A backend.app.task.celery beat --loglevel=info
```

### Production

```bash
# With concurrency and prefetch
celery -A backend.app.task.celery worker \
    --loglevel=info \
    --concurrency=4 \
    --prefetch-multiplier=2
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tasks` | GET | List tasks |
| `/api/v1/tasks/{task_id}` | GET | Get task status |
| `/api/v1/tasks` | POST | Create/trigger task |
| `/api/v1/tasks/{task_id}` | DELETE | Revoke task |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CELERY_BROKER` | `redis` | Broker type (redis/rabbitmq) |
| `CELERY_BROKER_REDIS_DATABASE` | - | Redis database number |
| `CELERY_RABBITMQ_HOST` | - | RabbitMQ host |
| `CELERY_RABBITMQ_PORT` | - | RabbitMQ port |
| `CELERY_RABBITMQ_USERNAME` | - | RabbitMQ username |
| `CELERY_RABBITMQ_PASSWORD` | - | RabbitMQ password |
| `CELERY_TASK_MAX_RETRIES` | 5 | Max task retries |

---

## Related Documentation

- [Configuration](../../core/configuration.md) - Celery settings
- [Redis](../../database/redis.md) - Result backend

---

*Last Updated: December 2024*
