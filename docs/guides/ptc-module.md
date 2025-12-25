# PTC Module - Programmatic Tool Calling

The **PTC (Programmatic Tool Calling)** module provides a production-ready implementation where agents write Python code to interact with tools instead of using JSON-based tool calls.

## Why PTC?

| Traditional Approach | PTC Approach |
|---------------------|--------------|
| LLM → JSON tool call → Result → LLM | LLM → Write Python → Execute in sandbox → Summary |
| Intermediate data fills context | Data stays in sandbox |
| Limited to single operations | Full programming power (loops, conditionals) |
| Tool results go back to LLM | Only summaries returned |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PTC Module (backend/src/ptc/)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐          │
│   │   PTCSandbox    │   │   MCPRegistry   │   │  ToolGenerator  │          │
│   │   (Daytona)     │   │ Tool Discovery  │   │ Python codegen  │          │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘          │
│            │                    │                    │                      │
│            └────────────────────┼────────────────────┘                      │
│                                 ▼                                            │
│                    ┌─────────────────────────┐                              │
│                    │   Session Manager       │                              │
│                    │   (Persistent State)    │                              │
│                    └─────────────────────────┘                              │
│                                 │                                            │
│                    ┌────────────┴────────────┐                              │
│                    ▼                         ▼                              │
│          ┌─────────────────┐       ┌─────────────────┐                     │
│          │   Interactive   │       │   Web Preview   │                     │
│          │      CLI        │       │     Links       │                     │
│          └─────────────────┘       └─────────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Structure

| Component | Description | Size | Code Path |
|-----------|-------------|------|-----------|
| **PTCSandbox** | Daytona cloud sandbox management | **76KB** | [`ptc/sandbox.py`](../../backend/src/ptc/sandbox.py) |
| **MCPRegistry** | MCP server connections, tool discovery | **25KB** | [`ptc/mcp_registry.py`](../../backend/src/ptc/mcp_registry.py) |
| **ToolGenerator** | Generate Python functions from MCP tools | **30KB** | [`ptc/tool_generator.py`](../../backend/src/ptc/tool_generator.py) |
| **SessionManager** | Session lifecycle, persistence | 6.7KB | [`ptc/session.py`](../../backend/src/ptc/session.py) |
| **Security** | Code validation, sandboxing | 10KB | [`ptc/security.py`](../../backend/src/ptc/security.py) |

---

## Quick Start

```bash
# Start the interactive agent
cd backend
python -m src.ptc.examples.langgraph_robust_agent
```

### Example Session

```
🔧 Initializing...
   ✓ Sandbox ID: sandbox-abc123
   ✓ Web Preview (port 8000): https://sandbox-abc123.daytona.io
   ✓ Tools: Bash, read_file, write_file, edit_file, glob, grep

You > Create a Flask API with /hello endpoint

🤖 Agent (5 tool calls):
   Creating app.py...
   
   ```python
   from flask import Flask
   app = Flask(__name__)
   
   @app.route('/hello')
   def hello():
       return {'message': 'Hello, World!'}
   
   if __name__ == '__main__':
       app.run(port=5000)
   ```
   
   Running server...
   ✓ Server running on port 5000

You > status
📊 Sandbox Status
   Preview (port 5000): https://sandbox-abc123.daytona.io:5000

You > exit
👋 Goodbye! Your sandbox is preserved.
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `help` | Show available commands |
| `status` | Show sandbox ID and preview URLs |
| `files` | List files in sandbox |
| `clear` | Clear screen |
| `exit` | Quit (sandbox persists) |

---

## Available Tools

### Core Tools

| Tool | Description |
|------|-------------|
| `execute_code` | Run Python code with MCP tools |
| `Bash` | Shell commands (git, npm, docker) |
| `read_file` | Read file with line numbers |
| `write_file` | Create/overwrite files |
| `edit_file` | Edit existing files |
| `glob` | Find files by pattern |
| `grep` | Search file contents |

### MCP Tools (Auto-discovered)

Tools from connected MCP servers are automatically converted to Python functions:

```python
# MCP tool definition
{
    "name": "search_web",
    "description": "Search the web",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        }
    }
}

# Generated Python function
def search_web(query: str) -> dict:
    """Search the web"""
    return _mcp_call("search_web", {"query": query})
```

---

## How PTC Works

### 1. Tool Discovery
```python
# Connect to MCP servers and discover tools
registry = MCPRegistry()
await registry.connect("filesystem", transport="stdio", command="npx", args=["@modelcontextprotocol/server-filesystem", "/workspace"])
tools = await registry.list_tools()
```

### 2. Code Generation
```python
# Generate Python functions from MCP tools
generator = ToolGenerator()
code = generator.generate_functions(tools)
# Creates: def read_file(path: str) -> str: ...
```

### 3. Sandbox Execution
```python
# Execute generated code in sandbox
sandbox = PTCSandbox()
await sandbox.create()
result = await sandbox.execute("""
import pandas as pd
df = pd.read_csv(read_file("data.csv"))
print(df.describe())
""")
```

### 4. Result Summarization
Instead of returning raw tool results to the LLM, only a summary is returned:
```python
# Instead of: {"content": "... 10MB of data ..."}
# Returns: "Successfully loaded data.csv with 10,000 rows and 15 columns"
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DAYTONA_API_KEY` | Daytona API key for sandbox |
| `DAYTONA_SERVER_URL` | Daytona server URL |
| `DAYTONA_TARGET` | Default sandbox target |

### MCP Server Configuration

```python
mcp_settings = {
    "servers": {
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@modelcontextprotocol/server-filesystem", "/workspace"]
        },
        "browser": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@anthropic/mcp-server-puppeteer"]
        }
    }
}
```

---

## Sandbox Lifecycle

```python
# Create sandbox
sandbox = PTCSandbox()
sandbox_id = await sandbox.create(image="python:3.11")

# Execute code
result = await sandbox.execute("print('Hello!')")

# Get preview URL
url = await sandbox.get_preview_url(port=8000)

# Sandbox persists after exit
# Resume later with:
sandbox = PTCSandbox(sandbox_id="sandbox-abc123")
await sandbox.connect()
```

---

## Security Features

1. **Code Validation**: Syntax checking before execution
2. **Import Restrictions**: Configurable allowed imports
3. **Resource Limits**: CPU/memory/disk limits
4. **Network Isolation**: Configurable network access
5. **File Access Control**: Workspace restrictions

```python
security = PTCSecurity(
    allowed_imports=["pandas", "numpy", "requests"],
    max_execution_time=60,
    max_memory_mb=512,
    allow_network=True
)
```

---

## Related Documentation

- [Sandbox Guide](sandbox-guide.md) - Sandbox architecture details
- [Agentic AI System](agentic-ai.md) - Agent orchestration
- [FastAPI Backend](fastapi-backend.md) - API endpoints
- [Main README](../../README.md) - Project overview
- [PTC README](../../backend/src/ptc/README.md) - Module-specific docs
