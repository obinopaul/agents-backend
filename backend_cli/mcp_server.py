"""
MCP Server for lgctl - LangGraph Memory Management.

Exposes lgctl functionality as MCP tools for AI agents.

Usage:
    # Run directly
    python -m lgctl.mcp_server

    # Or via entry point
    lgctl-mcp

    # Configure in Claude Desktop or other MCP clients
"""

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import LGCtlClient, get_client
from .commands import (
    AssistantCommands,
    MemoryOps,
    RunCommands,
    StoreCommands,
    ThreadCommands,
)
from .formatters import JsonFormatter

# Configure logging to stderr (NEVER use print with MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("lgctl.mcp")

# Load environment
load_dotenv()

# Initialize MCP server
mcp = FastMCP("lgctl")

# Global client instance (lazily initialized)
_client: Optional[LGCtlClient] = None
_formatter = JsonFormatter()


def get_lgctl_client() -> LGCtlClient:
    """Get or create the lgctl client."""
    global _client
    if _client is None:
        url = os.getenv("LANGSMITH_DEPLOYMENT_URL") or os.getenv("LANGGRAPH_URL")
        api_key = os.getenv("LANGSMITH_API_KEY")
        if not url:
            raise ValueError(
                "No LangGraph URL configured. Set LANGSMITH_DEPLOYMENT_URL or LANGGRAPH_URL environment variable."
            )
        _client = get_client(url=url, api_key=api_key)
        logger.info(f"Connected to LangGraph at {url}")
    return _client


# =============================================================================
# Store Tools
# =============================================================================


@mcp.tool()
async def store_list_namespaces(prefix: str = "", max_depth: int = 3, limit: int = 50) -> str:
    """List namespaces in the LangGraph memory store.

    Namespaces organize memories hierarchically (like directories).
    Use this to explore what data exists in the store.

    Args:
        prefix: Namespace prefix to filter (e.g., "user,123" for user 123's data).
                Use comma-separated values for nested namespaces.
        max_depth: How deep to traverse the namespace hierarchy (default: 3)
        limit: Maximum number of namespaces to return (default: 50)

    Returns:
        JSON list of namespaces found
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)
    result = await store.ls(namespace=prefix, max_depth=max_depth, limit=limit)
    return json.dumps(result, indent=2)


@mcp.tool()
async def store_list_items(namespace: str, limit: int = 20) -> str:
    """List items stored in a specific namespace.

    Args:
        namespace: The namespace to list items from (e.g., "user,123" or "website,products")
        limit: Maximum items to return (default: 20)

    Returns:
        JSON list of items with keys and metadata
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)
    result = await store.ls(namespace=namespace, limit=limit, show_items=True)
    return json.dumps(result, indent=2)


@mcp.tool()
async def store_get(namespace: str, key: str) -> str:
    """Get a specific item from the store by namespace and key.

    Args:
        namespace: The namespace (e.g., "user,123")
        key: The item key

    Returns:
        JSON object with the item's value and metadata, or error if not found
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)
    result = await store.get(namespace, key)
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Item not found: {namespace}/{key}"})


@mcp.tool()
async def store_put(namespace: str, key: str, value: str, is_json: bool = False) -> str:
    """Store an item in the memory store.

    Args:
        namespace: The namespace to store in (e.g., "user,123")
        key: The key for this item
        value: The value to store (string or JSON if is_json=True)
        is_json: If True, parse value as JSON object

    Returns:
        Confirmation of storage
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)

    if is_json:
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})
    else:
        parsed_value = value

    result = await store.put(namespace, key, parsed_value)
    return json.dumps(result, indent=2)


@mcp.tool()
async def store_delete(namespace: str, key: str) -> str:
    """Delete an item from the store.

    Args:
        namespace: The namespace (e.g., "user,123")
        key: The item key to delete

    Returns:
        Confirmation of deletion
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)
    result = await store.rm(namespace, key)
    return json.dumps(result, indent=2)


@mcp.tool()
async def store_search(namespace: str = "", query: str = "", limit: int = 10) -> str:
    """Search for items using semantic search.

    This uses embeddings to find semantically similar content.
    Great for finding relevant memories based on meaning, not just keywords.

    Args:
        namespace: Namespace to search in (empty string for all namespaces)
        query: Search query - finds items with semantically similar content
        limit: Maximum results to return (default: 10)

    Returns:
        JSON list of matching items with relevance scores
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)
    result = await store.search(namespace=namespace, query=query, limit=limit)
    return json.dumps(result, indent=2)


