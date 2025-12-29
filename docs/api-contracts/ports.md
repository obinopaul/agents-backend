# Port Reference

This document outlines the network ports used by the Agents Backend and its infrastructure components.

## Service Ports (Exposed to Host)

These ports are exposed on `"localhost"` via `docker-compose`.

| Port | Service | Description | Access |
|------|---------|-------------|--------|
| **8000** | Nginx | Reverse Proxy / API Gateway. Main entry point for the frontend or external clients. Proxies requests to the backend. | `http://localhost:8000` |
| **8001** | Backend (Granian) | Direct access to the Application Server (FastAPI). Used for health checks (`/health`) or bypassing Nginx for debugging. | `http://localhost:8001` |
| **8555** | Flower | Celery Task Monitor. Visual dashboard for viewing asynchronous task status. | `http://localhost:8555` |
| **15672**| RabbitMQ Management | RabbitMQ Web UI. Dashboard for managing message queues. | `http://localhost:15672` |

## Infrastructure Ports (Internal/Database)

These ports are generally for database connections and are mapped to localhost for development access (e.g., using DB GUI tools).

| Port | Service | Description |
|------|---------|-------------|
| **5432** | PostgreSQL | Primary relational database. |
| **6379** | Redis | In-memory cache and message broker backing the queue. |
| **5672** | RabbitMQ | AMPQ protocol port for message queue communication. |

## Sandbox & Tool Ports (Internal/Dynamic)

These ports are used *inside* the E2B sandbox environment or are strictly internal.

| Port | Service | Description |
|------|---------|-------------|
| **6060** | MCP Tool Server | The Model Context Protocol (MCP) server running inside the sandbox. Provides tools like "Bash", "Edit File", etc. to the agent. |
| **9000** | VS Code Server | (Optional) Code-Server instance for visual file editing in the sandbox. |

> **Note on Port 6000**: Port 6000 is **not** used by this project. The MCP server exclusively uses **6060**.
