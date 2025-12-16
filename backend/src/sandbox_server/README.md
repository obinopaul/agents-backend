# Sandbox Server (Embedded Library)

**NOTE:** This module has been integrated into the main Agent Backend (`fba_server`) as an embedded service.

## 🏗️ Architecture

The Sandbox Server logic (`SandboxController`, `E2BProvider`, etc.) is now consumed directly by the main application via `SandboxService`.

- **API Endpoints**: Exposed at `/api/v1/agent/sandboxes` (see [Main API Docs](/docs#/Agent%20Sandbox)).
- **Service Layer**: `backend/src/services/sandbox_service.py`
- **Configuration**: Managed via `backend/core/conf.py` (settings).

## 🧩 Components

This directory contains the core logic for the sandbox capabilities:

- **Lifecycle**: `lifecycle/sandbox_controller.py` - Manages creation, timeouts, and state.
- **Providers**: `sandboxes/` - E2B provider implementation.
- **Queue**: `lifecycle/queue.py` - Redis-based timeout scheduling.
- **Database**: `db/` - Sandbox persistence models (Postgres).

## 🛠️ Usage

To use the sandbox in the main application:

```python
from backend.src.services.sandbox_service import sandbox_service

# Get or create
sandbox = await sandbox_service.get_or_create_sandbox(user_id="user_123")

# Run Command
output = await sandbox_controller.run_cmd(sandbox.id, "python script.py")
```

## ⚠️ Legacy Note

The `main.py` in this directory is a legacy standalone entry point. Do not use it for production. Use the main `fba_server` instead.