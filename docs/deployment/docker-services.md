# Docker Services Architecture

> Complete guide to the 8 Docker containers that make up the Agents Backend.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Network: fba_network                        │
│                              Subnet: 172.10.10.0/24                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐                                                            │
│   │   NGINX     │ :8000 ──────────── Reverse Proxy                          │
│   │  fba_nginx  │                                                            │
│   └──────┬──────┘                                                            │
│          │                                                                   │
│          ▼                                                                   │
│   ┌─────────────┐                                                            │
│   │   FastAPI   │ :8001 ──────────── Main Application                       │
│   │  fba_server │                                                            │
│   └──────┬──────┘                                                            │
│          │                                                                   │
│    ┌─────┴─────┬─────────────┬─────────────┐                                │
│    ▼           ▼             ▼             ▼                                │
│ ┌───────┐  ┌───────┐   ┌──────────┐  ┌───────────┐                          │
│ │Postgres│  │ Redis │   │ RabbitMQ │  │  Celery   │                          │
│ │  :5432 │  │ :6379 │   │   :5672  │  │  Workers  │                          │
│ └───────┘  └───────┘   └─────┬────┘  └───────────┘                          │
│                              │                                               │
│                    ┌─────────┴─────────┐                                    │
│                    ▼                   ▼                                    │
│              ┌──────────┐       ┌──────────┐                                │
│              │  Worker  │       │   Beat   │                                │
│              │ (Tasks)  │       │ (Sched)  │                                │
│              └──────────┘       └──────────┘                                │
│                    │                                                         │
│                    ▼                                                         │
│              ┌──────────┐                                                   │
│              │  Flower  │ :8555 ─── Monitoring                              │
│              └──────────┘                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Container Details

### 1. fba_server (FastAPI Application)

**Purpose:** The main FastAPI backend application.

| Property | Value |
|----------|-------|
| Image | `fba_server:latest` |
| Internal Port | 8001 |
| Depends On | fba_postgres, fba_redis |
| Supervisor Config | `fba_server.conf` |

**Startup Command:**
```bash
wait-for-it -s fba_postgres:5432 -s fba_redis:6379 -t 300
bash /fba/backend/pre_start.sh
supervisord -c /etc/supervisor/supervisord.conf
```

**Environment:**
```yaml
volumes:
  - ./deploy/backend/docker-compose/.env.server:/fba/backend/.env
  - fba_static:/fba/backend/app/static
  - fba_static_upload:/fba/backend/static/upload
```

---

### 2. fba_nginx (Reverse Proxy)

**Purpose:** NGINX reverse proxy that routes requests to the FastAPI server.

| Property | Value |
|----------|-------|
| Image | `nginx:latest` |
| External Port | 8000 |
| Internal Port | 80 |
| Depends On | fba_server |

**Configuration:**
```nginx
# deploy/backend/nginx.conf
upstream backend {
    server fba_server:8001;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static {
        alias /www/fba_server/backend/static;
    }
}
```

---

### 3. fba_postgres (PostgreSQL Database)

**Purpose:** Primary database for all application data.

| Property | Value |
|----------|-------|
| Image | `postgres:16` |
| Port | 5432 |
| Database | `fba` |
| Password | `123456` (change in production!) |

**Volume:** `fba_postgres:/var/lib/postgresql/data`

**Tables Stored:**
- `sys_user` - User accounts
- `sys_role` - Roles
- `sys_menu` - Navigation menus
- `sandboxes` - Sandbox sessions
- `agent_mcp_settings` - MCP configurations
- ... and 20+ more tables

---

### 4. fba_redis (Cache & Sessions)

**Purpose:** Session storage, caching, rate limiting, and Celery broker (optional).

| Property | Value |
|----------|-------|
| Image | `redis:latest` |
| Port | 6379 |

**Used For:**
- JWT session storage
- Rate limiting (`FastAPILimiter`)
- Login captcha cache
- OAuth2 state storage
- Optional Celery broker (instead of RabbitMQ)

---

### 5. fba_rabbitmq (Message Broker)

**Purpose:** Message broker for Celery background tasks.

| Property | Value |
|----------|-------|
| Image | `rabbitmq:3.13.7` |
| AMQP Port | 5672 |
| Management UI | 15672 |
| Username | `guest` |
| Password | `guest` |

**Management UI:** http://localhost:15672

---

### 6. fba_celery_worker (Task Executor)

**Purpose:** Executes background tasks (emails, async jobs, etc.).

| Property | Value |
|----------|-------|
| Image | `fba_celery_worker:latest` |
| Depends On | fba_rabbitmq |
| Supervisor Config | `fba_celery_worker.conf` |

**Startup:**
```bash
wait-for-it -s fba_rabbitmq:5672 -t 300
supervisord -c /etc/supervisor/supervisord.conf
```

**Tasks Execute:**
- Email sending
- Async database operations
- Log aggregation
- Custom background tasks

---

### 7. fba_celery_beat (Task Scheduler)

**Purpose:** Schedules periodic/cron tasks.

| Property | Value |
|----------|-------|
| Image | `fba_celery_beat:latest` |
| Depends On | fba_rabbitmq, fba_celery_worker |
| Supervisor Config | `fba_celery_beat.conf` |

**Scheduled Tasks:**
```python
# backend/app/task/tasks/beat.py
LOCAL_BEAT_SCHEDULE = {
    'cleanup-expired-sessions': {
        'task': 'backend.app.task.tasks.tasks.cleanup_sessions',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
```

---

### 8. fba_celery_flower (Monitoring)

**Purpose:** Web UI for monitoring Celery tasks.

| Property | Value |
|----------|-------|
| Image | `fba_celery_flower:latest` |
| Port | 8555 |
| Depends On | fba_rabbitmq, fba_celery_worker |

**Access:** http://localhost:8555

**Features:**
- Real-time task monitoring
- Worker status
- Task history
- Rate limiting stats

---

## Volumes

```yaml
volumes:
  fba_postgres:    # Database data
  fba_redis:       # Cache data
  fba_static:      # Static files
  fba_static_upload: # User uploads
  fba_rabbitmq:    # Message queue data
```

---

## Network

All containers communicate on a private bridge network:

```yaml
networks:
  fba_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.10.10.0/24
```

---

## Starting Individual Services

```bash
# Database only
docker-compose up -d fba_postgres fba_redis

# Full stack without Celery
docker-compose up -d fba_postgres fba_redis fba_server fba_nginx

# Celery workers only
docker-compose up -d fba_rabbitmq fba_celery_worker fba_celery_beat

# Everything
docker-compose up -d
```

---

## Logs

```bash
# View all logs
docker-compose logs -f

# Specific service
docker-compose logs -f fba_server
docker-compose logs -f fba_celery_worker
```

---

## Health Checks

```bash
# Check all containers
docker-compose ps

# Check FastAPI health
curl http://localhost:8000/api/v1/health

# Check RabbitMQ
curl http://localhost:15672/api/overview
```
