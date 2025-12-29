# Select the image to build based on SERVER_TYPE, defaulting to agents_backend_server, or docker-compose build args
ARG SERVER_TYPE=agents_backend_server

# === Python environment from uv ===
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Used for build Python packages
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /agents_backend

WORKDIR /agents_backend

# Configure uv environment
ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install dependencies with cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-default-groups --group server

# === Runtime base server image ===
FROM python:3.11-slim AS base_server

# Install runtime dependencies including those for browser/media support
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    supervisor \
    curl \
    gnupg \
    ffmpeg \
    xvfb \
    libmagic1 \
    file \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-freefont-ttf \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and its dependencies
# We use uv run to execute the install within the environment context if needed, 
# or just install directly. Using uv tool install is also an option but 'uv run playwright' expects playwright in dev deps or similar.
# Since we are in base_server which doesn't have the source code yet, we need to install playwright CLI first or rely on the builder.
# However, to keep image size optimized, let's install browser deps here.
# Note: 'uv sync' in builder stage installed 'server' group. If playwright is in 'server' group it's available.
# But 'playwright install' needs to download browsers to /ms-playwright usually.
# Let's assume we want to install system deps for playwright:
RUN bash -c "if command -v playwright >/dev/null 2>&1; then playwright install --with-deps chromium; else echo 'Playwright not found, skipping browser install (can be installed later)'; fi"

COPY --from=builder /agents_backend /agents_backend

COPY --from=builder /usr/local /usr/local

COPY deploy/backend/supervisord.conf /etc/supervisor/supervisord.conf

WORKDIR /agents_backend/backend

# === FastAPI server image ===
FROM base_server AS agents_backend_server

COPY deploy/backend/agents_backend_server.conf /etc/supervisor/conf.d/

RUN mkdir -p /var/log/agents_backend

EXPOSE 8001

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# === Celery Worker image ===
FROM base_server AS agents_backend_celery_worker

COPY deploy/backend/agents_backend_celery_worker.conf /etc/supervisor/conf.d/

RUN mkdir -p /var/log/agents_backend

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# === Celery Beat image ===
FROM base_server AS agents_backend_celery_beat

COPY deploy/backend/agents_backend_celery_beat.conf /etc/supervisor/conf.d/

RUN mkdir -p /var/log/agents_backend

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# === Celery Flower image ===
FROM base_server AS agents_backend_celery_flower

COPY deploy/backend/agents_backend_celery_flower.conf /etc/supervisor/conf.d/

RUN mkdir -p /var/log/agents_backend

EXPOSE 8555

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# Build image
FROM ${SERVER_TYPE}
