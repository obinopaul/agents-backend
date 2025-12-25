# FBA CLI Reference

The FBA CLI is a powerful command-line tool for managing and testing all Agents Backend functionality.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# The fba command becomes available after installing the package
pip install -e .

# Verify installation
fba --help
```

---

## Complete Command Reference

### Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `fba run` | Start the FastAPI server | `fba run --host 0.0.0.0 --port 8000` |
| `fba run --no-reload` | Production mode (no auto-reload) | `fba run --no-reload --workers 4` |
| `fba init` | Initialize database (drop & recreate tables, run SQL scripts) | `fba init` |
| `fba agent` | Run the Deep Research Agent interactively | `fba agent --debug` |
| `fba --sql <path>` | Execute a SQL script in a transaction | `fba --sql ./scripts/init.sql` |

### Agent Command Options

| Option | Default | Description |
|--------|---------|-------------|
| `--debug` | `False` | Enable debug logging |
| `--max-plan-iterations` | `1` | Maximum number of plan revision cycles |
| `--max-step-num` | `3` | Maximum steps in each research plan |
| `--enable-background-investigation` | `True` | Run web search before planning |
| `--enable-clarification` | `False` | Enable multi-turn Q&A clarification |
| `--max-clarification-rounds` | `None` | Limit clarification rounds |

### Server Command Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Host IP address |
| `--port` | `8000` | Port number |
| `--no-reload` | `False` | Disable auto-reload |
| `--workers` | `1` | Number of worker processes (use with `--no-reload`) |

### Celery Commands

| Command | Description | Example |
|---------|-------------|---------|
| `fba celery worker` | Start Celery background worker | `fba celery worker -l info` |
| `fba celery beat` | Start Celery scheduler | `fba celery beat -l info` |
| `fba celery flower` | Start Celery monitoring UI | `fba celery flower --port 8555` |

### Code Generation

| Command | Description |
|---------|-------------|
| `fba codegen` | Generate CRUD code from database tables (interactive) |
| `fba codegen import` | Import table schema for code generation |

---

## Quick Examples

### Test the Deep Research Agent

```bash
# Interactive mode - asks for language and question
fba agent

# With debug logging
fba agent --debug

# With custom parameters
fba agent --max-step-num 5 --enable-clarification
```

**What happens:**
1. Select language (English / 中文)
2. Choose a built-in question or ask your own
3. Watch the agent research, plan, and generate a report

### Start Development Server

```bash
# Development mode with auto-reload
fba run

# Listen on all interfaces
fba run --host 0.0.0.0

# Production mode with multiple workers
fba run --no-reload --workers 4
```

### Initialize Fresh Database

```bash
# WARNING: This drops all tables!
fba init
```

This will:
1. Drop existing database tables
2. Clear Redis caches
3. Create fresh tables
4. Execute all SQL initialization scripts
5. Install plugin SQL scripts

---

## Running Without `fba` in PATH

If `fba` command is not in your PATH, use Python directly:

```bash
# Using Python to invoke CLI
python -c "import sys; sys.argv=['fba', 'agent']; from backend.cli import main; main()"

# Or run as module
python -m backend.cli agent
```

---

## Environment Variables

The CLI respects these environment variables (set in `backend/.env`):

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for LLM operations |
| `TAVILY_API_KEY` | Required for web search |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

---

## Related Documentation

- [FastAPI Backend Guide](fastapi-backend.md) - Full API reference
- [DeepAgents CLI](deepagents-cli.md) - Interactive coding assistant
- [Main README](../../README.md) - Project overview
