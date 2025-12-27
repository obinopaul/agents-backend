# Tool Server API Contract

## Overview

The `tool_server` is a collection of **40+ AI agent tools** that run inside E2B sandboxes via the **Model Context Protocol (MCP)**. It enables AI agents to execute code, browse the web, edit files, generate media, and more.

---

## Architecture

```mermaid
graph TB
    A[FastAPI Backend] --> B[Sandbox Service]
    B --> C[E2B Sandbox]
    C --> D[MCP Tool Server :6060]
    D --> E[40+ Tools]
    E --> E1[Shell]
    E --> E2[Files]
    E --> E3[Browser]
    E --> E4[Web]
    E --> E5[Media]
```

---

## Available Tools (40+)

### Shell Tools (`tools/shell/`)

| Tool | Description |
| ---- | ----------- |
| `shell_init` | Initialize terminal session |
| `shell_run_command` | Execute command |
| `shell_view` | View terminal output |
| `shell_stop_command` | Stop running command |
| `shell_list` | List active terminals |
| `shell_write_to_process` | Send input to process |

### File System Tools (`tools/file_system/`)

| Tool | Description |
| ---- | ----------- |
| `file_read` | Read file content |
| `file_write` | Write file content |
| `file_edit` | Edit file sections |
| `apply_patch` | Apply diff patch |
| `str_replace_editor` | Find/replace editing |
| `ast_grep` | AST-based code search |
| `grep` | Text search |

### Browser Tools (`tools/browser/`)

| Tool | Description |
| ---- | ----------- |
| `browser_click` | Click element |
| `browser_view` | View page/screenshot |
| `browser_navigate` | Navigate to URL |
| `browser_enter_text` | Type text |
| `browser_scroll_*` | Scroll up/down |
| `browser_switch_tab` | Switch tabs |
| +9 more | Additional browser tools |

### Web Tools (`tools/web/`)

| Tool | Description |
| ---- | ----------- |
| `web_search` | Search the web |
| `web_visit` | Visit and extract page |
| `web_visit_compress` | Compressed extraction |
| `image_search` | Search for images |
| `read_remote_image` | Read remote image |
| `web_batch_search` | Batch search |

### Media Tools (`tools/media/`)

| Tool | Description |
| ---- | ----------- |
| `image_generate` | Generate images (Vertex AI) |
| `video_generate` | Generate videos (Vertex AI) |

---

## LangChain Integration

The tool server provides a centralized registry in `backend/src/tool_server/tools/langchain_tools.py` to easily load tools for LangChain agents.

### Tool Registry

Import tools using category-specific functions or the master loader:

```python
from backend.src.tool_server.tools.langchain_tools import (
    get_langchain_browser_tools,    # 15 browser tools
    get_langchain_shell_tools,      # 6 shell tools
    get_langchain_file_tools,       # 7+ file tools
    get_langchain_web_tools,        # 6 web tools
    get_langchain_media_tools,      # 2 media tools
    get_langchain_agent_tools,      # 1 communication tool
    get_all_langchain_tools,        # Master loader
)
```

### Tool Categories

| Category | Function | Count | Tools Included |
|----------|----------|-------|----------------|
| **Browser** | `get_langchain_browser_tools(browser)` | 15 | `click`, `navigate`, `enter_text`, `scroll`, `tab`, `wait`, etc. |
| **Shell** | `get_langchain_shell_tools(sandbox)` | 6 | `run_command`, `view`, `stop`, `list`, etc. |
| **File** | `get_langchain_file_tools(sandbox)` | 7 | `read`, `write`, `edit`, `patch`, `grep`, `ast_grep`, etc. |
| **Web** | `get_langchain_web_tools(creds)` | 6 | `search`, `visit`, `compress`, `image_search`, `read_remote_image` |
| **Media** | `get_langchain_media_tools(creds)` | 2 | `image_generate`, `video_generate` |
| **Agent** | `get_langchain_agent_tools()` | 1 | `message_user` (Communicate with UI/User) |

### usage Example

```python
from langgraph.prebuilt import create_react_agent
from backend.src.llms.llm import get_llm
from backend.src.tool_server.tools.langchain_tools import get_all_langchain_tools
from backend.src.tool_server.browser.browser import Browser

async def main():
    # 1. Initialize resources
    start = time.time()
    browser = Browser()
    llm = get_llm()
    
    # 2. Load all tools
    tools = get_all_langchain_tools(
        workspace_path="/workspace",
        credential={"session_id": "sess_1", "user_api_key": "sk-..."},
        sandbox=sandbox_instance,  # Requires active sandbox connection
        browser=browser,
        include_web=True,
    )
    
    # 3. Create Agent
    agent = create_react_agent(llm, tools)
    
    # 4. Run Task
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": "Search for 'LangChain' and summarize the top result."}]
    })

    print(result)
```

---

## Test Files

```bash
cd backend/tests/live
```

| File | Tests | Status |
| ---- | ----- | ------ |
| `test_sandbox_comprehensive.py` | 10 sandbox API tests | ✅ 10/10 |
| `test_mcp_tool_server.py` | 6 MCP tests | ✅ 5/6 |
| `test_all_tools.py` | 25 tool tests | ✅ 24/25 |
| `run_langchain_agent.py` | LangChain agent | ✅ Working |
| `run_mcp_agent.py` | Sandbox agent | ✅ Working |
| `interactive_agent_test.py` | Interactive CLI Test | ✅ Implemented |

### Run Tests

```bash
cd backend/tests/live

# Comprehensive tool test (25 tests)
python test_all_tools.py

# LangChain agent with sandbox tools
python run_langchain_agent.py

# Sandbox agent (simple)
python run_mcp_agent.py
```

---

## Configuration

### Environment Variables

```bash
# backend/.env

# LLM Provider (for get_llm)
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini

# For web tools
TAVILY_API_KEY=your_tavily_key
SERPER_API_KEY=your_serper_key

# For image/video generation
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

---

## Location

```
backend/src/tool_server/
├── browser/       # Playwright browser automation
├── core/          # Workspace management
├── integrations/  # External service clients
├── mcp/           # MCP server entry point
└── tools/         # 40+ agent tools
    ├── shell/
    ├── file_system/
    ├── browser/
    ├── web/
    ├── media/
    └── slide_system/
```
