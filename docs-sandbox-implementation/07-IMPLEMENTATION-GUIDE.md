# Step-by-Step Implementation Guide

This is the practical guide for implementing the sandbox infrastructure in your own project.

---

## Prerequisites

1. **E2B Account** - Sign up at https://e2b.dev
2. **E2B API Key** - Get from E2B dashboard
3. **Python 3.10+** - For sandbox server
4. **Node.js 18+** - For E2B CLI and code-server
5. **Docker** - For building E2B template

---

## Project Structure

Create this structure for your sandbox infrastructure:

```
your-project/
├── sandbox-server/           # The sandbox management server
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── requirements.txt     # Dependencies
│   │
│   ├── sandboxes/           # Sandbox providers
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract base
│   │   └── e2b.py           # E2B implementation
│   │
│   ├── client/              # Client library
│   │   ├── __init__.py
│   │   └── client.py        # HTTP client
│   │
│   └── models/              # Pydantic models
│       ├── __init__.py
│       └── payload.py       # Request/Response
│
├── sandbox-template/         # E2B Docker template
│   ├── Dockerfile           # The E2B template
│   ├── start-services.sh    # Startup script
│   ├── requirements.txt     # Python deps for template
│   └── mcp-server/          # Your MCP tool server
│       ├── __init__.py
│       └── server.py
│
└── your-langchain-agent/     # Your existing project
    └── (integrates with sandbox-server)
```

---

## Step 1: Create the E2B Template

### 1.1 Dockerfile

Create `sandbox-template/Dockerfile`:

```dockerfile
# Base image with Python and Node.js
FROM nikolaik/python-nodejs:python3.10-nodejs20-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    tmux \
    ripgrep \
    xvfb \
    wget \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install code-server (VS Code in browser)
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Install Claude Code (optional)
RUN npm install -g @anthropic-ai/claude-code

# Install Playwright for browser automation (optional)
RUN npm install -g playwright
RUN npx playwright install chromium
RUN npx playwright install-deps

# Create workspace directory
RUN mkdir -p /workspace /app
WORKDIR /workspace

# Copy MCP server code
COPY mcp-server /app/mcp-server
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy startup script
COPY start-services.sh /app/start-services.sh
RUN chmod +x /app/start-services.sh

# Default environment
ENV HOME=/root
ENV WORKSPACE_DIR=/workspace

# Entry point runs startup script
CMD ["/app/start-services.sh"]
```

### 1.2 Startup Script

Create `sandbox-template/start-services.sh`:

```bash
#!/bin/bash

echo "Starting sandbox services..."

# Create workspace if not exists
mkdir -p /workspace
cd /workspace

# Start MCP tool server (port 6060)
echo "Starting MCP server on port 6060..."
tmux new-session -d -s mcp-server -c /workspace \
    'python -m mcp-server.server'

# Start code-server (port 9000)
echo "Starting code-server on port 9000..."
tmux new-session -d -s code-server -c /workspace \
    'code-server \
        --port 9000 \
        --auth none \
        --bind-addr 0.0.0.0:9000 \
        --disable-telemetry \
        /workspace'

# Wait a moment for services to start
sleep 2

# Verify services
echo "Checking services..."
if pgrep -f "mcp-server" > /dev/null; then
    echo "✓ MCP server running"
else
    echo "✗ MCP server failed"
fi

if pgrep -f "code-server" > /dev/null; then
    echo "✓ Code-server running"
else
    echo "✗ Code-server failed"
fi

echo "Sandbox ready!"

# Keep container running
tail -f /dev/null
```

### 1.3 MCP Server

Create `sandbox-template/mcp-server/server.py`:

