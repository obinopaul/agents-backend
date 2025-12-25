# DeepAgents CLI - Interactive AI Coding Assistant

DeepAgents CLI is an interactive terminal-based AI coding assistant that connects to a secure sandbox environment for writing, executing, and debugging code.

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DeepAgents CLI                                  │
│                 Interactive AI Coding Assistant                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   You > Create a Flask API with /hello endpoint                     │
│                                                                      │
│   🤖 Agent (3 tool calls):                                          │
│      ✓ Created app.py with Flask server                            │
│      ✓ Installed flask dependency                                  │
│      ✓ Server running on port 5000                                 │
│                                                                      │
│   Preview: http://localhost:8090                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# 1. Start the sandbox container
cd backend/src/sandbox/agent_infra_sandbox
docker-compose up -d

# 2. Set your API key
export OPENAI_API_KEY=your_key_here

# 3. Run DeepAgents CLI
python -m deepagents_cli
```

---

## CLI Commands

### Session Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/clear` | Clear screen and reset conversation |
| `/tokens` | Show token usage for current session |
| `/session list` | List all saved sessions |
| `/session save <name>` | Save current session |
| `/session load <name>` | Load a saved session |

### Model Commands

| Command | Description |
|---------|-------------|
| `/model list` | List available LLM models |
| `/model use <name>` | Switch to a different model |

### Skill Mode Commands

Skill modes inject specialized capabilities into the sandbox.

| Command | Description |
|---------|-------------|
| `/mode list` | List available skill modes |
| `/mode <name>` | Activate a skill mode |
| `/mode --sandbox <name>` | Inject skills to sandbox workspace only |
| `/mode --local <name>` | Inject skills to local `.deepagents/skills/` |
| `/mode --all <name>` | Inject skills to both sandbox and local |

### Shell Commands

| Command | Description |
|---------|-------------|
| `!<command>` | Execute a bash command locally |
| `!!<command>` | Execute command in sandbox |

---

## Sandbox Options

### Default (Agent Infra Sandbox)

```bash
python -m deepagents_cli
# or explicitly
python -m deepagents_cli --sandbox agent_infra
```

### No Sandbox (Local Only)

```bash
python -m deepagents_cli --sandbox none
```

### Auto-Approve Mode

Skip confirmation prompts for tool executions:

```bash
python -m deepagents_cli --auto-approve
```

---

## Example Session

```
🔧 Initializing DeepAgents CLI...
   ✓ Connected to Agent Infra Sandbox
   ✓ Sandbox URL: http://localhost:8090
   ✓ Model: gpt-4o

You > Create a simple todo API with FastAPI

🤖 Agent:
   Creating todo_api.py...
   
   ```python
   from fastapi import FastAPI
   app = FastAPI()
   todos = []
   
   @app.get("/todos")
   def get_todos():
       return todos
   
   @app.post("/todos")
   def add_todo(todo: str):
       todos.append(todo)
       return {"added": todo}
   ```
   
   Running: uvicorn todo_api:app --port 8000
   ✓ Server started on port 8000
   
   Preview: http://localhost:8090 → port 8000

You > /tokens
📊 Token Usage:
   Prompt: 1,234 tokens
   Completion: 567 tokens
   Total: 1,801 tokens

You > exit
👋 Goodbye! Your sandbox is preserved.
```

---

## Available Skill Modes

| Mode | Description | Tools Added |
|------|-------------|-------------|
| `web` | Web development | npm, node, browser-sync |
| `python` | Python development | pip, pytest, jupyter |
| `data` | Data science | pandas, matplotlib, jupyter |
| `devops` | DevOps tools | docker, kubectl, terraform |

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `DEEPAGENTS_MODEL` | Default model | `gpt-4o` |
| `DEEPAGENTS_SANDBOX` | Default sandbox | `agent_infra` |

### Config File

Create `~/.deepagents/config.yaml`:

```yaml
default_model: gpt-4o
default_sandbox: agent_infra
auto_approve: false
max_tokens: 4096
```

---

## Troubleshooting

### Sandbox Not Connecting

```bash
# Check if container is running
docker ps | grep agent_infra

# Restart the sandbox
cd backend/src/sandbox/agent_infra_sandbox
docker-compose down && docker-compose up -d

# Check logs
docker-compose logs -f
```

### Model Errors

```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Try a different model
/model use gpt-4o-mini
```

---

## Related Documentation

- [Agent Infra Sandbox README](../../backend/src/sandbox/agent_infra_sandbox/README.md)
- [CLI Reference](cli-reference.md) - FBA CLI commands
- [Main README](../../README.md) - Project overview
