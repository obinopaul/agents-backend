<div align="center">

<img alt="FBA Agents Backend Logo" width="320" src="https://wu-clan.github.io/picx-images-hosting/logo/fba.png">

# Agents Backend - Production Ready

**Enterprise-Grade AI Agent & Backend Platform**

[![GitHub License](https://img.shields.io/github/license/obinopaul/agents-backend)](https://github.com/obinopaul/agents-backend/blob/master/LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0%2B-%23336791)](https://www.postgresql.org)
[![SQLAlchemy v2](https://img.shields.io/badge/SQLAlchemy-2.0-%23778877)](https://www.sqlalchemy.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-%232496ED?logo=docker&logoColor=white)](https://www.docker.com)

[English] | [[简体中文](README.zh-CN.md)]

</div>

## 🚀 Overview

The **Agents Backend** is a unified, production-ready platform that combines a high-performance FastAPI backend with advanced **Agentic AI** capabilities. It is designed to be the foundational "One Platform" for deploying complex AI workflows, from streaming chat agents to autonomous code execution sandboxes.

Unlike traditional lightweight templates, this project implements a **robust enterprise architecture** featuring:
- **Unified Lifecycle**: Agents, Sandboxes, and Background Tasks start and scale together.
- **Embedded Sandbox**: Secure, E2B-powered Python environment integrated directly into the core service.
- **Production DevOps**: Auto-migrations, Docker-native workflow, and strict configuration management.

---

## ✨ Key Features

### 🤖 Advanced Agentic System
Powered by **LangChain** and **LangGraph**, the agent system provides:
- **Streaming Multi-Agent Chat**: Real-time reasoning and response streaming.
- **Tool Integration**: Built-in support for Web Search (Tavily), Text-to-Speech (TTS), and RAG.
- **Autonomous Sandbox**: The agents can write and execute Python code securely to solve complex math or data tasks.
- **Content Generation**: Specialized workflows for generating podcasts, presentations, and long-form prose.

### 🛡️ Production-Grade Backend (FBA Core)
Built on the **FastAPI Best Architecture** (FBA) foundation:
- **High Performance**: Fully AsyncIO stack with Uvicorn and Starlette.
- **Robust Database**: Async SQLAlchemy 2.0 with Alembic for automated migrations.
- **Security**: RBAC (Role-Based Access Control) via Casbin and JWT authentication.
- **Scalability**: Redis-based caching and limiting; RabbitMQ + Celery for background processing.

### 📦 Embedded Sandbox Server
A fully integrated execution environment for AI Agents:
- **Zero-Setup**: No separate microservice required. The sandbox logic is embedded in the main server.
- **Secure**: Uses E2B isolation for running untrusted AI-generated code.
- **Persistent**: Stateless or stateful sessions depending on agent needs.

---

## 🏗️ Architecture

This project adopts a **Modular Domain-Driven Design**. Instead of a simplistic MVC structure, we organize code by functional domains (`common`, `core`, `agent`, `admin`) to ensure scalability and maintainability.

| Layer | Component | Description |
|-------|-----------|-------------|
| **Interface** | `api/v1` | RESTful endpoints (FastAPI routers) |
| **Logic** | `service` | Business logic and transaction management |
| **Data** | `crud` | Type-safe database operations |
| **Model** | `model` | SQLAlchemy ORM definitions |
| **Schema** | `schema` | Pydantic data validation and serialization |
| **Agents** | `backend/src` | Independent Agentic modules (LangGraph) |

---

## ⚡ Quick Start

The entire system is containerized. You can start the Database, Redis, Worker, and API Server with **one command**.

### Prerequisites
- Docker & Docker Compose
- API Keys (OpenAI, E2B, Tavily) set in `.env` (or `deploy/backend/docker-compose/.env.server`)

### One-Command Deployment

```bash
# 1. Start everything (builds images and runs migrations automatically)
docker-compose up -d --build
```

**What happens next?**
1. **Postgres & Redis** start up.
2. **Backend Server** boots and waits for the DB.
3. **Auto-Migration**: `pre_start.sh` automatically applies `alembic upgrade head`.
4. **Initialization**: The `SandboxService` initializes, ready for traffic.
5. **Access**:
    - **Swagger UI**: [http://localhost:8001/docs](http://localhost:8001/docs)
    - **Agent API**: [http://localhost:8001/docs#/Agent](http://localhost:8001/docs#/Agent)

---

## 🛠️ Development

For local development without Docker:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start dependencies (DB/Redis) via Docker if needed
docker-compose up -d fba_postgres fba_redis

# 3. Run Migrations
cd backend
alembic upgrade head

# 4. Start Server
python main.py
```

---

## 📚 Documentation

- [Agent System Documentation](docs/agent-system.md) - Detailed guide on the agent architectures.
- [FastAPI Best Architecture Docs](https://fastapi-practices.github.io/fastapi_best_architecture_docs/) - Core backend documentation.

---

## 🤝 Contributors

<a href="https://github.com/obinopaul/agents-backend/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=obinopaul/agents-backend" alt="Contributors"/>
</a>

## 💖 Sponsor

If this project helps you, consider buying us a coffee!

[:coffee: Sponsor on BuyMeACoffee](https://buymeacoffee.com/acobapaulf)

## 📄 License

This project is licensed under the [MIT License](https://github.com/obinopaul/agents-backend/blob/master/LICENSE).

[![Stargazers over time](https://starchart.cc/obinopaul/agents-backend.svg?variant=adaptive)](https://starchart.cc/obinopaul/agents-backend)
