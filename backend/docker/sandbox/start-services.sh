#!/bin/bash
set -e

# If running as root, use gosu to re-execute as pn user
# IMPORTANT: Preserve API keys when switching users (needed for Graphiti, etc.)
if [ "$(id -u)" = "0" ]; then
    echo "Running as root, switching to pn user with gosu..."
    # Export API keys explicitly so they're preserved through gosu
    exec gosu pn env OPENAI_API_KEY="${OPENAI_API_KEY:-}" bash "$0" "$@"
fi

# Set up environment
export HOME=/home/pn
export PATH="/home/pn/.bun/bin:/app/agents_backend/.venv/bin:$PATH"
# Set npm cache to a directory that's writable by all users
export npm_config_cache=/home/pn/.npm

# Write API keys to a file so tmux sessions can source them
# (tmux new-session doesn't inherit env vars from parent shell)
echo "# Sandbox environment variables" > /tmp/sandbox_env
if [ -n "$OPENAI_API_KEY" ]; then
    echo "export OPENAI_API_KEY=\"$OPENAI_API_KEY\"" >> /tmp/sandbox_env
    echo "OPENAI_API_KEY found and written to /tmp/sandbox_env"
else
    echo "WARNING: OPENAI_API_KEY not set - Graphiti will fail!"
fi
chmod 644 /tmp/sandbox_env

# Production configuration
MCP_SERVER_PORT=${MCP_SERVER_PORT:-6060}
CODE_SERVER_PORT=${CODE_SERVER_PORT:-9000}
LATEX_EDITOR_PORT=${LATEX_EDITOR_PORT:-9001}
DESIGN_MCP_PORT=${DESIGN_MCP_PORT:-6002}
EXCALIDRAW_PORT=${EXCALIDRAW_PORT:-6003}
GRAPHITI_MCP_PORT=${GRAPHITI_MCP_PORT:-8500}
GRAPHITI_FALKORDB_PORT=${GRAPHITI_FALKORDB_PORT:-6380}
MAX_RETRIES=3
RETRY_DELAY=2

# Create workspace directory if it doesn't exist
mkdir -p /workspace
cd /workspace

# Runtime permission fix for multi-user access
# E2B runs SDK commands as 'user' (uid=1001), but services run as 'pn' (uid=1000)
# E2B sets HOME=/home/user, so npm cache uses /home/user/.npm (correct)
# But 'user' needs to access /home/pn/.bun for bun commands
chmod 777 /workspace 2>/dev/null || true
chmod 755 /home/pn 2>/dev/null || true
chmod -R 755 /home/pn/.bun 2>/dev/null || true
mkdir -p /home/user 2>/dev/null && chmod 755 /home/user 2>/dev/null || true

# Function to check if a service is running
check_service() {
    local service_name="$1"
    local pattern="$2"
    if pgrep -f "$pattern" > /dev/null; then
        echo "✓ $service_name is running"
        return 0
    else
        echo "✗ $service_name failed to start"
        return 1
    fi
}

# Function to wait for port to be available
wait_for_port() {
    local port="$1"
    local max_attempts="${2:-30}"
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if nc -z localhost "$port" 2>/dev/null || curl -s "http://localhost:$port/health" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    return 1
}

# Start the MCP tool server in the background
echo "Starting MCP tool server on port $MCP_SERVER_PORT..."
tmux new-session -d -s mcp-server-system-never-kill -c /workspace \
    "WORKSPACE_DIR=/workspace PYTHONPATH=/app/agents_backend/src xvfb-run python -m tool_server.mcp.server --port $MCP_SERVER_PORT 2>&1 | tee /tmp/mcp-server.log"

# Start code-server in the background
echo "Starting code-server on port $CODE_SERVER_PORT..."
tmux new-session -d -s code-server-system-never-kill -c /workspace \
    "code-server \
      --port $CODE_SERVER_PORT \
      --auth none \
      --bind-addr 0.0.0.0:$CODE_SERVER_PORT \
      --disable-telemetry \
      --disable-update-check \
      --trusted-origins '*' \
      --disable-workspace-trust \
      /workspace 2>&1 | tee /tmp/code-server.log"

# Start LaTeX Editor in the background (for Documents mode)
# Pre-built React app served via Python http.server - reliable and already available
echo "Starting LaTeX Editor on port $LATEX_EDITOR_PORT..."
tmux new-session -d -s latex-editor-system-never-kill -c /app/latex-editor \
    "python -m http.server $LATEX_EDITOR_PORT --bind 0.0.0.0 2>&1 | tee /tmp/latex-editor.log"

# Start Design MCP Server in the background (for Design/Draw.io mode)
# Pre-built TypeScript MCP server with embedded HTTP server for browser viewing
# Uses embed.diagrams.net (official draw.io embed) - no sign-up required
# Port 6002 serves both API endpoints AND the browser viewer
echo "Starting Design MCP Server on port $DESIGN_MCP_PORT..."
tmux new-session -d -s design-mcp-system-never-kill -c /app/design-mcp \
    "PORT=$DESIGN_MCP_PORT node dist/index.js 2>&1 | tee /tmp/design-mcp.log"

