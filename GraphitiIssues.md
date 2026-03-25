# Graphiti MCP Server - OpenAI API Key Issue

## Problem Summary

The Graphiti MCP server running inside E2B sandboxes returns a `401 Unauthorized` error when executing tools that require OpenAI API access (such as `mcp_graphiti_search_nodes` and `mcp_graphiti_search_memory_facts`). The error message states:

```
Error code: 401 - {'error': {'message': "You didn't provide an API key. You need to provide your API key in an Authorization header using Bearer auth..."}}
```

**The core issue:** The `OPENAI_API_KEY` environment variable is not reaching the Graphiti process inside the E2B sandbox, despite being configured in multiple places and passed through various mechanisms.

---

## Data Flow (Where the Problem Exists)

The API key must flow through this chain:

```
backend/.env → Settings (conf.py) → SandboxConfig → E2B Sandbox Creation → 
    → sandbox.commands.run() → start-services.sh → tmux session → Graphiti process
```

**Confirmed working:**
- ✅ `backend/.env` contains `OPENAI_API_KEY`
- ✅ `settings.OPENAI_API_KEY` loads correctly
- ✅ `SandboxConfig.openai_api_key` is populated
- ✅ Backend logs show "Passing OPENAI_API_KEY to sandbox"

**Confirmed broken:**
- ❌ Inside the sandbox, `/tmp/sandbox_env` file is created but contains NO API key
- ❌ The Graphiti process environment shows `OPENAI_API_KEY=` (empty)
- ❌ Graphiti fails with 401 when calling OpenAI embeddings

---

## Relevant Files to Investigate

### 1. Backend Configuration

#### `backend/.env` (Lines 114-116)
```env
OPENAI_API_KEY='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'
OPENAI_MODEL="gpt-5.2"
OPENAI_BASE_URL='https://api.openai.com/v1'
```

#### `backend/core/conf.py` (Line ~303)
```python
OPENAI_API_KEY: str = ''
```

---

### 2. Sandbox Configuration

#### `backend/src/sandbox/sandbox_server/config.py` (Lines 55-64)
```python
# API keys to pass to sandbox (for services like Graphiti that need LLM access)
data.setdefault("openai_api_key", getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY"))
```

---

### 3. E2B Sandbox Creation (Critical File)

#### `backend/src/sandbox/sandbox_server/sandboxes/e2b.py` (Lines 94-145)
```python
# Build environment variables to pass to sandbox
sandbox_envs = {}
if config.openai_api_key:
    sandbox_envs["OPENAI_API_KEY"] = config.openai_api_key
    logger.info(f"Passing OPENAI_API_KEY to sandbox (key starts with: {config.openai_api_key[:20]}...)")
else:
    logger.warning("No OPENAI_API_KEY found in config - Graphiti will fail!")

sandbox = await AsyncSandbox.create(
    sandbox_template_id if sandbox_template_id else config.e2b_template_id,
    api_key=config.e2b_api_key,
    metadata=metadata,
    envs=sandbox_envs if sandbox_envs else None,  # Passed to E2B
)

# Start services - THIS IS WHERE THE ISSUE LIKELY IS
try:
    logger.info(f"Starting services in sandbox {sandbox_id}")
    
    # Build environment variable exports for the command
    env_exports = ""
    if sandbox_envs:
        # Create exports inside the bash -c string
        env_parts = [f'export {k}="{v}"' for k, v in sandbox_envs.items()]
        env_exports = "; ".join(env_parts) + "; "
    
    # Use bash -c to ensure env vars are in the same shell as the script
    cmd = f"bash -c '{env_exports}/app/start-services.sh' &"
    logger.info(f"Running start command with {len(sandbox_envs)} env vars")
    
    await sandbox.commands.run(cmd, timeout=30)
except Exception as e:
    logger.warning(f"Service startup command returned: {e}")
```

---

### 4. E2B Template Startup Script

#### `backend/docker/sandbox/start-services.sh` (Lines 1-30)
```bash
#!/bin/bash
set -e

# If running as root, use gosu to re-execute as pn user
if [ "$(id -u)" = "0" ]; then
    echo "Running as root, switching to pn user with gosu..."
    exec gosu pn env OPENAI_API_KEY="${OPENAI_API_KEY:-}" bash "$0" "$@"
fi

# Set up environment
export HOME=/home/pn
export PATH="/home/pn/.bun/bin:/app/agents_backend/.venv/bin:$PATH"
export npm_config_cache=/home/pn/.npm

# Write API keys to a file so tmux sessions can source them
echo "# Sandbox environment variables" > /tmp/sandbox_env
if [ -n "$OPENAI_API_KEY" ]; then
    echo "export OPENAI_API_KEY=\"$OPENAI_API_KEY\"" >> /tmp/sandbox_env
    echo "OPENAI_API_KEY found and written to /tmp/sandbox_env"
else
    echo "WARNING: OPENAI_API_KEY not set - Graphiti will fail!"
fi
chmod 644 /tmp/sandbox_env
```

#### `backend/docker/sandbox/start-services.sh` (Lines 137-141) - Graphiti Startup
```bash
if [ -d /app/graphiti-mcp ]; then
    echo "Starting Graphiti MCP Server on port $GRAPHITI_MCP_PORT..."
    # Source env vars from file (tmux doesn't inherit parent env vars)
    tmux new-session -d -s graphiti-mcp-system-never-kill -c /app/graphiti-mcp \
        "source /tmp/sandbox_env 2>/dev/null; FALKORDB_URI=redis://localhost:$GRAPHITI_FALKORDB_PORT MCP_SERVER_HOST=0.0.0.0 MCP_SERVER_PORT=$GRAPHITI_MCP_PORT UV_PYTHON_DOWNLOADS=never uv run --no-sync main.py --transport http --port $GRAPHITI_MCP_PORT 2>&1 | tee /tmp/graphiti-mcp.log"
fi
```