```python
"""Simple MCP server with file and shell tools."""

import os
import subprocess
from fastmcp import FastMCP

app = FastMCP("Sandbox Tools")

WORKSPACE = os.getenv("WORKSPACE_DIR", "/workspace")


@app.tool()
async def read_file(path: str) -> str:
    """Read contents of a file."""
    full_path = os.path.join(WORKSPACE, path)
    
    if not os.path.exists(full_path):
        return f"Error: File not found: {path}"
    
    with open(full_path, "r") as f:
        return f.read()


@app.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates directories if needed."""
    full_path = os.path.join(WORKSPACE, path)
    
    os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
    
    with open(full_path, "w") as f:
        f.write(content)
    
    return f"Successfully wrote {len(content)} bytes to {path}"


@app.tool()
async def list_directory(path: str = ".") -> list[str]:
    """List files and directories in a path."""
    full_path = os.path.join(WORKSPACE, path)
    
    if not os.path.exists(full_path):
        return [f"Error: Directory not found: {path}"]
    
    items = []
    for item in os.listdir(full_path):
        item_path = os.path.join(full_path, item)
        if os.path.isdir(item_path):
            items.append(f"{item}/")
        else:
            items.append(item)
    
    return sorted(items)


@app.tool()
async def run_command(command: str, background: bool = False) -> str:
    """Run a shell command in the workspace."""
    if background:
        subprocess.Popen(
            command,
            shell=True,
            cwd=WORKSPACE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return f"Started background process: {command}"
    
    result = subprocess.run(
        command,
        shell=True,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    output = result.stdout + result.stderr
    if result.returncode != 0:
        output = f"[Exit code: {result.returncode}]\n{output}"
    
    return output


@app.tool()
async def search_files(pattern: str, path: str = ".") -> list[str]:
    """Search for files matching a pattern using ripgrep."""
    full_path = os.path.join(WORKSPACE, path)
    
    result = subprocess.run(
        ["rg", "--files", "-g", pattern],
        cwd=full_path,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return []
    
    return result.stdout.strip().split("\n") if result.stdout else []


if __name__ == "__main__":
    app.run(transport="http", host="0.0.0.0", port=6060)
```

### 1.4 Requirements

Create `sandbox-template/requirements.txt`:

```
fastmcp>=0.1.0
uvicorn>=0.20.0
```

### 1.5 Build and Upload Template

```bash
cd sandbox-template

# Install E2B CLI
npm install -g @e2b/cli

# Login to E2B
e2b login

# Build template (this uploads to E2B)
e2b template build --name my-sandbox-template

# Save the template ID that's printed
# Example output: Template ID: template_abc123xyz
```

---

## Step 2: Create the Sandbox Server

### 2.1 Configuration

Create `sandbox-server/config.py`:

```python
from pydantic_settings import BaseSettings


class SandboxConfig(BaseSettings):
    """Sandbox server configuration."""
    
    # E2B credentials (set via environment variables)
    e2b_api_key: str
    e2b_template_id: str
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    
    # Sandbox settings
    default_timeout: int = 3600  # 1 hour
    mcp_port: int = 6060
    vscode_port: int = 9000
    
    class Config:
        env_file = ".env"
```

### 2.2 Models

Create `sandbox-server/models/payload.py`:

```python
from pydantic import BaseModel
from typing import Optional


class CreateSandboxRequest(BaseModel):
    user_id: str
    template_id: Optional[str] = None


class CreateSandboxResponse(BaseModel):
    sandbox_id: str
    mcp_url: str
    vscode_url: str


class ConnectSandboxRequest(BaseModel):
    sandbox_id: str


class RunCommandRequest(BaseModel):
    sandbox_id: str
    command: str
    background: bool = False


class RunCommandResponse(BaseModel):
    output: str


class ExposePortRequest(BaseModel):
    sandbox_id: str
    port: int


class ExposePortResponse(BaseModel):
    url: str


class FileOperationRequest(BaseModel):
    sandbox_id: str
    path: str
    content: Optional[str] = None


class FileOperationResponse(BaseModel):
    content: Optional[str] = None
    success: bool = True


class SandboxStatusResponse(BaseModel):
    status: str
    sandbox_id: str
```

### 2.3 E2B Wrapper

Create `sandbox-server/sandboxes/e2b.py`:

