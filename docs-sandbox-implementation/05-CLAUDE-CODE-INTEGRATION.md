# Claude Code Integration - Deep Dive

This document explains exactly how Claude Code (Anthropic's AI coding CLI) is integrated and how you can use it.

---

## What is Claude Code?

**Claude Code** is Anthropic's official CLI tool for AI-assisted coding. It's essentially Claude with:
- File system access
- Shell command execution
- Code understanding
- Autonomous coding capabilities

Think of it as "Claude as a coding assistant that can actually edit your files."

```bash
# Example usage (if installed)
claude "Fix the bug in app.py"
# Claude reads app.py, understands the bug, edits the file
```

---

## How Claude Code is Installed in the Sandbox

### Step 1: NPM Global Install

In `e2b.Dockerfile`:

```dockerfile
RUN npm install -g @anthropic-ai/claude-code
```

This installs the official `claude` CLI command globally.

### Step 2: Pre-configured Settings

```dockerfile
COPY docker/sandbox/claude_template.json /home/pn/.claude.json
```

The `claude_template.json` contains:
```json
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true
}
```

This skips the initial setup dialogs that would normally require user interaction.

### Step 3: Credentials Directory

```dockerfile
RUN mkdir -p /home/pn/.claude
```

This is where Claude Code stores its credentials.

---

## The Authentication Flow

Claude Code needs OAuth tokens to authenticate with Anthropic. Here's the flow:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                       │
│                                                                             │
│  1. User clicks "Connect Claude Code"                                       │
│                    │                                                        │
│                    ▼                                                        │
│  2. Frontend generates PKCE code_verifier                                   │
│     (stored in sessionStorage)                                              │
│                    │                                                        │
│                    ▼                                                        │
│  3. Frontend opens Anthropic OAuth URL in new window:                       │
│     https://claude.ai/oauth/authorize?                                      │
│       client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e                       │
│       redirect_uri=https://console.anthropic.com/oauth/code/callback       │
│       scope=user:inference user:profile                                     │
│       code_challenge=<sha256(verifier)>                                    │
│       code_challenge_method=S256                                           │
│                    │                                                        │
│                    ▼                                                        │
│  4. User logs into claude.ai and authorizes                                 │
│                    │                                                        │
│                    ▼                                                        │
│  5. Anthropic redirects to callback with authorization_code                 │
│     (User copies the code)                                                  │
│                    │                                                        │
│                    ▼                                                        │
│  6. User pastes code into frontend input                                    │
│                    │                                                        │
│                    ▼                                                        │
│  7. Frontend sends to backend: POST /user-settings/mcp/claude-code         │
│     Body: { "authorization_code": "<code>#<verifier>" }                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                         │
│                                                                              │
│  8. Backend exchanges code for tokens:                                       │
│     POST https://console.anthropic.com/v1/oauth/token                       │
│     {                                                                        │
│       "code": "<authorization_code>",                                        │
│       "grant_type": "authorization_code",                                    │
│       "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",                  │
│       "redirect_uri": "https://console.anthropic.com/oauth/code/callback", │
│       "code_verifier": "<verifier>"                                          │
│     }                                                                        │
│                    │                                                         │
│                    ▼                                                         │
│  9. Anthropic returns tokens:                                                │
│     { "access_token": "...", "refresh_token": "...", "expires_in": 3600 }   │
│                    │                                                         │
│                    ▼                                                         │
│  10. Backend stores tokens in database (encrypted)                           │
│      as ClaudeCodeMetadata                                                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    WHEN SANDBOX IS CREATED                                   │
│                                                                              │
│  11. Sandbox Service retrieves user's Claude Code tokens                     │
│                    │                                                         │
│                    ▼                                                         │
│  12. Writes credentials to sandbox:                                          │
│      sandbox.write_file(                                                     │
│        "~/.claude/.credentials.json",                                        │
│        {                                                                     │
│          "claudeAiOauth": {                                                  │
│            "accessToken": "...",                                             │
│            "refreshToken": "...",                                            │
│            "expiresAt": 1234567890000,                                       │
│            "scopes": ["user:inference", "user:profile"]                      │
│          }                                                                   │
│        }                                                                     │
│      )                                                                       │
│                    │                                                         │
│                    ▼                                                         │
│  13. Claude Code CLI in sandbox can now authenticate!                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Code

### Models (mcp_settings/models.py)

```python
class ClaudeCodeMetadata(MCPMetadata):
    """Metadata specific to Claude Code MCP tool."""
    
    tool_type: str = Field(default="claude_code")
    
    auth_json: Dict[str, Any] = Field(
        ..., 
        description="Claude Code authentication JSON"
    )
    # Format:
    # {
    #   "claudeAiOauth": {
    #     "accessToken": "...",
    #     "refreshToken": "...",
    #     "expiresAt": 1234567890000,
    #     "scopes": ["user:inference", "user:profile"]
    #   }
    # }
    
    store_path: str = Field(
        default="~/.claude",
        description="Path where Claude Code stores its data"
    )
```

### OAuth Exchange (mcp_settings/views.py)

```python
async def exchange_code_for_tokens(code: str, verifier: str) -> dict:
    """Exchange authorization code for tokens."""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://console.anthropic.com/v1/oauth/token",
            headers={"Content-Type": "application/json"},
            json={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
                "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
                "code_verifier": verifier,
            },
        )
    
    if not response.is_success:
        raise HTTPException(status_code=400, detail="Token exchange failed")
    
    data = response.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"],
    }


@router.post("/claude-code")
async def configure_claude_code_mcp(request: ClaudeCodeConfigConfigure):
    """Configure Claude Code MCP."""
    
    # Parse authorization_code#verifier
    code, verifier = request.authorization_code.split("#")
    
    # Exchange for tokens
    tokens = await exchange_code_for_tokens(code, verifier)
    
    # Build credentials in Claude Code format
    auth_json = {
        "claudeAiOauth": {
            "accessToken": tokens["access_token"],
            "refreshToken": tokens["refresh_token"],
            "expiresAt": int(time.time() * 1000) + tokens["expires_in"] * 1000,
            "scopes": ["user:inference", "user:profile"],
        }
    }
    
    # Store in database
    metadata = ClaudeCodeMetadata(auth_json=auth_json)
    await create_mcp_settings(metadata=metadata)
    
    return {"success": True}
```

### Writing Credentials to Sandbox (sandbox_service.py)

```python
async def _register_user_mcp_servers(self, user_id: str, sandbox: IISandbox):
    """Register MCP servers and write credentials to sandbox."""
    
    # Get user's MCP settings
    mcp_settings = await list_mcp_settings(user_id=user_id)
    
    for setting in mcp_settings:
        metadata = setting.metadata
        
        if isinstance(metadata, ClaudeCodeMetadata):
            # Write credentials file to sandbox
            store_path = "/home/pn/.claude/.credentials.json"
            await sandbox.write_file(
                json.dumps(metadata.auth_json),
                store_path
            )
            print(f"Wrote Claude Code credentials to {store_path}")
```

---

## Using Claude Code as an MCP Tool

Claude Code can be exposed as an MCP tool using `@steipete/claude-code-mcp`:

### MCP Configuration

```python
mcp_json_config = {
    "mcpServers": {
        "claude-code-mcp": {
            "command": "npx",
            "args": ["-y", "@steipete/claude-code-mcp@latest"],
        },
    }
}
```

### How It Works

1. The MCP server proxies to `@steipete/claude-code-mcp`
2. This wrapper runs Claude Code CLI under the hood
3. Your agent calls it like any other MCP tool

```python
# Agent calls Claude Code via MCP
result = await mcp_client.call_tool(
    name="mcp_claude-code-mcp_execute",
    arguments={
        "prompt": "Add error handling to the parse_data function in utils.py"
    }
)
# Claude Code reads the file, makes changes, returns result
```

---

## Direct Claude Code Usage (Alternative)

You can also use Claude Code directly without MCP:

### In the Sandbox

```bash
# Run Claude Code directly
claude "Create a Flask app with user authentication"

# Or with specific file
claude "Fix the bug in app.py where users can't login"
```

### From Your Agent (via shell command)

```python
# Use the sandbox server to run Claude Code
result = await sandbox_client.run_command(
    sandbox_id=sandbox_id,
    command='claude "Add tests for the User model"'
)
print(result)  # Claude's output and file changes
```

---

## Frontend Implementation

### PKCE Generation

```typescript
// Generate PKCE code verifier
const generatePKCE = () => {
    const array = new Uint8Array(32)
    crypto.getRandomValues(array)
    return Array.from(array)
        .map(b => b.toString(16).padStart(2, '0'))
        .join('')
}

// Generate code challenge (SHA256 of verifier)
const generateChallenge = async (verifier: string) => {
    const encoder = new TextEncoder()
    const data = encoder.encode(verifier)
    const hash = await crypto.subtle.digest('SHA-256', data)
    
    return btoa(String.fromCharCode(...new Uint8Array(hash)))
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '')
}
```

### OAuth URL

```typescript
const handleLoginWithClaude = async () => {
    const verifier = generatePKCE()
    sessionStorage.setItem('claude_pkce_verifier', verifier)
    
    const challenge = await generateChallenge(verifier)
    
    const params = new URLSearchParams({
        code: 'true',
        client_id: '9d1c250a-e61b-44d9-88ed-5944d1962f5e',
        response_type: 'code',
        redirect_uri: 'https://console.anthropic.com/oauth/code/callback',
        scope: 'org:create_api_key user:profile user:inference',
        code_challenge: challenge,
        code_challenge_method: 'S256',
        state: verifier
    })
    
    window.open(`https://claude.ai/oauth/authorize?${params}`, '_blank')
}
```

### Submit Authorization Code

```typescript
const handleSaveConfig = async () => {
    const verifier = sessionStorage.getItem('claude_pkce_verifier')
    
    await api.post('/user-settings/mcp/claude-code', {
        authorization_code: `${authCode}#${verifier}`
    })
    
    toast.success('Claude Code configured!')
}
```

---

## Client ID Explanation

The client ID `9d1c250a-e61b-44d9-88ed-5944d1962f5e` is:
- A public OAuth client ID from Anthropic
- Designed for CLI tools (not web apps)
- Uses PKCE for security (no client secret needed)

You can use this same client ID for your own integration.

---

## Implementing in Your Project

### 1. Add Claude Code to Your E2B Template

```dockerfile
# In your Dockerfile
RUN npm install -g @anthropic-ai/claude-code
RUN mkdir -p /home/user/.claude
COPY claude_template.json /home/user/.claude.json
```

### 2. Create OAuth Endpoint

```python
@app.post("/auth/claude-code")
async def configure_claude_code(authorization_code: str):
    # Split code and verifier
    code, verifier = authorization_code.split("#")
    
    # Exchange for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://console.anthropic.com/v1/oauth/token",
            json={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
                "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
                "code_verifier": verifier,
            }
        )
    
    tokens = response.json()
    
    # Store tokens (in your database)
    await store_claude_tokens(user_id, tokens)
    
    return {"success": True}
