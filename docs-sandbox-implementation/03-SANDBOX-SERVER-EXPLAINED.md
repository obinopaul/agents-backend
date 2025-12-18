# Sandbox Server (ii_sandbox_server) - Deep Dive

This document explains how the sandbox server works and how to use it in your project.

---

## What is ii_sandbox_server?

It's a **FastAPI server** that acts as a management layer over E2B. Instead of your LangChain agent talking directly to E2B, it talks to this server.

```
Your Agent  →  Sandbox Server  →  E2B Cloud
                    │
                    └── Manages sessions, timeouts, credentials
```

---

## Directory Structure

```
src/ii_sandbox_server/
├── __init__.py
├── main.py              # FastAPI app with all endpoints
├── config.py            # Configuration (E2B API key, template ID)
├── logger.py            # Logging setup
├── requirements.txt     # Python dependencies
│
├── sandboxes/           # Sandbox provider implementations
│   ├── base.py          # Abstract base class
│   └── e2b.py           # E2B-specific implementation
│
├── lifecycle/           # Sandbox lifecycle management
│   ├── sandbox_controller.py   # Main controller
│   └── queue.py         # Timeout queue scheduler
│
├── models/              # Pydantic models
│   ├── __init__.py
│   ├── payload.py       # Request/Response models
│   └── exceptions.py    # Custom exceptions
│
├── db/                  # Optional database
│   ├── model.py         # SQLAlchemy models
│   └── manager.py       # Database operations
│
└── client/              # Client library to call the server
    └── client.py        # HTTP client
```

---

## Core Components Explained

### 1. main.py - The FastAPI Application

This is the entry point. All endpoints are defined here.

```python
# Simplified version of main.py

from fastapi import FastAPI, HTTPException
from ii_sandbox_server.lifecycle.sandbox_controller import SandboxController
from ii_sandbox_server.models.payload import (
    CreateSandboxRequest,
    CreateSandboxResponse,
    RunCommandRequest,
    RunCommandResponse,
    ExposePortRequest,
    ExposePortResponse,
)

app = FastAPI()
sandbox_controller = None  # Initialized on startup

@app.on_event("startup")
async def startup():
    global sandbox_controller
    config = SandboxConfig()
    sandbox_controller = SandboxController(config)

# ==================== ENDPOINTS ====================

@app.post("/sandboxes/create", response_model=CreateSandboxResponse)
async def create_sandbox(request: CreateSandboxRequest):
    """Create a new E2B sandbox."""
    sandbox_id = await sandbox_controller.create_sandbox(
        user_id=request.user_id,
        template_id=request.template_id
    )
    return CreateSandboxResponse(sandbox_id=sandbox_id)

@app.post("/sandboxes/connect")
async def connect_sandbox(request: ConnectSandboxRequest):
    """Connect to existing sandbox (resumes if paused)."""
    await sandbox_controller.connect_sandbox(request.sandbox_id)
    return {"success": True}

@app.post("/sandboxes/run-command", response_model=RunCommandResponse)
async def run_command(request: RunCommandRequest):
    """Run a shell command in the sandbox."""
    output = await sandbox_controller.run_command(
        sandbox_id=request.sandbox_id,
        command=request.command,
        background=request.background
    )
    return RunCommandResponse(output=output)

@app.post("/sandboxes/expose-port", response_model=ExposePortResponse)
async def expose_port(request: ExposePortRequest):
    """Get public URL for a port in the sandbox."""
    url = await sandbox_controller.expose_port(
        sandbox_id=request.sandbox_id,
        port=request.port
    )
    return ExposePortResponse(url=url)

@app.post("/sandboxes/write-file")
async def write_file(request: FileOperationRequest):
    """Write a file to the sandbox."""
    await sandbox_controller.write_file(
        sandbox_id=request.sandbox_id,
        path=request.path,
        content=request.content
    )
    return {"success": True}

@app.post("/sandboxes/read-file")
async def read_file(request: FileOperationRequest):
    """Read a file from the sandbox."""
    content = await sandbox_controller.read_file(
        sandbox_id=request.sandbox_id,
        path=request.path
    )
    return {"content": content}

@app.post("/sandboxes/timeout")
async def schedule_timeout(request: ScheduleTimeoutRequest):
    """Schedule sandbox for cleanup after N seconds."""
    await sandbox_controller.schedule_timeout(
        sandbox_id=request.sandbox_id,
        timeout_seconds=request.timeout
    )
    return {"success": True}

@app.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    """Immediately delete a sandbox."""
    await sandbox_controller.delete_sandbox(sandbox_id)
    return {"success": True}
```

