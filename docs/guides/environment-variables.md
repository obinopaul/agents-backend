# Environment Variables Guide

> Complete reference for all environment variables used in the Agents Backend.

---

## Quick Reference

| Category | Prefix | Example |
|----------|--------|---------|
| [Database](#database) | `DATABASE_` | `DATABASE_HOST` |
| [Redis](#redis) | `REDIS_` | `REDIS_HOST` |
| [Celery](#celery) | `CELERY_` | `CELERY_BROKER` |
| [OAuth2](#oauth2) | `OAUTH2_` | `OAUTH2_GITHUB_CLIENT_ID` |
| [LLM Providers](#llm-providers) | `OPENAI_`, `ANTHROPIC_`, etc. | `OPENAI_API_KEY` |
| [Agent](#agent-configuration) | `AGENT_` | `AGENT_RECURSION_LIMIT` |
| [Sandbox](#sandbox) | `SANDBOX_`, `E2B_`, `DAYTONA_` | `SANDBOX_PROVIDER` |
| [Search](#search--crawler) | `TAVILY_`, `JINA_`, etc. | `TAVILY_API_KEY` |
| [RAG](#rag) | `MILVUS_`, `QDRANT_`, etc. | `MILVUS_HOST` |
| [Tool Server](#tool-server) | `WEB_VISIT_`, `COMPRESSOR_` | `WEB_VISIT_JINA_API_KEY` |

---

## Core Configuration

### Environment

```bash
# Application environment
ENVIRONMENT='dev'              # 'dev' | 'production'
DEBUG=True                     # Enable debug mode
```

### Security

```bash
# JWT token secret (generate with: openssl rand -base64 32)
TOKEN_SECRET_KEY='your-secret-key-here'

# Opera log encryption key
OPERA_LOG_ENCRYPT_SECRET_KEY='your-encryption-key-here'
```

---

## Database

```bash
# Database type
DATABASE_TYPE='postgresql'     # 'postgresql' | 'mysql'

# Connection settings
DATABASE_HOST='127.0.0.1'
DATABASE_PORT=5432
DATABASE_USER='postgres'
DATABASE_PASSWORD='123456'
DATABASE_SCHEMA='postgres'     # Database name

# Optional
DATABASE_ECHO=False            # Log SQL queries
```

---

## Redis

```bash
REDIS_HOST='127.0.0.1'
REDIS_PORT=6379
REDIS_PASSWORD=''              # Leave empty if no auth
REDIS_USERNAME='default'       # For Redis 6+ ACL
REDIS_DATABASE=0
```

---

## Celery

```bash
# Broker selection
CELERY_BROKER='rabbitmq'       # 'rabbitmq' | 'redis'

# RabbitMQ settings
CELERY_RABBITMQ_HOST='127.0.0.1'
CELERY_RABBITMQ_PORT=5672
CELERY_RABBITMQ_USERNAME='guest'
CELERY_RABBITMQ_PASSWORD='guest'
CELERY_RABBITMQ_VHOST='/'

# Redis as broker (alternative)
CELERY_BROKER_REDIS_DATABASE=1
```

---

## OAuth2

### GitHub

```bash
OAUTH2_GITHUB_CLIENT_ID='your-github-client-id'
OAUTH2_GITHUB_CLIENT_SECRET='your-github-client-secret'
OAUTH2_GITHUB_REDIRECT_URI='http://localhost:8000/api/v1/oauth2/github/callback'
```

### Google

```bash
OAUTH2_GOOGLE_CLIENT_ID='your-google-client-id'
OAUTH2_GOOGLE_CLIENT_SECRET='your-google-client-secret'
OAUTH2_GOOGLE_REDIRECT_URI='http://localhost:8000/api/v1/oauth2/google/callback'
```

### LinuxDo

```bash
OAUTH2_LINUX_DO_CLIENT_ID='your-linux-do-client-id'
OAUTH2_LINUX_DO_CLIENT_SECRET='your-linux-do-client-secret'
```

### Frontend Redirects

```bash
OAUTH2_FRONTEND_LOGIN_REDIRECT_URI='http://localhost:3000/oauth/callback'
OAUTH2_FRONTEND_BINDING_REDIRECT_URI='http://localhost:3000/settings/social'
```

---

## LLM Providers

### Provider Selection

```bash
LLM_PROVIDER="openai"          # openai | anthropic | gemini | deepseek | groq | ollama | openai_compat
LLM_MAX_RETRIES=3
LLM_TOKEN_LIMIT=200000
LLM_TEMPERATURE=0.7
```

### OpenAI

```bash
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o"
OPENAI_BASE_URL=""             # Optional: for proxies
```

### Anthropic

```bash
ANTHROPIC_API_KEY="sk-ant-..."
ANTHROPIC_MODEL="claude-sonnet-4-20250514"
```

### Google Gemini

```bash
GOOGLE_API_KEY="..."
GEMINI_MODEL="gemini-2.0-flash"
```

### DeepSeek

```bash
DEEPSEEK_API_KEY="..."
DEEPSEEK_MODEL="deepseek-chat"
```

### Groq

```bash
GROQ_API_KEY="..."
GROQ_MODEL="llama-3.1-8b-instant"
```

### Ollama (Local)

```bash
OLLAMA_MODEL="llama3"
OLLAMA_BASE_URL="http://localhost:11434"
```

### OpenAI-Compatible

```bash
OPENAI_COMPAT_API_KEY=""
OPENAI_COMPAT_MODEL=""
OPENAI_COMPAT_BASE_URL=""      # Required
```

---

## Agent Configuration

### Workflow Limits

```bash
AGENT_RECURSION_LIMIT=30       # Max graph steps
AGENT_MAX_PLAN_ITERATIONS=1    # Planner revision limit
AGENT_MAX_STEP_NUM=3           # Steps per plan
AGENT_MAX_SEARCH_RESULTS=3     # Results per search
```

### Features

```bash
AGENT_ENABLE_DEEP_THINKING=False
AGENT_ENABLE_CLARIFICATION=False
AGENT_MAX_CLARIFICATION_ROUNDS=3
AGENT_ENFORCE_WEB_SEARCH=False
AGENT_ENFORCE_RESEARCHER_SEARCH=True
```

### Middleware

```bash
# Summarization
MIDDLEWARE_ENABLE_SUMMARIZATION=True
MIDDLEWARE_SUMMARIZATION_TRIGGER_TOKENS=100000
MIDDLEWARE_SUMMARIZATION_KEEP_MESSAGES=10

# Retry
MIDDLEWARE_ENABLE_MODEL_RETRY=True
MIDDLEWARE_MODEL_MAX_RETRIES=3

# Limits
MIDDLEWARE_ENABLE_MODEL_CALL_LIMIT=True
MIDDLEWARE_MODEL_CALL_THREAD_LIMIT=50

# Fallback
MIDDLEWARE_ENABLE_MODEL_FALLBACK=True
MIDDLEWARE_FALLBACK_MODELS="gpt-4o-mini"
```

---

## Sandbox

### Provider Selection

```bash
SANDBOX_PROVIDER=e2b           # e2b | daytona
```

### E2B

```bash
E2B_API_KEY='your-e2b-api-key'
E2B_TEMPLATE_ID='base'
```

### Daytona

```bash
DAYTONA_API_KEY='your-daytona-api-key'
DAYTONA_SERVER_URL='https://app.daytona.io/api'
DAYTONA_TARGET='us'
```

### Agent-Infra (Local Docker)

```bash
AGENT_INFRA_URL='http://localhost:8090'
AGENT_INFRA_TIMEOUT=60
```

### Ports

```bash
SANDBOX_MCP_SERVER_PORT=6060
SANDBOX_CODE_SERVER_PORT=9000
```

---

## Search & Crawler

### Search Engine

```bash
AGENT_SEARCH_ENGINE=tavily     # tavily | duckduckgo | brave | bing | searx

TAVILY_API_KEY='tvly-xxx'
BRAVE_SEARCH_API_KEY=''
BING_SEARCH_API_KEY=''
JINA_API_KEY='jina_xxx'
SEARX_HOST=''
```

### Crawler

```bash
CRAWLER_ENGINE=jina            # jina | infoquest
CRAWLER_FETCH_TIME=10
CRAWLER_TIMEOUT=30
```

---

## RAG

### Provider Selection

```bash
AGENT_RAG_PROVIDER=milvus      # milvus | qdrant | ragflow | dify
```

### Embeddings

```bash
EMBEDDING_PROVIDER="openai"
EMBEDDING_MODEL="text-embedding-ada-002"
EMBEDDING_API_KEY=""
```

### Milvus

```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION="agent_documents"
```

### Qdrant

```bash
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=""
QDRANT_COLLECTION="agent_documents"
```

---

## Tool Server

### Web Visit

```bash
WEB_VISIT_FIRECRAWL_API_KEY=''
WEB_VISIT_GEMINI_API_KEY=''
WEB_VISIT_JINA_API_KEY=''
WEB_VISIT_TAVILY_API_KEY=''
WEB_VISIT_MAX_OUTPUT_LENGTH=40000
```

### Content Compressor

```bash
COMPRESSOR_COMPRESS_TYPES='["llm"]'
COMPRESSOR_MAX_OUTPUT_WORDS=6500
COMPRESSOR_MAX_INPUT_WORDS=32000
```

---

## Tracing & Monitoring

### LangSmith

```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT='https://api.smith.langchain.com'
LANGSMITH_API_KEY='your-langsmith-key'
LANGSMITH_PROJECT='your-project'
```

### Langfuse

```bash
LANGFUSE_PUBLIC_KEY=''
LANGFUSE_SECRET_KEY=''
LANGFUSE_HOST=''
```

---

## Email Plugin

```bash
EMAIL_HOST='smtp.gmail.com'
EMAIL_PORT=587
EMAIL_USER='your@email.com'
EMAIL_PASSWORD='your-app-password'
EMAIL_USE_TLS=True
EMAIL_FROM='noreply@example.com'

EMAIL_CAPTCHA_REDIS_PREFIX='fba:email:captcha'
EMAIL_CAPTCHA_EXPIRE_SECONDS=300
```

---

## Cloud Storage

### Cloudflare R2

```bash
R2_ACCOUNT_ID=''
R2_ACCESS_KEY_ID=''
R2_SECRET_ACCESS_KEY=''
R2_BUCKET_NAME=''
```

### Google Cloud Storage

```bash
storage_provider='gcs'
gcs_bucket_name=''
gcs_project_id=''
```

---

## Sample `.env` File

```bash
# Core
ENVIRONMENT='dev'
TOKEN_SECRET_KEY='your-secret-key'

# Database
DATABASE_TYPE='postgresql'
DATABASE_HOST='127.0.0.1'
DATABASE_PORT=5432
DATABASE_USER='postgres'
DATABASE_PASSWORD='123456'
DATABASE_SCHEMA='postgres'

# Redis
REDIS_HOST='127.0.0.1'
REDIS_PORT=6379

# LLM
LLM_PROVIDER="openai"
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o"

# Sandbox
SANDBOX_PROVIDER=e2b
E2B_API_KEY='e2b-...'

# OAuth2
OAUTH2_GITHUB_CLIENT_ID='...'
OAUTH2_GITHUB_CLIENT_SECRET='...'
```

---

## Related Documentation

- [Getting Started](../getting-started.md) - Initial setup
- [Deployment Guide](../deployment/README.md) - Docker and local dev
- [Authentication](../frontend-connect/authentication.md) - OAuth2 setup
