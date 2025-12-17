# LangChain Sandbox Tools

Production-ready LangChain tools for integrating with [AIO Sandbox](https://github.com/agent-infra/sandbox) Docker containers.

## Key Features

- 🔒 **Automatic Workspace Isolation** - Each session gets its own workspace; agents can't escape
- 📁 **Relative Paths** - Tools use paths relative to workspace (no full paths needed)
- 🔄 **Persistent Sessions** - Shell and Jupyter state persists within a session
- 🌐 **Browser Automation** - Screenshots, actions, CDP integration for Playwright
- 🔌 **MCP Integration** - Access pre-configured MCP servers and tools

## Installation

```bash
cd langchain_tools
pip install -e .
```

## Prerequisites

```bash
docker run --security-opt seccomp=unconfined --rm -d -p 8080:8080 ghcr.io/agent-infra/sandbox:latest
```

## Quick Start (Session-Based)

**Recommended approach** - automatic workspace isolation:

```python
import asyncio
from langchain_tools import SandboxSession

async def main():
    # Create isolated session for a chat/agent
    session = await SandboxSession.create(session_id="chat_123")
    tools = session.get_tools()
    tool_map = {t.name: t for t in tools}
    
    # All paths are RELATIVE to workspace - can't escape!
    await tool_map["file_write"].ainvoke({
        "file": "app.py",  # -> /home/gem/workspaces/chat_123/app.py
        "content": "print('Hello!')",
    })
    
    # Shell runs IN the workspace directory
    result = await tool_map["shell_exec"].ainvoke({
        "command": "python app.py",  # Runs from workspace
    })
    print(result)  # [SUCCESS]\nHello!
    
    # Cleanup when done
    await session.cleanup()

asyncio.run(main())
```

### Using Context Manager

```python
async with await SandboxSession.create(session_id="chat_456") as session:
    tools = session.get_tools()
    # ... use tools ...
# Automatically cleaned up
```

## Session Architecture

```text
┌─────────────────────────────────────────────────────────┐
│          Single Docker Sandbox Container                 │
│                    (localhost:8080)                      │
├─────────────────────────────────────────────────────────┤
│  /home/gem/workspaces/                                   │
│    ├── chat_123/   ← Session 1's isolated files         │
│    ├── chat_456/   ← Session 2's isolated files         │
│    └── chat_789/   ← Session 3's isolated files         │
│                                                          │
│  Each session has dedicated:                             │
│    • Shell session (runs in its workspace)              │
│    • Jupyter kernel (cwd set to workspace)              │
└─────────────────────────────────────────────────────────┘
```

## Session Tools (23 tools)

### File Tools (6)

| Tool | Description |
|------|-------------|
| `file_read` | Read file (relative path) |
| `file_write` | Write file, auto-creates directories |
| `file_edit` | Replace content in file |
| `file_list` | List directory contents |
| `file_find` | Find files by glob pattern |
| `file_search` | Regex search in file |

### Shell Tools (5)

| Tool | Description |
|------|-------------|
| `shell_exec` | Execute command (runs in workspace) |
| `shell_view` | View session output |
| `shell_write` | Write to running process |
| `shell_wait` | Wait for background process |
| `shell_kill` | Kill running process |

### Code Tools (2)

| Tool | Description |
|------|-------------|
| `python_execute` | Run Python (persistent kernel) |
| `javascript_execute` | Run JavaScript |

### Browser Tools (3)

| Tool | Description |
|------|-------------|
| `browser_info` | Get CDP URL, viewport |
| `browser_screenshot` | Capture screenshot |
| `browser_action` | Mouse/keyboard actions |

### MCP Tools (3)

| Tool | Description |
|------|-------------|
| `mcp_list_servers` | List MCP servers |
| `mcp_list_tools` | List server tools |
| `mcp_execute` | Execute MCP tool |

### Search Tools (2)

| Tool | Description |
|------|-------------|
| `grep` | Content search with regex |
| `glob` | Find files by name pattern |

### Utility Tools (2)

| Tool | Description |
|------|-------------|
| `workspace_info` | Session info |
| `workspace_health` | Health check |

## Multi-Agent Example

```python
# Each chat gets its own isolated workspace
session_alice = await SandboxSession.create(session_id="alice_chat")
session_bob = await SandboxSession.create(session_id="bob_chat")

tools_alice = {t.name: t for t in session_alice.get_tools()}
tools_bob = {t.name: t for t in session_bob.get_tools()}

# Both write to "data.txt" - but they're isolated!
await tools_alice["file_write"].ainvoke({"file": "data.txt", "content": "Alice's data"})
await tools_bob["file_write"].ainvoke({"file": "data.txt", "content": "Bob's data"})

# Each sees only their own
alice_data = await tools_alice["file_read"].ainvoke({"file": "data.txt"})
bob_data = await tools_bob["file_read"].ainvoke({"file": "data.txt"})
# alice_data = "Alice's data"
# bob_data = "Bob's data"
```

## Path Security

Paths are automatically validated and resolved relative to workspace:

```python
# ✅ Allowed - relative paths
await tools["file_write"].ainvoke({"file": "app.py", ...})
await tools["file_write"].ainvoke({"file": "src/utils.py", ...})

# ❌ Blocked - escape attempts
await tools["file_read"].ainvoke({"file": "../../../etc/passwd"})
# ERROR: Path attempts to escape workspace
```

## Direct Usage (No Isolation)

For simple cases without workspace isolation:

```python
from langchain_tools import create_sandbox_tools

tools = create_sandbox_tools(base_url="http://localhost:8080")
# Tools use absolute paths
```

## License

Apache 2.0
