# CLAUDE.md - lgctl Project Guide

## Project Overview

**lgctl** (LangGraph Control) is a Unix-style CLI for managing LangGraph stores, threads, runs, assistants, and crons. It provides both a command-line interface and an MCP server for AI agent integration.

## Quick Commands

```bash
# Development setup
uv venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e ".[dev]"

# Run tests
uv run pytest lgctl/tests/ -v

# Run specific test file
uv run pytest lgctl/tests/test_cli.py -v

# Run MCP server tests (requires mcp package)
uv pip install -e ".[mcp]"
uv run pytest lgctl/tests/test_mcp_server.py -v

# Linting and formatting
uv run ruff check lgctl/              # Check for lint errors
uv run ruff check lgctl/ --fix        # Auto-fix lint errors
uv run ruff format lgctl/             # Format code
```

## Architecture

```
lgctl/
├── __init__.py          # Package exports
├── cli.py               # CLI entry point and argument parsing
├── client.py            # LGCtlClient wrapper around langgraph-sdk
├── repl.py              # Interactive REPL with namespace navigation
├── mcp_server.py        # MCP server for AI agent integration
├── formatters.py        # Output formatters (table, json, raw)
├── commands/
│   ├── __init__.py      # Command exports
│   ├── store.py         # Store operations (ls, get, put, rm, search, etc.)
│   ├── threads.py       # Thread operations
│   ├── runs.py          # Run operations
│   ├── assistants.py    # Assistant operations
│   ├── crons.py         # Cron job operations
│   └── ops.py           # Memory operations (analyze, grep, find, export, etc.)
└── tests/
    ├── conftest.py      # Mock clients and fixtures
    └── test_*.py        # Test files
```

## Key Patterns

### Namespace Format
Namespaces use comma-separated components: `user,123,preferences`
- `parse_namespace("user,123")` → `("user", "123")`
- `format_namespace(("user", "123"))` → `"user,123"`

### Client Structure
`LGCtlClient` wraps the langgraph-sdk and provides access to:
- `client.store` - Key-value store with semantic search
- `client.threads` - Conversation threads
- `client.runs` - Execution runs
- `client.assistants` - Assistant configurations
- `client.crons` - Scheduled jobs

### Command Classes
Each command module has a class that takes `(client, formatter)`:
```python
store = StoreCommands(client, formatter)
result = await store.ls(namespace="user,123")
```

### Formatters
Three output formats: `TableFormatter`, `JsonFormatter`, `RawFormatter`
- Use `get_formatter("json")` to get formatter by name

## CLI Usage

```bash
# Store commands
lgctl store ls                      # List namespaces
lgctl store ls -i user,123          # List items in namespace
lgctl store get user,123 key        # Get item
lgctl store put user,123 key value  # Store item
lgctl store search user,123 "query" # Semantic search

# Thread commands
lgctl threads ls                    # List threads
lgctl threads get <id>              # Get thread
lgctl threads state <id>            # Get thread state

# Memory operations
lgctl ops analyze                   # Analyze memory usage
lgctl ops grep "pattern"            # Search all values
lgctl ops find -k "key_pattern"     # Find by key pattern
lgctl ops export -o backup.jsonl    # Export memories

# Interactive mode
lgctl repl
```

## Entry Points

- `lgctl` → `lgctl.cli:main` - Main CLI
- `lgctl-mcp` → `lgctl.mcp_server:main` - MCP server

## Environment Variables

- `LANGSMITH_DEPLOYMENT_URL` - LangGraph server URL (primary)
- `LANGGRAPH_URL` - Alternative URL variable
- `LANGSMITH_API_KEY` - API key for authentication

## Testing Notes

- Tests use mock clients in `conftest.py` - no live server needed
- MCP tests auto-skip if `mcp` package not installed
- Async tests use `pytest-asyncio` with auto mode
- Run `uv pip install -e ".[dev,mcp]"` for full test suite
- Always add new tests for new or improved functionality

## Code Style

This project uses **ruff** for linting and formatting:
- Line length: 100 characters
- Target: Python 3.10+
- Rules: E (errors), F (pyflakes), I (isort), W (warnings)

Before committing, ensure code passes:
```bash
uv run ruff check lgctl/
uv run ruff format --check lgctl/
```

## Dependencies

- `langgraph-sdk>=0.2.10` - LangGraph API client
- `python-dotenv>=1.0.0` - Environment loading
- `typing_extensions>=4.0.0` - Required by langgraph-sdk
- `mcp>=1.0.0` (optional) - MCP server support
- `ruff>=0.8.0` (dev) - Linting and formatting
