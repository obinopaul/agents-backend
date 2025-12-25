# Sandbox Execution Environment - Complete Guide

The Agents Backend includes **two sandbox systems** for different use cases: a local containerized sandbox for development and a production-grade cloud sandbox with multiple providers.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Sandbox Architecture                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    ┌─────────────────────────────────────┐                  │
│                    │         Sandbox Controller          │                  │
│                    │     (Lifecycle Management)          │                  │
│                    └─────────────────────────────────────┘                  │
│                                    │                                         │
│              ┌─────────────────────┼─────────────────────┐                  │
│              ▼                     ▼                     ▼                  │
│     ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐        │
│     │  Agent Infra    │   │    E2B Cloud    │   │    Daytona      │        │
│     │   (Local Dev)   │   │  (Production)   │   │  (Production)   │        │
│     └─────────────────┘   └─────────────────┘   └─────────────────┘        │
│              │                     │                     │                  │
│              └─────────────────────┼─────────────────────┘                  │
│                                    ▼                                         │
│                    ┌─────────────────────────────────────┐                  │
│                    │         Unified API                 │                  │
│                    │   (file ops, shell, preview)        │                  │
│                    └─────────────────────────────────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Agent Infra Sandbox (Local Development)

A containerized local sandbox for development and testing.

### Quick Start

```bash
# 1. Navigate to sandbox directory
cd backend/src/sandbox/agent_infra_sandbox

# 2. Start the container
docker-compose up -d

# 3. Verify it's running
python check_sandbox.py

# 4. Access the sandbox
# Web UI: http://localhost:8090
```

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Infra Sandbox (Docker)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────────┐    ┌─────────────────────┐                │
│   │   DeepAgents CLI    │    │   LangChain Tools   │                │
│   │  (Interactive AI    │    │  (23+ sandbox tools │                │
│   │   coding assistant) │    │   for agents)       │                │
│   └─────────────────────┘    └─────────────────────┘                │
│              │                        │                              │
│              └────────────┬───────────┘                              │
│                           ▼                                          │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │              Shared Infrastructure                          │   │
│   │  • client.py - Unified sandbox client                      │   │
│   │  • session.py - Workspace isolation                        │   │
│   │  • exceptions.py - Common error handling                   │   │
│   └────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Integration Options

| Approach | Description | Best For |
|----------|-------------|----------|
| **DeepAgents CLI** | Interactive terminal AI coding assistant | Developers, interactive sessions |
| **LangChain Tools** | 23+ tools for LangChain/LangGraph agents | Production agents, automation |

### DeepAgents CLI Commands

```bash
# Interactive mode (default)
python -m deepagents_cli

# With auto-approve
python -m deepagents_cli --auto-approve

# Reset an agent's memory
python -m deepagents_cli reset --agent my_agent

# Without sandbox
python -m deepagents_cli --sandbox none
```

### LangChain Tools Usage

```python
from agent_infra_sandbox import SandboxSession

async with await SandboxSession.create(session_id="chat_123") as session:
    tools = session.get_tools()
    tool_map = {t.name: t for t in tools}
    
    # Write a file
    await tool_map["file_write"].ainvoke({
        "file": "app.py",
        "content": "print('Hello!')"
    })
    
    # Execute a command
    result = await tool_map["shell_exec"].ainvoke({
        "command": "python app.py"
    })
    print(result)
```

### Available Tools (23+)

| Category | Tools |
|----------|-------|
| **File Operations** | `file_read`, `file_write`, `file_delete`, `file_list`, `file_search` |
| **Shell** | `shell_exec`, `shell_interactive` |
| **Git** | `git_clone`, `git_commit`, `git_push`, `git_status` |
| **Python** | `python_exec`, `pip_install` |
| **Web** | `http_request`, `browser_open` |
| **System** | `env_get`, `env_set`, `process_list` |

---

## 2. Sandbox Server (Production-Grade)

Enterprise sandbox with session management, lifecycle control, and cloud providers.

### Providers

| Provider | Description | Features | Code Path |
|----------|-------------|----------|-----------|
| **E2B** | Cloud-based isolation | Persistent, secure, VS Code integration | [`e2b.py`](../../backend/src/sandbox/sandbox_server/sandboxes/e2b.py) |
| **Daytona** | Managed dev environments | Git integration, custom images | [`daytona.py`](../../backend/src/sandbox/sandbox_server/sandboxes/daytona.py) |

### Configuration

```bash
# Environment variables
SANDBOX_PROVIDER=e2b  # or 'daytona'
E2B_API_KEY=your_key_here
DAYTONA_API_KEY=your_key_here
DAYTONA_SERVER_URL=https://your-daytona-server.com
```

