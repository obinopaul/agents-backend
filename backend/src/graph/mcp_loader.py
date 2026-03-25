"""
Shared MCP Tool Loader with Retry Logic.

This module provides a robust, reusable function for loading MCP tools
from one or more MCP servers. It includes:
    - Retry logic (3 attempts with 2s delay between retries)
    - Pre-flight health check for sandbox MCP servers
    - Detailed logging for diagnostics
    - Graceful degradation (returns empty list on total failure)

Usage:
    from backend.src.graph.mcp_loader import load_mcp_tools_with_retry

    tools = await load_mcp_tools_with_retry(
        mcp_servers={"sandbox": {"transport": "http", "url": "https://.../mcp"}},
        mcp_url="https://...",
        enabled_tools={"my_tool": "my_server"},
        max_retries=3,
        retry_delay=2.0,
    )

This replaces the duplicated inline MCP loading logic found in:
    - backend/src/graph/nodes.py
    - backend/src/module/*/executor/node.py
    - backend/src/module/*/coder/node.py
    - backend/src/module/*/planner/node.py
    - backend/src/module/*/analyzer/node.py
    - backend/src/module/*/verifier/node.py
"""

import asyncio
import logging
from typing import Dict, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


async def load_mcp_tools_with_retry(
    mcp_servers: Dict[str, dict],
    mcp_url: Optional[str] = None,
    enabled_tools: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    caller: str = "unknown",
) -> List:
    """
    Load MCP tools from configured MCP servers with retry logic.

    This function handles the common pattern of connecting to MCP servers,
    listing available tools, filtering them, and attributing their source.
    It retries on failure or empty results.

    Args:
        mcp_servers: Dict of server_name -> connection config
            (e.g. {"sandbox": {"transport": "http", "url": "https://.../mcp"}})
        mcp_url: The dynamic sandbox MCP base URL (without /mcp suffix).
            Used to determine if tools should be accepted from the dynamic
            sandbox (if set, all tools from sandbox are accepted).
        enabled_tools: Dict of tool_name -> server_name for statically
            configured tools. Only tools in this dict (or from dynamic
            sandbox) are accepted.
        max_retries: Maximum number of attempts (default: 3).
        retry_delay: Seconds between retries (default: 2.0).
        caller: Name of the calling function for log messages.

    Returns:
        List of loaded MCP tools (LangChain BaseTool instances), filtered
        and with source attribution in descriptions. Returns empty list if
        all retries fail.
    """
    if not mcp_servers:
        return []

    if enabled_tools is None:
        enabled_tools = {}

    all_tools = []
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"[MCP_TOOLS:{caller}] Loading from {len(mcp_servers)} server(s): "
                f"{list(mcp_servers.keys())} (attempt {attempt}/{max_retries})"
            )

            # Pre-flight health check on first attempt for sandbox MCP
            if mcp_url and attempt == 1:
                await _health_check(mcp_url, caller)

            client = MultiServerMCPClient(mcp_servers)
            all_tools = await client.get_tools()

            logger.info(
                f"[MCP_TOOLS:{caller}] get_tools() returned {len(all_tools)} tools "
                f"on attempt {attempt}"
            )

            if all_tools:
                for t in all_tools:
                    logger.info(f"[MCP_TOOLS:{caller}] Found tool: {t.name}")
                break  # Success
            else:
                logger.warning(
                    f"[MCP_TOOLS:{caller}] get_tools() returned 0 tools "
                    f"on attempt {attempt}/{max_retries}"
                )
                last_error = "get_tools() returned empty list"
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        except Exception as e:
            last_error = e
            logger.warning(
                f"[MCP_TOOLS:{caller}] Failed on attempt {attempt}/{max_retries}: {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"[MCP_TOOLS:{caller}] All {max_retries} attempts failed. "
                    f"Last error: {e}",
                    exc_info=True,
                )

    # Filter and attribute tools
    loaded_tools: List = []
    is_dynamic_sandbox = bool(mcp_url)

    for tool in all_tools:
        is_static_allowed = tool.name in enabled_tools

        if is_static_allowed or is_dynamic_sandbox:
            source = enabled_tools.get(
                tool.name, "sandbox" if is_dynamic_sandbox else "unknown"
            )
            tool.description = f"Powered by '{source}'.\n{tool.description}"
            loaded_tools.append(tool)
            logger.debug(f"[MCP_TOOLS:{caller}] Loaded: {tool.name} from {source}")

    logger.info(
        f"[MCP_TOOLS:{caller}] Loaded {len(loaded_tools)} MCP tools "
        f"(from {len(all_tools)} available)"
    )

    if len(loaded_tools) == 0 and mcp_url:
        logger.error(
            f"[MCP_TOOLS:{caller}] WARNING: mcp_url is set ({mcp_url}) but "
            f"0 MCP tools were loaded! Last error: {last_error}. "
            "Agent will run without sandbox tools (file_read, shell_run_command, "
            "excalidraw_*, slide_write, etc)."
        )

    return loaded_tools


async def _health_check(mcp_url: str, caller: str) -> None:
    """Run a pre-flight health check against the sandbox MCP server."""
    try:
        import httpx

        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{mcp_url}/health", timeout=10.0)
            if resp.status_code == 200:
                logger.info(f"[MCP_TOOLS:{caller}] Sandbox MCP health check passed")
            else:
                logger.warning(
                    f"[MCP_TOOLS:{caller}] Sandbox MCP health check "
                    f"returned {resp.status_code}"
                )
    except Exception as e:
        logger.warning(
            f"[MCP_TOOLS:{caller}] Sandbox MCP health check failed: {e}. "
            "Will still attempt tool loading."
        )