# Start Excalidraw Canvas Server in the background (for whiteboard/freeform diagram mode)
# Pre-built TypeScript Express + WebSocket server with embedded React frontend
# Uses @excalidraw/excalidraw package for hand-drawn style diagrams and whiteboarding
# Port 6003 serves both REST API endpoints AND the browser viewer (WebSocket real-time sync)
echo "Starting Excalidraw Canvas Server on port $EXCALIDRAW_PORT..."
tmux new-session -d -s excalidraw-system-never-kill -c /app/excalidraw \
    "PORT=$EXCALIDRAW_PORT node dist/server.js 2>&1 | tee /tmp/excalidraw.log"

# Start FalkorDB (Redis with graph module) in the background (for Knowledge Graph mode)
# Pre-installed Redis server with FalkorDB module - provides graph database capabilities
# Port 6379 is used for Redis protocol connections from Graphiti MCP server
if [ -f /var/lib/falkordb/bin/falkordb.so ]; then
    echo "Starting FalkorDB on port $GRAPHITI_FALKORDB_PORT..."
    tmux new-session -d -s falkordb-system-never-kill -c /var/lib/falkordb \
        "redis-server --loadmodule /var/lib/falkordb/bin/falkordb.so --protected-mode no --bind 0.0.0.0 --port $GRAPHITI_FALKORDB_PORT --dir /var/lib/falkordb/data 2>&1 | tee /tmp/falkordb.log"
    
    # Wait for FalkorDB to be ready before starting Graphiti MCP
    sleep 2
    
    # Start Graphiti MCP Server in the background (for Knowledge Graph mode)
    # Pre-built Python MCP HTTP server providing knowledge graph tools
    # Port 8500 serves fastmcp HTTP endpoints at /mcp/ and /health
    # OPENAI_API_KEY is required for LLM/embedder operations (passed from sandbox env)
    if [ -d /app/graphiti-mcp ]; then
        echo "Starting Graphiti MCP Server on port $GRAPHITI_MCP_PORT..."
        # Source env vars from file (tmux doesn't inherit parent env vars)
        tmux new-session -d -s graphiti-mcp-system-never-kill -c /app/graphiti-mcp \
            "source /tmp/sandbox_env 2>/dev/null; FALKORDB_URI=redis://localhost:$GRAPHITI_FALKORDB_PORT MCP_SERVER_HOST=0.0.0.0 MCP_SERVER_PORT=$GRAPHITI_MCP_PORT UV_PYTHON_DOWNLOADS=never uv run --no-sync main.py --transport http --port $GRAPHITI_MCP_PORT 2>&1 | tee /tmp/graphiti-mcp.log"
    else
        echo "Graphiti MCP Server not installed, skipping..."
    fi
else
    echo "FalkorDB module not installed, skipping Graphiti services..."
fi

# Wait for services to start
sleep 3

# Check if processes are running
echo ""
echo "Checking service status..."
echo "=========================="

mcp_running=false
code_server_running=false
latex_editor_running=false
design_mcp_running=false
excalidraw_running=false

if check_service "MCP Tool Server" "tool_server.mcp.server"; then
    mcp_running=true
fi

if check_service "Code-Server" "code-server"; then
    code_server_running=true
fi

if check_service "LaTeX Editor" "http.server $LATEX_EDITOR_PORT"; then
    latex_editor_running=true
fi

if check_service "Design MCP Server" "node dist/index.js"; then
    design_mcp_running=true
fi

if check_service "Excalidraw Canvas Server" "dist/server.js"; then
    excalidraw_running=true
fi

graphiti_running=false
if check_service "Graphiti MCP Server" "graphiti-mcp"; then
    graphiti_running=true
fi

echo ""
echo "=========================="
echo "Sandbox Ready!"
echo ""
echo "Services:"
echo "  - MCP Tool Server: http://localhost:$MCP_SERVER_PORT"
echo "  - Code-Server: http://localhost:$CODE_SERVER_PORT"
echo "  - LaTeX Editor: http://localhost:$LATEX_EDITOR_PORT"
echo "  - Design MCP Server: http://localhost:$DESIGN_MCP_PORT"
echo "  - Excalidraw Canvas: http://localhost:$EXCALIDRAW_PORT"
echo "  - Graphiti MCP (Knowledge Graph): http://localhost:$GRAPHITI_MCP_PORT"
echo "=========================="

# If both services failed, exit with error
if [ "$mcp_running" = false ] && [ "$code_server_running" = false ]; then
    echo "ERROR: All services failed to start"
    exit 1
fi

# Keep the container running by waiting indefinitely
# Using tail -f /dev/null is more reliable than 'wait' for this purpose
tail -f /dev/null

