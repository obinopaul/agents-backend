# FalkorDB module extraction for Graphiti Knowledge Graph
# Extract the compiled FalkorDB Redis module from the official image
FROM falkordb/falkordb:latest AS falkordb-module

# Build Codex SSE HTTP server
FROM rust:1.75-slim AS codex-builder

# Optimization: Use cache mount for apt-get to speed up repeated builds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update && apt-get install -y \
  git \
  ca-certificates \
  pkg-config \
  libssl-dev

WORKDIR /build
RUN git clone --branch v0.0.1 https://github.com/Intelligent-Internet/codex.git
WORKDIR /build/codex/codex-rs

# Optimization: Use cargo cache mount to avoid re-downloading dependencies
RUN --mount=type=cache,target=/usr/local/cargo/registry \
  --mount=type=cache,target=/build/codex/codex-rs/target \
  cargo build --release --bin sse-http-server && \
  cp /build/codex/codex-rs/target/release/sse-http-server /sse-http-server

# Multi-stage build to obfuscate tool_server inside Linux environment
FROM nikolaik/python-nodejs:python3.12-nodejs24-slim AS obfuscator

# Optimization: Use pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install pyarmor

# Copy source files and obfuscation script
WORKDIR /obfuscate
COPY backend/src/tool_server /obfuscate/tool_server
COPY docker_obfuscate.py /obfuscate/obfuscate.py

# Remove .venv if it exists and run obfuscation in one layer
RUN rm -rf /obfuscate/tool_server/.venv && \
  python obfuscate.py

# Main application stage
FROM nikolaik/python-nodejs:python3.12-nodejs24-slim

# Copy bashrc to both root (for build) and pn user (for runtime)
COPY backend/docker/sandbox/.bashrc /root/.bashrc
COPY backend/docker/sandbox/.bashrc /home/pn/.bashrc

