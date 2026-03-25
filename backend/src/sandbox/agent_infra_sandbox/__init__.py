"""Agent-Infra Sandbox - Unified sandbox environment for AI agents.

This package provides two ways to use the Docker-based Agent-Infra sandbox:

1. **LangChain Tools** (langchain_tools):
   - LangChain-compatible tools for file ops, shell, code execution
   - Best for LangChain/LangGraph agents
   - Session-based isolation for multi-tenant usage

2. **DeepAgents CLI** (deepagents_cli):
   - Interactive CLI with advanced agent capabilities
   - Memory, skills, and human-in-the-loop features
   - Supports local filesystem or remote sandbox execution

## Quick Start

### Start the Sandbox
```bash
cd backend/src/sandbox/agent_infra_sandbox
docker-compose up -d
```

### LangChain Tools Approach
```python
from agent_infra_sandbox import SandboxSession, SandboxClient

# Check sandbox health
client = SandboxClient()
if await client.health_check():
    print("Sandbox is running!")

# Create isolated session
async with await SandboxSession.create(session_id="my_session") as session:
    tools = session.get_tools()
    # Use tools...
```

### DeepAgents CLI Approach
```bash
# Run the interactive CLI with Agent-Infra sandbox (default)
python -m agent_infra_sandbox.deepagents_cli

# Or with explicit sandbox specification
python -m agent_infra_sandbox.deepagents_cli --sandbox agent_infra
```

## Environment Variables

- `AGENT_INFRA_URL`: Sandbox URL (default: http://localhost:8080)
- `AGENT_INFRA_TIMEOUT`: Request timeout in seconds (default: 60)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: Required for DeepAgents CLI
- `TAVILY_API_KEY`: Optional, enables web search in DeepAgents CLI
"""

# Shared infrastructure
from .client import SandboxClient
from .session import SandboxSession
from .exceptions import (
    SandboxError,
    SandboxConnectionError,
    SandboxTimeoutError,
    SandboxExecutionError,
    SandboxNotRunningError,
)

__all__ = [
    # Core classes
    "SandboxClient",
    "SandboxSession",
    # Exceptions
    "SandboxError",
    "SandboxConnectionError",
    "SandboxTimeoutError",
    "SandboxExecutionError",
    "SandboxNotRunningError",
]

__version__ = "0.3.0"
