# Tool Server API Contracts

> **Base URL:** `http://localhost:6060` (default)
>
> The Tool Server is a separate FastMCP-based service that runs in the sandbox
> and provides tools for file operations, shell commands, browser automation,
> and more via the Model Context Protocol (MCP).

---

## Overview

The Tool Server is started inside each sandbox to provide AI agents with access to:
- File system operations
- Shell command execution
- Browser automation
- Web scraping and search
- Media processing
- Slide/presentation creation
- Developer tools

**Architecture:**
```
┌─────────────────────────┐     ┌──────────────────────────┐
│   FastAPI Backend       │────►│  Tool Server (MCP)       │
│   (port 8000)           │     │  (port 6060)             │
│                         │     │                          │
│  Uses /agent/mcp/       │     │  Provides 50+ tools      │
│  to connect             │     │  via MCP protocol        │
└─────────────────────────┘     └──────────────────────────┘
```

---

## Table of Contents

1. [HTTP Routes](#1-http-routes)
2. [Tool Categories](#2-tool-categories)
3. [File System Tools](#3-file-system-tools)
4. [Shell Tools](#4-shell-tools)
5. [Browser Tools](#5-browser-tools)
6. [Web Tools](#6-web-tools)
7. [Dev Tools](#7-dev-tools)
8. [Media Tools](#8-media-tools)
9. [Slide Tools](#9-slide-tools)
10. [Configuration](#10-configuration)

---

## 1. HTTP Routes

The Tool Server exposes these HTTP endpoints:

### GET `/health`

Health check endpoint.

**Response:**
```json
{"status": "ok"}
```

---

### POST `/credential`

Set authentication credentials for the tool server.

**Request:**
```json
{
  "user_api_key": "user_api_key_123",
  "session_id": "session_abc123"
}
```

**Response:**
```json
{"status": "success"}
```

---

### POST `/tool-server-url`

Register the tool server URL and initialize tools.

**Prerequisites:** `/credential` must be called first.

**Request:**
```json
{
  "tool_server_url": "http://localhost:6060"
}
```

**Response:**
```json
{"status": "success"}
```

**Effect:** Registers all sandbox tools (file_system, shell, browser, etc.)

---

### POST `/custom-mcp`

Mount a custom MCP server dynamically.

**Request:**
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-puppeteer"]
}
```

**Response:**
```json
{"status": "success"}
```

---

### POST `/register-codex`

Start the Codex SSE HTTP server subprocess.

**Response (success):**
```json
{
  "status": "success",
  "url": "http://0.0.0.0:1324"
}
```

**Response (already running):**
```json
{
  "status": "already_running",
  "url": "http://0.0.0.0:1324"
}
```

---

## 2. Tool Categories

Tools are organized into categories and exposed via MCP protocol:

| Category | Description | Tools |
|----------|-------------|-------|
| `file_system` | Read/write/manage files and directories | 9 tools |
| `shell` | Execute shell commands | 9 tools |
| `browser` | Browser automation and screenshots | 12 tools |
| `web` | Web scraping and HTTP requests | 7 tools |
| `dev` | Git, linting, code analysis | 11 tools |
| `media` | Image/video processing | 3 tools |
| `slide_system` | Create/edit presentation slides | 5 tools |
| `productivity` | Notes, calendar, todos | 4 tools |
| `agent` | Agent-to-agent communication | 2 tools |

---

## 3. File System Tools

### `read_file`
Read contents of a file.

**Input:**
```json
{
  "path": "/workspace/app.py"
}
```

**Output:** File contents as string

---

### `write_file`
Write content to a file.

**Input:**
```json
{
  "path": "/workspace/app.py",
  "content": "print('Hello World')"
}
```

---

### `create_directory`
Create a directory.

**Input:**
```json
{
  "path": "/workspace/new_folder",
  "exist_ok": true
}
```

---

### `list_directory`
List files in a directory.

**Input:**
```json
{
  "path": "/workspace",
  "recursive": false
}
```

---

### `delete_file`
Delete a file.

**Input:**
```json
{
  "path": "/workspace/old_file.txt"
}
```

---

### `move_file`
Move or rename a file.

**Input:**
```json
{
  "source": "/workspace/old.txt",
  "destination": "/workspace/new.txt"
}
```

---

### `copy_file`
Copy a file.

**Input:**
```json
{
  "source": "/workspace/original.txt",
  "destination": "/workspace/copy.txt"
}
```

---

### `file_exists`
Check if a file exists.

**Input:**
```json
{
  "path": "/workspace/check.txt"
}
```

---

### `get_file_info`
Get file metadata (size, created, modified).

**Input:**
```json
{
  "path": "/workspace/app.py"
}
```

---

## 4. Shell Tools

### `run_command`
Execute a shell command.

**Input:**
```json
{
  "command": "ls -la /workspace",
  "timeout": 30
}
```

**Output:**
```json
{
  "stdout": "...",
  "stderr": "",
  "exit_code": 0
}
```

---

### `run_python`
Execute Python code.

**Input:**
```json
{
  "code": "print(sum([1, 2, 3]))"
}
```

---

### `run_script`
Execute a script file.

**Input:**
```json
{
  "script_path": "/workspace/setup.sh"
}
```

---

### `install_package`
Install Python packages.

**Input:**
```json
{
  "packages": ["requests", "pandas"]
}
```

---

### `get_environment`
Get environment variables.

---

### `set_environment`
Set environment variables.

**Input:**
```json
{
  "key": "API_KEY",
  "value": "sk-..."
}
```

---

## 5. Browser Tools

### `navigate`
Navigate browser to URL.

**Input:**
```json
{
  "url": "https://example.com"
}
```

---

### `screenshot`
Take a screenshot.

**Input:**
```json
{
  "full_page": true,
  "output_path": "/workspace/screenshot.png"
}
```

---

### `click`
Click an element.

**Input:**
```json
{
  "selector": "#submit-button"
}
```

---

### `type_text`
Type text into an input.

**Input:**
```json
{
  "selector": "#search-input",
  "text": "AI research"
}
```

---

### `get_page_content`
Get page HTML or text content.

**Input:**
```json
{
  "format": "text"
}
```

---

### `scroll`
Scroll the page.

**Input:**
```json
{
  "direction": "down",
  "amount": 500
}
```

---

### `wait_for_element`
Wait for element to appear.

**Input:**
```json
{
  "selector": ".loaded-content",
  "timeout": 10
}
```

---

## 6. Web Tools

### `http_request`
Make HTTP requests.

**Input:**
```json
{
  "url": "https://api.example.com/data",
  "method": "GET",
  "headers": {"Authorization": "Bearer ..."}
}
```

---

### `web_search`
Search the web (via Tavily).

**Input:**
```json
{
  "query": "latest AI developments 2024",
  "max_results": 5
}
```

---

### `scrape_url`
Scrape and extract content from URL.

**Input:**
```json
{
  "url": "https://example.com/article",
  "extract_text": true
}
```

---

### `download_file`
Download a file from URL.

**Input:**
```json
{
  "url": "https://example.com/data.csv",
  "output_path": "/workspace/data.csv"
}
```

---

## 7. Dev Tools

### `git_clone`
Clone a Git repository.

**Input:**
```json
{
  "url": "https://github.com/user/repo",
  "destination": "/workspace/repo"
}
```

---

### `git_status`
Get Git status.

**Input:**
```json
{
  "repo_path": "/workspace/repo"
}
```

---

### `git_commit`
Create a Git commit.

**Input:**
```json
{
  "repo_path": "/workspace/repo",
  "message": "Add new feature",
  "files": ["src/app.py"]
}
```

---

### `lint_code`
Lint code files.

**Input:**
```json
{
  "path": "/workspace/app.py",
  "linter": "ruff"
}
```

---

### `format_code`
Format code files.

**Input:**
```json
{
  "path": "/workspace/app.py",
  "formatter": "black"
}
```

---

## 8. Media Tools

### `resize_image`
Resize an image.

**Input:**
```json
{
  "input_path": "/workspace/image.png",
  "output_path": "/workspace/resized.png",
  "width": 800,
  "height": 600
}
```

---

### `convert_image`
Convert image format.

**Input:**
```json
{
  "input_path": "/workspace/image.png",
  "output_path": "/workspace/image.jpg"
}
```

---

### `extract_audio`
Extract audio from video.

**Input:**
```json
{
  "video_path": "/workspace/video.mp4",
  "output_path": "/workspace/audio.mp3"
}
```

---

## 9. Slide Tools

### `create_slide`
Create a new slide.

**Input:**
```json
{
  "presentation_name": "my-presentation",
  "slide_number": 1,
  "title": "Introduction",
  "content": "<ul><li>Point 1</li><li>Point 2</li></ul>"
}
```

---

### `update_slide`
Update existing slide content.

**Input:**
```json
{
  "presentation_name": "my-presentation",
  "slide_number": 1,
  "content": "<h1>Updated Title</h1>"
}
```

---

### `delete_slide`
Delete a slide.

**Input:**
```json
{
  "presentation_name": "my-presentation",
  "slide_number": 3
}
```

---

### `list_slides`
List all slides in a presentation.

**Input:**
```json
{
  "presentation_name": "my-presentation"
}
```

---

### `export_presentation`
Export presentation to PDF.

**Input:**
```json
{
  "presentation_name": "my-presentation",
  "output_path": "/workspace/output.pdf"
}
```

---

## 10. Configuration

### Starting the Tool Server

```bash
# From within sandbox
cd backend/src/tool_server
python -m mcp.server --workspace_dir /workspace --port 6060
```

### Environment Variables

```env
# Workspace directory
WORKSPACE_DIR=/workspace

# Tool server port
TOOL_SERVER_PORT=6060

# Tavily (for web search)
TAVILY_API_KEY=tvly-...

# Git credentials (optional)
GIT_USER_EMAIL=user@example.com
GIT_USER_NAME=User Name
```

---

## Connecting from FastAPI Backend

The main FastAPI backend connects to the Tool Server via the MCP API:

```python
# backend/app/agent/api/v1/mcp.py

# Get tools from tool server
tools = await load_mcp_tools(
    server_type="http",
    url="http://localhost:6060",
    timeout_seconds=300
)
```

---

## Quick Test Commands

```bash
# Health check
curl http://localhost:6060/health

# Set credentials
curl -X POST http://localhost:6060/credential \
  -H "Content-Type: application/json" \
  -d '{"user_api_key":"key123","session_id":"session123"}'

# Register tool server URL
curl -X POST http://localhost:6060/tool-server-url \
  -H "Content-Type: application/json" \
  -d '{"tool_server_url":"http://localhost:6060"}'
```
