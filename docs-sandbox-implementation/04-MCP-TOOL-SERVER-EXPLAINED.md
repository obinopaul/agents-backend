# MCP Tool Server (ii_tool) - Deep Dive

This document explains how the MCP (Model Context Protocol) server works inside the sandbox.

---

## What is MCP?

**MCP (Model Context Protocol)** is a protocol created by Anthropic for AI agents to interact with tools. Think of it as a standardized API for AI tool calling.

```
Traditional Approach:
Agent → Custom HTTP API → Your Tools

MCP Approach:
Agent → MCP Protocol → MCP Server → Tools
       (Standardized)    (Your implementation)
```

### Why MCP?

1. **Standardized** - Same protocol works with Claude, GPT, any agent
2. **Discovery** - Agent can ask "what tools do you have?"
3. **Streaming** - Support for long-running operations
4. **Error Handling** - Built-in error format

---

## How ii_tool Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        E2B Sandbox                                   │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    ii_tool MCP Server                          │  │
│  │                    (Port 6060)                                 │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              Built-in Sandbox Tools                      │  │  │
│  │  │  ├── read_file      - Read file contents                │  │  │
│  │  │  ├── write_file     - Write to file                     │  │  │
│  │  │  ├── list_directory - List files                        │  │  │
│  │  │  ├── run_command    - Execute shell command             │  │  │
│  │  │  ├── search_files   - Find files by pattern             │  │  │
│  │  │  └── ...more                                            │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              Browser Tools (Playwright)                  │  │  │
│  │  │  ├── browser_navigate   - Go to URL                     │  │  │
│  │  │  ├── browser_click      - Click element                 │  │  │
│  │  │  ├── browser_type       - Type text                     │  │  │
│  │  │  ├── browser_screenshot - Take screenshot               │  │  │
│  │  │  └── ...more                                            │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              User MCP Servers (Proxied)                  │  │  │
│  │  │  ├── Claude Code MCP                                    │  │  │
│  │  │  ├── Codex MCP                                          │  │  │
│  │  │  └── Custom user MCPs                                   │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              ▲                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                          MCP Protocol
                               │
                    ┌──────────▼──────────┐
                    │   Your LangChain    │
                    │       Agent         │
                    └─────────────────────┘
```

---

## The MCP Server Code

### Main Server Setup (server.py)

```python
# src/ii_tool/mcp/server.py

import os
import json
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from starlette.responses import JSONResponse
from ii_tool.tools.manager import get_sandbox_tools
from ii_tool.mcp_integrations.manager import get_mcp_integrations

async def create_mcp(workspace_dir: str, custom_mcp_config: dict = None):
    """Create the MCP server with all tools."""
    
    # Create main FastMCP server
    main_server = FastMCP()
    
    # ==================== CUSTOM ENDPOINTS ====================
    
    @main_server.custom_route("/health", methods=["GET"])
    async def health(request):
        """Health check endpoint."""
        return JSONResponse({"status": "ok"})
    
    @main_server.custom_route("/credential", methods=["POST"])
    async def set_credential(request):
        """Set credentials for authenticated tool calls."""
        credential = await request.json()
        set_current_credential(credential)
        return JSONResponse({"status": "success"})
    
    @main_server.custom_route("/tool-server-url", methods=["POST"])
    async def set_tool_server_url(request):
        """Set the external tool server URL (for callbacks)."""
        data = await request.json()
        set_tool_server_url_singleton(data.get("tool_server_url"))
        
        # Now register all sandbox tools
        tools = get_sandbox_tools(
            workspace_path=workspace_dir,
            credential=get_current_credential(),
        )
        
        for tool in tools:
            # Register each tool with FastMCP
            main_server.tool(
                tool.execute_mcp_wrapper,
                name=tool.name,
                description=tool.description,
            )
            print(f"Registered tool: {tool.name}")
        
        return JSONResponse({"status": "success"})
    
    @main_server.custom_route("/custom-mcp", methods=["POST"])
    async def add_mcp_config(request):
        """Add a custom MCP server (proxy to it)."""
        mcp_config = await request.json()
        proxy = FastMCP.as_proxy(ProxyClient(mcp_config))
        main_server.mount(proxy, prefix="mcp")
        return JSONResponse({"status": "success"})
    
    @main_server.custom_route("/register-codex", methods=["POST"])
    async def register_codex(request):
        """Start and register the Codex SSE server."""
        # ... starts sse-http-server subprocess
        return JSONResponse({"status": "success", "url": codex_url})
    
    # ==================== BUILT-IN MCP INTEGRATIONS ====================
    
    # Load pre-configured MCP integrations (e.g., playwright)
    mcp_integrations = get_mcp_integrations(workspace_dir)
    for integration in mcp_integrations:
        proxy = FastMCP.as_proxy(ProxyClient(integration.config))
        for tool_name in integration.selected_tool_names:
            mirrored_tool = await proxy.get_tool(tool_name)
            main_server.add_tool(mirrored_tool.copy())
    
    # ==================== USER CUSTOM MCPS ====================
    
    if custom_mcp_config:
        proxy = FastMCP.as_proxy(ProxyClient(custom_mcp_config))
        main_server.mount(proxy, prefix="mcp")
    
    return main_server


