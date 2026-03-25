# CLAUDE.md - Agent Backend Project Context

This document provides high-level context, architectural guidelines, and references for AI agents working on the `agents-backend` project.

## 1. Project Overview

This is a robust AI Agent System with a **Python FastAPI backend** and a **Vite.js (React) frontend**.
-   **Backend**: Built for robustness, supporting both simple chat and complex autonomous agents.
-   **Frontend**: Adapted from the `II-Agent` project, requiring careful integration with the backend.

## 2. Core Architecture: Two Streams

The backend supports two distinct modes of interaction ("Streams"):

### A. Chat Stream (Simple)
-   **Protocol**: **SSE (Server-Sent Events)** for text streaming.
-   **Capabilities**: Basic LLM interaction, tools (no sandbox).
-   **Use Case**: Simple Q&A, fast responses.
-   **Key Reference**: `FRONTEND_BACKEND_CHAT_INTEGRATION.md`

### B. Agent Stream (Advanced)
-   **Protocol**: **WebSockets** (Socket.IO).
-   **Capabilities**: Full autonomous agent with **Sandboxing**.
-   **Sandbox**: Uses **E2B** (default) or Daytona.
    -   **Tools**: Injected via **MCP (Model Context Protocol)** servers running outside the sandbox but connecting into it.
    -   **Apps**: Inside sandbox, exposed via ports (e.g., CodeServer/VSCode, Excalidraw, Graphite urls).
-   **Modules**: The agent stream supports various "Modules" (Deep Research, Data Scientist, Quantum, Slides, Dev) which are specialized agentic workflows.
-   **Key Reference**: `FRONTEND_BACKEND_AGENT_INTEGRATION.md`

## 3. Essential Integration Plans (MUST READ)

The following markdown files in the root directory are **critical** for understanding the system's design and integration status. You should reference these when planning any changes.

| File | Purpose |
|------|---------|
| `FRONTEND_BACKEND_INTEGRATION_PLAN.md` | **The Master Plan**. Step-by-step integration components (Auth, WS, Session, Files, etc.). |
| `FRONTEND_BACKEND_AGENT_INTEGRATION.md` | Deep dive into the **WebSocket Agent Stream**, events, and sandbox lifecycle. |
| `FRONTEND_BACKEND_CHAT_INTEGRATION.md` | Deep dive into the **SSE Chat Stream**, event protocols, and API contracts. |
| `FRONTEND_BACKEND_FILE_SLIDE_INTEGRATION.md` | Guide for File System, Uploads, and Slide Integrations. |
| `FRONTEND_BACKEND_INTEGRATION.md` | Documentation for the **Event Adapter** layer (converting backend events to frontend formats). |
| `COMPREHENSIVE_INTEGRATION_PLAN.md` | High-level roadmap, gap analysis, and risk assessment. |

## 4. Codebase Structure

### Backend (`backend/`)
-   **Entry Point**: `backend/main.py` (Registers app, plugins, starts server).
-   **`backend/app/`**: FastAPI implementation (Routers, Admin, Tasks).
    -   `backend/app/agent/`: Agent-specific API routes.
-   **`backend/src/`**: Core Agent Logic & Modules.
    -   `backend/src/sandbox/`: Sandbox management (E2B integration).
    -   `backend/src/graph/`: LangGraph definitions.
    -   `backend/src/tools/`: Tool definitions.
    -   `backend/src/tool_server/`: Main Tools component used in this project. Most of these tools are loaded inside the E2B sandbox via MCP, while the rest of the tools in the tool_server are still loaded via MCP (just not sent ran from the sandbox).
    -   `backend/src/module/`: Specialized agent modules.
-   **`backend/common/`**: Shared utilities (Socket.IO handlers, Database).
-   **`backend/plugin/`**: Plugin system.

NB: We have two main agent systems:
1. The Agent Stream (WebSocket) - This is the main agent system that we are working on. It is a full autonomous agent with a sandbox and tools. `backend\app\agent\api\v1\agent.py` is the entry point for the agent stream.
2. The Chat Stream (SSE) - This is a simple chat system that we are working on. It is a basic LLM interaction with tools. `backend\app\chat\api\v1\chat.py` is the entry point for the chat stream.
3. You may see a folder like `external_github` in the root directory. This folder contains code snippets from II-agent prjects backend. I have this folder as a reference to help me build the agent system. It is not part of the current project. But since or frontend folder is a copy of II-agent frontend, i have to also copy their backend as a reference to help me better build my backend component.

### Frontend (`frontend/`)
-   Built with Vite + React.
-   Integration points are primarily in `frontend/src/services/` (API calls) and `frontend/src/hooks/` (WebSocket/SSE handling).

### Documentation (`docs/`)
-   **`docs/api contracts/`**: Detailed Markdown files for API specifications.
-   **`docs/guides/`**: Setup and usage guides.
-   **`docs/backend/`**: Backend-specific documentation.

### Tests (`backend/tests/`)
-   Contains unit and integration tests. Always check here for test patterns before writing new code.

## 5. Development Guidelines

1.  **Reference Plans**: Before implementing a feature, check the relevant `*_INTEGRATION.md` file to see the expected contract and implementation steps.
2.  **Sandbox/MCP**: When adding tools to the Agent Stream, remember they run via MCP and interact with the Sandbox environment.
3.  **Event Adapters**: The backend uses an "Event Adapter" pattern to translate internal event formats to what the II-Agent frontend expects. Ensure any new events are securely added to `backend/app/agent/event_adapter.py`.
4.  **Logging**: The system uses `rich` for console logging. Maintains logs in `backend_logs.txt` (or similar).

## 6. Common Commands

-   **Start Backend**: `uv run python backend/main.py` (or similar via `start.sh`)
-   **Start Frontend**: `cd frontend && npm run dev`
-   **Run Tests**: `pytest backend/tests`
