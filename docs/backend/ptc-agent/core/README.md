# PTC-Agent Core Layer

The `core/` directory contains the infrastructure components that power the PTC-Agent framework.

---

## Directory Structure

```
core/
├── __init__.py              # Package exports
├── sandbox.py               # PTCSandbox - Daytona wrapper (~76KB)
├── mcp_registry.py          # MCPRegistry - MCP server management (~25KB)
├── session.py               # SessionManager - Session lifecycle (~7KB)
├── security.py              # Code validation (~10KB)
└── tool_generator.py        # Dynamic tool generation (~30KB)
```

---

## Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CORE LAYER                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────────┐
    │                             │                                 │
    ▼                             ▼                                 ▼
┌─────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  PTCSandbox │          │   MCPRegistry   │          │ SessionManager  │
│ ─────────── │          │ ─────────────── │          │ ─────────────── │
│ • Daytona   │          │ • MCP server    │          │ • Session       │
│   API       │          │   discovery     │          │   lifecycle     │
│ • Code exec │          │ • Tool schemas  │          │ • Resource      │
│ • File ops  │          │ • Dynamic tools │          │   cleanup       │
└─────────────┘          └─────────────────┘          └─────────────────┘
        │                         │                           │
        │                         ▼                           │
        │                ┌─────────────────┐                  │
        │                │  ToolGenerator  │                  │
        │                │ ─────────────── │                  │
        │                │ • MCP → Python  │                  │
        │                │ • Schema convert│                  │
        │                └─────────────────┘                  │
        │                         │                           │
        └─────────────────────────┼───────────────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    Security     │
                         │ ─────────────── │
                         │ • Code validate │
                         │ • Pattern check │
                         │ • Import filter │
                         └─────────────────┘
```

---

## PTCSandbox (sandbox.py)

The largest component (~76KB), wrapping the Daytona API for secure code execution.

### Key Features

- **Sandbox Lifecycle**: Create, start, stop, destroy sandboxes
- **Code Execution**: Run Python code in isolated environment
- **File Operations**: Read, write, list files in sandbox
- **Package Management**: Install dependencies
- **State Persistence**: Save/restore workspace state

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PTCSandbox                                   │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├── create_sandbox()      → Create new Daytona instance
        ├── execute_code()        → Run Python code
        ├── execute_command()     → Run shell commands
        ├── read_file()           → Read file contents
        ├── write_file()          → Write file contents
        ├── list_files()          → List directory contents
        ├── install_packages()    → pip install packages
        ├── export_workspace()    → Save workspace state
        └── cleanup()             → Destroy sandbox
```

### Usage

```python
from ptc_agent.core import PTCSandbox

# Create sandbox
sandbox = PTCSandbox(config)
await sandbox.initialize()

# Execute code
result = await sandbox.execute_code("""
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
print(df.describe())
""")

# File operations
await sandbox.write_file("/workspace/data.csv", csv_content)
data = await sandbox.read_file("/workspace/data.csv")

# Cleanup
await sandbox.cleanup()
```

---

## MCPRegistry (mcp_registry.py)

Manages Model Context Protocol servers for extensible tool capabilities.

### Key Features

- **Server Discovery**: Find and connect to MCP servers
- **Tool Schema**: Parse MCP tool definitions
- **Dynamic Registration**: Add/remove servers at runtime
- **Health Checks**: Monitor server status

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCPRegistry                                  │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├── register_server()     → Add MCP server
        ├── discover_tools()      → Get available tools from server
        ├── get_tool()            → Get specific tool by name
        ├── call_tool()           → Execute tool on server
        └── list_servers()        → List registered servers
        
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │     MCP Servers         │
                    ├─────────────────────────┤
                    │ ┌─────────┐ ┌─────────┐ │
                    │ │yfinance │ │ tavily  │ │
                    │ │ server  │ │ server  │ │
                    │ └─────────┘ └─────────┘ │
                    └─────────────────────────┘
```

### Usage

```python
from ptc_agent.core import MCPRegistry
from ptc_agent.config import MCPServerConfig

