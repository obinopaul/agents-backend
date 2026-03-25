# Understanding Sandbox URLs: VS Code, Codex & MCP

A practical guide to how sandbox URLs work and how to use them.

## Quick Reference

| Service | Port | URL Pattern | Purpose |
|---------|------|-------------|---------|
| VS Code | 9000 | `https://{e2b_id}-9000.e2b.dev` | View/edit code in browser |
| MCP Server | 6060 | `https://{e2b_id}-6060.e2b.dev` | Agent tool operations |
| Codex SSE | 1324 | `https://{e2b_id}-1324.e2b.dev` | AI coding assistant streaming |

## What Are These URLs?

When you create a sandbox, E2B provisions a remote container with services running on specific ports. These services are:

### 📺 VS Code (Port 9000)
- **Browser-based IDE** where you can see your agent writing code in real-time
- Open the URL and watch as the agent creates files, edits code, runs commands
- Works like a window into the agent's workspace

### 🔧 MCP Server (Port 6060)
- **Internal tool server** that provides capabilities to the agent
- Powers tools like: `Write`, `Read`, `Bash`, `ApplyPatch`, `SlideWrite`
- You don't open this URL - the agent uses it internally

### 🤖 Codex SSE (Port 1324)
- **AI coding assistant** that can be delegated complex tasks
- Streams events (thinking, tool calls, results) back to your agent
- Requires Codex credentials to be configured

## The Two Types of Sandbox IDs

This is important to understand:

### Your Application's `sandbox_id`
```
"test-session-20260104133500"  or  "user-123-thread-456"
```
- **You create this** based on your conversation's `thread_id`
- Stored in your database
- Used to look up sandboxes

### E2B's `provider_sandbox_id`
```
"f7d8e9a0-1234-5678-abcd-ef1234567890"
```
- **E2B creates this** when you provision a sandbox
- Used to generate the actual URLs
- You get this from the E2B SDK

### How They Connect

```
Your Code                    Database                      E2B
─────────                    ────────                      ───
thread_id ────────────────→ sandbox_id ───────────────→ provider_sandbox_id
"my-chat-123"                "my-chat-123"                 "f7d8e9a0..."

                                                          ↓
                                                        
URLs Generated:
https://f7d8e9a0-1234-5678-abcd-ef1234567890-9000.e2b.dev  (VS Code)
https://f7d8e9a0-1234-5678-abcd-ef1234567890-6060.e2b.dev  (MCP)
https://f7d8e9a0-1234-5678-abcd-ef1234567890-1324.e2b.dev  (Codex)
```

## How URLs Are Generated (Code)

In `backend/src/sandbox/sandbox_server/sandboxes/e2b.py`:

```python
async def expose_port(self, port: int) -> str:
    return f"https://{self._sandbox.get_host(port)}"
```

E2B's `get_host(port)` returns: `{e2b_sandbox_id}-{port}.e2b.dev`

## Getting URLs in Your Code

### From Agent Stream Endpoint

When using `/agent/agent/stream`, listen for these SSE events:

```python
# Event: status
if data.get("type") == "vscode_ready":
    vscode_url = data.get("vscode_url")
    print(f"Open VS Code: {vscode_url}")

if data.get("type") == "codex_ready":
    codex_url = data.get("codex_url")
    print(f"Codex available: {codex_url}")

if data.get("type") == "complete":
    # Both URLs also available in completion event
    vscode_url = data.get("vscode_url")
    codex_url = data.get("codex_url")
```

### Manually Exposing Ports

```python
from backend.src.sandbox.agent_sandbox import AgentSandbox

async with AgentSandbox(sandbox_id="my-session") as sandbox:
    # Get URLs
    mcp_url = await sandbox.expose_port(6060)
    vscode_url = await sandbox.expose_port(9000)
    codex_url = await sandbox.expose_port(1324)
    
    print(f"VS Code: {vscode_url}")
```

## Authentication & Access

### E2B Level
- Sandbox creation requires `E2B_API_KEY` (server-side only)
- Anyone with a valid sandbox URL can access it (no password)

### Application Level
- Your app uses JWT tokens for user authentication
- Sandboxes are associated with user IDs in the database
- Access control is enforced by your application logic

### Security Considerations

> ⚠️ **VS Code URLs are public** once generated. Anyone with the link can view the workspace.

For production:
1. Consider enabling code-server password protection
2. Short sandbox timeouts (auto-pause after inactivity)
3. Never expose sandbox URLs in client-side logs

## Troubleshooting

### "VS Code URL doesn't load"

**Sandbox may be paused/deleted:**
```python
# Check sandbox status
from backend.src.sandbox.sandbox_server.db.manager import Sandboxes
sandbox = await Sandboxes.get_sandbox_by_id(sandbox_id)
print(f"Status: {sandbox.status}")  # Should be 'running'
```

**Services still starting:**
- Wait 10-30 seconds after sandbox creation
- Services start in background via `start-services.sh`

### "Codex URL not available"

Codex requires:
1. User has Codex credentials saved (`MCPSetting` with `tool_type=CODEX`)
2. E2B template was built with `sse-http-server` binary
3. `/register-codex` endpoint was called during sandbox init

### "Can't connect after a while"

Sandboxes pause after inactivity (default: ~10 minutes). Resume by:
1. Sending a new message through the agent
2. Calling the sandbox resume API

## Test Script Example

See `backend/tests/live/test_codex_integration.py` for a complete example that:
1. Authenticates with the backend
2. Sends a message to create a sandbox
3. Captures and displays all URLs
4. Shows the VS Code URL prominently for clicking

```bash
python backend/tests/live/test_codex_integration.py
```

## Related Guides

- [Sandbox Guide](./sandbox-guide.md) - General sandbox usage
- [Sandbox Startup Lifecycle](./sandbox-startup-lifecycle.md) - How services start
- [Agent Endpoint](./agent-endpoint.md) - Using the agent stream API