### Lifecycle Management

| Component | Description | Code Path |
|-----------|-------------|-----------|
| **Queue Scheduler** | Message queue for sandbox operations | [`lifecycle/queue.py`](../../backend/src/sandbox/sandbox_server/lifecycle/queue.py) |
| **Sandbox Controller** | Create, stop, delete, timeout handling | [`lifecycle/sandbox_controller.py`](../../backend/src/sandbox/sandbox_server/lifecycle/sandbox_controller.py) |

### Sandbox Factory

```python
from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import create_sandbox

# Create based on SANDBOX_PROVIDER env var
sandbox = await create_sandbox()

# Or specify provider
sandbox = await create_sandbox(provider="e2b")
sandbox = await create_sandbox(provider="daytona")
```

### API Usage

```python
# Create sandbox
sandbox_id = await sandbox.create(
    template="python-3.11",
    timeout=3600  # 1 hour
)

# Execute command
result = await sandbox.run_command("pip install pandas")

# Read/write files
content = await sandbox.read_file("/workspace/data.csv")
await sandbox.write_file("/workspace/output.txt", "Hello!")

# Get preview URL
url = await sandbox.get_preview_url(port=8000)

# Cleanup
await sandbox.delete()
```

---

## Sandbox Templates

Pre-configured environments for common use cases.

| Template | Purpose | Included Tools | Code Path |
|----------|---------|----------------|-----------|
| **Code Server** | VS Code in browser | Python, Node, Git | [`docker/sandbox/start-services.sh`](../../backend/docker/sandbox/start-services.sh) |
| **Cloud Code** | Google Cloud Shell compatible | gcloud, kubectl | [`docker/sandbox/`](../../backend/docker/sandbox/) |
| **Claude Template** | Claude-optimized | Anthropic tools | [`docker/sandbox/claude_template.json`](../../backend/docker/sandbox/claude_template.json) |
| **Codex Config** | OpenAI Codex | Code completion | [`docker/sandbox/codex_config.toml`](../../backend/docker/sandbox/codex_config.toml) |

---

## E2B Provider Details

| Feature | Description |
|---------|-------------|
| **Isolation** | Each sandbox runs in isolated container |
| **Persistence** | State persists across sessions |
| **VS Code** | Web-based VS Code available |
| **Timeout** | Configurable auto-shutdown |
| **Resources** | 2 CPU, 4GB RAM default |

```python
from backend.src.sandbox.sandbox_server.sandboxes.e2b import E2BSandbox

sandbox = E2BSandbox()
await sandbox.create(template="python-data-science")

# Run Python
result = await sandbox.execute("""
import pandas as pd
df = pd.DataFrame({'a': [1,2,3]})
print(df)
""")
```

---

## Daytona Provider Details

| Feature | Description |
|---------|-------------|
| **Git Integration** | Clone repos on startup |
| **Custom Images** | Use any Docker image |
| **Port Forwarding** | Expose any port as URL |
| **Workspace Persistence** | Keep files across restarts |

```python
from backend.src.sandbox.sandbox_server.sandboxes.daytona import DaytonaSandbox

sandbox = DaytonaSandbox()
await sandbox.create(
    git_url="https://github.com/user/repo",
    image="python:3.11-slim"
)

# Get web preview
url = await sandbox.get_preview_url(port=8000)
# Returns: https://sandbox-id.daytona.io:8000
```

---

## Environment Variables Summary

### Agent Infra Sandbox
| Variable | Description |
|----------|-------------|
| `SANDBOX_HOST` | Sandbox container host (default: localhost) |
| `SANDBOX_PORT` | Sandbox container port (default: 8090) |

### E2B Provider
| Variable | Description |
|----------|-------------|
| `E2B_API_KEY` | E2B API key |
| `E2B_TIMEOUT` | Sandbox timeout in seconds |

### Daytona Provider
| Variable | Description |
|----------|-------------|
| `DAYTONA_API_KEY` | Daytona API key |
| `DAYTONA_SERVER_URL` | Daytona server URL |
| `DAYTONA_TARGET` | Default target environment |

### General
| Variable | Description |
|----------|-------------|
| `SANDBOX_PROVIDER` | Which provider to use (e2b, daytona) |

---

## Related Documentation

- [DeepAgents CLI Guide](deepagents-cli.md) - Interactive CLI details
- [PTC Module](ptc-module.md) - Programmatic Tool Calling
- [Agent Infra Sandbox README](../../backend/src/sandbox/agent_infra_sandbox/README.md)
- [Main README](../../README.md) - Project overview
</Parameter>
<parameter name="Complexity">4