# Optimization: Use cache mounts for apt-get and combine into single layer
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update && apt-get install -y \
  build-essential \
  procps \
  lsof \
  git \
  tmux \
  bc \
  net-tools \
  ripgrep \
  unzip \
  libmagic1 \
  xvfb \
  pandoc \
  weasyprint \
  libpq-dev \
  wget \
  gosu \
  redis-server \
  && rm -rf /var/lib/apt/lists/*

# Install texlive for local LaTeX compilation in Documents mode
# This enables the agent to compile LaTeX documents to PDF within the sandbox
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update && apt-get install -y --no-install-recommends \
  texlive-base \
  texlive-latex-base \
  texlive-latex-extra \
  texlive-fonts-recommended \
  texlive-bibtex-extra \
  biber \
  latexmk \
  && rm -rf /var/lib/apt/lists/*

# Optimization: Combine all curl installs and npm installs into fewer layers
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Optimization: Use npm cache mount and install playwright package and system deps as root
RUN --mount=type=cache,target=/root/.npm \
  npm install -g playwright@1.55.0 @intelligent-internet/codex @ast-grep/cli @anthropic-ai/claude-code

RUN --mount=type=cache,target=/root/.npm \
  npm install -g vercel

RUN usermod -aG sudo pn
# Install browser binaries as pn user so they're accessible at runtime
USER pn
RUN curl -fsSL https://bun.sh/install | bash
RUN playwright install chromium
USER root
RUN playwright install-deps

# Set environment variables
ENV NODE_OPTIONS="--max-old-space-size=4096"


RUN mkdir -p /app/agents_backend

# Install the project into `/app`
WORKDIR /app/agents_backend

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install uv package manager for much faster dependency resolution (10-100x faster than pip)
RUN pip install uv

# Copy e2b-specific requirements.txt (curated dependencies for sandbox environment)
COPY backend/e2b-requirements.txt /app/agents_backend/requirements.txt

# Install dependencies with uv (significantly faster than pip)
# uv pip install is 10-100x faster than pip for dependency resolution
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install --system -r /app/agents_backend/requirements.txt

# Copy obfuscated tool_server and PyArmor runtime from build stage
# The obfuscation script outputs to /final/tool_server and /final/pyarmor_runtime_*
COPY --from=obfuscator /obfuscate/final/tool_server /app/agents_backend/src/tool_server
COPY --from=obfuscator /obfuscate/final/pyarmor_runtime_000000 /app/agents_backend/src/pyarmor_runtime_000000

# Optimization: Copy from cached location in codex-builder
COPY --from=codex-builder /sse-http-server /usr/local/bin/sse-http-server

COPY backend/README.md /app/agents_backend/

# Optimization: Combine mkdir and touch into one layer
RUN mkdir -p /app/agents_backend/src/agents_backend && \
  touch /app/agents_backend/src/agents_backend/__init__.py

# Create backend.src.tool_server structure for imports to work inside sandbox
# This allows code using 'from backend.src.tool_server...' to resolve correctly
# when PYTHONPATH is /app/agents_backend/src
# NOTE: We use cp -r instead of symlink because importlib.resources.read_text()
# doesn't follow symlinks when loading resource files like .js
RUN mkdir -p /app/agents_backend/src/backend/src && \
  cp -r /app/agents_backend/src/tool_server /app/agents_backend/src/backend/src/tool_server && \
  touch /app/agents_backend/src/backend/__init__.py && \
  touch /app/agents_backend/src/backend/src/__init__.py

# Copy config files for root (build time) and pn user (runtime)
RUN mkdir -p /root/.codex /home/pn/.codex /home/pn/.claude
COPY backend/docker/sandbox/template.css /app/template.css
COPY backend/docker/sandbox/claude_template.json /root/.claude.json
COPY backend/docker/sandbox/claude_template.json /home/pn/.claude.json

# COPY Template files
COPY .templates /app/agents_backend/.templates

# COPY slides template
COPY .slides /app/agents_backend/.slides

# COPY latex templates
COPY .latex /app/agents_backend/.latex

# Build LaTeX AI Editor for Documents mode
# Pre-built during Docker image build for instant sandbox startup (<0.7s)
# Served via python http.server on port 9001
# VITE_ env vars are baked into the build by Vite
COPY backend/src/latex /tmp/latex-editor-src
WORKDIR /tmp/latex-editor-src
RUN --mount=type=cache,target=/root/.npm \
  npm install && \
  VITE_WORKSPACE_PATH=/workspace/documents \
  VITE_API_BASE_URL=http://localhost:6060 \
  VITE_LATEX_API_URL=http://localhost:6060/api/compile \
  npm run build && \
  mkdir -p /app/latex-editor && \
  cp -r dist/* /app/latex-editor/ && \
  rm -rf /tmp/latex-editor-src
WORKDIR /app/agents_backend

# Build Design MCP Server for diagramming/draw.io mode
# Pre-built during Docker image build for instant sandbox startup
# This is the STANDALONE MCP server which includes its own HTTP server on port 6002
# It serves an HTML page with iframe to embed.diagrams.net (no sign-up required)
# NOTE: We build only packages/mcp-server, NOT the full Next.js app
COPY backend/src/design/packages/mcp-server /tmp/design-mcp-src
WORKDIR /tmp/design-mcp-src
RUN --mount=type=cache,target=/root/.npm \
  npm install && \
  npm run build && \
  mkdir -p /app/design-mcp && \
  cp -r dist /app/design-mcp/ && \
  cp package.json /app/design-mcp/ && \
  cp -r node_modules /app/design-mcp/ && \
  rm -rf /tmp/design-mcp-src
WORKDIR /app/agents_backend

# Build Excalidraw Canvas Server for whiteboard/freeform diagramming mode
# Pre-built during Docker image build for instant sandbox startup (<0.7s)
# TypeScript Express + WebSocket server with embedded React frontend
# Uses @excalidraw/excalidraw npm package for hand-drawn style diagrams
# Port 6003 serves both REST API endpoints AND the browser viewer (WebSocket)
COPY backend/src/excalidraw /tmp/excalidraw-src
WORKDIR /tmp/excalidraw-src
RUN --mount=type=cache,target=/root/.npm \
  npm install && \
  npm run build && \
  mkdir -p /app/excalidraw && \
  cp -r dist /app/excalidraw/ && \
  cp package.json /app/excalidraw/ && \
  cp -r node_modules /app/excalidraw/ && \
  rm -rf /tmp/excalidraw-src
WORKDIR /app/agents_backend

# Build Graphiti MCP Server for Knowledge Graph mode
# Pre-built during Docker image build for instant sandbox startup
# Python MCP HTTP server on port 8500 with FalkorDB (Redis + graph module) on port 6379
# FalkorDB module is copied from official image to extend standard redis-server
# Provides 10 MCP tools: add_memory, search_nodes, search_memory_facts, etc.

# Copy FalkorDB module binary from official image (required for graph operations)
# This .so file extends Redis with graph database capabilities
COPY --from=falkordb-module /var/lib/falkordb/bin /var/lib/falkordb/bin

# Create data directory for FalkorDB persistence
RUN mkdir -p /var/lib/falkordb/data

# Copy and build Graphiti MCP server
COPY backend/src/graphiti/mcp_server /tmp/graphiti-mcp-src
WORKDIR /tmp/graphiti-mcp-src

# Install Graphiti MCP server dependencies with uv
# IMPORTANT: Remove local source reference in pyproject.toml (tool.uv.sources)
# and regenerate lock file to use PyPI graphiti-core instead of local editable install
# CRITICAL: Remove .python-version (3.10) to use system Python 3.12, and set UV_PYTHON_DOWNLOADS=never
# to prevent uv from trying to download a different Python version
ARG GRAPHITI_CORE_VERSION=0.23.1
ENV UV_PYTHON_DOWNLOADS=never
RUN sed -i '/\[tool\.uv\.sources\]/,/graphiti-core/d' pyproject.toml && \
  if [ -n "${GRAPHITI_CORE_VERSION}" ]; then \
  sed -i "s/graphiti-core\[falkordb\]>=[0-9]\+\.[0-9]\+\.[0-9]\+$/graphiti-core[falkordb]==${GRAPHITI_CORE_VERSION}/" pyproject.toml; \
  fi && \
  rm -f uv.lock .python-version && \
  uv lock --python 3.12

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --python 3.12 --no-group dev && \
  mkdir -p /app/graphiti-mcp && \
  cp -r . /app/graphiti-mcp/ && \
  rm -rf /tmp/graphiti-mcp-src

WORKDIR /app/agents_backend


# COPY Skills library for agent injection at runtime
# Skills are baked into /app/skills/ and selectively copied to workspace on sandbox creation
# Three categories: basic (general), scientific_skills (scientific), academic (academic)
COPY backend/src/skills /app/skills

# Dependencies already installed with pip above


RUN mkdir /workspace
WORKDIR /workspace

# Create startup and utility scripts
COPY backend/docker/sandbox/start-services.sh /app/start-services.sh
COPY backend/docker/sandbox/entrypoint.sh /app/entrypoint.sh
COPY backend/docker/sandbox/inject-skills.sh /app/inject-skills.sh
RUN chmod +x /app/start-services.sh /app/entrypoint.sh /app/inject-skills.sh

# Create 'backend' command for E2B (their cloud syncs start_cmd="backend")
# This ensures the 'backend' command exists and calls our startup script
RUN printf '#!/bin/bash\nexec bash /app/start-services.sh "$@"\n' > /usr/local/bin/backend && \
  chmod +x /usr/local/bin/backend

# Fix ownership and permissions for multi-user access
# Architecture:
#   - 'pn' (uid=1000): Base image user, runs MCP server and code-server
#   - 'user' (uid=1001): E2B's default user for SDK commands (sandbox.commands.run)
# E2B sets HOME=/home/user, so npm cache goes to /home/user/.npm (correct)
# But 'user' needs to access /home/pn/.bun for bun commands
# This is safe because each E2B sandbox is completely isolated per-user
RUN chown -R pn:pn /home/pn /app /workspace && \
  chmod -R 755 /app && \
  chmod -R 755 /home/pn/.claude && \
  # CRITICAL: Make /home/pn accessible so 'user' can access bun
  chmod 755 /home/pn && \
  # Make bun accessible to all users
  chmod -R 755 /home/pn/.bun && \
  # Make workspace writable by all users
  chmod 777 /workspace && \
  # Create and configure home directory for E2B's 'user' (uid=1001)
  mkdir -p /home/user && chown 1001:1001 /home/user && chmod 755 /home/user && \
  # Fix permissions for Graphiti and FalkorDB - owned by 'pn' since services run as 'pn' (via gosu in start-services.sh)
  # Note: 'user' (uid=1001) is for E2B SDK commands, but Graphiti MCP runs as 'pn' in tmux session
  chown -R pn:pn /app/graphiti-mcp /var/lib/falkordb && \
  # Ensure Graphiti virtualenv has proper execute permissions for 'uv run' to work
  chmod -R 755 /app/graphiti-mcp/.venv/bin

# Set environment for pn user
ENV HOME=/home/pn
ENV PATH="/home/pn/.bun/bin:/app/agents_backend/.venv/bin:$PATH"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["bash", "/app/start-services.sh"]
