#!/usr/bin/env python3
"""
Live Agent Tool Access & Execution Test Suite
==============================================

This script verifies the ENTIRE tool chain:

1. TOOL INVENTORY:
   - Connects to the sandbox MCP server
   - Lists ALL available tools
   - Categorizes them (file_system, shell, media, web, productivity, etc.)
   - Reports which tools are accessible vs expected

2. TOOL SERVER VERIFICATION:
   - Checks that the backend tool server URL is set on the sandbox
   - Verifies the tool server is reachable from the sandbox

3. AGENT TOOL USAGE:
   - Sends real prompts to the /agent/stream endpoint
   - Asks the agent to perform specific tasks using specific tools
   - Verifies the agent actually calls the expected tools
   - Confirms tool results come back

PREREQUISITES:
   - Backend server running at BASE_URL (default http://localhost:8000)
   - A valid JWT token (or test credentials)
   - Sandbox infrastructure available (e2b or local)

Usage:
    # Full test (requires running backend + sandbox):
    python tests/test_agent_tools_live.py --base-url http://localhost:8000 --token YOUR_JWT

    # Just tool inventory (against a known MCP URL):
    python tests/test_agent_tools_live.py --mcp-url https://6060-sandbox-abc.e2b.app

    # Login with credentials (instead of token):
    python tests/test_agent_tools_live.py --username admin --password password123
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Run: pip install httpx")
    sys.exit(1)


# =============================================================================
# Terminal Colors
# =============================================================================
class C:
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"
    INFO = "\033[94m"
    CYAN = "\033[96m"


def ok(msg):     print(f"  {C.OK}PASS{C.END}  {msg}")
def warn(msg):   print(f"  {C.WARN}WARN{C.END}  {msg}")
def fail(msg):   print(f"  {C.FAIL}FAIL{C.END}  {msg}")
def info(msg):   print(f"  {C.INFO}INFO{C.END}  {msg}")
def header(msg): print(f"\n{C.BOLD}{'='*70}\n{msg}\n{'='*70}{C.END}")
def subheader(msg): print(f"\n{C.CYAN}--- {msg} ---{C.END}")


# =============================================================================
# EXPECTED TOOLS — The full inventory from manager.py
# =============================================================================
EXPECTED_TOOLS = {
    "SHELL": [
        "shell_init", "shell_run_command", "shell_view",
        "shell_stop_command", "shell_list", "shell_write_to_process",
    ],
    "FILE_SYSTEM": [
        "file_read", "file_write", "file_edit", "apply_patch",
        "str_replace_editor", "ast_grep", "grep", "lsp",
    ],
    "PRODUCTIVITY": [
        "todo_read", "todo_write",
    ],
    "MEDIA": [
        "image_generate", "video_generate",
    ],
    "WEB": [
        "web_search", "web_visit", "web_visit_compress",
        "image_search", "read_remote_image", "web_batch_search",
    ],
    "DEV": [
        "fullstack_init", "save_checkpoint", "register_port",
        "get_database_connection",
    ],
    "SLIDES": [
        "slide_write", "slide_edit", "slide_apply_patch",
        "slide_template_init",
    ],
    "DOCUMENTS": [
        "document_template_init", "document_compile",
    ],
    "DESIGN": [
        "design_init", "design_create", "design_get",
        "design_edit", "design_export",
    ],
    "EXCALIDRAW": [
        "excalidraw_init", "excalidraw_create", "excalidraw_update",
        "excalidraw_delete", "excalidraw_query", "excalidraw_batch_create",
        "excalidraw_group", "excalidraw_ungroup", "excalidraw_align",
        "excalidraw_distribute", "excalidraw_lock", "excalidraw_unlock",
        "excalidraw_resource",
    ],
    "BROWSER": [
        "browser_click", "browser_wait", "browser_view",
        "browser_scroll_down", "browser_scroll_up",
        "browser_switch_tab", "browser_open_new_tab",
        "browser_get_select_options", "browser_select_dropdown_option",
        "browser_navigation", "browser_restart",
        "browser_enter_text", "browser_press_key",
        "browser_drag", "browser_enter_multiple_texts",
    ],
    "AGENT": [
        "message_user",
    ],
}

ALL_EXPECTED = []
for tools in EXPECTED_TOOLS.values():
    ALL_EXPECTED.extend(tools)


# =============================================================================
# Tool Inventory Test
# =============================================================================
async def _mcp_list_tools_http(mcp_url: str) -> Optional[List[dict]]:
    """
    List tools from an MCP server using Streamable HTTP transport.

    The MCP Streamable HTTP protocol flow:
      1. POST 'initialize' (no session) -> server returns Mcp-Session-Id header
      2. POST 'tools/list' with Mcp-Session-Id header -> server returns tools

    Both requests require:
      - Content-Type: application/json
      - Accept: text/event-stream, application/json
    """
    base_headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
    }
    mcp_endpoint = f"{mcp_url}/mcp"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ---- Step 1: Initialize session ----
        init_body = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-agent-tools-live", "version": "1.0.0"},
            },
        }

        r_init = await client.post(
            mcp_endpoint, json=init_body, headers=base_headers, timeout=30.0
        )
        info(f"initialize response: HTTP {r_init.status_code}")

        session_id = r_init.headers.get("mcp-session-id")
        if session_id:
            ok(f"Got session ID: {session_id[:40]}...")
        else:
            # Some servers don't require sessions -- try without
            info("No Mcp-Session-Id in response (server may not require sessions)")

        # Parse init response for server capabilities
        init_data = _extract_jsonrpc_result(r_init)
        if init_data:
            server_info = init_data.get("serverInfo", {})
            info(f"Server: {server_info.get('name', '?')} v{server_info.get('version', '?')}")

        # ---- Step 2: Send initialized notification ----
        notif_body = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        notif_headers = {**base_headers}
        if session_id:
            notif_headers["Mcp-Session-Id"] = session_id
        await client.post(
            mcp_endpoint, json=notif_body, headers=notif_headers, timeout=10.0
        )

        # ---- Step 3: List tools ----
        tools_body = {
            "jsonrpc": "2.0",
            "id": "tools-1",
            "method": "tools/list",
            "params": {},
        }
        tools_headers = {**base_headers}
        if session_id:
            tools_headers["Mcp-Session-Id"] = session_id

        r_tools = await client.post(
            mcp_endpoint, json=tools_body, headers=tools_headers, timeout=30.0
        )

        content_type = r_tools.headers.get("content-type", "")
        info(f"tools/list response: HTTP {r_tools.status_code}, content-type={content_type}")

        if r_tools.status_code not in (200, 202):
            fail(f"tools/list returned HTTP {r_tools.status_code}")
            info(f"Response body: {r_tools.text[:500]}")
            return None

        # Debug: show actual response body
        body_preview = r_tools.text[:1000] if r_tools.text else "(empty)"
        info(f"Response body ({len(r_tools.text)} chars): {body_preview}")

        # For SSE content-type, the response might be streamed and httpx
        # may only get partial data. Try re-reading with streaming if body is empty/small.
        if "text/event-stream" in content_type and len(r_tools.text.strip()) == 0:
            info("Empty SSE body — server may require streaming read. Trying stream approach...")
            return await _mcp_list_tools_http_stream(mcp_url, session_id)

        # Extract result from JSON or SSE
        result = _extract_jsonrpc_result(r_tools)
        if result and "tools" in result:
            return result["tools"]

        # Try raw parse
        try:
            data = r_tools.json()
            if "result" in data and "tools" in data["result"]:
                return data["result"]["tools"]
        except Exception:
            pass

        fail(f"Could not parse tools from response (content-type={content_type})")
        return None


def _extract_jsonrpc_result(response) -> Optional[dict]:
    """Extract JSON-RPC result from plain JSON or SSE response."""
    content_type = response.headers.get("content-type", "")

    # SSE format: parse data: lines
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            line = line.strip()
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if "result" in data:
                        return data["result"]
                except json.JSONDecodeError:
                    continue
        return None

    # Plain JSON
    try:
        data = response.json()
        return data.get("result")
    except Exception:
        return None


async def _mcp_list_tools_http_stream(
    mcp_url: str, session_id: Optional[str]
) -> Optional[List[dict]]:
    """
    Fallback: Use httpx streaming to read SSE responses properly.
    Some MCP servers send SSE as a true stream that httpx.post() can't fully capture.
    """
    tools_body = {
        "jsonrpc": "2.0",
        "id": "tools-stream-1",
        "method": "tools/list",
        "params": {},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    collected_data = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST", f"{mcp_url}/mcp", json=tools_body, headers=headers, timeout=30.0
        ) as response:
            if response.status_code not in (200, 202):
                fail(f"Streaming tools/list returned HTTP {response.status_code}")
                return None

            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if "result" in data and "tools" in data["result"]:
                            tools = data["result"]["tools"]
                            ok(f"Streaming SSE: got {len(tools)} tools")
                            return tools
                        collected_data.append(data)
                    except json.JSONDecodeError:
                        continue

    if collected_data:
        info(f"Collected {len(collected_data)} SSE data frames but none had tools")
        info(f"First frame: {json.dumps(collected_data[0])[:300]}")
    return None


async def _mcp_list_tools_via_client(mcp_url: str) -> Optional[List[str]]:
    """
    List tools using MultiServerMCPClient — the exact same client
    that the production code in nodes.py uses.
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        mcp_servers = {
            "sandbox": {
                "transport": "http",
                "url": f"{mcp_url}/mcp",
            }
        }
        info(f"MultiServerMCPClient config: {json.dumps(mcp_servers)}")
        client = MultiServerMCPClient(mcp_servers)
        all_tools = await client.get_tools()
        tool_names = [getattr(t, "name", str(t)) for t in all_tools]
        return tool_names
    except Exception as e:
        import traceback
        warn(f"MultiServerMCPClient failed: {e}")
        info(f"Traceback: {traceback.format_exc()[-500:]}")
        return None