async def main():
    workspace_dir = os.getenv("WORKSPACE_DIR", "/workspace")
    mcp = await create_mcp(workspace_dir)
    await mcp.run_async(transport="http", host="0.0.0.0", port=6060)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Tool Manager (tools/manager.py)

```python
# src/ii_tool/tools/manager.py

from typing import List
from ii_tool.tools.base import BaseTool
from ii_tool.tools.file import ReadFileTool, WriteFileTool, ListDirectoryTool
from ii_tool.tools.shell import RunCommandTool
from ii_tool.tools.search import SearchFilesTool
from ii_tool.tools.browser import BrowserTools


def get_sandbox_tools(workspace_path: str, credential: dict) -> List[BaseTool]:
    """Get all available sandbox tools."""
    
    tools = []
    
    # File operation tools
    tools.append(ReadFileTool(workspace_path))
    tools.append(WriteFileTool(workspace_path))
    tools.append(ListDirectoryTool(workspace_path))
    
    # Shell tools
    tools.append(RunCommandTool(workspace_path))
    
    # Search tools
    tools.append(SearchFilesTool(workspace_path))
    
    # Browser tools (Playwright-based)
    browser_tools = BrowserTools(workspace_path)
    tools.extend(browser_tools.get_all_tools())
    
    return tools
```

### Example Tool Implementation (tools/file.py)

```python
# src/ii_tool/tools/file.py

from ii_tool.tools.base import BaseTool
from pydantic import BaseModel, Field
from typing import Optional


class ReadFileInput(BaseModel):
    """Input schema for read_file tool."""
    path: str = Field(..., description="Path to the file to read")
    encoding: str = Field(default="utf-8", description="File encoding")


class ReadFileTool(BaseTool):
    """Tool to read file contents."""
    
    name = "read_file"
    description = "Read the contents of a file at the specified path"
    input_schema = ReadFileInput.model_json_schema()
    
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
    
    async def execute(self, path: str, encoding: str = "utf-8") -> str:
        """Execute the tool."""
        import os
        
        # Resolve path relative to workspace
        full_path = os.path.join(self.workspace_path, path)
        
        # Security check
        if not full_path.startswith(self.workspace_path):
            raise ValueError("Path must be within workspace")
        
        with open(full_path, "r", encoding=encoding) as f:
            return f.read()
    
    async def execute_mcp_wrapper(self, **kwargs) -> str:
        """Wrapper for MCP protocol."""
        return await self.execute(**kwargs)


class WriteFileInput(BaseModel):
    """Input schema for write_file tool."""
    path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write")


class WriteFileTool(BaseTool):
    """Tool to write file contents."""
    
    name = "write_file"
    description = "Write content to a file at the specified path"
    input_schema = WriteFileInput.model_json_schema()
    
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
    
    async def execute(self, path: str, content: str) -> str:
        """Execute the tool."""
        import os
        
        full_path = os.path.join(self.workspace_path, path)
        
        # Create directories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w") as f:
            f.write(content)
        
        return f"Successfully wrote {len(content)} bytes to {path}"
    
    async def execute_mcp_wrapper(self, **kwargs) -> str:
        return await self.execute(**kwargs)
```

---

## MCP Protocol Format

### Tool Discovery

```http
GET /mcp/tools
```

Response:
```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read the contents of a file",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "Path to file"},
          "encoding": {"type": "string", "default": "utf-8"}
        },
        "required": ["path"]
      }
    },
    {
      "name": "write_file",
      "description": "Write content to a file",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "content": {"type": "string"}
        },
        "required": ["path", "content"]
      }
    }
  ]
}
```

### Tool Execution

```http
POST /mcp/tools/call
Content-Type: application/json

{
  "name": "read_file",
  "arguments": {
    "path": "src/main.py"
  }
}
```

Response:
```json
{
  "content": [
    {
      "type": "text",
      "text": "import os\nprint('hello')\n"
    }
  ]
}
```

---

## Startup Process

When the sandbox starts, this is what happens:

### 1. start-services.sh runs

