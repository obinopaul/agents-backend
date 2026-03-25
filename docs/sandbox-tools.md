# Sandbox Tools Reference

> Complete guide to the 44+ tools available inside the E2B sandbox via MCP.

---

## Overview

Tools run inside the sandbox and are exposed via the **MCP Tool Server** on port 6060. They can be accessed:
1. **Via MCP Protocol** - Using MCPClient from outside the sandbox
2. **Direct Python Import** - From within the sandbox
3. **Via LangChain** - Using `get_langchain_tools()` adapter

---

## Tool Categories

| Category | Count | Description |
|----------|-------|-------------|
| Shell | 6 | Terminal/command execution |
| File System | 7 | File operations |
| Browser | 15 | Web browser automation |
| Web | 6 | Web search and scraping |
| Media | 2 | Image/video generation |
| Slide | 3 | Presentation creation |
| Dev | 4 | Development utilities |
| Productivity | 2 | Task management |
| Agent | 1 | User communication |

---

## Shell Tools

Tools for terminal/shell interactions using tmux sessions.

| Tool | Name | Description |
|------|------|-------------|
| `ShellInit` | `shell_init` | Initialize a new tmux session |
| `ShellRunCommand` | `shell_run_command` | Execute a shell command |
| `ShellView` | `shell_view` | View terminal output |
| `ShellStopCommand` | `shell_stop_command` | Stop a running command |
| `ShellList` | `shell_list` | List active sessions |
| `ShellWriteToProcessTool` | `shell_write_to_process` | Send input to a process |

### Example: Run a Command
```python
# Via MCP
result = await client.call_tool("shell_run_command", {
    "command": "npm install",
    "wait_for_completion": True
})
```

---

## File System Tools

Tools for reading, writing, and editing files.

| Tool | Name | Description |
|------|------|-------------|
| `FileReadTool` | `file_read` | Read file contents |
| `FileWriteTool` | `file_write` | Create/overwrite file |
| `FileEditTool` | `file_edit` | Edit file sections |
| `ApplyPatchTool` | `apply_patch` | Apply unified diff patch |
| `StrReplaceEditorTool` | `str_replace_editor` | String replacement edits |
| `ASTGrepTool` | `ast_grep` | AST-based code search |
| `GrepTool` | `grep` | Pattern-based search |

### Example: Read a File
```python
result = await client.call_tool("file_read", {
    "path": "/workspace/package.json"
})
```

### Example: Write a File
```python
result = await client.call_tool("file_write", {
    "path": "/workspace/index.js",
    "content": "console.log('Hello');"
})
```

---

## Browser Tools

Tools for web browser automation using Playwright.

| Tool | Name | Description |
|------|------|-------------|
| `BrowserNavigationTool` | `browser_navigate` | Navigate to URL |
| `BrowserViewTool` | `browser_view` | View current page |
| `BrowserClickTool` | `browser_click` | Click element |
| `BrowserEnterTextTool` | `browser_enter_text` | Type text |
| `BrowserPressKeyTool` | `browser_press_key` | Press keyboard key |
| `BrowserScrollDownTool` | `browser_scroll_down` | Scroll down |
| `BrowserScrollUpTool` | `browser_scroll_up` | Scroll up |
| `BrowserWaitTool` | `browser_wait` | Wait for element |
| `BrowserSwitchTabTool` | `browser_switch_tab` | Switch tab |
| `BrowserOpenNewTabTool` | `browser_open_new_tab` | Open new tab |
| `BrowserGetSelectOptionsTool` | `browser_get_select_options` | Get dropdown options |
| `BrowserSelectDropdownOptionTool` | `browser_select_dropdown` | Select dropdown option |
| `BrowserDragTool` | `browser_drag` | Drag element |
| `BrowserEnterMultipleTextsTool` | `browser_enter_multiple` | Fill multiple fields |
| `BrowserRestartTool` | `browser_restart` | Restart browser |

### Example: Navigate and Click
```python
await client.call_tool("browser_navigate", {"url": "https://example.com"})
await client.call_tool("browser_click", {"selector": "button.submit"})
```

---

## Web Tools

Tools for web search and content retrieval.

