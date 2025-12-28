# Local Development Guide

> Running the Agents Backend without Docker for faster development.

---

## Prerequisites

### 1. Python 3.10+

```bash
python --version  # Should be 3.10 or higher
```

### 2. PostgreSQL & Redis (via Docker)

You still need the databases running:

```bash
# Start only the databases
cd agents-backend
docker-compose up -d fba_postgres fba_redis
```

Verify they're running:
```bash
docker-compose ps
# Should show fba_postgres and fba_redis as "Up"
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Application

### Option 1: Direct uvicorn (Recommended for Development)

```bash
cd backend

# With hot reload (watches for file changes)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345]
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
✓ 插件准备就绪
✓ Database tables created
✓ Redis connection established
INFO:     Application startup complete.
```

### Option 2: FBA CLI

```bash
cd backend
fba run --host 0.0.0.0 --port 8000
```

### Option 3: Python Module

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Environment Configuration

### Copy Example Environment

```bash
cp backend/.env.example backend/.env
```

### Minimum Required Settings

```bash
# Database (matches docker-compose defaults)
DATABASE_TYPE='postgresql'
DATABASE_HOST='127.0.0.1'
DATABASE_PORT=5432
DATABASE_USER='postgres'
DATABASE_PASSWORD='123456'
DATABASE_SCHEMA='postgres'

# Redis
REDIS_HOST='127.0.0.1'
REDIS_PORT=6379
REDIS_PASSWORD=''

# Security
TOKEN_SECRET_KEY='your-secret-key-here'
```

### LLM Provider (Choose One)

```bash
# OpenAI
LLM_PROVIDER="openai"
OPENAI_API_KEY="sk-..."

# Or Anthropic
LLM_PROVIDER="anthropic"
ANTHROPIC_API_KEY="sk-ant-..."

# Or Google Gemini
LLM_PROVIDER="gemini"
GOOGLE_API_KEY="..."
```

---

## Database Migrations

### Apply Existing Migrations

```bash
cd backend
alembic upgrade head
```

### Create New Migration

```bash
alembic revision --autogenerate -m "Add new table"
```

### View Migration History

```bash
alembic history
```

---

## Running Celery Workers (Optional)

For background tasks, you need RabbitMQ:

```bash
# Start RabbitMQ
docker-compose up -d fba_rabbitmq

# Terminal 1: Celery Worker
cd backend
celery -A backend.app.task.celery:celery_app worker --loglevel=INFO

# Terminal 2: Celery Beat (scheduled tasks)
celery -A backend.app.task.celery:celery_app beat --loglevel=INFO
```

---

## Accessing the Application

| Service | URL |
|---------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |
| Admin API | http://localhost:8000/api/v1/admin |
| Agent API | http://localhost:8000/api/v1/agent |

---

## What Happens at Startup

The application startup sequence:

```
1. Plugin Discovery
   └─ Finds oauth2, email, config plugins
   
2. Install Plugin Dependencies
   └─ pip install -r plugin/*/requirements.txt
   
3. FastAPI App Creation
   └─ register_app() in core/registrar.py

4. Lifespan: Startup
   ├─ Create database tables
   ├─ Open Redis connection
   ├─ Initialize rate limiter
   ├─ Initialize Snowflake ID generator
   ├─ Start opera log consumer task
   └─ Initialize Sandbox Service

5. Middleware Registration (bottom to top)
   ├─ ContextMiddleware (request ID)
   ├─ AccessMiddleware (logging)
   ├─ I18nMiddleware (localization)
   ├─ JwtAuthMiddleware (authentication)
   ├─ StateMiddleware (request state)
   └─ OperaLogMiddleware (audit logs)

6. Router Registration
   └─ All API routes mounted

7. Server Ready
   └─ Listening on http://0.0.0.0:8000
```

---

## Debugging Tips

### Enable Debug Mode

```bash
# In .env
ENVIRONMENT='dev'
DEBUG=True
```

### View SQL Queries

```bash
# In .env
DATABASE_ECHO=True
```

### View All Routes

```bash
# After server starts
curl http://localhost:8000/openapi.json | jq '.paths | keys'
```

---

## Common Issues

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Use different port
uvicorn backend.main:app --port 8001
```

### Database Connection Error

```bash
# Check if PostgreSQL is running
docker-compose ps fba_postgres

# Check connection
psql -h 127.0.0.1 -U postgres -d postgres
```

### Redis Connection Error

```bash
# Check if Redis is running
docker-compose ps fba_redis

# Test connection
redis-cli ping  # Should return "PONG"
```

---

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- Python Test Explorer

**`.vscode/settings.json`:**
```json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.analysis.extraPaths": ["backend"],
    "python.testing.pytestEnabled": true
}
```

### PyCharm

1. Mark `backend` as Sources Root
2. Set Python interpreter to virtual environment
3. Configure Run Configuration:
   - Script: `uvicorn`
   - Parameters: `backend.main:app --reload`
   - Working directory: `agents-backend`