### 2. config.py - Configuration

```python
from pydantic_settings import BaseSettings

class SandboxConfig(BaseSettings):
    """Sandbox server configuration."""
    
    # E2B credentials
    e2b_api_key: str
    e2b_template_id: str  # Your custom template ID
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    
    # Timeout settings
    default_timeout: int = 3600  # 1 hour
    max_timeout: int = 86400    # 24 hours
    
    # Database (optional)
    database_url: str = "sqlite:///./sandboxes.db"
    
    class Config:
        env_file = ".env"
```

### 3. sandbox_controller.py - The Brain

```python
from typing import Dict, Optional
from ii_sandbox_server.sandboxes.e2b import E2BSandbox
from ii_sandbox_server.lifecycle.queue import SandboxQueueScheduler

class SandboxController:
    """Manages sandbox lifecycle."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.sandboxes: Dict[str, E2BSandbox] = {}  # In-memory cache
        self.queue = SandboxQueueScheduler()  # For timeouts
    
    async def create_sandbox(
        self, 
        user_id: str,
        template_id: Optional[str] = None
    ) -> str:
        """Create a new sandbox."""
        # Generate unique ID for this sandbox
        sandbox_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        
        # Create via E2B
        sandbox = await E2BSandbox.create(
            config=self.config,
            sandbox_id=sandbox_id,
            template_id=template_id or self.config.e2b_template_id
        )
        
        # Cache it
        self.sandboxes[sandbox_id] = sandbox
        
        # Schedule default timeout
        await self.queue.schedule(sandbox_id, self.config.default_timeout)
        
        return sandbox_id
    
    async def connect_sandbox(self, sandbox_id: str):
        """Connect to existing sandbox (resumes if paused)."""
        if sandbox_id in self.sandboxes:
            sandbox = self.sandboxes[sandbox_id]
        else:
            sandbox = await E2BSandbox.connect(
                config=self.config,
                sandbox_id=sandbox_id
            )
            self.sandboxes[sandbox_id] = sandbox
        
        # Reset timeout on reconnect
        await self.queue.schedule(sandbox_id, self.config.default_timeout)
    
    async def run_command(
        self, 
        sandbox_id: str, 
        command: str,
        background: bool = False
    ) -> str:
        """Run command in sandbox."""
        sandbox = self._get_sandbox(sandbox_id)
        return await sandbox.run_command(command, background=background)
    
    async def expose_port(self, sandbox_id: str, port: int) -> str:
        """Get public URL for port."""
        sandbox = self._get_sandbox(sandbox_id)
        return await sandbox.expose_port(port)
    
    async def write_file(self, sandbox_id: str, path: str, content: str):
        """Write file to sandbox."""
        sandbox = self._get_sandbox(sandbox_id)
        await sandbox.write_file(path, content)
    
    async def read_file(self, sandbox_id: str, path: str) -> str:
        """Read file from sandbox."""
        sandbox = self._get_sandbox(sandbox_id)
        return await sandbox.read_file(path)
    
    async def schedule_timeout(self, sandbox_id: str, seconds: int):
        """Schedule sandbox for deletion."""
        await self.queue.schedule(sandbox_id, seconds)
    
    async def delete_sandbox(self, sandbox_id: str):
        """Delete sandbox immediately."""
        sandbox = self.sandboxes.pop(sandbox_id, None)
        if sandbox:
            await sandbox.close()
        await self.queue.cancel(sandbox_id)
    
    def _get_sandbox(self, sandbox_id: str) -> E2BSandbox:
        """Get sandbox from cache."""
        if sandbox_id not in self.sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return self.sandboxes[sandbox_id]
```

