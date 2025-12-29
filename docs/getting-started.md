# Getting Started with Agents Backend

> **Complete guide to installing, configuring, and running the Agents Backend system**

---

## 📖 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
  - [Local Development Setup](#local-development-setup)
  - [Docker Setup](#docker-setup)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Database Configuration](#database-configuration)
  - [Redis Configuration](#redis-configuration)
- [Database Initialization](#database-initialization)
- [Running the Application](#running-the-application)
- [Verifying Installation](#verifying-installation)
- [Common Issues](#common-issues)
- [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Python** | 3.10 | 3.11+ |
| **RAM** | 2 GB | 4 GB+ |
| **Disk Space** | 1 GB | 5 GB+ |
| **OS** | Windows 10, Ubuntu 20.04, macOS 12 | Latest LTS versions |

### Required Software

```
┌─────────────────────────────────────────────────────────────────┐
│                     REQUIRED DEPENDENCIES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Python     │  │   Database   │  │       Redis          │  │
│  │   3.10+      │  │  MySQL 8.0+  │  │       7.0+           │  │
│  │              │  │     OR       │  │                      │  │
│  │              │  │ PostgreSQL   │  │                      │  │
│  │              │  │    14+       │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  Optional:                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Docker     │  │   Git        │  │   Node.js (for       │  │
│  │   24.0+      │  │   2.40+      │  │   frontend dev)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Installing Prerequisites

#### Python 3.10+

**Windows:**
```powershell
# Using winget
winget install Python.Python.3.11

# Or download from https://www.python.org/downloads/
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

**macOS:**
```bash
brew install python@3.11
```

#### MySQL 8.0+

**Windows:**
```powershell
winget install Oracle.MySQL
```

**Linux:**
```bash
sudo apt install mysql-server
sudo mysql_secure_installation
```

**macOS:**
```bash
brew install mysql
brew services start mysql
```

#### PostgreSQL 14+ (Alternative)

**Windows:**
```powershell
winget install PostgreSQL.PostgreSQL
```

**Linux:**
```bash
sudo apt install postgresql postgresql-contrib
```

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

#### Redis 7.0+

**Windows:**
```powershell
# Use WSL2 or Docker
# WSL2:
wsl --install
# Then in WSL:
sudo apt install redis-server
```

**Linux:**
```bash
sudo apt install redis-server
sudo systemctl start redis-server
```

**macOS:**
```bash
brew install redis
brew services start redis
```

---

## Installation Methods

### Local Development Setup

#### Step 1: Clone the Repository

```bash
git clone https://github.com/obinopaul/agents-backend.git
cd agents-backend
```

#### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
# Install main dependencies
pip install --upgrade pip
pip install -r requirements.txt

# For development (includes testing and linting tools)
pip install -r requirements-dev.txt  # if available
```

#### Step 4: Verify Installation

```bash
# Check that Agents Backend CLI is available
agents-backend --help
```

Expected output:
```
Usage: agents-backend [OPTIONS] COMMAND [ARGS]...

  Agents Backend CLI

Options:
  --help  Show this message and exit.

Commands:
  celery-beat    Start Celery beat scheduler
  celery-flower  Start Celery Flower monitoring
  celery-worker  Start Celery worker
  init           Initialize database
  install        Install plugin
  run            Start development server
```

---

### Docker Setup

#### Prerequisites for Docker

- Docker Engine 24.0+
- Docker Compose 2.0+

#### Step 1: Clone and Configure

```bash
git clone https://github.com/obinopaul/agents-backend.git
cd agents-backend

# Copy environment file
cp .env.example .env
# Edit .env with your settings
```

#### Step 2: Start Services

```bash
# Build all services
docker-compose build

# Start all services (backend, database, redis)
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

#### Docker Compose Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE SERVICES                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Network: agents-net                   │    │
│  │                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │    │
│  │  │   backend    │  │    redis     │  │     db       │   │    │
│  │  │              │  │              │  │              │   │    │
│  │  │  Port: 8000  │◄─┤  Port: 6379  │  │  Port: 3306  │   │    │
│  │  │              │  │              │  │  (or 5432)   │   │    │
│  │  │  FastAPI     │  │  Redis 7.0   │  │  MySQL/      │   │    │
│  │  │  Granian     │  │              │  │  PostgreSQL  │   │    │
│  │  └──────┬───────┘  └──────────────┘  └──────┬───────┘   │    │
│  │         │                                     │          │    │
│  │         └────────────────┬────────────────────┘          │    │
│  │                          │                               │    │
│  │                          ▼                               │    │
│  │                 ┌──────────────┐                         │    │
│  │                 │   volumes    │                         │    │
│  │                 │  - db_data   │                         │    │
│  │                 │  - redis_data│                         │    │
│  │                 │  - uploads   │                         │    │
│  │                 └──────────────┘                         │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Useful Docker Commands

```bash
# Stop all services
docker-compose down

# Rebuild and start
docker-compose up -d --build

# View specific service logs
docker-compose logs -f backend

# Execute command in container
docker-compose exec backend bash

# Reset everything (including volumes)
docker-compose down -v
docker-compose up -d
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following settings:

```ini
# =============================================================================
# APPLICATION SETTINGS
# =============================================================================

# Environment: dev, test, prod
ENVIRONMENT=dev

# Debug mode (disable in production)
DEBUG=true

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# Database type: mysql or postgresql
DB_TYPE=mysql

# MySQL Settings
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_secure_password
MYSQL_DATABASE=agents_backend

# PostgreSQL Settings (if using PostgreSQL)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DATABASE=agents_backend

# Primary key generation mode: autoincrement or snowflake
DB_PK_MODE=snowflake

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DATABASE=0

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# JWT Secret Key (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production

# Token expiration (seconds)
ACCESS_TOKEN_EXPIRE_SECONDS=1800    # 30 minutes
REFRESH_TOKEN_EXPIRE_SECONDS=604800  # 7 days

# Multi-login support (allow same user on multiple devices)
MULTI_LOGIN=true

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

# Broker: redis or rabbitmq
CELERY_BROKER_TYPE=redis
CELERY_BROKER_URL=redis://localhost:6379/1

# =============================================================================
# PLUGIN SETTINGS (Optional)
# =============================================================================

# OAuth2 - GitHub
OAUTH2_GITHUB_CLIENT_ID=
OAUTH2_GITHUB_CLIENT_SECRET=

# OAuth2 - Google
OAUTH2_GOOGLE_CLIENT_ID=
OAUTH2_GOOGLE_CLIENT_SECRET=

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_FROM=

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL=DEBUG
LOG_FORMAT=<level>{level: <8}</level> | <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>

# =============================================================================
# AI AGENT CONFIGURATION
# =============================================================================

# LLM Providers (Required)
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=sk-...

# Agent Features
AGENT_RECURSION_LIMIT=25
AGENT_ENABLE_WEB_SEARCH=true
AGENT_ENABLE_DEEP_THINKING=false

# Search Services (Optional, for web search)
TAVILY_API_KEY=tvly-...
```

### Configuration Schema

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION HIERARCHY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    .env (Root)                          │    │
│  │            Environment-specific overrides               │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              backend/core/conf.py                        │    │
│  │         Pydantic Settings (type validation)              │    │
│  │                                                          │    │
│  │  class Settings(BaseSettings):                           │    │
│  │      ENVIRONMENT: str                                    │    │
│  │      DB_TYPE: DatabaseType                               │    │
│  │      REDIS_HOST: str                                     │    │
│  │      JWT_SECRET_KEY: str                                 │    │
│  │      ...                                                 │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               settings (Global Instance)                 │    │
│  │                                                          │    │
│  │  from backend.core.conf import settings                  │    │
│  │  print(settings.DB_TYPE)  # mysql                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Database Configuration

#### MySQL Setup

```sql
-- Create database
CREATE DATABASE agents_backend CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (optional, for non-root access)
CREATE USER 'agents_backend_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON agents_backend.* TO 'agents_backend_user'@'localhost';
FLUSH PRIVILEGES;
```

#### PostgreSQL Setup

```sql
-- Create database
CREATE DATABASE agents_backend WITH ENCODING 'UTF8';

-- Create user (optional)
CREATE USER agents_backend_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE agents_backend TO agents_backend_user;
```

### Redis Configuration

```bash
# Test Redis connection
redis-cli ping
# Expected: PONG

# Set password (optional but recommended)
redis-cli CONFIG SET requirepass "your_redis_password"
```

---

## Database Initialization

### Using Agents Backend CLI

```bash
# Initialize database (creates tables and runs seed data)
agents-backend init

# This command will:
# 1. Create all SQLAlchemy model tables
# 2. Run SQL initialization scripts from backend/sql/
# 3. Create default admin user
# 4. Set up initial roles and permissions
```

### Initialization Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE INITIALIZATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  $ agents-backend init                                          │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. Connect to Database                                   │   │
│  │     - Validate connection settings                        │   │
│  │     - Check database exists                               │   │
│  └──────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  2. Create Tables (SQLAlchemy)                            │   │
│  │     - Base.metadata.create_all()                          │   │
│  │     - Creates: sys_user, sys_role, sys_menu, etc.         │   │
│  └──────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  3. Run SQL Scripts                                       │   │
│  │     - backend/sql/mysql/init_*.sql (or postgresql/)       │   │
│  │     - Inserts default data                                │   │
│  └──────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  4. Initialize Plugins                                    │   │
│  │     - Load plugin SQL scripts                             │   │
│  │     - Create plugin tables                                │   │
│  └──────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ✓ Database Ready                                         │   │
│  │    Default Admin: admin / admin123                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Default Credentials

| User | Password | Role |
|------|----------|------|
| admin | admin123 | Super Administrator |

> ⚠️ **Security Warning**: Change the default password immediately after first login!

---

## Running the Application

### Development Mode

```bash
# Using Agents Backend CLI (recommended)
agents-backend run

# Or using uvicorn directly (for debugging)
python backend/run.py

# Or with uvicorn command
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode

```bash
# Using Granian (high performance)
granian --interface asgi --host 0.0.0.0 --port 8000 backend.main:app

# With multiple workers
granian --interface asgi --host 0.0.0.0 --port 8000 --workers 4 backend.main:app
```

### Starting Celery Workers

```bash
# Terminal 1: Start Celery worker
agents-backend celery-worker

# Terminal 2: Start Celery beat (scheduler)
agents-backend celery-beat

# Terminal 3: Start Flower (optional, for monitoring)
agents-backend celery-flower
```

### Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RUNNING SERVICES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Terminal 1:                Terminal 2:              Terminal 3: │
│  ┌──────────────┐           ┌──────────────┐        ┌──────────┐│
│  │agents-backend run│       │ celery-worker│        │ celery-  ││
│  │              │           │              │        │ beat     ││
│  │ FastAPI      │           │ Task         │        │          ││
│  │ Server       │           │ Executor     │        │ Scheduler││
│  │ :8000        │           │              │        │          ││
│  └──────┬───────┘           └──────┬───────┘        └────┬─────┘│
│         │                          │                      │      │
│         └──────────────────────────┼──────────────────────┘      │
│                                    │                             │
│                                    ▼                             │
│                           ┌──────────────┐                       │
│                           │    Redis     │                       │
│                           │   (Broker)   │                       │
│                           └──────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Verifying Installation

### 1. Check API Documentation

Open your browser and navigate to:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 2. Health Check Endpoint

```bash
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-12-29T13:20:08.419998+00:00",
  "version": "1.11.2",
  "service": "agents-backend"
}
```

> **Note**: The `/health` endpoint is available at the root path (not under `/api/v1`) for easy load balancer and monitoring integration.

### 3. Test Authentication

```bash
# Login request
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Expected response:
# {
#   "code": 200,
#   "msg": "Success",
#   "data": {
#     "access_token": "eyJ...",
#     "refresh_token": "eyJ...",
#     "token_type": "Bearer"
#   }
# }
```

### 4. Verify Redis Connection

```bash
redis-cli ping
# PONG

# Check for keys (after login)
redis-cli keys "*"
```

### 5. Verify Database

```bash
# MySQL
mysql -u root -p agents_backend -e "SHOW TABLES;"

# PostgreSQL
psql -U postgres agents_backend -c "\dt"
```

---

## Common Issues

### Issue 1: Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'backend'
```

**Solution:**
```bash
# Ensure you're in the project root
cd agents-backend

# Install in development mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Issue 2: Database Connection Failed

**Error:**
```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server")
```

**Solution:**
```bash
# Check MySQL is running
sudo systemctl status mysql

# Verify credentials in .env
cat .env | grep MYSQL

# Test connection manually
mysql -u root -p
```

### Issue 3: Redis Connection Refused

**Error:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**Solution:**
```bash
# Start Redis
sudo systemctl start redis-server

# Check Redis status
redis-cli ping
```

### Issue 4: Port Already in Use

**Error:**
```
OSError: [Errno 98] Address already in use
```

**Solution:**
```bash
# Find process using port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
agents-backend run --port 8001
```

### Issue 5: Permission Denied (Windows)

**Error:**
```
PermissionError: [WinError 5] Access is denied
```

**Solution:**
```powershell
# Run PowerShell as Administrator
# Or adjust execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Next Steps

Now that you have the application running, explore:

1. **[Architecture Overview](architecture-overview.md)** - Understand the system design
2. **[Backend Documentation](backend/README.md)** - Deep dive into components
3. **[API Reference](backend/app/README.md)** - Explore available endpoints
4. **[Security Guide](backend/common/security/README.md)** - Configure authentication
5. **[Plugin System](backend/plugin/README.md)** - Extend functionality
5. **[Plugin System](backend/plugin/README.md)** - Extend functionality
6. **[AI Agents](agent-system.md)** - Configure and use AI capabilities
7. **[Backend Documentation](backend/README.md)** - Deep dive into components

---

<div align="center">

**[← Back to Main Docs](README.md)** | **[Architecture Overview →](architecture-overview.md)**

</div>