registry = MCPRegistry()

# Register server
await registry.register_server(MCPServerConfig(
    name="yfinance",
    command="uv",
    args=["run", "python", "yfinance_server.py"],
))

# Discover tools
tools = await registry.discover_tools("yfinance")
# [{"name": "get_stock_price", "schema": {...}}, ...]

# Call tool
result = await registry.call_tool("yfinance", "get_stock_price", {"symbol": "AAPL"})
```

---

## SessionManager (session.py)

Manages agent session lifecycle including sandbox and MCP initialization.

### Key Features

- **Session Creation**: Create new agent sessions
- **Resource Management**: Initialize sandbox + MCP registry
- **Cleanup**: Proper resource disposal
- **Session Lookup**: Get existing sessions by ID

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SessionManager                                 │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├── get_session()         → Get or create session
        ├── create_session()      → Create new session
        └── destroy_session()     → Clean up session
        
                    ┌─────────────────────────┐
                    │        Session          │
                    ├─────────────────────────┤
                    │ • session_id            │
                    │ • sandbox: PTCSandbox   │
                    │ • mcp_registry: MCPReg  │
                    │ • config: CoreConfig    │
                    │ • created_at: datetime  │
                    └─────────────────────────┘
```

### Usage

```python
from ptc_agent.core import SessionManager

# Get or create session
session = SessionManager.get_session("user-123", config)
await session.initialize()

# Use session resources
sandbox = session.sandbox
mcp_registry = session.mcp_registry

# Cleanup when done
await session.cleanup()
```

---

## Security (security.py)

Validates code before execution to prevent malicious operations.

### Validation Checks

| Check | Description |
|-------|-------------|
| **Code Length** | Enforce maximum code size |
| **Syntax Validation** | Parse AST to check validity |
| **Forbidden Patterns** | Block dangerous operations |
| **Import Filtering** | Restrict module imports |
| **Network Restrictions** | Limit external connections |

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Security Validator                                │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│   Code Input          │
│   ```python           │
│   import os           │
│   os.system("rm -rf")│
│   ```                 │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 1. Length Check       │  ← Max 10,000 characters
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 2. AST Parsing        │  ← Syntax validation
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 3. Pattern Matching   │  ← Block: eval, exec, __import__
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 4. Import Filtering   │  ← Block: subprocess, socket
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ PASS or REJECT        │
└───────────────────────┘
```

### Usage

```python
from ptc_agent.core.security import validate_code

try:
    validate_code(user_code, max_length=10000)
    # Code is safe to execute
except SecurityError as e:
    # Code failed validation
    print(f"Blocked: {e}")
```

---

## ToolGenerator (tool_generator.py)

Converts MCP tool schemas to callable Python functions.

### Key Features

- **Schema Parsing**: Read MCP tool specifications
- **Function Generation**: Create async Python functions
- **Type Mapping**: Convert JSON Schema to Python types
- **Documentation**: Generate docstrings from schema

### Flow

```
MCP Tool Schema (JSON)
        │
        ▼
┌───────────────────────────────────────┐
│ {                                     │
│   "name": "get_stock_price",          │
│   "description": "Get stock price",   │
│   "inputSchema": {                    │
│     "type": "object",                 │
│     "properties": {                   │
│       "symbol": {"type": "string"}    │
│     }                                 │
│   }                                   │
│ }                                     │
└───────────────────────┬───────────────┘
                        │
                        ▼
              ToolGenerator
                        │
                        ▼
┌───────────────────────────────────────┐
│ async def get_stock_price(            │
│     symbol: str                       │
│ ) -> dict:                            │
│     """Get stock price"""             │
│     return await mcp.call(            │
│         "get_stock_price",            │
│         {"symbol": symbol}            │
│     )                                 │
└───────────────────────────────────────┘
```

---

## Related Documentation

- [Agent Layer](../agent/README.md) - How agents use core components
- [Configuration](../config/README.md) - Core configuration options

---

*Last Updated: December 2024*
