#!/bin/bash
set -e

# If running as root, use gosu to re-execute as pn user
if [ "$(id -u)" = "0" ]; then
    echo "Running as root, switching to pn user with gosu..."
    exec gosu pn bash "$0" "$@"
fi

# Set up environment
export HOME=/home/pn
export PATH="/home/pn/.bun/bin:/app/agents_backend/.venv/bin:$PATH"

# Production configuration
MCP_SERVER_PORT=${MCP_SERVER_PORT:-6060}
CODE_SERVER_PORT=${CODE_SERVER_PORT:-9000}
MAX_RETRIES=3
RETRY_DELAY=2

# Create workspace directory if it doesn't exist
mkdir -p /workspace
cd /workspace

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

# Wait for services to start
sleep 3

# Check if processes are running
echo ""
echo "Checking service status..."
echo "=========================="

mcp_running=false
code_server_running=false

if check_service "MCP Tool Server" "tool_server.mcp.server"; then
    mcp_running=true
fi

if check_service "Code-Server" "code-server"; then
    code_server_running=true
fi

echo ""
echo "=========================="
echo "Sandbox Ready!"
echo ""
echo "Services:"
echo "  - MCP Tool Server: http://localhost:$MCP_SERVER_PORT"
echo "  - Code-Server: http://localhost:$CODE_SERVER_PORT"
echo "=========================="

# If both services failed, exit with error
if [ "$mcp_running" = false ] && [ "$code_server_running" = false ]; then
    echo "ERROR: All services failed to start"
    exit 1
fi

# Keep the container running by waiting indefinitely
# Using tail -f /dev/null is more reliable than 'wait' for this purpose
tail -f /dev/null