```bash
#!/bin/bash

# Start MCP server in background via tmux
tmux new-session -d -s mcp-server \
  'WORKSPACE_DIR=/workspace xvfb-run python -m ii_tool.mcp.server'

# xvfb-run is needed for Playwright (headless browser)
```

### 2. MCP Server starts but waits

The server is running, but tools aren't registered yet.

### 3. Agent connects and configures

```python
# From your agent (via sandbox client)

# Step 1: Set credentials
await client.post("/mcp/credential", json={
    "session_id": "abc123",
    "user_api_key": "xxx"
})

# Step 2: Set tool server URL (triggers tool registration)
await client.post("/mcp/tool-server-url", json={
    "tool_server_url": "https://your-backend.com/tools"
})

# Now all tools are registered and ready
```

### 4. Agent uses tools

```python
# List available tools
response = await client.get("/mcp/tools")
tools = response.json()["tools"]

# Call a tool
result = await client.post("/mcp/tools/call", json={
    "name": "read_file",
    "arguments": {"path": "app.py"}
})
```

---

## Adding Custom MCP Servers (Claude Code, etc.)

The MCP server can proxy to OTHER MCP servers:

```python
# Register Claude Code MCP
await client.post("/mcp/custom-mcp", json={
    "mcpServers": {
        "claude-code": {
            "command": "npx",
            "args": ["-y", "@steipete/claude-code-mcp@latest"]
        }
    }
})

# Now you can call Claude Code tools
result = await client.post("/mcp/tools/call", json={
    "name": "mcp_claude-code_execute",  # Prefixed with mcp_
    "arguments": {
        "prompt": "Fix the bug in app.py"
    }
})
```

---

## Tool Categories in ii_tool

### File Operations
- `read_file` - Read file content
- `write_file` - Write/create file
- `list_directory` - List files in directory
- `create_directory` - Create directory
- `delete_file` - Delete file

### Shell Operations
- `run_command` - Execute shell command (bash)
- `run_background` - Run command in background

### Search Operations
- `search_files` - Search by filename pattern
- `search_content` - Search file contents (ripgrep)

### Browser Operations (Playwright)
- `browser_navigate` - Go to URL
- `browser_click` - Click element by selector
- `browser_type` - Type text into input
- `browser_screenshot` - Take screenshot
- `browser_scroll` - Scroll page
- `browser_evaluate` - Execute JavaScript
- ... and many more

### Development Tools
- `register_port` - Expose a development server port
- `git_*` - Git operations
- `npm_*` - NPM operations

---

## Building Your Own MCP Server

If you want to simplify, here's a minimal MCP server:

```python
# minimal_mcp_server.py

from fastmcp import FastMCP
import os

app = FastMCP("My Sandbox Tools")

WORKSPACE = os.getenv("WORKSPACE_DIR", "/workspace")


@app.tool()
async def read_file(path: str) -> str:
    """Read a file from the workspace."""
    full_path = os.path.join(WORKSPACE, path)
    with open(full_path, "r") as f:
        return f.read()


@app.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    full_path = os.path.join(WORKSPACE, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"


@app.tool()
async def run_command(command: str) -> str:
    """Run a shell command."""
    import subprocess
    result = subprocess.run(
        command, 
        shell=True, 
        capture_output=True, 
        text=True,
        cwd=WORKSPACE
    )
    return result.stdout + result.stderr


@app.tool()
async def list_directory(path: str = ".") -> list[str]:
    """List files in a directory."""
    full_path = os.path.join(WORKSPACE, path)
    return os.listdir(full_path)


if __name__ == "__main__":
    app.run(transport="http", host="0.0.0.0", port=6060)
```

Run it with:
```bash
pip install fastmcp
python minimal_mcp_server.py
```

---

## Using MCP from LangChain

LangChain has MCP support:

```python
from langchain_core.tools import StructuredTool
import httpx

class MCPClient:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
    
    async def call_tool(self, name: str, arguments: dict) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/mcp/tools/call",
                json={"name": name, "arguments": arguments}
            )
            return response.json()["content"][0]["text"]
    
    async def list_tools(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/mcp/tools")
            return response.json()["tools"]


def mcp_tools_to_langchain(mcp_client: MCPClient) -> list[StructuredTool]:
    """Convert MCP tools to LangChain tools."""
    tools = []
    
    mcp_tools = await mcp_client.list_tools()
    
    for mcp_tool in mcp_tools:
        async def call_mcp(name=mcp_tool["name"], **kwargs):
            return await mcp_client.call_tool(name, kwargs)
        
        tool = StructuredTool.from_function(
            coroutine=call_mcp,
            name=mcp_tool["name"],
            description=mcp_tool["description"],
        )
        tools.append(tool)
    
    return tools
```
