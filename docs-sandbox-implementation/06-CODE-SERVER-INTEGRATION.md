# Code-Server (VS Code in Browser) Integration

This document explains how VS Code runs in the browser via code-server.

---

## What is Code-Server?

**code-server** is an open-source project that runs VS Code as a web server. Users access the full VS Code IDE through their browser.

- **Repository**: https://github.com/coder/code-server
- **Website**: https://coder.com/

```
Traditional VS Code:
Desktop App → Local Files

Code-Server:
Browser → HTTP → Code-Server → Remote Files (in sandbox)
```

---

## Why Use Code-Server?

When your AI agent is working in an E2B sandbox:
- Files exist ONLY in the sandbox
- User wants to see/edit those files
- You can't just "open VS Code" on their machine

**Solution**: Run VS Code AS A WEB SERVER inside the sandbox, expose the port.

```
User's Browser
     │
     │ HTTPS
     ▼
https://sandbox-id-9000.e2b.dev
     │
     │ (E2B Port Forwarding)
     ▼
Sandbox:9000 (code-server)
     │
     │ (File System Access)
     ▼
/workspace (user's code)
```

---

## Installation in E2B Template

### In e2b.Dockerfile

```dockerfile
# Install code-server using official script
RUN curl -fsSL https://code-server.dev/install.sh | sh
```

This installs:
- `code-server` binary
- All VS Code dependencies
- Service management scripts

---

## Starting Code-Server

### In docker/sandbox/start-services.sh

```bash
#!/bin/bash

# Start code-server in the background using tmux
echo "Starting code-server on port 9000..."
tmux new-session -d -s code-server-system-never-kill -c /workspace 'code-server \
  --port 9000 \
  --auth none \
  --bind-addr 0.0.0.0:9000 \
  --disable-telemetry \
  --disable-update-check \
  --trusted-origins * \
  --disable-workspace-trust \
  /workspace'
```

### Command Arguments Explained

| Argument | Purpose |
|----------|---------|
| `--port 9000` | Listen on port 9000 |
| `--auth none` | No password required (security via E2B isolation) |
| `--bind-addr 0.0.0.0:9000` | Accept connections from any IP |
| `--disable-telemetry` | Don't send usage data |
| `--disable-update-check` | Don't check for updates |
| `--trusted-origins *` | Allow embedding in any iframe |
| `--disable-workspace-trust` | Skip "trust this folder" dialog |
| `/workspace` | Open this directory |

### Why tmux?

```bash
tmux new-session -d -s code-server-system-never-kill ...
```

