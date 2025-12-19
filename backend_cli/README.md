# lgctl - LangGraph Memory Management CLI

[![PyPI version](https://badge.fury.io/py/lgctl.svg)](https://badge.fury.io/py/lgctl)
[![Python](https://img.shields.io/pypi/pyversions/lgctl.svg)](https://pypi.org/project/lgctl/)
[![CI](https://github.com/Barneyjm/lgctl/actions/workflows/ci.yml/badge.svg)](https://github.com/Barneyjm/lgctl/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Unix-style command-line tool for managing LangGraph memory stores, threads, runs, assistants, and crons.

## Features

- **Unix-style commands**: Familiar commands like `ls`, `get`, `put`, `rm`, `mv`, `cp`
- **Multiple output formats**: Table (human-readable), JSON (for piping), Raw (for scripts)
- **Interactive REPL**: Context-aware shell with namespace navigation
- **Higher-level operations**: Analyze, prune, export/import, dedupe, grep
- **MCP Server**: Plug into AI agents via Model Context Protocol
- **Flexible connectivity**: Works with local dev servers and remote LangSmith deployments

## Installation

```bash
# From the package directory
pip install lgctl

# With MCP server support
pip install -e "lgctl[mcp]"
```

## Quick Start

```bash
# Set your environment (or use .env file)
export LANGSMITH_DEPLOYMENT_URL=https://your-deployment.langsmith.com
export LANGSMITH_API_KEY=your-api-key

# List namespaces
lgctl store ls

# Search items
lgctl store search user,123 "preferences"

# Get a specific item
lgctl store get user,123 settings

# Interactive mode
lgctl repl
```

## Commands

### Command Aliases

All main commands have short aliases for faster typing:

| Full Command | Alias |
| ------------ | ----- |
| `store`      | `s`   |
| `threads`    | `t`   |
| `runs`       | `r`   |
| `assistants` | `a`   |
| `crons`      | `c`   |
| `ops`        | `o`   |

### Store Commands

```bash
lgctl store ls [namespace]              # List namespaces
lgctl store ls -i user,123              # List items in namespace
lgctl store ls -d 10                    # List with max depth
lgctl store get user,123 key            # Get item
lgctl store put user,123 key "value"    # Store item
lgctl store rm user,123 key             # Delete item
lgctl store search user,123 "query"     # Semantic search
lgctl store mv src,ns key dst,ns        # Move item
lgctl store cp src,ns key dst,ns        # Copy item
lgctl store count user,123              # Count items
lgctl store tree                        # Show namespace tree

# Short alias: 's' for 'store'
lgctl s ls                              # Same as: lgctl store ls
```

### Thread Commands

```bash
lgctl threads ls                        # List threads
lgctl threads get <thread_id>           # Get thread details
lgctl threads create                    # Create new thread
lgctl threads rm <thread_id>            # Delete thread
lgctl threads state <thread_id>         # Get thread state
lgctl threads history <thread_id>       # Get state history

# Short alias: 't' for 'threads'
lgctl t ls                              # Same as: lgctl threads ls
```

### Run Commands

```bash
lgctl runs ls <thread_id>               # List runs
lgctl runs get <thread_id> <run_id>     # Get run details
lgctl runs cancel <thread_id> <run_id>  # Cancel run

# Short alias: 'r' for 'runs'
lgctl r ls <thread_id>                  # Same as: lgctl runs ls
```

### Assistant Commands

```bash
lgctl assistants ls                     # List assistants
lgctl assistants get <id>               # Get assistant
lgctl assistants schema <id>            # Get schemas
lgctl assistants graph <id>             # Get graph definition

# Short alias: 'a' for 'assistants'
lgctl a ls                              # Same as: lgctl assistants ls
```

### Cron Commands

```bash
lgctl crons ls                          # List cron jobs
lgctl crons get <cron_id>               # Get cron details
lgctl crons rm <cron_id>                # Delete cron

# Short alias: 'c' for 'crons'
lgctl c ls                              # Same as: lgctl crons ls
```

### Memory Operations

```bash
lgctl ops analyze [namespace]           # Analyze memory usage
lgctl ops analyze -d                    # Detailed analysis
lgctl ops stats                         # Overall statistics
lgctl ops export -o backup.jsonl        # Export memories
lgctl ops export user,123 -o user.jsonl # Export specific namespace
lgctl ops export -k "pref" -o prefs.jsonl  # Export keys containing "pref"
lgctl ops export -v "pizza" -o pizza.jsonl # Export values containing "pizza"
lgctl ops export --export-format json   # Export as JSON (default: jsonl)
lgctl ops import backup.jsonl           # Import memories
lgctl ops import backup.jsonl --dry-run # Preview import
lgctl ops import backup.jsonl --overwrite  # Overwrite existing
lgctl ops import backup.jsonl --prefix archive  # Add namespace prefix
lgctl ops prune user,123 --days 30      # Remove old items (dry-run)
lgctl ops prune user,123 --days 30 --force  # Actually delete
lgctl ops dedupe user,123               # Remove duplicates (dry-run)
lgctl ops dedupe user,123 --force       # Actually remove duplicates
lgctl ops find -k pattern               # Find by key pattern
lgctl ops find -v "search"              # Find by value content
lgctl ops grep "search term"            # Search all values

# Short alias: 'o' for 'ops'
lgctl o stats                           # Same as: lgctl ops stats
```

## Interactive REPL

```bash
lgctl repl
```

In the REPL:

```
lgctl> use user,123              # Set working namespace
[user,123]> ls -i                # List items
[user,123]> s "preferences"      # Quick search
[user,123]> get settings         # Get item (namespace implied)
[user,123]> put newkey "value"   # Store (namespace implied)
[user,123]> ..                   # Go up one level
[user]> cd /                     # Go to root
lgctl> threads                   # List threads
lgctl> analyze                   # Analyze all memory
lgctl> exit
```

## Output Formats

```bash
# Human-readable table (default)
lgctl store ls

# JSON for piping to jq
lgctl -f json store ls | jq '.[] | .namespace'

# Raw for scripting
lgctl -f raw store ls
```

## Configuration

### Environment Variables

```bash
LANGSMITH_DEPLOYMENT_URL    # LangGraph deployment URL
LANGGRAPH_URL              # Alternative URL variable
LANGSMITH_API_KEY          # API key for authentication
```

### .env File

```env
LANGSMITH_DEPLOYMENT_URL=https://your-deployment.langsmith.com
LANGSMITH_API_KEY=lsv2_...
```

### Command Line

```bash
lgctl -u http://localhost:8123 store ls
lgctl -k your-api-key store ls
```

## Usage Patterns

### Backup and Restore

```bash
# Export all memories
lgctl ops export -o backup.jsonl

# Export specific namespace
lgctl ops export user,123 -o user_backup.jsonl

# Export with filters
lgctl ops export -k "settings" -o settings.jsonl
lgctl ops export website,products -v "haltech" -o haltech.jsonl

# Export as JSON instead of JSONL
lgctl ops export --export-format json -o backup.json

# Restore (dry-run first)
lgctl ops import backup.jsonl --dry-run

# Restore (actually import)
lgctl ops import backup.jsonl

# Restore with overwrite
lgctl ops import backup.jsonl --overwrite
```

### Cleanup Old Data

```bash
# Preview what would be deleted
lgctl ops prune user,123 --days 90 --dry-run

# Actually delete
lgctl ops prune user,123 --days 90 --force
```

### Find Specific Data

```bash
# Find by key pattern
lgctl ops find -k "pref"

# Find by value content
lgctl ops find -v "pizza"

# Grep across all memories
lgctl ops grep "email@example.com"
```

### Migrate Data

```bash
# Move item between namespaces
lgctl store mv old,ns key new,ns

# Copy entire namespace (via export/import)
lgctl ops export old,ns -o temp.jsonl
lgctl ops import temp.jsonl --prefix new
```

## MCP Server (for AI Agents)

lgctl includes an MCP (Model Context Protocol) server that exposes memory management tools to AI agents.

### Running the MCP Server

```bash
# Install with MCP support
pip install -e ".[mcp]"

# Run the server
lgctl-mcp

# Or via Python
python -m lgctl.mcp_server
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "lgctl": {
      "command": "lgctl-mcp",
      "env": {
        "LANGSMITH_DEPLOYMENT_URL": "https://your-deployment.langsmith.com",
        "LANGSMITH_API_KEY": "your-api-key"
      }
    }
  }
}
```

Or with uv:

```json
{
  "mcpServers": {
    "lgctl": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/lgctl", "lgctl-mcp"],
      "env": {
        "LANGSMITH_DEPLOYMENT_URL": "https://your-deployment.langsmith.com",
        "LANGSMITH_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Available MCP Tools

| Tool                    | Description                  |
| ----------------------- | ---------------------------- |
| `store_list_namespaces` | List namespaces in the store |
| `store_list_items`      | List items in a namespace    |
| `store_get`             | Get a specific item          |
| `store_put`             | Store an item                |
| `store_delete`          | Delete an item               |
| `store_search`          | Semantic search              |
| `store_count`           | Count items                  |
| `threads_list`          | List threads                 |
| `threads_get`           | Get thread details           |
| `threads_get_state`     | Get thread state             |
| `threads_get_history`   | Get thread history           |
| `threads_create`        | Create a thread              |
| `threads_delete`        | Delete a thread              |
| `memory_analyze`        | Analyze memory usage         |
| `memory_stats`          | Get memory statistics        |
| `memory_find`           | Find by key/value pattern    |
| `memory_grep`           | Search values with regex     |
| `memory_export`         | Export memories              |
| `assistants_list`       | List assistants              |
| `assistants_get`        | Get assistant details        |
| `runs_list`             | List runs for a thread       |
| `runs_get`              | Get run details              |

### Agent Usage Example

Once configured, an AI agent can use the tools naturally:

```
Agent: Let me check what memories are stored for this user.
[Uses store_list_items with namespace="user,123"]

Agent: I found 15 items. Let me search for food preferences.
[Uses store_search with namespace="user,123", query="food preferences"]

Agent: The user prefers Italian food. Let me update their profile.
[Uses store_put with namespace="user,123", key="food_pref", value="Italian cuisine"]
```

## Python API

```python
from lgctl import get_client
from lgctl.commands import StoreCommands
from lgctl.formatters import get_formatter

# Create client
client = get_client(url="http://localhost:8123")

# Use commands programmatically
formatter = get_formatter("json")
store = StoreCommands(client, formatter)

# Async operations
import asyncio

async def main():
    items = await store.search("user,123", "preferences")
    print(items)

asyncio.run(main())
```

## Architecture

```
lgctl/
├── __init__.py          # Package exports
├── __main__.py          # python -m lgctl entry
├── client.py            # LangGraph SDK wrapper
├── cli.py               # CLI argument parser & dispatcher
├── repl.py              # Interactive REPL
├── formatters.py        # Output formatting (table/json/raw)
├── mcp_server.py        # MCP server for AI agents
└── commands/
    ├── __init__.py
    ├── store.py         # Store operations
    ├── threads.py       # Thread operations
    ├── runs.py          # Run operations
    ├── assistants.py    # Assistant operations
    ├── crons.py         # Cron operations
    └── ops.py           # Higher-level operations
```

## License

MIT
