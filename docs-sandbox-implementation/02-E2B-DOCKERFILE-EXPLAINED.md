# E2B Dockerfile - Line by Line Explanation

This document explains every section of `e2b.Dockerfile` - the template that creates your sandbox environment.

---

## Overview

The Dockerfile uses **multi-stage builds** with 3 stages:
1. **codex-builder** - Compiles the Codex SSE server from Rust
2. **obfuscator** - Obfuscates ii_tool Python code (you can skip this)
3. **main** - The actual sandbox image

---

## Stage 1: Build Codex SSE Server

```dockerfile
# Build Codex SSE HTTP server
FROM rust:1.75-slim AS codex-builder
```

**What is this?** 
Codex (OpenAI's coding AI) needs a server to communicate via SSE (Server-Sent Events). This stage compiles that server from Rust source code.

**Do you need this?**
Only if you want to use OpenAI Codex. If you only want Claude Code, you can remove this stage.

```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update && apt-get install -y \
  git \
  ca-certificates \
  pkg-config \
  libssl-dev
```

**What is this?**
Installing build dependencies for Rust compilation.

```dockerfile
WORKDIR /build
RUN git clone --branch v0.0.1 https://github.com/Intelligent-Internet/codex.git
WORKDIR /build/codex/codex-rs
```

**What is this?**
Cloning their fork of Codex and navigating to the Rust codebase.

```dockerfile
RUN --mount=type=cache,target=/usr/local/cargo/registry \
  --mount=type=cache,target=/build/codex/codex-rs/target \
  cargo build --release --bin sse-http-server && \
  cp /build/codex/codex-rs/target/release/sse-http-server /sse-http-server
```

**What is this?**
Compiling the `sse-http-server` binary. The result is saved at `/sse-http-server`.

---

## Stage 2: Obfuscate ii_tool (Optional)

```dockerfile
FROM nikolaik/python-nodejs:python3.10-nodejs24-slim AS obfuscator

RUN --mount=type=cache,target=/root/.cache/pip \
  pip install pyarmor
```

**What is this?**
They obfuscate their `ii_tool` code using PyArmor (code protection). This is for their commercial product.

**Do you need this?**
NO. You can skip this entirely and copy ii_tool directly. Replace with:

```dockerfile
# If you don't need obfuscation, just skip this stage
```

---

## Stage 3: Main Application Image

### Base Image

```dockerfile
FROM nikolaik/python-nodejs:python3.10-nodejs24-slim
```

**What is this?**
`nikolaik/python-nodejs` is a popular Docker image that includes BOTH Python and Node.js. This is perfect for a development sandbox because agents often need both.

**Image contents:**
- Python 3.10
- Node.js 24
- npm, pip
- Common build tools

**Alternative:** You could use separate Python/Node images, but this is convenient.

### Shell Configuration

```dockerfile
COPY docker/sandbox/.bashrc /root/.bashrc
COPY docker/sandbox/.bashrc /home/pn/.bashrc
```

**What is this?**
Custom bash configuration for the sandbox. The `pn` user is the non-root user in the nikolaik image.

### System Dependencies

```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update && apt-get install -y \
  build-essential \    # C/C++ compiler, make, etc.
  procps \             # Process utilities (ps, top)
  lsof \               # List open files
  git \                # Version control
  tmux \               # Terminal multiplexer (for background processes)
  bc \                 # Calculator
  net-tools \          # Network utilities
  ripgrep \            # Fast text search
  unzip \              # Archive extraction
  libmagic1 \          # File type detection
  xvfb \               # Virtual framebuffer (for headless browser)
  pandoc \             # Document converter
  weasyprint \         # HTML to PDF
  libpq-dev \          # PostgreSQL client
  wget \               # Download utility
  gosu                 # Run commands as different user
&& rm -rf /var/lib/apt/lists/*
```

**Key packages:**
- `tmux` - Runs Code-Server and MCP server in background
- `xvfb` - Required for Playwright headless browser
- `gosu` - Allows switching users in entrypoint

### Code-Server Installation

```dockerfile
RUN curl -fsSL https://code-server.dev/install.sh | sh
```

**What is this?**
Installs **code-server** - VS Code that runs as a web server. When started, you can access VS Code at `http://sandbox:9000`.

**How it works:**
1. Sandbox starts
2. `start-services.sh` runs `code-server --port 9000`
3. E2B exposes port 9000 → `https://sandbox-id-9000.e2b.dev`
4. User opens URL in browser → sees VS Code!

### NPM Global Packages

```dockerfile
RUN --mount=type=cache,target=/root/.npm \
  npm install -g playwright@1.55.0 @intelligent-internet/codex @ast-grep/cli @anthropic-ai/claude-code
```

**Packages installed:**

| Package | Purpose |
|---------|---------|
| `playwright` | Browser automation framework |
| `@intelligent-internet/codex` | Their Codex wrapper |
| `@ast-grep/cli` | AST-based code search (like grep for code) |
| `@anthropic-ai/claude-code` | **Claude Code CLI** - Anthropic's AI coding tool |

**Claude Code is installed here!** It's a global npm package that you can run:
```bash
claude-code "Fix the bug in app.py"
```

### Vercel CLI

```dockerfile
RUN --mount=type=cache,target=/root/.npm \
  npm install -g vercel
```

**What is this?**
For deploying websites to Vercel directly from the sandbox.

### User Setup

```dockerfile
RUN usermod -aG sudo pn
USER pn
RUN curl -fsSL https://bun.sh/install | bash
RUN playwright install chromium
USER root
RUN playwright install-deps
```

**What is this?**
- Adding `pn` user to sudo group
- Installing Bun (fast JS runtime) as `pn` user
- Installing Chromium browser for Playwright

### Node Memory Configuration

```dockerfile
ENV NODE_OPTIONS="--max-old-space-size=4096"
```

**What is this?**
Increases Node.js memory limit to 4GB. Important for large builds.

### UV Package Manager Setup

```dockerfile
RUN mkdir -p /app/ii_agent
WORKDIR /app/ii_agent

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY uv.lock pyproject.toml /app/ii_agent/

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --prerelease=allow --no-install-project --no-dev
```

**What is this?**
Using `uv` (ultra-fast Python package manager) to install Python dependencies.

### Copy ii_tool (MCP Server)

```dockerfile
# If you kept obfuscation:
COPY --from=obfuscator /obfuscate/final/ii_tool /app/ii_agent/src/ii_tool

# If you skip obfuscation, do this instead:
# COPY src/ii_tool /app/ii_agent/src/ii_tool
```

**What is this?**
Copying the MCP tool server into the image. This is what runs on port 6060.

### Copy Codex Binary

```dockerfile
COPY --from=codex-builder /sse-http-server /usr/local/bin/sse-http-server
```

**What is this?**
The compiled Codex SSE server from stage 1.

### Configuration Files

```dockerfile
RUN mkdir -p /root/.codex /home/pn/.codex /home/pn/.claude

COPY docker/sandbox/template.css /app/template.css
COPY docker/sandbox/claude_template.json /root/.claude.json
COPY docker/sandbox/claude_template.json /home/pn/.claude.json
```

**What is this?**
- Creating config directories for Codex and Claude Code
- Copying pre-configured settings for Claude Code

**The claude_template.json:**
```json
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true
  // Skips initial setup dialogs
}
```

### Final Python Setup

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --prerelease=allow --no-dev
```

**What is this?**
Final Python dependency installation with the project.

### Workspace Setup

```dockerfile
RUN mkdir /workspace
WORKDIR /workspace
```

**What is this?**
Creating `/workspace` - this is where user's code will live.

### Startup Scripts

```dockerfile
COPY docker/sandbox/start-services.sh /app/start-services.sh
COPY docker/sandbox/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/start-services.sh /app/entrypoint.sh
```

**What is this?**
Copying the scripts that start services when sandbox boots.

### Permissions

```dockerfile
RUN chown -R pn:pn /home/pn /app /workspace && \
    chmod -R 755 /app && \
    chmod -R 755 /home/pn/.claude
```

**What is this?**
Ensuring the `pn` user owns all necessary directories.

### Environment

```dockerfile
ENV HOME=/home/pn
```

**What is this?**
Setting the home directory for the default user.

---

## Simplified Version for Your Project

If you want a minimal version without Codex:

```dockerfile
# Minimal Sandbox Template
FROM nikolaik/python-nodejs:python3.10-nodejs24-slim

# System dependencies
RUN apt-get update && apt-get install -y \
  build-essential \
  git \
  tmux \
  ripgrep \
  xvfb \
  wget \
  gosu \
&& rm -rf /var/lib/apt/lists/*

# Code-Server (VS Code in browser)
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code playwright@1.55.0

# Install Playwright browser
RUN npx playwright install chromium && npx playwright install-deps

# Create workspace
RUN mkdir -p /workspace /app
WORKDIR /workspace

# Copy your MCP server
COPY src/ii_tool /app/ii_tool

# Install Python dependencies for MCP server
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Startup script
COPY start-services.sh /app/start-services.sh
RUN chmod +x /app/start-services.sh

ENV HOME=/root
```

---

## Building the Template

```bash
# Install E2B CLI
npm install -g @e2b/cli

# Login
e2b login

# Build template (takes 5-10 minutes)
e2b template build -d e2b.Dockerfile --name my-sandbox

# Output: Template ID: template_abc123
# Save this ID - you'll use it when creating sandboxes
```

---

## Using the Template

```python
from e2b_code_interpreter import Sandbox

# Create sandbox from YOUR template
sandbox = Sandbox(template="template_abc123")

# Services are automatically started by start-services.sh
# Code-Server at port 9000
# MCP Server at port 6060

# Get public URLs
vscode_url = sandbox.get_host(9000)  # https://xxx-9000.e2b.dev
mcp_url = sandbox.get_host(6060)     # https://xxx-6060.e2b.dev
```
