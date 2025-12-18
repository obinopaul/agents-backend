# Sandbox Implementation Guide - Overview

## What You're Building

You want to extract the **sandbox infrastructure** from this project and integrate it into your own LangChain-based agent. This guide will explain everything you need to know.

## The Three Core Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        YOUR LANGCHAIN APPLICATION                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Your Agent (LangChain)                           │    │
│  │  - Your own LLM orchestration                                        │    │
│  │  - Your own prompts and chains                                       │    │
│  │  - Your own tool definitions                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              COMPONENT 1: Sandbox Server (ii_sandbox_server)         │    │
│  │  - FastAPI server that manages E2B sandbox instances                 │    │
│  │  - Handles create/connect/delete sandboxes                           │    │
│  │  - Exposes ports, runs commands, manages files                       │    │
│  │  - YOU NEED THIS                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              COMPONENT 2: E2B Template (e2b.Dockerfile)              │    │
│  │  - Custom Docker image uploaded to E2B                               │    │
│  │  - Pre-installed with: Code-Server, Claude Code, Python, Node.js    │    │
│  │  - Contains: MCP Server (ii_tool), startup scripts                  │    │
│  │  - YOU NEED THIS                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              COMPONENT 3: MCP Tool Server (ii_tool)                  │    │
│  │  - Runs INSIDE the E2B sandbox                                       │    │
│  │  - Exposes tools via MCP protocol                                    │    │
│  │  - Your agent calls these tools remotely                             │    │
│  │  - YOU NEED THIS (or build your own tool server)                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## What You DON'T Need

- `src/ii_agent/` - This is THEIR agent implementation. You have LangChain.
- `frontend/` - This is their React frontend. You might have your own.
- `docs/` - Their documentation site.

## What You DO Need

| Component | Location | Purpose |
|-----------|----------|---------|
| **ii_sandbox_server** | `src/ii_sandbox_server/` | FastAPI server to manage E2B sandboxes |
| **e2b.Dockerfile** | `e2b.Dockerfile` | Docker template for E2B with all tools |
| **ii_tool** | `src/ii_tool/` | MCP server that runs inside sandbox |
| **docker/sandbox/** | `docker/sandbox/` | Startup scripts and configs |

## The Big Picture

```
YOUR MACHINE                           E2B CLOUD
─────────────────────────────────────────────────────────────────────────
                                       
┌────────────────────┐                ┌─────────────────────────────────┐
│ Your LangChain App │                │     E2B Sandbox Instance        │
│                    │                │  (Created from e2b.Dockerfile)  │
│ ┌────────────────┐ │                │                                 │
│ │  Agent Logic   │ │                │  ┌───────────────────────────┐  │
│ │  (LangChain)   │ │                │  │  Code-Server (VS Code)    │  │
│ └───────┬────────┘ │                │  │  Port 9000                │  │
│         │          │                │  └───────────────────────────┘  │
│         │          │                │                                 │
│ ┌───────▼────────┐ │   HTTP/WS      │  ┌───────────────────────────┐  │
│ │ Sandbox Client │◄├───────────────►│  │  MCP Tool Server          │  │
│ │ (HTTP calls)   │ │                │  │  Port 6060                │  │
│ └───────┬────────┘ │                │  │  - File operations        │  │
│         │          │                │  │  - Shell commands         │  │
└─────────┼──────────┘                │  │  - Browser automation     │  │
          │                           │  │  - Claude Code            │  │
          │                           │  └───────────────────────────┘  │
┌─────────▼──────────┐                │                                 │
│  Sandbox Server    │   HTTP         │  ┌───────────────────────────┐  │
│  (ii_sandbox_srv)  │◄──────────────►│  │  /workspace               │  │
│  - Manages E2B     │                │  │  (Your project files)     │  │
│  - Port exposure   │                │  └───────────────────────────┘  │
│  - File I/O        │                │                                 │
└────────────────────┘                └─────────────────────────────────┘
```

## Reading Order

1. **01-WHY-EACH-COMPONENT.md** - Deep explanation of why each part exists
2. **02-E2B-DOCKERFILE-EXPLAINED.md** - Line-by-line breakdown of the Dockerfile
3. **03-SANDBOX-SERVER-EXPLAINED.md** - How ii_sandbox_server works
4. **04-MCP-TOOL-SERVER-EXPLAINED.md** - How ii_tool works inside sandbox
5. **05-CLAUDE-CODE-INTEGRATION.md** - How Claude Code is integrated
6. **06-CODE-SERVER-INTEGRATION.md** - How VS Code in browser works
7. **07-IMPLEMENTATION-GUIDE.md** - Step-by-step to implement in your project
8. **08-LANGCHAIN-INTEGRATION.md** - Specifically for LangChain projects

## Quick Start (If You're Impatient)

```bash
# 1. You need an E2B API key
export E2B_API_KEY=your_key_here

# 2. Build and push your E2B template
e2b template build -d e2b.Dockerfile

# 3. Start the sandbox server
cd src/ii_sandbox_server
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080

# 4. From your LangChain app, call the sandbox server
POST http://localhost:8080/sandboxes/create
POST http://localhost:8080/sandboxes/run-command
# etc.
```

But don't do this yet - read the documentation first to understand WHY.
