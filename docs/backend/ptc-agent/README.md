# PTC-Agent Framework

The `ptc-agent/` module is an AI agent framework implementing **Programmatic Tool Calling (PTC)** - a novel approach that replaces JSON-based tool calls with code generation and execution in secure sandboxes.

---

## Overview

PTC-Agent enables AI models to execute arbitrary code in Daytona sandboxes while integrating with MCP (Model Context Protocol) servers for extensible tool capabilities.

**Key Differentiator:** Instead of calling tools via structured JSON:
```json
{"tool": "search", "args": {"query": "weather"}}
```

PTC generates and executes actual Python code:
```python
result = await search("weather")
print(result)
```

---

## Directory Structure

```
ptc-agent/
├── __init__.py              # Package exports
├── README.md                # Package documentation
├── pyproject.toml           # Package configuration
├── Makefile                 # Build commands
│
├── agent/                   # Agent implementation
│   ├── agent.py             # PTCAgent, PTCExecutor (~20KB)
│   ├── graph.py             # LangGraph workflow construction
│   ├── backends/            # Sandbox backends (Daytona)
│   ├── middleware/          # Agent middleware stack
│   ├── prompts/             # Jinja2 prompt templates
│   ├── subagents/           # Specialized subagents
│   └── tools/               # Built-in tools
│
├── config/                  # Configuration system
│   ├── core.py              # CoreConfig, MCPServerConfig
│   ├── agent.py             # AgentConfig, LLMConfig
│   ├── loaders.py           # File-based config loading
│   └── utils.py             # Config utilities
│
├── core/                    # Core infrastructure
│   ├── sandbox.py           # PTCSandbox (~76KB)
│   ├── mcp_registry.py      # MCPRegistry (~25KB)
│   ├── session.py           # SessionManager (~7KB)
│   ├── security.py          # Code validation (~10KB)
│   └── tool_generator.py    # Dynamic tool generation (~30KB)
│
├── utils/                   # Utilities
│   └── storage/             # Cloud storage (S3, R2, OSS)
│
├── ii-agent/                # II-Agent subproject
│   └── ...                  # Separate agent implementation
│
└── tests/                   # Test suite
    └── ...
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                                  │
│          "Get AAPL stock price and create a chart"                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         PTCAgent                                     │
│  ─────────────────────────────────────                              │
│  • Receives natural language request                                 │
│  • Creates LangGraph agent with tools                                │
│  • Manages middleware stack                                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MIDDLEWARE STACK                                │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐│
│  │ DeepAgentMiddleware│  │ PlanModeMiddleware│  │BackgroundMiddleware││
│  │ (orchestration)   │  │ (planning mode)   │  │ (background tasks)││
│  └───────────────────┘  └───────────────────┘  └───────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LLM REASONING                                 │
│  ─────────────────────────────────                                  │
│  Model decides to generate Python code:                              │
│                                                                     │
│  ```python                                                          │
│  from yfinance_tools import get_stock_price, create_chart           │
│  price = await get_stock_price("AAPL")                              │
│  chart = await create_chart(price)                                  │
│  ```                                                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       CODE VALIDATION                                │
│                     (core/security.py)                               │
│  ─────────────────────────────────                                  │
│  • Check code length limits                                          │
│  • Validate syntax                                                   │
│  • Detect forbidden patterns                                         │
│  • Sanitize imports                                                  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SANDBOX EXECUTION                              │
│                      (core/sandbox.py)                               │
│  ─────────────────────────────────                                  │
│  PTCSandbox wraps Daytona API:                                       │
│  • Create/manage sandbox instances                                   │
│  • Execute code in isolated environment                              │
│  • File system operations                                            │
│  • Return execution results                                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       MCP INTEGRATION                                │
│                    (core/mcp_registry.py)                            │
│  ─────────────────────────────────                                  │
│  MCPRegistry provides:                                               │
│  • MCP server discovery and management                               │
│  • Tool schema conversion                                            │
│  • Dynamic tool generation                                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RESPONSE                                     │
│              "AAPL is at $185.50, chart saved to chart.png"          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

| Component | File | Description |
|-----------|------|-------------|
| **PTCAgent** | `agent/agent.py` | Main agent orchestrator |
| **PTCExecutor** | `agent/agent.py` | Code execution handler |
| **PTCSandbox** | `core/sandbox.py` | Daytona sandbox wrapper |
| **MCPRegistry** | `core/mcp_registry.py` | MCP server management |
| **SessionManager** | `core/session.py` | Conversation lifecycle |
| **ToolGenerator** | `core/tool_generator.py` | MCP → Python functions |
| **SecurityValidator** | `core/security.py` | Code validation |

---

## Quick Start

```python
import asyncio
from langchain.chat_models import init_chat_model
from ptc_agent import AgentConfig, PTCAgent
from ptc_agent.config import MCPServerConfig
from ptc_agent.core import SessionManager

async def main():
    # 1. Create LLM
    llm = init_chat_model("gpt-4o")

    # 2. Configure agent
    config = AgentConfig.create(
        llm=llm,
        mcp_servers=[
            MCPServerConfig(
                name="yfinance",
                description="Stock data tools",
                command="uv",
                args=["run", "python", "mcp_servers/yfinance_mcp_server.py"],
            ),
        ],
        subagents_enabled=["general-purpose", "research"],
    )

    # 3. Create session
    session = SessionManager.get_session("demo", config.to_core_config())
    await session.initialize()

    try:
        # 4. Create and run agent
        ptc_agent = PTCAgent(config)
        agent = ptc_agent.create_agent(
            sandbox=session.sandbox,
            mcp_registry=session.mcp_registry,
        )

        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Get AAPL stock price"}]
        })
        print(result)

    finally:
        await session.cleanup()

asyncio.run(main())
```

---

## Configuration

### Programmatic Configuration

```python
config = AgentConfig.create(
    llm=llm,
    
    # Daytona settings
    daytona_base_url="https://app.daytona.io/api",
    python_version="3.12",
    auto_stop_interval=3600,
    
    # Security
    max_execution_time=300,
    max_code_length=10000,
    
    # Agent features
    use_custom_filesystem_tools=True,
    subagents_enabled=["general-purpose", "research"],
    
    # MCP servers
    mcp_servers=[...],
)
```

### File-Based Configuration

```python
from ptc_agent.config import load_from_files

config = await load_from_files()  # Auto-discovers config.yaml
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DAYTONA_API_KEY` | Yes | Daytona sandbox API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Claude models |
| `OPENAI_API_KEY` | If using OpenAI | GPT models |
| `TAVILY_API_KEY` | Optional | Web search |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Agent Layer](./agent/README.md) | PTCAgent, middleware, tools |
| [Core Layer](./core/README.md) | Sandbox, MCP, sessions |
| [Configuration](./config/README.md) | Config system |

---

*Last Updated: December 2024*
