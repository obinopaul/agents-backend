# Agent & Sandbox Lifecycle Explainer

This document explains exactly how the Agent Stream starts, how it triggers the Sandbox, and how the connection is established. It traces the code execution path from the initial HTTP request to the running agent.

## 1. The Trigger: Agent Stream Endpoint

Everything starts when the frontend sends a POST request to start the agent.

**File**: `backend/app/agent/api/v1/agent.py`

When `POST /agent/agent/stream` is called, it triggers the `stream_agent` function, which immediately returns a `StreamingResponse` wrapping the `_agent_stream_generator`.

```python
# backend/app/agent/api/v1/agent.py

@router.post("/agent/stream")
async def stream_agent(...):
    # ...
    return StreamingResponse(
        _agent_stream_generator(...),
        media_type="text/event-stream"
    )
```

## 2. The Coordinator: `_agent_stream_generator`

This function is the "brain" of the startup process. It keeps the connection open with the user while orchestrating the heavy lifting in the background.

**File**: `backend/app/agent/api/v1/agent.py`

It performs three critical steps:
1.  **Creates the Sandbox** (`Sandboxes.create`)
2.  **Waits for MCP** (The connection handshake)
3.  **Starts the Agent Graph** (`_graph.astream_events`)

```python
# backend/app/agent/api/v1/agent.py

async def _agent_stream_generator(...):
    # 1. Create the Sandbox
    yield _make_event("status", {"type": "sandbox_start", ...})
    sandbox = await Sandboxes.create(...) 
    
    # 2. Wait for MCP Server to be ready
    # This loop pings the sandbox until the tool server responds
    start_time = time.time()
    while True:
        try:
             # Checks http://sandbox-url:6060/health
            if await _check_mcp_health(mcp_url):
                break
        except:
             pass
        
        # KEY: Sends keep-alive events to frontend to prevent timeout
        yield _make_event("status", {"type": "mcp_waiting", ...})
        await asyncio.sleep(0.1)

    # 3. Start the Agent Graph
    async for event in _graph.astream_events(...):
        # Stream chunks back to user
```

## 3. The Sandbox Creation: `E2BSandbox`

When `Sandboxes.create` is called, it delegates to the specific provider (E2B). This is where the virtual machine is allocated.

**File**: `backend/src/sandbox/sandbox_server/sandboxes/e2b.py`

The `create` method allocates the VM and **immediately** kicks off the startup script.

```python
# backend/src/sandbox/sandbox_server/sandboxes/e2b.py

class E2BSandbox(BaseSandbox):
    @classmethod
    async def create(cls, ...):
        # 1. Allocate VM from E2B cloud
        sandbox = await AsyncSandbox.create(...)
        
        # 2. Start Services INSIDE the sandbox
        # Note: It runs in background '&' so Python doesn't block waiting for it
        await sandbox.commands.run(
            "bash /app/start-services.sh &", 
            timeout=30
        )
```

## 4. Inside the Sandbox: `start-services.sh`

This script runs *inside* the newly created remote VM. It is responsible for bringing up the tools.

**File**: `backend/docker/sandbox/start-services.sh`

It starts two main servers:
1.  **Code Server** (VS Code backend)
2.  **MCP Tool Server** (The slow part)

```bash
# backend/docker/sandbox/start-services.sh

# Start MCP tool server in background using tmux
# This command launches the heavy Python process
tmux new-session -d -s mcp-server ... \
    "xvfb-run python -m tool_server.mcp.server --port 6060"
```

**Why the 80s wait?**
The command `python -m tool_server.mcp.server` has to:
1.  Initialize Python interpreter.
2.  Import heavy libraries (`langchain`, `pydantic`, `playwright`, etc.).
3.  Initialize X11 display (`xvfb`) for browser tools.
4.  Bind port 6060.

Until step 4 completes, the **Coordinator** (Step 2) keeps checking `/health` and getting "Connection Refused", causing it to loop and yield `mcp_waiting`.

## 5. Agent Execution: `nodes.py`

Once the wait is over, `agent.py` starts the graph. The execution lands in the `base_node`.

**File**: `backend/src/graph/nodes.py`

The node connects to the now-running sandbox tools.

```python
# backend/src/graph/nodes.py

async def base_node(state, config):
    # 1. Load tools from the remote sandbox
    # It uses the mcp_url we waited for
    tools = await _load_mcp_tools(sandbox_id, mcp_url)
    
    # 2. Bind tools to the LLM
    start_time = time.time()
    agent = create_agent(llm, tools, ...)
    
    # 3. Invoke the LLM
    # This is where it fails if OPENAI_API_KEY is missing!
    response = await agent.ainvoke(...)
```

## Summary of the Flow

1.  **User** -> `POST /stream`
2.  **Backend** (`agent.py`) -> Creates Sandbox (`e2b.py`).
3.  **Sandbox** (`e2b.py`) -> Boots VM -> Runs `bash start-services.sh`.
4.  **Sandbox Script** -> Starts `python tool_server` (Takes ~80s).
5.  **Backend** (`agent.py`) -> Loops "Waiting for MCP..." until port 6060 opens.
6.  **Backend** (`nodes.py`) -> Connects to Port 6060 -> Loads Tools -> Calls LLM.