| Tool | Name | Description | Auth Required |
|------|------|-------------|---------------|
| `WebSearchTool` | `web_search` | Search the web | ✅ TAVILY_API_KEY |
| `WebVisitTool` | `web_visit` | Fetch webpage content | ✅ |
| `WebVisitCompressTool` | `web_visit_compress` | Compressed fetch | ✅ |
| `ImageSearchTool` | `image_search` | Search for images | ✅ |
| `WebBatchSearchTool` | `web_batch_search` | Batch searches | ✅ |
| `ReadRemoteImageTool` | `read_remote_image` | Read remote image | ❌ |

### Example: Web Search
```python
result = await client.call_tool("web_search", {
    "query": "FastAPI best practices"
})
```

---

## Media Tools

Tools for AI-powered media generation.

| Tool | Name | Description | Auth Required |
|------|------|-------------|---------------|
| `ImageGenerateTool` | `image_generate` | Generate images | ✅ API Key |
| `VideoGenerateTool` | `video_generate` | Generate videos | ✅ API Key |

### Example: Generate Image
```python
result = await client.call_tool("image_generate", {
    "prompt": "A futuristic city at sunset",
    "style": "photorealistic"
})
```

---

## Slide Tools

Tools for presentation creation.

| Tool | Name | Description |
|------|------|-------------|
| `SlideWriteTool` | `slide_write` | Create new slide |
| `SlideEditTool` | `slide_edit` | Edit existing slide |
| `SlideApplyPatchTool` | `slide_apply_patch` | Apply slide changes |

---

## Dev Tools

Development and project utilities.

| Tool | Name | Description |
|------|------|-------------|
| `FullStackInitTool` | `fullstack_init` | Initialize project template |
| `RegisterPort` | `register_port` | Expose sandbox port |
| `SaveCheckpointTool` | `save_checkpoint` | Save work checkpoint |
| `GetDatabaseConnection` | `get_database_connection` | Get DB connection |

---

## Productivity Tools

Task management utilities.

| Tool | Name | Description |
|------|------|-------------|
| `TodoReadTool` | `todo_read` | Read todo list |
| `TodoWriteTool` | `todo_write` | Write to todo list |

---

## Agent Tools

Communication with user.

| Tool | Name | Description |
|------|------|-------------|
| `MessageUserTool` | `message_user` | Send message to user |

---

## Connecting via MCP

### From Outside Sandbox (MCPClient)

```python
from backend.src.tool_server.mcp.client import MCPClient

async with MCPClient("https://6060-sandbox-id.e2b.app") as client:
    # Set credentials for authenticated tools
    await client.set_credential({
        "user_api_key": "your-api-key",
        "session_id": "session-123"
    })
    
    # List available tools
    tools = await client.list_tools()
    
    # Call a tool
    result = await client.call_tool("shell_run_command", {
        "command": "ls -la"
    })
```

### Using LangChain Integration

```python
from backend.src.tool_server.tools.manager import get_langchain_tools
from langgraph.prebuilt import create_react_agent

# Get all tools as LangChain tools
tools = get_langchain_tools("/workspace", {"TAVILY_API_KEY": "..."})

# Create agent
agent = create_react_agent(llm, tools)

# Run
result = await agent.ainvoke({"messages": [...]})
```

---

## Tool Base Class

All tools extend `BaseTool`:

```python
from backend.src.tool_server.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    input_schema = {"type": "object", "properties": {...}}
    read_only = False
    display_name = "My Tool"
    
    async def execute(self, tool_input: dict) -> ToolResult:
        # Implementation
        return ToolResult(llm_content="Success!")
```

---

## Authentication

Some tools require API credentials:

| Credential | Tools | How to Set |
|------------|-------|------------|
| `TAVILY_API_KEY` | Web search/visit | Environment or credential |
| `OPENAI_API_KEY` | Image/video gen | MCP Settings → Codex |
| `user_api_key` | All auth tools | POST /credential |

Credentials are auto-written to sandbox on creation if configured in MCP Settings.

---

## Related Documentation

- [MCP Configuration](../mcp-configuration.md) - How MCP connects tools
- [API Endpoints](./api-endpoints.md) - Sandbox API reference
- [Frontend Connect](../frontend-connect/README.md) - UI integration