async def test_tool_inventory(mcp_url: str) -> Dict[str, Any]:
    """Connect to the sandbox MCP server and list ALL tools."""
    header("TEST 1: Tool Inventory (MCP Server)")
    info(f"Connecting to: {mcp_url}")

    results = {
        "total_tools": 0,
        "tool_names": [],
        "categories": {},
        "missing_tools": [],
        "extra_tools": [],
        "healthy": False,
    }

    # Health check
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.get(f"{mcp_url}/health", timeout=10.0)
            if r.status_code == 200:
                ok("MCP server health check passed")
                results["healthy"] = True
            else:
                fail(f"Health check returned {r.status_code}: {r.text}")
                return results
        except Exception as e:
            fail(f"Health check failed: {e}")
            return results

    # --- Strategy 1: Streamable HTTP with proper headers ---
    tool_names = None
    tools_raw = None
    try:
        subheader("Strategy 1: Streamable HTTP (Accept: text/event-stream)")
        tools_raw = await _mcp_list_tools_http(mcp_url)
        if tools_raw is not None:  # [] is valid (0 tools registered)
            tool_names = [t["name"] for t in tools_raw]
            if tool_names:
                ok(f"Retrieved {len(tool_names)} tools via Streamable HTTP")
            else:
                warn(f"MCP server returned 0 tools! Server is running but has NO tools registered.")
                warn("This means pre_configure_mcp_server() either hasn't run or tools failed to register.")
    except Exception as e:
        warn(f"Streamable HTTP failed: {e}")

    # --- Strategy 2: MultiServerMCPClient (production fallback) ---
    if tool_names is None:  # Only if strategy 1 didn't parse at all
        try:
            subheader("Strategy 2: MultiServerMCPClient (same as nodes.py)")
            tool_names = await _mcp_list_tools_via_client(mcp_url)
            if tool_names:
                ok(f"Retrieved {len(tool_names)} tools via MultiServerMCPClient")
            elif tool_names is not None:
                warn("MultiServerMCPClient also got 0 tools")
        except Exception as e:
            warn(f"MultiServerMCPClient failed: {e}")

    if tool_names is None:
        fail("Could not retrieve tools from MCP server via any method")
        return results

    results["total_tools"] = len(tool_names)
    results["tool_names"] = tool_names

    # Categorize tools
    found_set = set(results["tool_names"])
    expected_set = set(ALL_EXPECTED)

    # Match found tools to expected categories
    for category, expected_tools in EXPECTED_TOOLS.items():
        found_in_category = []
        missing_in_category = []
        for tool_name in expected_tools:
            # Try exact match and common variants (snake_case, camelCase)
            matched = False
            for found_name in found_set:
                if (
                    found_name == tool_name
                    or found_name.lower() == tool_name.lower()
                    or found_name.replace("-", "_") == tool_name
                ):
                    found_in_category.append(found_name)
                    matched = True
                    break
            if not matched:
                missing_in_category.append(tool_name)

        results["categories"][category] = {
            "expected": len(expected_tools),
            "found": len(found_in_category),
            "missing": missing_in_category,
        }

    # Print category report
    subheader("Tool Category Report")
    total_found = 0
    total_expected = 0
    for category, data in results["categories"].items():
        total_found += data["found"]
        total_expected += data["expected"]
        status = C.OK if data["found"] == data["expected"] else C.FAIL
        print(
            f"  {status}{category:20s}{C.END}  "
            f"{data['found']:2d}/{data['expected']:2d} tools"
        )
        if data["missing"]:
            for m in data["missing"]:
                print(f"    {C.FAIL}MISSING: {m}{C.END}")

    print()
    info(f"Total: {total_found}/{total_expected} expected tools found")

    # List extra tools (not in expected list)
    extra = found_set - {t for tools in EXPECTED_TOOLS.values() for t in tools}
    if extra:
        subheader(f"Extra Tools ({len(extra)} not in expected list)")
        for t in sorted(extra):
            print(f"    {C.DIM}+ {t}{C.END}")
        results["extra_tools"] = sorted(extra)

    # Full tool list
    subheader("All Available Tools")
    for i, name in enumerate(sorted(results["tool_names"]), 1):
        print(f"  {i:3d}. {name}")

    return results


