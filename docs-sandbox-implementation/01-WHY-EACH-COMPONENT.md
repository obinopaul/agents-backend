# Why Each Component Exists

## The Problem Being Solved

When you build an AI coding agent, you need a place for it to:
1. **Write code** - Create/edit files safely
2. **Run code** - Execute commands without destroying your machine
3. **Preview results** - See websites, run servers
4. **Use AI tools** - Claude Code, Codex, etc.

You can't do this on your local machine because:
- Security risk (AI could `rm -rf /`)
- Isolation needed (multiple users, multiple sessions)
- Scalability (spin up/down on demand)

**Solution: Remote sandboxed environments (E2B)**

---

## Component 1: E2B (The Cloud Sandbox Provider)

### What is E2B?

E2B (https://e2b.dev) is a cloud service that provides:
- **Isolated Linux VMs** that spin up in ~300ms
- **Pre-built templates** or custom Docker images
- **Port forwarding** to expose services to the internet
- **File system access** via API
- **Command execution** via API

### Why Use E2B Instead of Running Locally?

| Local Docker | E2B |
|--------------|-----|
| Runs on YOUR machine | Runs on E2B's cloud |
| Consumes YOUR resources | Scales infinitely |
| Security risk | Fully isolated |
| Can't share URLs | Auto-generates public URLs |
| Manual cleanup | Auto-cleanup after timeout |

### How E2B Works

```python
from e2b_code_interpreter import Sandbox

# Creates a new isolated VM in ~300ms
sandbox = Sandbox()

# Run any command
result = sandbox.run_code("print('Hello from sandbox!')")

# Files persist during session
sandbox.files.write("/home/user/app.py", "print('hi')")

# Expose ports to internet
url = sandbox.get_host(3000)  # Returns https://xxx-3000.e2b.dev

# Cleanup
sandbox.close()
```

---

## Component 2: ii_sandbox_server (The Management Layer)

### Why Not Just Use E2B Directly?

You COULD call E2B's SDK directly from your LangChain app, but:

1. **Session Management** - You need to track which sandbox belongs to which user/session
2. **Lifecycle Management** - Auto-pause idle sandboxes, resume them later
3. **Centralized Control** - One place to manage all sandboxes
4. **Credential Isolation** - Your E2B API key stays on the server
5. **Queue Management** - Handle concurrent sandbox requests

### What ii_sandbox_server Does

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ii_sandbox_server                             │
│                        (FastAPI Application)                         │
│                                                                      │
│  Endpoints:                                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ POST /sandboxes/create    - Create new E2B sandbox             │ │
│  │ POST /sandboxes/connect   - Connect to existing/paused sandbox │ │
│  │ POST /sandboxes/timeout   - Schedule sandbox for deletion      │ │
│  │ POST /sandboxes/delete    - Delete sandbox immediately         │ │
│  │ POST /sandboxes/expose-port - Get public URL for a port        │ │
│  │ POST /sandboxes/run-command - Execute shell command            │ │
│  │ POST /sandboxes/write-file  - Write file to sandbox            │ │
│  │ POST /sandboxes/read-file   - Read file from sandbox           │ │
│  │ GET  /sandboxes/status      - Get sandbox status               │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Internal Components:                                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ SandboxController - Manages sandbox lifecycle                  │ │
│  │ SandboxQueueScheduler - Handles timeouts and cleanup           │ │
│  │ E2BSandbox - Wrapper around E2B SDK                            │ │
│  │ Database (optional) - Persist sandbox metadata                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Database in Sandbox Server?

The database in `ii_sandbox_server` is for:
1. **Tracking sandbox metadata** - Which sandbox ID maps to which user
2. **Queue persistence** - Scheduled timeouts survive server restarts
3. **Not for chat history** - That's in the main backend

For a simple implementation, you can use SQLite or skip the database entirely.

---

## Component 3: e2b.Dockerfile (The Template)

### What is an E2B Template?

When you create a sandbox, E2B uses a **template** - a pre-built Docker image. You can:
1. Use E2B's default templates (basic Python, Node.js, etc.)
2. Create custom templates with YOUR tools pre-installed

### Why Create a Custom Template?

```
Default E2B Template:
- Basic Linux
- Python 3
- That's it

Custom Template (e2b.Dockerfile):
- Python 3.10 + Node.js 24
- Code-Server (VS Code in browser)
- Claude Code CLI (Anthropic's AI coder)
- Codex CLI (OpenAI's AI coder)  
- Playwright (browser automation)
- Your MCP Tool Server
- Tmux for background processes
- Pre-configured development environment
```

### Template Build Process

```bash
# 1. Write your Dockerfile (e2b.Dockerfile)

# 2. Install E2B CLI
npm install -g @e2b/cli

# 3. Login to E2B
e2b login

# 4. Build and upload template
e2b template build -d e2b.Dockerfile

# 5. Get your template ID
# Output: Template ID: abc123xyz

# 6. Use template ID when creating sandboxes
sandbox = Sandbox(template="abc123xyz")
```

---

## Component 4: ii_tool (MCP Server Inside Sandbox)

### The Problem

Your LangChain agent needs to perform actions in the sandbox:
- Read/write files
- Run shell commands  
- Control a browser
- Use Claude Code

You COULD make individual HTTP calls for each operation, but:
- That's many round trips
- Complex error handling
- No standard protocol

### The Solution: MCP (Model Context Protocol)

MCP is a protocol (by Anthropic) for AI agents to interact with tools. It provides:
- Standard tool definitions (name, description, parameters)
- Request/response format
- Streaming support

### How ii_tool Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        E2B Sandbox                                   │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    ii_tool MCP Server                          │  │
│  │                    (Port 6060)                                 │  │
│  │                                                                │  │
│  │  Tools Available:                                              │  │
│  │  ├── read_file(path) → file content                           │  │
│  │  ├── write_file(path, content) → success                      │  │
│  │  ├── run_command(cmd) → output                                │  │
│  │  ├── browser_navigate(url) → screenshot                       │  │
│  │  ├── browser_click(selector) → result                         │  │
│  │  ├── claude_code(prompt) → code changes                       │  │
│  │  └── ... many more                                            │  │
│  │                                                                │  │
│  │  Also proxies to:                                              │  │
│  │  ├── User's custom MCP servers                                │  │
│  │  ├── Claude Code MCP                                          │  │
│  │  └── Codex MCP                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              ▲                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │ MCP Protocol (HTTP + SSE)
                               │
┌──────────────────────────────┴───────────────────────────────────────┐
│                     Your LangChain Agent                             │
│                                                                      │
│  from langchain.tools import MCP                                     │
│  tools = MCP.from_url("https://sandbox-id-6060.e2b.dev/mcp/")       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component 5: docker/sandbox/ (Startup Scripts)

### What's in This Directory?

| File | Purpose |
|------|---------|
| `start-services.sh` | Script that runs when sandbox starts |
| `entrypoint.sh` | Docker entrypoint (switches to correct user) |
| `claude_template.json` | Pre-configured Claude Code settings |
| `codex_config.toml` | Pre-configured Codex settings |

### Why start-services.sh?

When an E2B sandbox starts, you need to:
1. Start the MCP tool server
2. Start Code-Server (VS Code)
3. Start any other background services

This script does all that:

```bash
#!/bin/bash

# Start MCP tool server in background
tmux new-session -d -s mcp-server 'python -m ii_tool.mcp.server'

# Start VS Code in browser in background
tmux new-session -d -s code-server 'code-server --port 9000'

# Keep container running
wait
```

---

## Summary: Data Flow

```
1. User sends message to your LangChain agent
                    │
                    ▼
2. Agent decides to write code
                    │
                    ▼
3. Agent calls sandbox_client.create_sandbox()
                    │
                    ▼
4. Sandbox Server calls E2B API
                    │
                    ▼
5. E2B spins up VM from your template (e2b.Dockerfile)
                    │
                    ▼
6. Template's start-services.sh runs:
   - Starts MCP server on port 6060
   - Starts Code-Server on port 9000
                    │
                    ▼
7. Sandbox Server returns sandbox ID + URLs
                    │
                    ▼
8. Agent calls MCP tools via sandbox URL
   POST https://sandbox-id-6060.e2b.dev/mcp/
   {"tool": "write_file", "args": {"path": "...", "content": "..."}}
                    │
                    ▼
9. MCP server in sandbox executes tool
                    │
                    ▼
10. User can view code at https://sandbox-id-9000.e2b.dev (VS Code)
```

---

## What You Need to Implement

### Minimum Viable Implementation

1. **E2B Account** - Sign up at e2b.dev
2. **Custom Template** - Build from e2b.Dockerfile
3. **Sandbox Server** - Run ii_sandbox_server (or build simpler version)
4. **LangChain Integration** - Call sandbox server from your agent

### Optional (But Recommended)

1. **ii_tool** - Use their MCP server or build your own
2. **Claude Code** - If you want AI-powered coding in sandbox
3. **Code-Server** - If you want VS Code in browser
4. **Database** - For production sandbox management
