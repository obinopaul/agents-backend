# Agent-Infra Sandbox

A unified sandbox environment for AI agents, providing two powerful integration options:
**LangChain Tools** for programmatic agent tooling and **DeepAgents CLI** for interactive terminal-based AI coding.

## Features

- 🐳 **Docker-based Sandbox** - Isolated execution environment
- 🔒 **Workspace Isolation** - Each session gets its own workspace
- 🛠️ **LangChain Tools** - 23+ tools for file, shell, code, browser operations
- 💻 **DeepAgents CLI** - Interactive AI coding assistant with memory and skills
- 🔗 **Unified Client** - Shared infrastructure for both approaches

## Quick Start

### 1. Start the Sandbox

```bash
cd backend/src/sandbox/agent_infra_sandbox
docker-compose up -d
```

### 2. Verify Sandbox is Running

```bash
python check_sandbox.py
```

Expected output:
```
✅ Sandbox is running and healthy!
   Home directory: /home/gem
   System: Linux ...
```

### 3. Choose Your Integration

#### Option A: DeepAgents CLI (Interactive)

```bash
# Set your API key
export OPENAI_API_KEY=your_key_here
# Or: export ANTHROPIC_API_KEY=your_key_here

# Run the interactive CLI (uses agent_infra sandbox by default)
python -m deepagents_cli

# Or with explicit sandbox:
python -m deepagents_cli --sandbox agent_infra

# With auto-approve (no confirmation prompts):
python -m deepagents_cli --auto-approve
```

#### Option B: LangChain Tools (Programmatic)

```python
from agent_infra_sandbox import SandboxSession

async with await SandboxSession.create(session_id="my_agent") as session:
    tools = session.get_tools()
    tool_map = {t.name: t for t in tools}
    
    # Write a file
    await tool_map["file_write"].ainvoke({
        "file": "hello.py",
        "content": "print('Hello from sandbox!')"
    })
    
    # Execute it
    result = await tool_map["shell_exec"].ainvoke({
        "command": "python hello.py"
    })
    print(result)  # Hello from sandbox!
```

## Project Structure

```
agent_infra_sandbox/
├── __init__.py           # Unified API entry point
├── client.py             # Shared SandboxClient
├── session.py            # Shared SandboxSession
├── exceptions.py         # Common exceptions
├── check_sandbox.py      # Sandbox health check script
├── docker-compose.yaml   # Sandbox container config
├── examples/             # Usage examples
│   └── deepagent_cli_example.py
├── langchain_tools/      # LangChain integration
│   ├── tools/            # Individual tools
│   ├── examples/         # LangChain examples
│   └── README.md
└── deepagents_cli/       # Interactive CLI agent
    ├── main.py           # CLI entry point
    ├── agent.py          # Agent creation
    ├── config.py         # Configuration
    └── integrations/     # Sandbox backends
        └── agent_infra.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_INFRA_URL` | `http://localhost:8090` | Sandbox URL |
| `AGENT_INFRA_TIMEOUT` | `60` | Request timeout (seconds) |
| `OPENAI_API_KEY` | - | OpenAI API key (for DeepAgents CLI) |
| `ANTHROPIC_API_KEY` | - | Anthropic API key (alternative) |
| `GOOGLE_API_KEY` | - | Google Gemini API key (alternative) |
| `TAVILY_API_KEY` | - | Tavily API key (enables web search) |

## DeepAgents CLI Commands

```bash
# Interactive mode with sandbox
python -m deepagents_cli

# List available agents
python -m deepagents_cli list

# Reset an agent's memory
python -m deepagents_cli reset --agent my_agent

# Run without sandbox (local filesystem only)
python -m deepagents_cli --sandbox none

# Show help
python -m deepagents_cli help
```

## LangChain Tools Available

| Category | Tools |
|----------|-------|
| **File** | `file_read`, `file_write`, `file_edit`, `file_list`, `file_find`, `file_search` |
| **Shell** | `shell_exec`, `shell_view`, `shell_write`, `shell_wait`, `shell_kill` |
| **Code** | `python_execute`, `javascript_execute` |
| **Browser** | `browser_info`, `browser_screenshot`, `browser_action` |
| **MCP** | `mcp_list_servers`, `mcp_list_tools`, `mcp_execute` |
| **Search** | `grep`, `glob` |
| **Utility** | `workspace_info`, `workspace_health` |

## License

Apache 2.0
