# PTC Module - Programmatic Tool Calling

A production-ready implementation of **Programmatic Tool Calling (PTC)** with Daytona cloud sandboxes. Instead of traditional JSON-based tool calls, agents write Python code to interact with tools, keeping intermediate results out of the LLM context window.

## What is PTC?

Traditional agent approach:
```
LLM → JSON tool call → Execute → Return result to LLM → LLM processes → Next call
```

PTC approach:
```
LLM → Write Python code → Execute in sandbox → Only return summary to LLM
```

**Benefits:**
- 🚀 **Token efficiency**: Intermediate data stays in sandbox, not LLM context
- 🔧 **Full programming power**: Agents can use loops, conditionals, imports
- 🏗️ **Persistent workspace**: Files and state persist across calls
- 🌐 **Web preview**: See what's being built in your browser

## Quick Start

### 1. Set Environment Variables

```bash
export DAYTONA_API_KEY="your-daytona-key"  # Get from https://app.daytona.io
export OPENAI_API_KEY="your-openai-key"     # Or ANTHROPIC_API_KEY
```

### 2. Run the Interactive CLI

```bash
cd backend
python -m src.ptc.examples.langgraph_robust_agent
```

### 3. Start Building!

```
You > Create a Flask API with a /hello endpoint
🤖 Agent (thinking...)
   ✓ Created app.py
   ✓ Server running on port 5000

You > status
📊 Sandbox Status
   Preview (port 5000): https://your-sandbox.daytona.io

You > exit
```

## Module Structure

```
backend/src/ptc/
├── __init__.py           # Exports: PTCSandbox, MCPRegistry, Session, etc.
├── sandbox.py            # Core sandbox management (Daytona SDK)
├── mcp_registry.py       # MCP server connections and tool discovery
├── session.py            # Session lifecycle management
├── tool_generator.py     # Convert MCP tools to Python functions
├── security.py           # Code validation and security
├── config/
│   ├── agent.py          # AgentConfig, LLMConfig
│   ├── loaders.py        # YAML-based config loading
│   └── utils.py          # Config helpers
├── utils/storage/        # Cloud storage (S3, R2, OSS)
└── examples/
    ├── ptc_demo.py                # Basic usage demos
    ├── langgraph_ptc_agent.py     # Simple LangGraph agent
    └── langgraph_robust_agent.py  # Production CLI agent ⭐
```

## Core Components

### PTCSandbox

Manages Daytona cloud sandboxes for secure code execution:

```python
from backend.src.ptc import PTCSandbox
from backend.src.config.core import CoreConfig, DaytonaConfig, ...

config = CoreConfig(
    daytona=DaytonaConfig(api_key="..."),
    security=SecurityConfig(),
    mcp=MCPConfig(servers=[]),
    logging=LoggingConfig(),
    filesystem=FilesystemConfig(),
)

sandbox = PTCSandbox(config)
await sandbox.initialize()

result = await sandbox.execute("print('Hello from sandbox!')")
print(result.output)

await sandbox.cleanup()
```

### Creating Tools

Tools are created with the sandbox injected:

```python
from backend.src.tools.bash import create_execute_bash_tool
from backend.src.tools.file_ops import create_filesystem_tools
from backend.src.tools.glob import create_glob_tool
from backend.src.tools.grep import create_grep_tool

# Create tools with sandbox
bash_tool = create_execute_bash_tool(sandbox)
read_file, write_file, edit_file = create_filesystem_tools(sandbox)
glob_tool = create_glob_tool(sandbox)
grep_tool = create_grep_tool(sandbox)

tools = [bash_tool, read_file, write_file, edit_file, glob_tool, grep_tool]
```

### LangGraph Integration

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")
agent = create_react_agent(llm, tools, state_modifier=SYSTEM_PROMPT)

result = await agent.ainvoke({"messages": [HumanMessage(content="Build a web app")]})
```

## Available Tools

| Tool | File | Description |
|------|------|-------------|
| `execute_code` | `tools/code_execution.py` | Run Python code, MCP tools |
| `Bash` | `tools/bash.py` | Shell commands (git, npm, docker) |
| `read_file` | `tools/file_ops.py` | Read file with line numbers |
| `write_file` | `tools/file_ops.py` | Create/overwrite files |
| `edit_file` | `tools/file_ops.py` | Edit existing files |
| `glob` | `tools/glob.py` | Find files by pattern |
| `grep` | `tools/grep.py` | Search file contents |

## Configuration

### Programmatic

```python
from backend.src.ptc.config import AgentConfig
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-20250514")
config = AgentConfig.create(llm=llm)
core_config = config.to_core_config()
```

### File-based (config.yaml)

```yaml
daytona:
  base_url: "https://app.daytona.io/api"
  python_version: "3.12"

security:
  max_execution_time: 600
  max_code_length: 50000

mcp:
  servers: []
  tool_discovery_enabled: true

logging:
  level: "INFO"

filesystem:
  working_directory: "/home/daytona"
  allowed_directories:
    - "/home/daytona"
    - "/tmp"
```

## CLI Commands

When running the interactive CLI:

| Command | Description |
|---------|-------------|
| `help` | Show available commands |
| `status` | Show sandbox ID and preview URLs |
| `files` | List files in sandbox |
| `clear` | Clear screen |
| `exit` | Quit (sandbox persists) |

## Examples

### Build a Web App

```
You > Create a Next.js app with Tailwind CSS
You > Add a dark mode toggle to the header
You > Start the dev server
You > status  # Get preview URL
```

### Data Processing

```
You > Create a Python script that downloads weather data from an API
You > Process it and create a visualization
You > Save the chart as weather.png
```

### Research Task

```
You > Research the top 5 Python web frameworks
You > Create a comparison table in markdown
You > Save it as frameworks.md
```

## Dependencies

```
daytona-sdk
langchain-core
langchain-openai  # or langchain-anthropic
langgraph
structlog
aiofiles
pydantic
```

## Related

- [Daytona](https://daytona.io) - Cloud development environments
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent framework
- [MCP](https://modelcontextprotocol.io) - Model Context Protocol

## License

Part of the agents-backend project.