### 4. e2b.py - E2B Wrapper

```python
from e2b_code_interpreter import AsyncSandbox

class E2BSandbox:
    """Wrapper around E2B SDK."""
    
    def __init__(self, sandbox: AsyncSandbox, sandbox_id: str):
        self._sandbox = sandbox
        self._sandbox_id = sandbox_id
    
    @classmethod
    async def create(cls, config, sandbox_id: str, template_id: str):
        """Create new E2B sandbox."""
        sandbox = await AsyncSandbox.create(
            template=template_id,
            api_key=config.e2b_api_key
        )
        return cls(sandbox, sandbox_id)
    
    @classmethod
    async def connect(cls, config, sandbox_id: str):
        """Connect to existing sandbox."""
        sandbox = await AsyncSandbox.connect(
            sandbox_id=sandbox_id,
            api_key=config.e2b_api_key
        )
        return cls(sandbox, sandbox_id)
    
    async def run_command(self, command: str, background: bool = False) -> str:
        """Run shell command."""
        if background:
            await self._sandbox.commands.run(command, background=True)
            return ""
        else:
            result = await self._sandbox.commands.run(command)
            return result.stdout + result.stderr
    
    async def expose_port(self, port: int) -> str:
        """Get public URL for port."""
        # E2B format: https://{sandbox_id}-{port}.e2b.dev
        return f"https://{self._sandbox.get_host(port)}"
    
    async def write_file(self, path: str, content: str):
        """Write file to sandbox."""
        await self._sandbox.files.write(path, content)
    
    async def read_file(self, path: str) -> str:
        """Read file from sandbox."""
        return await self._sandbox.files.read(path)
    
    async def close(self):
        """Close/delete the sandbox."""
        await self._sandbox.close()
```

### 5. client.py - Client Library

This is what your LangChain app uses to talk to the server:

```python
import httpx
from typing import Optional

class SandboxClient:
    """Client to communicate with Sandbox Server."""
    
    def __init__(self, server_url: str, timeout: int = 60):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
    
    async def create_sandbox(
        self, 
        user_id: str,
        template_id: Optional[str] = None
    ) -> str:
        """Create a new sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/create",
                json={
                    "user_id": user_id,
                    "template_id": template_id
                }
            )
            response.raise_for_status()
            return response.json()["sandbox_id"]
    
    async def connect_sandbox(self, sandbox_id: str):
        """Connect to existing sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/connect",
                json={"sandbox_id": sandbox_id}
            )
            response.raise_for_status()
    
    async def run_command(
        self, 
        sandbox_id: str, 
        command: str,
        background: bool = False
    ) -> str:
        """Run command in sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/run-command",
                json={
                    "sandbox_id": sandbox_id,
                    "command": command,
                    "background": background
                }
            )
            response.raise_for_status()
            return response.json()["output"]
    
    async def expose_port(self, sandbox_id: str, port: int) -> str:
        """Get public URL for port."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/expose-port",
                json={
                    "sandbox_id": sandbox_id,
                    "port": port
                }
            )
            response.raise_for_status()
            return response.json()["url"]
    
    async def write_file(self, sandbox_id: str, path: str, content: str):
        """Write file to sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/write-file",
                json={
                    "sandbox_id": sandbox_id,
                    "path": path,
                    "content": content
                }
            )
            response.raise_for_status()
    
    async def read_file(self, sandbox_id: str, path: str) -> str:
        """Read file from sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/read-file",
                json={
                    "sandbox_id": sandbox_id,
                    "path": path
                }
            )
            response.raise_for_status()
            return response.json()["content"]
    
    async def schedule_timeout(self, sandbox_id: str, timeout: int):
        """Schedule sandbox for deletion."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/timeout",
                json={
                    "sandbox_id": sandbox_id,
                    "timeout": timeout
                }
            )
            response.raise_for_status()
    
    async def delete_sandbox(self, sandbox_id: str):
        """Delete sandbox immediately."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.server_url}/sandboxes/{sandbox_id}"
            )
            response.raise_for_status()
```