@mcp.tool()
async def store_count(namespace: str = "") -> str:
    """Count items in a namespace.

    Args:
        namespace: Namespace to count (empty for all)

    Returns:
        JSON with namespace and count
    """
    client = get_lgctl_client()
    store = StoreCommands(client, _formatter)
    result = await store.count(namespace)
    return json.dumps(result, indent=2)


# =============================================================================
# Thread Tools
# =============================================================================


@mcp.tool()
async def threads_list(limit: int = 20, status: str = "") -> str:
    """List conversation threads.

    Threads maintain state across multiple interactions with the agent.

    Args:
        limit: Maximum threads to return (default: 20)
        status: Filter by status: "idle", "busy", "interrupted", "error" (optional)

    Returns:
        JSON list of threads with IDs and metadata
    """
    client = get_lgctl_client()
    threads = ThreadCommands(client, _formatter)
    kwargs = {"limit": limit}
    if status:
        kwargs["status"] = status
    result = await threads.ls(**kwargs)
    return json.dumps(result, indent=2)


@mcp.tool()
async def threads_get(thread_id: str) -> str:
    """Get details for a specific thread.

    Args:
        thread_id: The thread ID

    Returns:
        JSON with thread details or error
    """
    client = get_lgctl_client()
    threads = ThreadCommands(client, _formatter)
    result = await threads.get(thread_id)
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Thread not found: {thread_id}"})


@mcp.tool()
async def threads_get_state(thread_id: str) -> str:
    """Get the current state of a thread.

    The state contains the accumulated values from all interactions.

    Args:
        thread_id: The thread ID

    Returns:
        JSON with thread state (values, checkpoint, etc.)
    """
    client = get_lgctl_client()
    threads = ThreadCommands(client, _formatter)
    result = await threads.state(thread_id)
    if result:
        return json.dumps(result, indent=2, default=str)
    return json.dumps({"error": f"Thread not found: {thread_id}"})


@mcp.tool()
async def threads_get_history(thread_id: str, limit: int = 10) -> str:
    """Get the state history of a thread.

    Shows how the thread state evolved over time (checkpoints).

    Args:
        thread_id: The thread ID
        limit: Maximum history entries (default: 10)

    Returns:
        JSON list of historical states
    """
    client = get_lgctl_client()
    threads = ThreadCommands(client, _formatter)
    result = await threads.history(thread_id, limit=limit)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def threads_create(thread_id: str = "", metadata_json: str = "") -> str:
    """Create a new thread.

    Args:
        thread_id: Optional custom thread ID (auto-generated if empty)
        metadata_json: Optional JSON metadata for the thread

    Returns:
        JSON with created thread details
    """
    client = get_lgctl_client()
    threads = ThreadCommands(client, _formatter)

    kwargs = {}
    if thread_id:
        kwargs["thread_id"] = thread_id
    if metadata_json:
        try:
            kwargs["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid metadata JSON: {e}"})

    result = await threads.create(**kwargs)
    return json.dumps(result, indent=2)


@mcp.tool()
async def threads_delete(thread_id: str) -> str:
    """Delete a thread.

    Args:
        thread_id: The thread ID to delete

    Returns:
        Confirmation of deletion
    """
    client = get_lgctl_client()
    threads = ThreadCommands(client, _formatter)
    result = await threads.rm(thread_id)
    return json.dumps(result, indent=2)


# =============================================================================
# Memory Operations Tools
# =============================================================================