```python
from typing import Optional
from e2b_code_interpreter import AsyncSandbox


class E2BSandbox:
    """Wrapper around E2B SDK."""
    
    def __init__(self, sandbox: AsyncSandbox, sandbox_id: str):
        self._sandbox = sandbox
        self._sandbox_id = sandbox_id
    
    @property
    def sandbox_id(self) -> str:
        return self._sandbox_id
    
    @classmethod
    async def create(
        cls, 
        api_key: str, 
        template_id: str,
        sandbox_id: str
    ) -> "E2BSandbox":
        """Create a new E2B sandbox."""
        sandbox = await AsyncSandbox.create(
            template=template_id,
            api_key=api_key
        )
        return cls(sandbox, sandbox_id)
    
    @classmethod
    async def connect(
        cls, 
        api_key: str, 
        e2b_sandbox_id: str,
        sandbox_id: str
    ) -> "E2BSandbox":
        """Connect to existing sandbox."""
        sandbox = await AsyncSandbox.connect(
            sandbox_id=e2b_sandbox_id,
            api_key=api_key
        )
        return cls(sandbox, sandbox_id)
    
    async def expose_port(self, port: int) -> str:
        """Get public URL for a port."""
        return f"https://{self._sandbox.get_host(port)}"
    
    async def run_command(
        self, 
        command: str, 
        background: bool = False
    ) -> str:
        """Run shell command."""
        if background:
            await self._sandbox.commands.run(command, background=True)
            return "Command started in background"
        
        result = await self._sandbox.commands.run(command)
        return result.stdout + result.stderr
    
    async def write_file(self, path: str, content: str):
        """Write file to sandbox."""
        await self._sandbox.files.write(path, content)
    
    async def read_file(self, path: str) -> str:
        """Read file from sandbox."""
        return await self._sandbox.files.read(path)
    
    async def close(self):
        """Close the sandbox."""
        await self._sandbox.close()
    
    async def get_status(self) -> str:
        """Get sandbox status."""
        try:
            await self._sandbox.commands.run("echo ok", timeout=5)
            return "running"
        except:
            return "paused"
```

### 2.4 Main Application

Create `sandbox-server/main.py`:

```python
import uuid
from typing import Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import SandboxConfig
from sandboxes.e2b import E2BSandbox
from models.payload import (
    CreateSandboxRequest,
    CreateSandboxResponse,
    ConnectSandboxRequest,
    RunCommandRequest,
    RunCommandResponse,
    ExposePortRequest,
    ExposePortResponse,
    FileOperationRequest,
    FileOperationResponse,
    SandboxStatusResponse,
)


# Global state
config = SandboxConfig()
sandboxes: Dict[str, E2BSandbox] = {}
sandbox_e2b_ids: Dict[str, str] = {}  # sandbox_id -> e2b_sandbox_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print(f"Starting sandbox server on {config.host}:{config.port}")
    print(f"E2B Template ID: {config.e2b_template_id}")
    yield
    # Cleanup on shutdown
    for sandbox in sandboxes.values():
        try:
            await sandbox.close()
        except:
            pass


app = FastAPI(title="Sandbox Server", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sandboxes/create", response_model=CreateSandboxResponse)
async def create_sandbox(request: CreateSandboxRequest):
    """Create a new sandbox."""
    sandbox_id = f"{request.user_id}_{uuid.uuid4().hex[:8]}"
    template_id = request.template_id or config.e2b_template_id
    
    try:
        sandbox = await E2BSandbox.create(
            api_key=config.e2b_api_key,
            template_id=template_id,
            sandbox_id=sandbox_id
        )
        
        sandboxes[sandbox_id] = sandbox
        sandbox_e2b_ids[sandbox_id] = sandbox._sandbox.sandbox_id
        
        # Get URLs for services
        mcp_url = await sandbox.expose_port(config.mcp_port)
        vscode_url = await sandbox.expose_port(config.vscode_port)
        
        return CreateSandboxResponse(
            sandbox_id=sandbox_id,
            mcp_url=mcp_url,
            vscode_url=vscode_url
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/connect")
async def connect_sandbox(request: ConnectSandboxRequest):
    """Connect to existing sandbox (resumes if paused)."""
    sandbox_id = request.sandbox_id
    
    if sandbox_id not in sandbox_e2b_ids:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    try:
        e2b_id = sandbox_e2b_ids[sandbox_id]
        sandbox = await E2BSandbox.connect(
            api_key=config.e2b_api_key,
            e2b_sandbox_id=e2b_id,
            sandbox_id=sandbox_id
        )
        sandboxes[sandbox_id] = sandbox
        
        return {"success": True}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/run-command", response_model=RunCommandResponse)
async def run_command(request: RunCommandRequest):
    """Run a command in the sandbox."""
    if request.sandbox_id not in sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = sandboxes[request.sandbox_id]
    
    try:
        output = await sandbox.run_command(
            request.command,
            background=request.background
        )
        return RunCommandResponse(output=output)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/expose-port", response_model=ExposePortResponse)
async def expose_port(request: ExposePortRequest):
    """Get public URL for a port."""
    if request.sandbox_id not in sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = sandboxes[request.sandbox_id]
    
    try:
        url = await sandbox.expose_port(request.port)
        return ExposePortResponse(url=url)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/write-file", response_model=FileOperationResponse)
async def write_file(request: FileOperationRequest):
    """Write a file to the sandbox."""
    if request.sandbox_id not in sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    if not request.content:
        raise HTTPException(status_code=400, detail="Content required")
    
    sandbox = sandboxes[request.sandbox_id]
    
    try:
        await sandbox.write_file(request.path, request.content)
        return FileOperationResponse(success=True)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/read-file", response_model=FileOperationResponse)
async def read_file(request: FileOperationRequest):
    """Read a file from the sandbox."""
    if request.sandbox_id not in sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = sandboxes[request.sandbox_id]
    
    try:
        content = await sandbox.read_file(request.path)
        return FileOperationResponse(content=content, success=True)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sandboxes/{sandbox_id}/status", response_model=SandboxStatusResponse)
async def get_status(sandbox_id: str):
    """Get sandbox status."""
    if sandbox_id not in sandboxes:
        if sandbox_id in sandbox_e2b_ids:
            return SandboxStatusResponse(status="paused", sandbox_id=sandbox_id)
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = sandboxes[sandbox_id]
    status = await sandbox.get_status()
    
    return SandboxStatusResponse(status=status, sandbox_id=sandbox_id)


@app.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    """Delete a sandbox."""
    if sandbox_id not in sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = sandboxes.pop(sandbox_id)
    sandbox_e2b_ids.pop(sandbox_id, None)
    
    try:
        await sandbox.close()
    except:
        pass
    
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
```

