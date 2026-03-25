# Deployment Guide

> How to run the Agents Backend locally and in production.

---

## Quick Start Options

| Method | Best For | Time |
|--------|----------|------|
| [Docker Compose](#docker-compose-recommended) | Production, full stack | 5 min |
| [Local Development](#local-development) | Development, debugging | 3 min |
| [Celery Workers](#celery-workers) | Background tasks | 2 min |

---

## Docker Compose (Recommended)

The easiest way to run the complete stack.

### Start All Services

```bash
# Clone and configure
git clone https://github.com/obinopaul/agents-backend.git
cd agents-backend
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# Start everything
docker-compose up -d
```

### What Gets Started

| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5432 | - |
| Redis | 6379 | - |
| RabbitMQ | 15672 | http://localhost:15672 |
| Celery Flower | 8555 | http://localhost:8555 |

### Stop All Services

```bash
docker-compose down
```

---

## Local Development

Run the FastAPI server directly without Docker.

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (still need these)
docker-compose up -d fba_postgres fba_redis
```

### Run the Server

```bash
cd backend

# Option 1: Using uvicorn directly
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Using the FBA CLI
fba run --host 0.0.0.0 --port 8000

# Option 3: Running specific module
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Access Points

| Service | URL |
|---------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| API Base | http://localhost:8000/api/v1 |

---

## Celery Workers

For background tasks (email, scheduled jobs, etc.).

### Start Workers

```bash
# Terminal 1: Celery Worker (task execution)
celery -A backend.app.task.celery:celery_app worker --loglevel=INFO

# Terminal 2: Celery Beat (scheduled tasks)
celery -A backend.app.task.celery:celery_app beat --loglevel=INFO

# Terminal 3: Celery Flower (monitoring UI)
celery -A backend.app.task.celery:celery_app flower --port=8555
```

### RabbitMQ Requirement

Celery requires RabbitMQ (or Redis) as a message broker:

```bash
docker-compose up -d fba_rabbitmq
```

---

## Database Migrations

```bash
cd backend

# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

---

## Detailed Documentation

| Document | Description |
|----------|-------------|
| [Docker Services](./docker-services.md) | All 8 containers explained |
| [Local Development](./local-development.md) | Development setup |
| [Celery Workers](./celery-workers.md) | Background task system |