@mcp.tool()
async def memory_analyze(namespace: str = "", detailed: bool = False) -> str:
    """Analyze memory usage and patterns.

    Provides insights into how memory is being used across namespaces.

    Args:
        namespace: Namespace to analyze (empty for all)
        detailed: Include detailed per-namespace analysis

    Returns:
        JSON analysis report with namespace breakdown and statistics
    """
    client = get_lgctl_client()
    ops = MemoryOps(client, _formatter)
    result = await ops.analyze(namespace, detailed=detailed)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def memory_stats() -> str:
    """Get overall memory statistics.

    Returns:
        JSON with total namespaces, items, and approximate size
    """
    client = get_lgctl_client()
    ops = MemoryOps(client, _formatter)
    result = await ops.stats()
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def memory_find(
    namespace: str = "", key_pattern: str = "", value_contains: str = "", limit: int = 50
) -> str:
    """Find memories matching specific criteria.

    Use this for exact/substring matching (vs semantic search).

    Args:
        namespace: Namespace to search (empty for all)
        key_pattern: Find items whose key contains this string
        value_contains: Find items whose value contains this string
        limit: Maximum results (default: 50)

    Returns:
        JSON list of matching items
    """
    client = get_lgctl_client()
    ops = MemoryOps(client, _formatter)
    result = await ops.find(
        namespace=namespace,
        key_pattern=key_pattern or None,
        value_contains=value_contains or None,
        limit=limit,
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def memory_grep(pattern: str, namespace: str = "", limit: int = 50) -> str:
    """Search memory values with a text/regex pattern.

    Like grep, searches through all stored values for matches.

    Args:
        pattern: Text or regex pattern to search for
        namespace: Namespace to search (empty for all)
        limit: Maximum results (default: 50)

    Returns:
        JSON list of matches with context
    """
    client = get_lgctl_client()
    ops = MemoryOps(client, _formatter)
    result = await ops.grep(pattern, namespace=namespace, limit=limit)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def memory_export(namespace: str = "", format: str = "json") -> str:
    """Export memories from a namespace.

    Useful for backup or analysis.

    Args:
        namespace: Namespace to export (empty for all)
        format: Output format - "json" or "jsonl"

    Returns:
        Exported data in the requested format
    """
    client = get_lgctl_client()
    ops = MemoryOps(client, _formatter)
    result = await ops.export(namespace=namespace, format=format)

    if "data" in result:
        if format == "jsonl":
            return result["data"]
        else:
            return json.dumps(result["data"], indent=2, default=str)
    return json.dumps(result, indent=2, default=str)


# =============================================================================
# Assistant Tools
# =============================================================================


@mcp.tool()
async def assistants_list(limit: int = 20) -> str:
    """List available assistants (graph configurations).

    Args:
        limit: Maximum assistants to return

    Returns:
        JSON list of assistants with IDs and metadata
    """
    client = get_lgctl_client()
    assistants = AssistantCommands(client, _formatter)
    result = await assistants.ls(limit=limit)
    return json.dumps(result, indent=2)


@mcp.tool()
async def assistants_get(assistant_id: str) -> str:
    """Get details for a specific assistant.

    Args:
        assistant_id: The assistant ID

    Returns:
        JSON with assistant details
    """
    client = get_lgctl_client()
    assistants = AssistantCommands(client, _formatter)
    result = await assistants.get(assistant_id)
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Assistant not found: {assistant_id}"})


# =============================================================================
# Run Tools
# =============================================================================


@mcp.tool()
async def runs_list(thread_id: str, limit: int = 20) -> str:
    """List runs for a thread.

    Runs are executions of the graph on a thread.

    Args:
        thread_id: The thread ID
        limit: Maximum runs to return

    Returns:
        JSON list of runs with status and metadata
    """
    client = get_lgctl_client()
    runs = RunCommands(client, _formatter)
    result = await runs.ls(thread_id, limit=limit)
    return json.dumps(result, indent=2)


@mcp.tool()
async def runs_get(thread_id: str, run_id: str) -> str:
    """Get details for a specific run.

    Args:
        thread_id: The thread ID
        run_id: The run ID

    Returns:
        JSON with run details
    """
    client = get_lgctl_client()
    runs = RunCommands(client, _formatter)
    result = await runs.get(thread_id, run_id)
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Run not found: {run_id}"})


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Run the MCP server."""
    logger.info("Starting lgctl MCP server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