---

## Why Use the Sandbox Server Instead of Direct E2B?

### Direct E2B Approach (Simple but Limited)

```python
# In your LangChain agent
from e2b_code_interpreter import Sandbox

# Problem 1: E2B API key is in your agent code
sandbox = Sandbox(api_key="e2b_...")

# Problem 2: No session management
# If your agent crashes, you lose track of the sandbox

# Problem 3: No timeout management
# Sandbox runs forever unless you manually close it

# Problem 4: No multi-user support
# Hard to track which sandbox belongs to which user
```

### With Sandbox Server (Production Ready)

```python
# In your LangChain agent
from sandbox_client import SandboxClient

client = SandboxClient("http://sandbox-server:8080")

# Create sandbox for user
sandbox_id = await client.create_sandbox(user_id="user123")

# Sandbox server handles:
# - E2B API key (stored server-side)
# - Session tracking (maps user_id to sandbox_id)
# - Automatic timeout (sandbox deleted after 1 hour of inactivity)
# - Reconnection (if sandbox is paused, it resumes)
```

---

## Why the Database?

The database is OPTIONAL but useful for:

1. **Persistence** - If sandbox server restarts, it remembers existing sandboxes
2. **Timeout Queue** - Scheduled timeouts survive restarts
3. **Analytics** - Track sandbox usage, costs, etc.

### Without Database (In-Memory Only)

```python
class SandboxController:
    def __init__(self):
        self.sandboxes = {}  # Lost on restart!
```

### With Database

```python
class SandboxController:
    def __init__(self, db):
        self.db = db
    
    async def create_sandbox(self, user_id):
        sandbox = await E2BSandbox.create(...)
        
        # Persist to database
        await self.db.execute(
            "INSERT INTO sandboxes (id, user_id, e2b_id) VALUES (?, ?, ?)",
            sandbox_id, user_id, sandbox.e2b_id
        )
        
        return sandbox_id
    
    async def on_restart(self):
        # Reload sandboxes from database
        rows = await self.db.fetchall("SELECT * FROM sandboxes")
        for row in rows:
            sandbox = await E2BSandbox.connect(row.e2b_id)
            self.sandboxes[row.id] = sandbox
```

---

## Running the Sandbox Server

### Development

```bash
cd src/ii_sandbox_server

# Create .env file
cat > .env << EOF
E2B_API_KEY=your_e2b_api_key
E2B_TEMPLATE_ID=your_template_id
EOF

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Production

```bash
# With Docker
docker build -t sandbox-server .
docker run -p 8080:8080 \
  -e E2B_API_KEY=xxx \
  -e E2B_TEMPLATE_ID=xxx \
  sandbox-server
```

---

## Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sandboxes/create` | Create new sandbox |
| POST | `/sandboxes/connect` | Connect to existing sandbox |
| POST | `/sandboxes/run-command` | Execute shell command |
| POST | `/sandboxes/expose-port` | Get public URL for port |
| POST | `/sandboxes/write-file` | Write file |
| POST | `/sandboxes/read-file` | Read file |
| POST | `/sandboxes/timeout` | Schedule cleanup |
| DELETE | `/sandboxes/{id}` | Delete immediately |
| GET | `/sandboxes/{id}/status` | Get sandbox status |
