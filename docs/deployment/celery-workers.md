# Celery Workers Guide

> Background task processing with Celery, RabbitMQ, and Flower.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Celery Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐                                                │
│   │   FastAPI   │ ─── Enqueue Task ───┐                         │
│   │   Server    │                      │                         │
│   └─────────────┘                      ▼                         │
│                               ┌─────────────────┐                │
│   ┌─────────────┐             │    RabbitMQ     │                │
│   │Celery Beat  │ ─Schedule──►│   (Broker)      │                │
│   │ (Scheduler) │             │   :5672         │                │
│   └─────────────┘             └────────┬────────┘                │
│                                        │                         │
│                                        ▼                         │
│                            ┌────────────────────┐                │
│                            │  Celery Worker(s)  │                │
│                            │  (Task Execution)  │                │
│                            └─────────┬──────────┘                │
│                                      │                           │
│                         ┌────────────┴────────────┐              │
│                         ▼                         ▼              │
│                  ┌─────────────┐          ┌─────────────┐        │
│                  │  PostgreSQL │          │   Flower    │        │
│                  │  (Results)  │          │  (Monitor)  │        │
│                  │   :5432     │          │   :8555     │        │
│                  └─────────────┘          └─────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Using Docker Compose

```bash
# Start all Celery components
docker-compose up -d fba_rabbitmq fba_celery_worker fba_celery_beat fba_celery_flower

# View logs
docker-compose logs -f fba_celery_worker
```

### Manual Start (Development)

```bash
# Terminal 1: Start RabbitMQ
docker-compose up -d fba_rabbitmq

# Terminal 2: Celery Worker
cd backend
celery -A backend.app.task.celery:celery_app worker --loglevel=INFO

# Terminal 3: Celery Beat
celery -A backend.app.task.celery:celery_app beat --loglevel=INFO

# Terminal 4: Flower (optional)
celery -A backend.app.task.celery:celery_app flower --port=8555
```

---

## Configuration

### Environment Variables

```bash
# .env file

# Broker Selection (rabbitmq or redis)
CELERY_BROKER='rabbitmq'  # or 'redis'

# RabbitMQ Settings
CELERY_RABBITMQ_HOST='127.0.0.1'
CELERY_RABBITMQ_PORT=5672
CELERY_RABBITMQ_USERNAME='guest'
CELERY_RABBITMQ_PASSWORD='guest'
CELERY_RABBITMQ_VHOST='/'

# Redis as Broker (alternative)
CELERY_BROKER_REDIS_DATABASE=1
```

### Celery Configuration

Located in `backend/app/task/celery.py`:

```python
app = celery.Celery(
    'fba_celery',
    broker_url=broker_url,
    result_backend=result_backend,
    beat_schedule=LOCAL_BEAT_SCHEDULE,
    beat_scheduler='backend.app.task.utils.schedulers:DatabaseScheduler',
    task_cls='backend.app.task.tasks.base:TaskBase',
    task_track_started=True,
    timezone=settings.DATETIME_TIMEZONE,
)
```

---

## Task Types

### Immediate Tasks

Execute as soon as possible:

```python
# In your code
from backend.app.task.celery import celery_app

@celery_app.task
def send_email_task(to: str, subject: str, body: str):
    # Send email logic
    pass

# Call the task
send_email_task.delay("user@example.com", "Hello", "Welcome!")
```

### Scheduled Tasks (Beat)

Execute on a schedule:

```python
# backend/app/task/tasks/beat.py

from celery.schedules import crontab

LOCAL_BEAT_SCHEDULE = {
    # Run every day at midnight
    'cleanup-expired-sessions': {
        'task': 'backend.app.task.tasks.tasks.cleanup_sessions',
        'schedule': crontab(hour=0, minute=0),
    },
    
    # Run every hour
    'sync-user-stats': {
        'task': 'backend.app.task.tasks.tasks.sync_stats',
        'schedule': crontab(minute=0),
    },
    
    # Run every 5 minutes
    'health-check': {
        'task': 'backend.app.task.tasks.tasks.health_check',
        'schedule': 300.0,  # seconds
    },
}
```