```

### 3. Write Credentials to Sandbox

```python
async def setup_sandbox_for_user(user_id: str, sandbox):
    # Get stored tokens
    tokens = await get_claude_tokens(user_id)
    
    if tokens:
        credentials = {
            "claudeAiOauth": {
                "accessToken": tokens["access_token"],
                "refreshToken": tokens["refresh_token"],
                "expiresAt": tokens["expires_at"],
                "scopes": ["user:inference", "user:profile"]
            }
        }
        
        await sandbox.write_file(
            "~/.claude/.credentials.json",
            json.dumps(credentials)
        )
```

### 4. Use from Your Agent

```python
# Option 1: Direct CLI
result = await sandbox.run_command('claude "Fix the bug"')

# Option 2: As MCP tool
tools = await load_mcp_tools(sandbox_mcp_url)
claude_tool = next(t for t in tools if "claude" in t.name)
result = await claude_tool.invoke({"prompt": "Fix the bug"})
```

---

## Important Notes

1. **Token Refresh**: Claude Code handles token refresh automatically using the refresh_token

2. **Scopes**: 
   - `user:inference` - Allows running Claude queries
   - `user:profile` - Allows reading user info
   - `org:create_api_key` - Allows creating API keys (optional)

3. **Security**: Never expose tokens to the frontend. Store them server-side only.

4. **Rate Limits**: Claude Code usage counts against your Anthropic account limits

5. **Costs**: Using Claude Code uses your Anthropic API credits