- **Background**: `-d` runs detached (doesn't block startup)
- **Named session**: `-s code-server-system-never-kill` for easy identification
- **Persistent**: Survives if SSH disconnects

---

## Exposing the Port

### Backend Configuration

In `src/ii_agent/core/config/ii_agent_config.py`:

```python
class IIAgentConfig(BaseSettings):
    vscode_port: int = Field(default=9000)
```

### Getting the Public URL

In `src/ii_agent/server/socket/command/query_handler.py`:

```python
# When initializing a chat session
vscode_url = await sandbox.expose_port(config.vscode_port)

# This returns something like:
# https://abc123xyz-9000.e2b.dev
```

### How expose_port Works

```python
# In E2B sandbox
async def expose_port(self, port: int) -> str:
    # E2B automatically creates a public HTTPS URL
    return f"https://{self._sandbox.get_host(port)}"
```

E2B handles:
- SSL/TLS termination
- DNS routing
- Port forwarding to the sandbox

---

## Frontend Integration

### Redux State

In `frontend/src/state/slice/workspace.ts`:

```typescript
interface WorkspaceState {
    vscodeUrl: string  // The code-server URL
    browserUrl: string // For web preview (different)
}
```

### Receiving the URL

In `frontend/src/hooks/use-app-events.tsx`:

```typescript
case AgentEvent.AGENT_INITIALIZED: {
    // Backend sends vscode_url when agent starts
    const vscode_url = data.content.vscode_url as string
    if (vscode_url) {
        dispatch(setVscodeUrl(vscode_url))
    }
    break
}
```

### Rendering VS Code

In `frontend/src/app/routes/agent.tsx`:

```tsx
// Get URL from Redux state
const vscodeUrl = useAppSelector(selectVscodeUrl)

// Render as iframe
{vscodeUrl && (
    <iframe
        src={vscodeUrl}
        className="w-full h-full"
        title="VS Code"
    />
)}
```

---

## Complete Data Flow

```
1. User starts chat session
            │
            ▼
2. Backend creates E2B sandbox
            │
            ▼
3. Sandbox runs start-services.sh
   ├── Starts code-server on port 9000
   └── Starts MCP server on port 6060
            │
            ▼
4. Backend gets vscode_url:
   vscode_url = await sandbox.expose_port(9000)
   # Returns: https://abc123-9000.e2b.dev
            │
            ▼
5. Backend sends AGENT_INITIALIZED event:
   {
     "type": "AGENT_INITIALIZED",
     "content": {
       "vscode_url": "https://abc123-9000.e2b.dev"
     }
   }
            │
            ▼
6. Frontend receives event
   dispatch(setVscodeUrl(vscode_url))
            │
            ▼
7. Frontend renders iframe
   <iframe src="https://abc123-9000.e2b.dev" />
            │
            ▼
8. User sees VS Code in their browser!
```

---

## Sandbox Status Handling

### Paused Sandbox Problem

E2B sandboxes pause after inactivity to save resources. When paused:
- The VM is hibernated
- Ports are no longer accessible
- iframe shows connection error

### Solution: Wake-Up Flow

In `frontend/src/app/routes/agent.tsx`:

```tsx
// Check if sandbox is paused
{vscodeUrl && 
 isE2bLink(vscodeUrl) && 
 !isSandboxIframeAwake && 
 !isRunning ? (
    <AwakeMeUpScreen
        isLoading={isAwakeLoading}
        onAwakeClick={handleAwakeClick}
    />
) : (
    <iframe src={vscodeUrl} />
)}
```

### Wake-Up Handler

```typescript
const handleAwakeClick = async () => {
    setIsAwakeLoading(true)
    
    // Call backend to resume sandbox
    await socketService.send({
        type: "WAKE_UP_SANDBOX",
        session_id: sessionId
    })
    
    // Wait for sandbox to be ready
    await waitForSandboxReady()
    
    setIsSandboxIframeAwake(true)
    setIsAwakeLoading(false)
}
```

---

## Configuration Options

### Custom Settings

You can customize code-server with a config file:

```yaml
# ~/.config/code-server/config.yaml
bind-addr: 0.0.0.0:9000
auth: none
cert: false
```

### Extensions Pre-installation

Add extensions to your Dockerfile:

```dockerfile
# Install extensions during build
RUN code-server --install-extension ms-python.python
RUN code-server --install-extension esbenp.prettier-vscode
```

### Custom Theme/Settings

```dockerfile
# Copy VS Code settings
COPY settings.json /home/pn/.local/share/code-server/User/settings.json
```

Example settings.json:
```json
{
    "workbench.colorTheme": "One Dark Pro",
    "editor.fontSize": 14,
    "editor.tabSize": 2,
    "editor.formatOnSave": true
}
```

---

## Security Considerations

### Why --auth none is OK

Normally, code-server requires a password. Here it's disabled because:

1. **E2B Isolation** - Each sandbox is isolated per session
2. **Unique URLs** - Random sandbox IDs are unpredictable
3. **Short-lived** - Sandboxes auto-delete after timeout
4. **HTTPS** - E2B provides SSL encryption

### If You Need Authentication

```bash
# Set password via environment variable
export PASSWORD="your-password"
code-server --auth password
```

Or use code-server's token auth:
```bash
code-server --auth password --hashed-password='$argon2i$...'
```

---

## Implementing in Your Project

### 1. Add to Dockerfile

```dockerfile
# Install code-server
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Optional: Pre-install extensions
RUN code-server --install-extension ms-python.python
```

### 2. Create Startup Script

```bash
#!/bin/bash
# start-services.sh

# Start code-server
code-server \
    --port 9000 \
    --auth none \
    --bind-addr 0.0.0.0 \
    /workspace &

echo "Code-server started on port 9000"
```

### 3. Expose Port from Backend

```python
async def get_vscode_url(sandbox_id: str) -> str:
    sandbox = await sandbox_service.get_sandbox(sandbox_id)
    return await sandbox.expose_port(9000)
```

### 4. Display in Frontend

```tsx
function CodeEditor({ sandboxId }) {
    const [vscodeUrl, setVscodeUrl] = useState(null)
    
    useEffect(() => {
        async function getUrl() {
            const url = await api.getVscodeUrl(sandboxId)
            setVscodeUrl(url)
        }
        getUrl()
    }, [sandboxId])
    
    if (!vscodeUrl) return <div>Loading editor...</div>
    
    return (
        <iframe 
            src={vscodeUrl}
            style={{ width: '100%', height: '100%', border: 'none' }}
        />
    )
}
```

---

## Alternative: OpenVSCode Server

If you prefer, you can use **OpenVSCode Server** (Microsoft's official version):

```dockerfile
# Instead of code-server
RUN curl -fsSL https://github.com/gitpod-io/openvscode-server/releases/download/openvscode-server-v1.85.0/openvscode-server-v1.85.0-linux-x64.tar.gz | tar xz
```

The interface is nearly identical to code-server.

---

## Troubleshooting

### iframe Blank/Not Loading

1. **Check port is exposed**: `curl https://sandbox-id-9000.e2b.dev`
2. **Check code-server running**: `pgrep code-server`
3. **Check logs**: `tmux attach -t code-server-system-never-kill`

### Connection Refused

1. **Check bind address**: Must be `0.0.0.0`, not `127.0.0.1`
2. **Check firewall**: E2B shouldn't block, but custom firewalls might

### Mixed Content Error

Make sure you're using HTTPS URLs. E2B provides HTTPS automatically.

### iframe Sandbox Restrictions

Some browsers restrict iframe functionality. You may need:

```tsx
<iframe
    src={vscodeUrl}
    allow="clipboard-read; clipboard-write"
    sandbox="allow-same-origin allow-scripts allow-forms"
/>
```