### 2.5 Requirements

Create `sandbox-server/requirements.txt`:

```
fastapi>=0.100.0
uvicorn>=0.20.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
e2b-code-interpreter>=0.0.10
httpx>=0.24.0
python-dotenv>=1.0.0
```

### 2.6 Environment File

Create `sandbox-server/.env`:

```bash
E2B_API_KEY=your_e2b_api_key_here
E2B_TEMPLATE_ID=template_abc123xyz
```

---

## Step 3: Create Client Library

Create `sandbox-server/client/client.py`:

```python
import httpx
from typing import Optional


class SandboxClient:
    """Client to interact with the sandbox server."""
    
    def __init__(self, server_url: str, timeout: int = 60):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
    
    async def create_sandbox(
        self, 
        user_id: str,
        template_id: Optional[str] = None
    ) -> dict:
        """Create a new sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.server_url}/sandboxes/create",
                json={"user_id": user_id, "template_id": template_id}
            )
            response.raise_for_status()
            return response.json()
    
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
                json={"sandbox_id": sandbox_id, "port": port}
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
                json={"sandbox_id": sandbox_id, "path": path}
            )
            response.raise_for_status()
            return response.json()["content"]
    
    async def delete_sandbox(self, sandbox_id: str):
        """Delete sandbox."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.server_url}/sandboxes/{sandbox_id}"
            )
            response.raise_for_status()
```

---

## Step 4: Running Everything

### Start Sandbox Server

```bash
cd sandbox-server

# Install dependencies
pip install -r requirements.txt

# Run server
python main.py
# Or with uvicorn for auto-reload
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Test with Client

```python
import asyncio
from client import SandboxClient

async def main():
    client = SandboxClient("http://localhost:8080")
    
    # Create sandbox
    result = await client.create_sandbox(user_id="test_user")
    print(f"Sandbox ID: {result['sandbox_id']}")
    print(f"VS Code URL: {result['vscode_url']}")
    print(f"MCP URL: {result['mcp_url']}")
    
    sandbox_id = result['sandbox_id']
    
    # Run a command
    output = await client.run_command(sandbox_id, "ls -la")
    print(f"Command output:\n{output}")
    
    # Write a file
    await client.write_file(sandbox_id, "hello.py", "print('Hello!')")
    
    # Read the file
    content = await client.read_file(sandbox_id, "hello.py")
    print(f"File content: {content}")
    
    # Run Python
    output = await client.run_command(sandbox_id, "python hello.py")
    print(f"Python output: {output}")
    
    # Cleanup
    await client.delete_sandbox(sandbox_id)
    print("Sandbox deleted")

asyncio.run(main())
```

---

## Next Steps

See **08-LANGCHAIN-INTEGRATION.md** for integrating with your LangChain agent.