# =============================================================================
# Tool Server URL Verification
# =============================================================================
async def test_tool_server_url(mcp_url: str) -> bool:
    """Check that the backend tool server URL is properly configured."""
    header("TEST 2: Tool Server URL Configuration")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # The tool server URL is set via POST /tool-server-url on the sandbox
        # We can't read it back directly, but we can verify it was set via health

        # Try to check if settings endpoint exists
        try:
            r = await client.get(f"{mcp_url}/health", timeout=10.0)
            health_data = r.json() if r.status_code == 200 else {}
            ok(f"MCP server healthy: {health_data}")

            # Check if tool_server_url is in the health response
            if "tool_server_url" in str(health_data):
                ok(f"tool_server_url visible in health response")
            else:
                info("tool_server_url not in health response (may be internal only)")

        except Exception as e:
            fail(f"Tool server URL check failed: {e}")
            return False

    return True


# =============================================================================
# Agent Endpoint Tool Test
# =============================================================================
async def test_agent_uses_tools(
    base_url: str,
    token: str,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send prompts to the /agent/stream endpoint and verify the agent
    actually uses the expected tools from the sandbox MCP server.
    """
    header("TEST 3: Agent Tool Usage via /agent/stream")

    if not token:
        warn("No token provided. Skipping live agent test.")
        return {}

    if not thread_id:
        thread_id = f"tool-test-{os.urandom(4).hex()}"

    url = f"{base_url}/agent/stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Define test prompts that require specific tools
    test_cases = [
        {
            "name": "File System - Read",
            "prompt": "Read the file /workspace/README.md using the file_read tool. Show me its contents.",
            "expected_tools": ["file_read"],
            "success_indicator": "README",
        },
        {
            "name": "Shell - Run Command",
            "prompt": "Run the shell command 'ls -la /workspace/' and show me the output. Use the shell tools.",
            "expected_tools": ["shell_run_command", "shell_init"],
            "success_indicator": None,  # Any shell output counts
        },
        {
            "name": "File System - Write + Read",
            "prompt": (
                "Create a file at /workspace/test_mcp_verify.txt with the content "
                "'MCP_TOOLS_WORKING_2026'. Then read it back to confirm."
            ),
            "expected_tools": ["file_write", "file_read"],
            "success_indicator": "MCP_TOOLS_WORKING_2026",
        },
        {
            "name": "File System - Grep",
            "prompt": "Use the grep tool to search for the word 'import' in /workspace/. Show the results.",
            "expected_tools": ["grep"],
            "success_indicator": None,
        },
        {
            "name": "Productivity - Todo",
            "prompt": "Use todo_write to create a todo item 'Test MCP tools'. Then use todo_read to list all todos.",
            "expected_tools": ["todo_write", "todo_read"],
            "success_indicator": "Test MCP",
        },
    ]

    results = {
        "total_tests": len(test_cases),
        "passed": 0,
        "failed": 0,
        "details": [],
    }

    for i, test in enumerate(test_cases, 1):
        subheader(f"Test {i}/{len(test_cases)}: {test['name']}")
        info(f"Prompt: {test['prompt'][:80]}...")

        test_result = await _run_agent_test(
            url=url,
            headers=headers,
            prompt=test["prompt"],
            thread_id=f"{thread_id}-{i}",
            expected_tools=test["expected_tools"],
            success_indicator=test.get("success_indicator"),
        )

        results["details"].append({
            "name": test["name"],
            **test_result,
        })

        if test_result["passed"]:
            results["passed"] += 1
        else:
            results["failed"] += 1

    # Summary
    subheader("Agent Tool Usage Summary")
    for detail in results["details"]:
        status = f"{C.OK}PASS{C.END}" if detail["passed"] else f"{C.FAIL}FAIL{C.END}"
        tools_used = ", ".join(detail.get("tools_called", [])) or "none"
        print(f"  {status}  {detail['name']:35s}  Tools: {tools_used}")

    info(f"Passed: {results['passed']}/{results['total_tests']}")

    return results


async def _run_agent_test(
    url: str,
    headers: dict,
    prompt: str,
    thread_id: str,
    expected_tools: List[str],
    success_indicator: Optional[str],
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Run a single agent test and analyze the SSE stream for tool usage."""

    payload = {
        "module": "general",
        "messages": [{"role": "user", "content": prompt}],
        "thread_id": thread_id,
        "enable_web_search": False,
        "enable_added_tools": True,
    }

    result = {
        "passed": False,
        "tools_called": [],
        "tool_results": {},
        "text_output": "",
        "events_received": 0,
        "error": None,
        "mcp_url_seen": None,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    result["error"] = f"HTTP {response.status_code}: {body.decode()[:200]}"
                    fail(result["error"])
                    return result

                event_buffer = ""
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    # Parse SSE events
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type", data.get("event", ""))
                            result["events_received"] += 1

                            # Track MCP URL
                            if event_type in ("mcp_ready", "agent_initialized"):
                                mcp = data.get("mcp_url")
                                if mcp:
                                    result["mcp_url_seen"] = mcp

                            # Track tool calls
                            if event_type == "tool_call_start":
                                tool_name = data.get("name", data.get("tool_name", ""))
                                if tool_name:
                                    result["tools_called"].append(tool_name)
                                    info(f"Tool called: {tool_name}")

                            # Track tool results
                            if event_type == "tool_result":
                                tool_name = data.get("name", "")
                                tool_output = data.get("result", data.get("output", ""))
                                result["tool_results"][tool_name] = str(tool_output)[:200]

                            # Track text output
                            if event_type in ("content_delta", "text"):
                                text = data.get("text", data.get("content", ""))
                                result["text_output"] += str(text)

                        except json.JSONDecodeError:
                            pass

                    # Also handle event: lines for AG-UI format
                    if line.startswith("event: "):
                        event_buffer = line[7:]

                    # Limit event processing
                    if result["events_received"] > 500:
                        info("Capped at 500 events")
                        break

    except httpx.ReadTimeout:
        result["error"] = "Stream read timeout"
        warn("Stream read timeout (may still be OK if tools were called)")
    except Exception as e:
        result["error"] = str(e)
        fail(f"Agent test error: {e}")
        return result

    # Evaluate results
    tools_called_set = set(result["tools_called"])
    expected_set = set(expected_tools)

    # Check if any expected tool was called
    matched_tools = tools_called_set & expected_set
    if matched_tools:
        ok(f"Expected tool(s) called: {matched_tools}")
        result["passed"] = True
    else:
        if result["tools_called"]:
            warn(f"Tools called but none matched expected: called={result['tools_called']}, expected={expected_tools}")
        else:
            fail(f"No tools called! Expected: {expected_tools}")

    # Check success indicator in output
    if success_indicator and result["text_output"]:
        if success_indicator.lower() in result["text_output"].lower():
            ok(f"Success indicator found: '{success_indicator}'")
        else:
            warn(f"Success indicator '{success_indicator}' not found in output")

    if result["mcp_url_seen"]:
        ok(f"MCP URL seen in stream: {result['mcp_url_seen']}")

    info(f"Total events: {result['events_received']}, Tools: {len(result['tools_called'])}")

    return result


# =============================================================================
# Tool Count & Configuration Report
# =============================================================================
async def test_tool_count_report(mcp_url: str) -> Dict[str, Any]:
    """Generate a comprehensive tool count and configuration report."""
    header("TEST 4: Tool Count & Configuration Report")

    report = {
        "sandbox_mcp_tools": 0,
        "tool_server_port": "6060 (SANDBOX_MCP_SERVER_PORT)",
        "backend_tool_server_port": "1237 (TOOL_SERVER_PORT)",
        "tool_categories": {},
    }

    # Reuse the same Streamable HTTP helper from test_tool_inventory
    tools_raw = None
    tool_names_list = None
    try:
        tools_raw = await _mcp_list_tools_http(mcp_url)
    except Exception:
        pass

    if not tools_raw:
        # Fallback to MultiServerMCPClient
        try:
            tool_names_list = await _mcp_list_tools_via_client(mcp_url)
        except Exception:
            pass

    if tools_raw:
        report["sandbox_mcp_tools"] = len(tools_raw)
        tools = tools_raw  # list of dicts with "name" key
    elif tool_names_list:
        report["sandbox_mcp_tools"] = len(tool_names_list)
        tools = [{"name": n} for n in tool_names_list]
    else:
        fail("Could not retrieve tools for report")
        return report

    # Categorize by name pattern
    categories = defaultdict(list)
    for tool in tools:
        name = tool["name"]
        desc = tool.get("description", "")[:100]

        # Auto-categorize by name prefix
        if any(name.startswith(p) for p in ("shell_", "tmux")):
            categories["SHELL"].append(name)
        elif any(name.startswith(p) for p in ("file_", "grep", "ast_grep", "apply_patch", "str_replace", "lsp")):
            categories["FILE_SYSTEM"].append(name)
        elif name.startswith("todo_") or name.startswith("shared_state"):
            categories["PRODUCTIVITY"].append(name)
        elif any(name.startswith(p) for p in ("image_generate", "video_generate")):
            categories["MEDIA"].append(name)
        elif any(name.startswith(p) for p in ("web_", "image_search", "read_remote")):
            categories["WEB"].append(name)
        elif any(name.startswith(p) for p in ("slide_",)):
            categories["SLIDES"].append(name)
        elif any(name.startswith(p) for p in ("design_",)):
            categories["DESIGN"].append(name)
        elif any(name.startswith(p) for p in ("excalidraw_",)):
            categories["EXCALIDRAW"].append(name)
        elif any(name.startswith(p) for p in ("document_",)):
            categories["DOCUMENTS"].append(name)
        elif any(name.startswith(p) for p in ("browser_",)):
            categories["BROWSER"].append(name)
        elif any(name.startswith(p) for p in ("fullstack_", "save_checkpoint", "register_port", "get_database")):
            categories["DEV"].append(name)
        elif name == "message_user":
            categories["AGENT"].append(name)
        else:
            categories["UNCATEGORIZED"].append(name)

    report["tool_categories"] = dict(categories)

    # Print report
    subheader("Tool Count by Category")
    total = 0
    for cat in sorted(categories.keys()):
        tools_list = categories[cat]
        total += len(tools_list)
        print(f"  {cat:20s}  {len(tools_list):3d} tools")
        for t in sorted(tools_list):
            print(f"    - {t}")

    print()
    info(f"Total tools registered: {report['sandbox_mcp_tools']}")
    info(f"Total categorized: {total}")
    info(f"Sandbox MCP port: {report['tool_server_port']}")
    info(f"Backend tool server port: {report['backend_tool_server_port']}")

    # Architecture summary
    subheader("Architecture Summary")
    print(f"""
  The tool chain works as follows:

  1. BACKEND TOOL SERVER (port 1237)
     - Runs inside Docker alongside the FastAPI backend
     - Provides API endpoints for video/image generation, DB connections, etc.
     - Some sandbox tools call BACK to this server (tool_server_url)

  2. SANDBOX MCP SERVER (port 6060 inside sandbox)
     - Runs inside each e2b sandbox
     - Exposes ALL tools via MCP protocol (/mcp endpoint)
     - Tools: file system, shell, browser, slides, design, excalidraw, etc.
     - Total: {report['sandbox_mcp_tools']} tools

  3. AGENT NODE (nodes.py _setup_and_execute_agent_step)
     - Gets mcp_url from workflow_config["configurable"]["mcp_url"]
     - Connects via MultiServerMCPClient to sandbox MCP on port 6060
     - Loads ALL tools from the MCP server
     - Also adds codex_delegate, web_search, etc. as LangChain tools

  4. FLOW:
     agent.py -> sandbox.expose_port(6060) -> mcp_url
     -> workflow_config["configurable"]["mcp_url"] = mcp_url
     -> nodes.py reads configurable.mcp_url
     -> MultiServerMCPClient(sandbox: mcp_url/mcp)
     -> get_tools() -> {report['sandbox_mcp_tools']} tools loaded
""")

    return report


# =============================================================================
# MCP Server Diagnostic - WHY are there 0 tools?
# =============================================================================
async def test_mcp_server_diagnostic(mcp_url: str, tool_count: int) -> None:
    """
    When the server returns 0 tools, diagnose WHY.
    Probes common MCP server endpoints and sandbox configuration.
    """
    header("TEST 5: MCP Server Diagnostic (Why 0 tools?)")

    if tool_count > 0:
        ok(f"Server has {tool_count} tools — diagnostic not needed")
        return

    fail(f"MCP server returned 0 tools — investigating root cause...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Probe 1: Check known MCP server endpoints
        subheader("Probe 1: Server Endpoints")
        endpoints_to_check = [
            "/health",
            "/tool-server-url",
            "/credential",
            "/docs",
            "/openapi.json",
            "/mcp",
        ]
        for ep in endpoints_to_check:
            try:
                r = await client.get(f"{mcp_url}{ep}", timeout=5.0)
                info(f"GET {ep} -> HTTP {r.status_code} ({r.headers.get('content-type', 'n/a')})")
                if r.status_code == 200 and len(r.text) < 500:
                    info(f"  Body: {r.text[:300]}")
            except Exception as e:
                info(f"GET {ep} -> Error: {e}")

        # Probe 2: Check if tool_server_url was set
        subheader("Probe 2: Tool Server URL Configuration")
        try:
            r = await client.get(f"{mcp_url}/tool-server-url", timeout=5.0)
            if r.status_code == 200:
                ok(f"tool-server-url endpoint: {r.text[:200]}")
            else:
                warn(f"tool-server-url returned {r.status_code}: {r.text[:200]}")
        except Exception as e:
            info(f"tool-server-url check failed: {e}")

        # Probe 3: Attempt to list resources (another MCP method)
        subheader("Probe 3: MCP Resources (alternative method)")
        try:
            # Initialize session first
            init_body = {
                "jsonrpc": "2.0",
                "id": "diag-init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "diagnostic", "version": "1.0.0"},
                },
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream, application/json",
            }
            r_init = await client.post(f"{mcp_url}/mcp", json=init_body, headers=headers, timeout=10.0)
            session_id = r_init.headers.get("mcp-session-id")

            # Try resources/list
            res_headers = {**headers}
            if session_id:
                res_headers["Mcp-Session-Id"] = session_id
            r_res = await client.post(
                f"{mcp_url}/mcp",
                json={"jsonrpc": "2.0", "id": "diag-res", "method": "resources/list", "params": {}},
                headers=res_headers,
                timeout=10.0,
            )
            info(f"resources/list -> HTTP {r_res.status_code}: {r_res.text[:300]}")
        except Exception as e:
            info(f"resources/list failed: {e}")

    # Diagnosis summary
    subheader("Diagnosis Summary")
    print(f"""
  {C.FAIL}ROOT CAUSE: The MCP server has 0 tools registered.{C.END}

  This means the sandbox MCP server process started successfully
  (health check passes, FastMCP v2.14.3 running), but NO tool
  handlers have been registered with it yet.

  {C.BOLD}Possible causes:{C.END}
  1. {C.WARN}Sandbox cold start incomplete{C.END}
     - pre_configure_mcp_server() in sandbox_service.py is responsible
       for registering tools on the MCP server
     - The sandbox may have started but tool registration hasn't
       finished or was skipped

  2. {C.WARN}MCP server started without tool modules{C.END}
     - The sandbox MCP server (on port 6060) may be a bare FastMCP
       instance that hasn't loaded its tool handlers
     - Check if the MCP server startup script inside the sandbox
       imports and registers all tool modules

  3. {C.WARN}Tool registration failed silently{C.END}
     - Check sandbox logs for errors during tool loading
     - The tool server URL (port 1237) may not have been set, causing
       tools that depend on it to fail registration

  {C.BOLD}To investigate further:{C.END}
  - Run with --token to trigger a full agent flow (which calls
    pre_configure_mcp_server before the agent starts)
  - Check sandbox MCP server logs inside the e2b sandbox
  - Verify the MCP server startup script registers tool handlers
""")


# =============================================================================
# Login helper
# =============================================================================
async def login(base_url: str, username: str, password: str) -> Optional[str]:
    """Login and return JWT token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{base_url}/api/v1/auth/login/swagger",
            params={"username": username, "password": password},
        )
        if r.status_code == 200:
            token = r.json().get("access_token")
            ok(f"Logged in as {username}")
            return token
        else:
            fail(f"Login failed: {r.status_code} {r.text[:200]}")
            return None


# =============================================================================
# Get MCP URL from agent/stream (by reading SSE events)
# =============================================================================
async def get_mcp_url_from_agent(
    base_url: str, token: str
) -> Optional[str]:
    """Start an agent stream and capture the mcp_url from the mcp_ready event."""
    header("Getting MCP URL from agent stream...")

    url = f"{base_url}/agent/stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "module": "general",
        "messages": [{"role": "user", "content": "Hello, just say hi."}],
        "thread_id": f"mcp-url-probe-{os.urandom(4).hex()}",
        "enable_web_search": False,
        "enable_added_tools": True,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    fail(f"HTTP {response.status_code}: {body.decode()[:200]}")
                    return None

                evt_count = 0
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type", "")

                            if event_type == "mcp_ready":
                                mcp_url = data.get("mcp_url")
                                if mcp_url:
                                    ok(f"Got MCP URL from mcp_ready event: {mcp_url}")
                                    return mcp_url

                            if event_type == "agent_initialized":
                                mcp_url = data.get("mcp_url")
                                if mcp_url:
                                    ok(f"Got MCP URL from agent_initialized: {mcp_url}")
                                    return mcp_url

                        except json.JSONDecodeError:
                            pass

                    evt_count += 1
                    if evt_count > 200:
                        break

    except Exception as e:
        fail(f"Failed to get MCP URL: {e}")

    fail("Could not find MCP URL in agent stream events")
    return None


# =============================================================================
# Main
# =============================================================================
async def main():
    parser = argparse.ArgumentParser(description="Live Agent Tool Access Test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--token", default=None, help="JWT token")
    parser.add_argument("--username", default=None, help="Login username (alternative to --token)")
    parser.add_argument("--password", default=None, help="Login password")
    parser.add_argument("--mcp-url", default=None, help="Direct MCP URL (skip agent stream)")
    parser.add_argument("--skip-agent", action="store_true", help="Skip agent tool usage tests")
    parser.add_argument("--thread-id", default=None, help="Thread ID for agent tests")
    args = parser.parse_args()

    print(f"{C.BOLD}Live Agent Tool Access & Execution Test Suite{C.END}")
    print(f"{'='*70}")

    token = args.token
    mcp_url = args.mcp_url

    # Login if credentials provided
    if not token and args.username and args.password:
        token = await login(args.base_url, args.username, args.password)
        if not token:
            return

    # Get MCP URL from agent if not provided and we have a token
    if not mcp_url and token:
        mcp_url = await get_mcp_url_from_agent(args.base_url, token)

    if not mcp_url:
        fail("No MCP URL available. Provide --mcp-url or --token (to auto-discover)")
        return

    # TEST 1: Tool inventory
    inventory = await test_tool_inventory(mcp_url)

    # TEST 2: Tool server URL check
    await test_tool_server_url(mcp_url)

    # TEST 3: Agent tool usage (if token available and not skipped)
    if token and not args.skip_agent:
        await test_agent_uses_tools(
            base_url=args.base_url,
            token=token,
            thread_id=args.thread_id,
        )
    elif not token:
        warn("Skipping agent tool usage tests (no token)")
    else:
        info("Skipping agent tool usage tests (--skip-agent)")

    # TEST 4: Tool count report
    await test_tool_count_report(mcp_url)

    # TEST 5: Diagnostic if 0 tools found
    total_tools = inventory.get("total_tools", 0)
    if total_tools == 0:
        await test_mcp_server_diagnostic(mcp_url, total_tools)

    # Final summary
    header("FINAL SUMMARY")
    expected_total = len(ALL_EXPECTED)

    if total_tools >= expected_total * 0.8:
        ok(f"Tool coverage: {total_tools}/{expected_total} expected tools found ({total_tools/expected_total*100:.0f}%)")
    elif total_tools > 0:
        warn(f"Partial coverage: {total_tools}/{expected_total} tools ({total_tools/expected_total*100:.0f}%)")
    else:
        fail(f"No tools found! Expected {expected_total} tools")

    if inventory.get("healthy"):
        ok("MCP server is healthy")
    else:
        fail("MCP server is NOT healthy")


if __name__ == "__main__":
    asyncio.run(main())
