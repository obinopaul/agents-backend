# Deployment & Setup Guide

> Enterprise-grade deployment guide for the Agents Backend.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Local Development](#3-local-development)
4. [Production Deployment](#4-production-deployment)
5. [Environment Configuration](#5-environment-configuration)
6. [Health Checks & Monitoring](#6-health-checks--monitoring)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Load Balancer / CDN                         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          ┌─────────────────┐           ┌─────────────────┐
          │  FastAPI App    │           │  FastAPI App    │
          │  (Instance 1)   │           │  (Instance N)   │
          │  Port 8000      │           │  Port 8000      │
          └────────┬────────┘           └────────┬────────┘
                   │                             │
     ┌─────────────┴─────────────────────────────┴─────────────┐
     │                    Shared Services                       │
     ├──────────────────────────────────────────────────────────┤
     │  PostgreSQL    │  Redis        │  Vector DB    │ Sandbox │
     │  (Primary)     │  (Cluster)    │  (Milvus/     │ Provider│
     │                │               │   Qdrant)     │ (E2B)   │
     └──────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

### Required Services

| Service | Purpose | Min Version |
|---------|---------|-------------|
| **Python** | Runtime | 3.11+ |
| **PostgreSQL** | Primary database | 14+ |
| **Redis** | Caching, sessions, rate limiting | 6+ |

### Optional Services

| Service | Purpose | When Needed |
|---------|---------|-------------|
| **Milvus/Qdrant** | Vector DB for RAG | If using knowledge base |
| **E2B/Daytona** | Sandbox environments | If using code execution |
| **SMTP Server** | Email notifications | If using email features |

---

## 3. Local Development

### Option A: Docker Compose (Recommended)

```bash
# Clone and start all services
git clone <repo-url>
cd agents-backend

# Start PostgreSQL, Redis, and the app
docker-compose up -d

# View logs
docker-compose logs -f app
```

### Option B: Manual Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# 4. Start PostgreSQL & Redis (if not using Docker)
# PostgreSQL: localhost:5432
# Redis: localhost:6379

# 5. Run database migrations
cd backend
alembic upgrade head

# 6. Start the development server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Verify Installation

```bash
# Health check
curl http://localhost:8000/api/v1/monitors/server

# Login test
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

---

## 4. Production Deployment

### Docker Production Build

```dockerfile
# Dockerfile (production)
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
ENV PYTHONPATH=/app

CMD ["gunicorn", "backend.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agents-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agents-backend
  template:
    spec:
      containers:
      - name: app
        image: agents-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_HOST
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: host
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/v1/monitors/server
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/monitors/server
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Cloud Database Options

| Provider | Service | Notes |
|----------|---------|-------|
| **Supabase** | PostgreSQL | Free tier available, use `postgres` as schema |
| **AWS RDS** | PostgreSQL | Production-grade, auto-scaling |
| **Redis Cloud** | Redis | Managed Redis clusters |
| **Upstash** | Redis | Serverless, pay-per-request |

---

## 5. Environment Configuration

### Core Settings (Required)

```env
# Environment
ENVIRONMENT=prod  # dev, prod

# Database (PostgreSQL)
DATABASE_TYPE=postgresql
DATABASE_HOST=your-db-host.com
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=strong-password-here
DATABASE_SCHEMA=fba  # Use 'postgres' for Supabase

# Redis
REDIS_HOST=your-redis-host.com
REDIS_PORT=6379
REDIS_PASSWORD=redis-password
REDIS_DATABASE=0

# Security
TOKEN_SECRET_KEY=generate-with-secrets.token_urlsafe(32)
```

### LLM Providers (At least one required for agents)

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google
GOOGLE_API_KEY=...

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Agent Features

```env
# Agent Behavior
AGENT_RECURSION_LIMIT=100
AGENT_DEFAULT_REPORT_STYLE=ACADEMIC
AGENT_ENABLE_DEEP_THINKING=true
AGENT_ENABLE_CLARIFICATION=true

# MCP (Model Context Protocol)
AGENT_MCP_ENABLED=true
AGENT_MCP_TIMEOUT_SECONDS=300

# Web Search
TAVILY_API_KEY=tvly-...

# RAG (Vector Database)
AGENT_RAG_PROVIDER=milvus  # or 'qdrant', or empty to disable
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### Sandbox Configuration

```env
# E2B Sandbox Provider
SANDBOX_PROVIDER=e2b
E2B_API_KEY=your-e2b-api-key

# Sandbox Ports
SANDBOX_MCP_SERVER_PORT=6060
SANDBOX_CODE_SERVER_PORT=9000
```

### OAuth2 (Optional)

```env
# GitHub OAuth
OAUTH2_GITHUB_CLIENT_ID=...
OAUTH2_GITHUB_CLIENT_SECRET=...
OAUTH2_GITHUB_REDIRECT_URI=https://yourapp.com/api/v1/oauth2/github/callback

# Google OAuth
OAUTH2_GOOGLE_CLIENT_ID=...
OAUTH2_GOOGLE_CLIENT_SECRET=...
```

---

## 6. Health Checks & Monitoring

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/monitors/server` | Server health (CPU, memory, disk) |
| `GET /api/v1/monitors/redis` | Redis connection status |

### Recommended Monitoring Stack

```
Prometheus → Grafana (metrics)
Sentry (error tracking)
Loki (log aggregation)
```

### Logging Configuration

```env
# Log Level
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Log Format
LOG_FORMAT=json  # For production log aggregation
```

---

## Quick Reference

### Start Commands

| Environment | Command |
|-------------|---------|
| Development | `uvicorn backend.main:app --reload` |
| Production | `gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker` |
| Docker | `docker-compose up -d` |

### Default Ports

| Service | Port |
|---------|------|
| FastAPI App | 8000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Tool Server (MCP) | 6060 |
| VS Code Server | 9000 |
| Milvus | 19530 |

### Default Credentials (Development Only!)

```
Username: admin
Password: admin123
```

> ⚠️ **Change these immediately in production!**