---

## Creating Custom Tasks

### 1. Create Task Module

```python
# backend/app/task/tasks/notifications/tasks.py

from backend.app.task.celery import celery_app
from backend.app.task.tasks.base import TaskBase

@celery_app.task(bind=True, base=TaskBase)
async def send_notification(self, user_id: int, message: str):
    """Send notification to user."""
    try:
        # Your notification logic
        return {"status": "sent", "user_id": user_id}
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60)
```

### 2. Auto-Discovery

Tasks are automatically discovered from any `tasks.py` file in:
```
backend/app/task/tasks/*/tasks.py
```

### 3. Call from API

```python
# In your FastAPI endpoint
from backend.app.task.tasks.notifications.tasks import send_notification

@router.post("/notify")
async def notify_user(user_id: int, message: str):
    task = send_notification.delay(user_id, message)
    return {"task_id": task.id}
```

---

## Existing Tasks

### Location

```
backend/app/task/tasks/
├── __init__.py
├── base.py           # TaskBase class with error handling
├── beat.py           # Scheduled task definitions
├── tasks.py          # General tasks
└── db_log/
    └── tasks.py      # Database logging tasks
```

### Database Logging Tasks

```python
# Tasks for async logging to database
- log_operation_task()  # Log user operations
- log_login_task()      # Log login attempts
```

---

## Monitoring with Flower

Access at: http://localhost:8555

### Features

| Feature | Description |
|---------|-------------|
| Dashboard | Overview of all workers |
| Tasks | Active, completed, failed tasks |
| Workers | Worker status and statistics |
| Broker | RabbitMQ connection status |
| Monitor | Real-time task updates |

### Authentication (Optional)

```bash
celery -A backend.app.task.celery:celery_app flower \
    --port=8555 \
    --basic_auth=admin:password
```

---

## Task Results

Results are stored in PostgreSQL:

```python
# Check task result
from backend.app.task.celery import celery_app

result = celery_app.AsyncResult(task_id)
print(result.state)   # PENDING, STARTED, SUCCESS, FAILURE
print(result.result)  # Task return value
```

### Result Backends

| Backend | Configuration |
|---------|---------------|
| PostgreSQL | `db+postgresql://...` (default) |
| MySQL | `db+mysql://...` |
| Redis | `redis://...` |

---

## Error Handling

### Retry on Failure

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def reliable_task(self, data):
    try:
        # Process data
        pass
    except TemporaryError as e:
        raise self.retry(exc=e)
```

### Dead Letter Queue

Failed tasks after max retries go to a dead letter queue for manual inspection.

---

## Scaling Workers

### Multiple Workers

```bash
# Start 4 worker processes
celery -A backend.app.task.celery:celery_app worker \
    --loglevel=INFO \
    --concurrency=4
```

### Distributed Workers

In Docker Compose, remove `container_name` and scale:

```bash
docker-compose up -d --scale fba_celery_worker=3
```

---

## Common Issues

### Tasks Not Executing

1. Check RabbitMQ is running:
   ```bash
   docker-compose ps fba_rabbitmq
   ```

2. Check worker is connected:
   ```bash
   docker-compose logs fba_celery_worker | grep "Connected"
   ```

3. Check task is registered:
   ```bash
   celery -A backend.app.task.celery:celery_app inspect registered
   ```

### Beat Not Scheduling

1. Verify Beat is running:
   ```bash
   docker-compose logs fba_celery_beat
   ```

2. Check schedule:
   ```python
   from backend.app.task.tasks.beat import LOCAL_BEAT_SCHEDULE
   print(LOCAL_BEAT_SCHEDULE)
   ```

---

## Alternative: Redis as Broker

If you prefer Redis over RabbitMQ:

```bash
# .env
CELERY_BROKER='redis'
CELERY_BROKER_REDIS_DATABASE=1
```

Pros:
- Simpler setup (no RabbitMQ container)
- Already have Redis for sessions

Cons:
- Less robust message guarantees
- No management UI like RabbitMQ
