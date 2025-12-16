# Agent System Production Deployment Guide

This document outlines best practices for deploying the synchronized AI Agent System to production, ensuring scalability, security, and robustness.

## 1. Database & Migrations

### Migration Strategy
The agent system now uses **Alembic** for all database schema changes. The "lazy initialization" (creating tables at runtime) has been replaced with a formal migration process.

**Steps:**
1.  **Run Migrations**: Before starting the application containers, run the migration upgrades.
    ```bash
    alembic upgrade head
    ```
2.  **Configuration**: Ensure `AGENT_SKIP_DB_SETUP=true` is set in your production environment variables. This prevents the application from attempting to create tables on startup, avoiding race conditions in multi-replica deployments.

### Connection Pooling
The agent checkpointer (`AsyncPostgresSaver`) and the main application (`FastAPI`) share the same PostgreSQL database. Utilize a connection pooler like **PgBouncer** in front of your database for high-scale deployments (millions of users) to manage connection limits efficiently.

## 2. Hybrid Architecture (IO vs. CPU)

To scale effectively, separate interactive workloads from background processing.

### Interactive Layer (AsyncIO / FastAPI)
*   **Role**: Handles real-time Chat Streaming (SSE), WebSocket connections, and quick API responses.
*   **Scaling**: Scale this layer horizontally based on **concurrent connections** and **memory usage**.
*   **Constraint**: Do NOT run heavy blocking CPU tasks here (e.g., local embedding generation, heavy data processing) as it will block the event loop and kill real-time performance.

### Background Worker Layer (Celery)
*   **Role**: Handles heavy lifting, including:
    *   Report generation
    *   Periodic RAG knowledge base indexing
    *   long-running research tasks (if not streaming)
*   **Scaling**: Scale this layer based on **queue depth** (RabbitMQ/Redis) and **CPU utilization**.

## 3. Configuration Management

All configuration is now centralized in `backend/core/conf.py` and loaded from environment variables.

**Critical Production Variables:**
*   `AGENT_SKIP_DB_SETUP=true`: **REQUIRED** for production.
*   `LANGGRAPH_CHECKPOINT_ENABLED=true`: Enable persistence.
*   `LANGGRAPH_CHECKPOINT_DB_URL`: Postgres connection string (e.g., `postgresql://user:pass@host:5432/db`).
    *   **Tip**: Use the internal Docker network DNS if deploying via Docker Compose / K8s.
*   `AGENT_RECURSION_LIMIT`: Set reasonable limits (e.g., 50-100) to prevent infinite loops in agent graphs.

## 4. Security

*   **JWT Authentication**: The agent API (`/api/v1/agent/*`) is now protected by the same JWT middleware as the main app. Ensure your frontend handles token refresh flows correctly.
*   **CORS**: Configure `ALLOWED_ORIGINS` strictly. Do not use `*` in production.
*   **MCP Security**: If using Model Context Protocol (MCP), ensure `mcp_settings` are validated and only trusted tools are enabled.

## 5. Monitoring & Logging

*   **LangSmith**: For debugging agent logic in production, enable LangSmith tracing via environment variables (`LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY=...`).
*   **Application Logs**: The application uses structured logging. Ensure logs are shipped to a centralized system (ELK, Datadog, CloudWatch).
*   **Health Checks**: Monitor the `/docs` or a dedicated health endpoint to ensure the agent router is loaded and database connections are active.

## 6. Deprecation Notice

The following entry points are **DEPRECATED** and removed:
*   `backend/server.py`
*   `backend/main_2.py`

**New Entry Points:**
*   **Web Server**: `uvicorn backend.main:app`
*   **CLI / Interactive**: `python backend/cli.py agent-chat`