---

### 5. Docker Configuration

#### `docker-compose.yml` (Lines 40-41)
```yaml
volumes:
  - ./deploy/backend/docker-compose/.env.server:/agents_backend/backend/.env
```

#### `deploy/backend/docker-compose/.env.server` (Line 42)
```env
OPENAI_API_KEY='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'
```

---

## Docker Commands to Investigate

### Check Backend Application Logs
```bash
# Check sandbox creation logs (look for OPENAI_API_KEY passing)
docker exec agents_backend_server sh -c "grep -E 'OPENAI|Passing|env vars|sandbox' /var/log/agents_backend/agents_backend_server.log | tail -30"

# Check for errors during startup
docker exec agents_backend_server sh -c "grep -i 'error\|exception\|traceback' /var/log/agents_backend/agents_backend_server.log | tail -20"

# Check the actual command being run
docker exec agents_backend_server sh -c "grep 'Running start command' /var/log/agents_backend/agents_backend_server.log | tail -10"
```

### Check Container Code Matches Local Code
```bash
# Verify the e2b.py has the latest fixes
docker exec agents_backend_server sh -c "grep -A20 'Build environment variable' /agents_backend/backend/src/sandbox/sandbox_server/sandboxes/e2b.py"

# Check if env_exports logic exists
docker exec agents_backend_server sh -c "grep -c 'env_exports' /agents_backend/backend/src/sandbox/sandbox_server/sandboxes/e2b.py"
```

### Check Environment Variables in Container
```bash
# Check if .env is mounted correctly
docker exec agents_backend_server sh -c "grep OPENAI_API_KEY /agents_backend/backend/.env | head -1"

# Check settings loading
docker exec agents_backend_server python -c "from backend.core.conf import settings; print(f'OPENAI_API_KEY set: {bool(settings.OPENAI_API_KEY)}')"
```

---

## Inside the E2B Sandbox - Files to Check

Access the sandbox VS Code terminal at `https://9000-<sandbox-id>.e2b.app` and run:

### Check Environment Variables
```bash
# Check if OPENAI_API_KEY is in current environment
echo $OPENAI_API_KEY
env | grep OPENAI

# Check the sandbox_env file that should contain the key
cat /tmp/sandbox_env

# Check if the file has the key
grep OPENAI_API_KEY /tmp/sandbox_env
```

### Check Graphiti Process Environment
```bash
# Find the Graphiti process and check its environment
ps aux | grep graphiti

# Get the PID and check its environment
cat /proc/<PID>/environ | tr '\0' '\n' | grep OPENAI
```

### Check start-services.sh in Template
```bash
# Verify the script has the env writing logic
cat /app/start-services.sh | grep -A10 "sandbox_env"

# Check the gosu line
cat /app/start-services.sh | grep gosu
```

### Check Graphiti Logs
```bash
# Check Graphiti MCP server logs for errors
cat /tmp/graphiti-mcp.log | tail -50

# Look for API key related errors
grep -i "api\|key\|401\|auth" /tmp/graphiti-mcp.log
```

---

## Key Questions to Answer

1. **Is the E2B `envs` parameter working?** - When sandbox is created with `envs={"OPENAI_API_KEY": "..."}`, does the sandbox shell have this variable?

2. **Is `sandbox.commands.run()` preserving env vars?** - When running a command with env vars, does the subshell inherit them?

3. **Does the bash -c wrapper work with background processes?** - Does `bash -c 'export X=Y; cmd' &` properly export to the command?

4. **Is `gosu` preserving the environment?** - When switching from root to pn user, does `gosu pn env OPENAI_API_KEY="$OPENAI_API_KEY" bash...` work?

5. **Is tmux inheriting parent environment?** - When `tmux new-session` runs, does the new session have access to exported variables?

6. **Is the E2B template up to date?** - Does the template contain the latest `start-services.sh` with the /tmp/sandbox_env file logic?

---

## Error Evidence

The Graphiti process was started with an empty API key:
```
ps aux output shows:
bash -c OPENAI_API_KEY= FALKORDB_URI=redis://localhost:6380 ... uv run main.py
```

The `/tmp/sandbox_env` file contains only:
```
# Sandbox environment variables
```
(No OPENAI_API_KEY line)

---

## Files Summary

| File | Path | Purpose |
|------|------|---------|
| Backend .env | `backend/.env` | Source of OPENAI_API_KEY |
| Docker .env.server | `deploy/backend/docker-compose/.env.server` | Docker mounted env |
| Settings | `backend/core/conf.py` | Pydantic settings loader |
| Sandbox Config | `backend/src/sandbox/sandbox_server/config.py` | Sandbox config with API key |
| E2B Sandbox | `backend/src/sandbox/sandbox_server/sandboxes/e2b.py` | Creates sandbox, passes env vars |
| Start Script | `backend/docker/sandbox/start-services.sh` | Starts services in sandbox (in E2B template) |
| E2B Dockerfile | `backend/e2b.Dockerfile` | Builds the E2B template |
| Docker Compose | `docker-compose.yml` | Mounts env files |
