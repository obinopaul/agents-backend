# Sandbox Startup Lifecycle & Latency Analysis

This document details the startup process for the Agent execution environment (Sandbox) and analyzes the factors contributing to the latency (typically 80-90 seconds) observed during the `Waiting for MCP...` phase.

## 1. High-Level Overview

When a user initiates a chat with the Agent (`POST /agent/agent/stream`), the backend must provision a secure, isolated environment (Sandbox) to execute the agent's logic and tools. This involves:

1.  **Provisioning**: Requesting a Virtual Machine (VM) from the `e2b` provider.
2.  **Bootstrapping**: Starting necessary services inside the VM (MCP Tool Server, Code Server).
3.  **Health Check**: Waiting for services to become responsive before starting the agent workflow.

## 2. Detailed Process Flow

### Step 1: Agent Request & Sandbox Initialization
*   **Trigger**: User sends a request to the backend.
*   **Action**: `backend/app/agent/api/v1/agent.py` calls `Sandboxes.create(...)`.
*   **Code**: `backend/src/sandbox/sandbox_server/sandboxes/e2b.py`.

### Step 2: E2B VM Allocation (Time: ~2-5s)
*   The backend calls the E2B API to create a sandbox instance using a specific **Template ID** (e.g., `base`), which contains the pre-built Docker image with Python, Node.js, and dependencies.
*   E2B allocates a micro-VM. Note that "cold starts" (when no VMs are pre-warmed) can add latency, but this is usually fast.

### Step 3: Service Startup Script (Time: <1s)
*   Once the VM is running, the backend executes the startup command:
    ```bash
    bash /app/start-services.sh &
    ```
*   **Script Location**: `/app/start-services.sh` (inside sandbox).
*   **What it does**:
    1.  Sets up environment variables (`HOME`, `PATH`).
    2.  Fixes permissions for the `pn` user.
    3.  Starts **Code Server** (for IDE features) in a tmux session.
    4.  Starts **MCP Tool Server** in a tmux session.

### Step 4: MCP Tool Server Initialization (Time: ~70-90s - The "Slow" Part)
*   **Command**: 
    ```bash
    xvfb-run python -m tool_server.mcp.server --port 6060
    ```
*   **Why so slow?**:
    This step is the primary bottleneck. The process involves:
    1.  **Python Interpreter Startup**: Loading the Python runtime.
    2.  **Heavy Library Imports**: Importing massive libraries like `langchain`, `pydantic`, `numpy`, and potentially `playwright` or `selenium` dependencies. On the limited hardware resources of a micro-VM (often 1 vCPU / small RAM), parsing and loading these Python modules is CPU-bound and slow.
    3.  **X11 Display Initialization**: `xvfb-run` initializes a virtual X server to support headless browser tools. This adds overhead.
    4.  **Tool Registration**: The server iterates through available tools, initializing classes and validating schemas.

### Step 5: Health Check Polling (Backend Wait)
*   **Action**: The backend enters a loop in `agent.py`, pinging the sandbox URL (e.g., `http://...:6060/health`) every 0.1s.
*   **Status Updates**: It emits `mcp_waiting` events to the frontend every 10-12 seconds to keep the HTTP connection alive.
*   **Completion**: Once the Python process binds port 6060 and answers HTTP, the wait ends.

## 3. Latency Breakdown

| Phase | Estimated Time | Cause |
|-------|----------------|-------|
| Request & Auth | < 1s | Network overhead |
| VM Allocation | 2 - 5s | Cloud provider provisioning (E2B) |
| Script Execution | < 1s | Bash script execution |
| **MCP Server Init** | **80 - 90s** | **Python imports & X11 startup on limited vCPU** |
| Total | **~90s** | |

## 4. Addressing the "80+ Minutes" Confusion

In the test logs, you noticed:
```
⏳ Waiting for MCP... (86s)
```
This indicates **86 seconds** (approx 1.5 minutes), not 80 minutes. While 1.5 minutes is long for a user to wait, it is within the realm of possibility for cold-starting a heavy Python application on a micro-instance.

### Potential Optimizations
To reduce this time in the future:
1.  **Pre-baked Imports**: Use a custom Docker image where Python is "warmed up" or compiled.
2.  **Lazy Loading**: Modify `tool_server` to lazy-import heavy libraries (like `langchain` components) only when tools are actually called, rather than at startup.
3.  **Resource Upgrade**: Increase the CPU/RAM allocation for the sandbox template in E2B settings.
