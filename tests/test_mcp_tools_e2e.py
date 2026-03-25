#!/usr/bin/env python3
"""
End-to-End MCP Tool Verification Test
=======================================

Tests the ENTIRE tool pipeline:
  1. Backend server is up and has PUBLIC_TOOL_SERVER_URL set
  2. Tool Server is reachable via ngrok
  3. Register/login a test user → get JWT token
  4. Call /agent/stream → triggers sandbox creation (cold start)
  5. Capture MCP URL from stream events
  6. Connect to the sandbox MCP server and list tools
  7. Verify tool count > 0

This is the single test that proves the full pipeline works.

Usage:
    python tests/test_mcp_tools_e2e.py
    python tests/test_mcp_tools_e2e.py --base-url http://localhost:8001
    python tests/test_mcp_tools_e2e.py --token EXISTING_JWT_TOKEN
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Run: pip install httpx")
    sys.exit(1)


# =============================================================================
# Styling
# =============================================================================
G = "\033[92m"  # green
Y = "\033[93m"  # yellow
R = "\033[91m"  # red
B = "\033[1m"   # bold
D = "\033[2m"   # dim
C = "\033[96m"  # cyan
X = "\033[0m"   # reset


def ok(msg):   print(f"  {G}PASS{X}  {msg}")
def warn(msg): print(f"  {Y}WARN{X}  {msg}")
def fail(msg): print(f"  {R}FAIL{X}  {msg}")
def info(msg): print(f"  {C}INFO{X}  {msg}")
def header(msg):
    print(f"\n{B}{'='*70}{X}")
    print(f"  {B}{msg}{X}")
    print(f"{B}{'='*70}{X}")


results = {"pass": 0, "fail": 0, "warn": 0}


def record(status: str):
    results[status] += 1


# =============================================================================
# Test 1: Backend Health & Config
# =============================================================================
async def test_backend_health(base_url: str) -> bool:
    header("TEST 1: Backend Server Health & Configuration")

    # 1a. Basic health
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base_url}/api/v1/auth/codes", timeout=5.0)
            # Any response (even 401) means the server is running
            ok(f"Backend server responding at {base_url} (HTTP {r.status_code})")
            record("pass")
    except Exception as e:
        fail(f"Backend not reachable at {base_url}: {e}")
        record("fail")
        return False

    # 1b. Check PUBLIC_TOOL_SERVER_URL inside the container
    info("Checking if PUBLIC_TOOL_SERVER_URL is set inside backend container...")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "agents_backend_server", "python", "-c",
             "from backend.core.conf import settings; print(settings.PUBLIC_TOOL_SERVER_URL)"],
            capture_output=True, text=True, timeout=15
        )
        url = result.stdout.strip()
        if url and url.startswith("http"):
            ok(f"PUBLIC_TOOL_SERVER_URL = {url}")
            record("pass")
        else:
            fail(f"PUBLIC_TOOL_SERVER_URL is EMPTY inside the backend container!")
            fail("The container needs to be restarted after setting the URL in .env")
            fail("Run: docker compose up -d --force-recreate agents_backend_server")
            record("fail")
            return False
    except Exception as e:
        warn(f"Could not check container config (not critical if running locally): {e}")
        record("warn")

    return True


# =============================================================================
# Test 2: Tool Server via ngrok
# =============================================================================
async def test_tool_server_via_ngrok() -> Optional[str]:
    header("TEST 2: Tool Server Reachable via ngrok")

    # Get ngrok URL
    ngrok_url = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("http://localhost:4040/api/tunnels")
            tunnels = r.json().get("tunnels", [])
            for t in tunnels:
                if t.get("public_url", "").startswith("https://"):
                    ngrok_url = t["public_url"]
                    break
    except Exception as e:
        fail(f"Cannot reach ngrok dashboard at localhost:4040: {e}")
        record("fail")
        return None

    if not ngrok_url:
        fail("No active ngrok tunnel found")
        record("fail")
        return None

    ok(f"ngrok tunnel URL: {ngrok_url}")
    record("pass")

    # Test tool server health through ngrok
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{ngrok_url}/health")
            if r.status_code == 200:
                ok(f"Tool Server healthy via ngrok (HTTP 200)")
                record("pass")
            else:
                fail(f"Tool Server returned HTTP {r.status_code}")
                record("fail")
                return None
    except Exception as e:
        fail(f"Tool Server not reachable via ngrok: {e}")
        record("fail")
        return None

    return ngrok_url


# =============================================================================
# Test 3: Auth - Register or Login
# =============================================================================
async def test_auth(base_url: str, existing_token: str = None) -> Optional[str]:
    header("TEST 3: Authentication (Register / Login)")

    if existing_token:
        # Validate existing token
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{base_url}/api/v1/auth/codes",
                    headers={"Authorization": f"Bearer {existing_token}"}
                )
                if r.status_code == 200:
                    ok("Existing token is valid")
                    record("pass")
                    return existing_token
                else:
                    warn(f"Existing token may be invalid (HTTP {r.status_code}), will try login")
        except Exception as e:
            warn(f"Token validation failed: {e}")

    # Try register a new test user
    test_email = f"mcp_test_{uuid.uuid4().hex[:8]}@test.com"
    test_password = "TestPass123!"
    test_name = "MCP Test User"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Try register
        info(f"Registering test user: {test_email}")
        try:
            r = await client.post(
                f"{base_url}/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": test_password,
                    "name": test_name,
                }
            )

            if r.status_code == 200:
                data = r.json()
                # response_base wraps in {"code": 200, "data": {...}}
                token_data = data.get("data", data)
                token = token_data.get("access_token")
                if token:
                    ok(f"Registered and got JWT token ({len(token)} chars)")
                    record("pass")
                    return token

            warn(f"Register returned {r.status_code}: {r.text[:200]}")
        except Exception as e:
            warn(f"Register failed: {e}")

        # Try swagger login with admin/admin
        info("Trying swagger login with admin/admin...")
        try:
            r = await client.post(
                f"{base_url}/api/v1/auth/login/swagger",
                params={"username": "admin", "password": "admin"},
            )
            if r.status_code == 200:
                token = r.json().get("access_token")
                if token:
                    ok(f"Logged in as admin ({len(token)} chars)")
                    record("pass")
                    return token
        except Exception as e:
            warn(f"Swagger login failed: {e}")

        # Try JSON login
        info("Trying JSON login with admin/admin...")
        try:
            r = await client.post(
                f"{base_url}/api/v1/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            if r.status_code == 200:
                data = r.json()
                token_data = data.get("data", data)
                token = token_data.get("access_token")
                if token:
                    ok(f"Logged in via JSON ({len(token)} chars)")
                    record("pass")
                    return token
        except Exception as e:
            warn(f"JSON login failed: {e}")

    fail("Could not obtain a JWT token via any method")
    fail("Please provide a token via --token flag")
    record("fail")
    return None


# =============================================================================
# Test 4: Agent Stream → Sandbox Creation → MCP URL
# =============================================================================
async def test_agent_stream(base_url: str, token: str) -> dict:
    header("TEST 4: Agent Stream → Sandbox & MCP URL Discovery")

    result = {
        "mcp_url": None,
        "sandbox_created": False,
        "events_received": 0,
        "event_types": [],
        "tool_calls": [],
        "errors": [],
    }

    thread_id = f"mcp-e2e-test-{uuid.uuid4().hex[:8]}"
    payload = {
        "module": "general",
        "messages": [{"role": "user", "content": "List all files in the current directory using shell"}],
        "thread_id": thread_id,
        "enable_web_search": False,
        "enable_added_tools": True,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    info(f"Sending agent request (thread: {thread_id})...")
    info("Prompt: 'List all files in the current directory using shell'")
    info("This will trigger sandbox creation (cold start ~30-60s)...")

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            start_time = time.time()
            async with client.stream("POST", f"{base_url}/agent/agent/stream",
                                     json=payload, headers=headers) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    fail(f"HTTP {response.status_code}: {body.decode()[:300]}")
                    result["errors"].append(f"HTTP {response.status_code}")
                    record("fail")
                    return result

                ok(f"Stream connected (HTTP 200)")
                record("pass")

                event_type_counts = {}
                async for line in response.aiter_lines():
                    elapsed = time.time() - start_time

                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        raw = line[6:]
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        result["events_received"] += 1
                        evt_type = data.get("type", "unknown")
                        event_type_counts[evt_type] = event_type_counts.get(evt_type, 0) + 1

                        if evt_type not in result["event_types"]:
                            result["event_types"].append(evt_type)

                        # Capture MCP URL
                        if evt_type in ("mcp_ready", "agent_initialized"):
                            mcp_url = data.get("mcp_url")
                            if mcp_url:
                                result["mcp_url"] = mcp_url
                                result["sandbox_created"] = True
                                ok(f"MCP URL discovered: {mcp_url} ({elapsed:.1f}s)")
                                record("pass")

                        # Capture tool calls
                        if evt_type == "tool_call":
                            tool_name = data.get("name", data.get("tool", "?"))
                            result["tool_calls"].append(tool_name)
                            info(f"  Tool called: {tool_name} ({elapsed:.1f}s)")

                        # If there's a tool_use/tool_call in messages
                        if evt_type == "message" or evt_type == "messages/partial":
                            msg = data.get("message", data)
                            if isinstance(msg, dict):
                                tool_calls = msg.get("tool_calls", [])
                                for tc in tool_calls:
                                    tc_name = tc.get("name", "?")
                                    if tc_name not in result["tool_calls"]:
                                        result["tool_calls"].append(tc_name)
                                        info(f"  Tool called: {tc_name} ({elapsed:.1f}s)")

                        # Check for errors
                        if evt_type == "error":
                            err_msg = data.get("message", data.get("error", str(data)))
                            result["errors"].append(err_msg)
                            warn(f"  Error event: {err_msg[:200]}")

                        # Print heartbeat progress
                        if result["events_received"] % 20 == 0:
                            info(f"  ... {result['events_received']} events received ({elapsed:.1f}s)")

                        # Safety: stop after 5 minutes or if done
                        if elapsed > 300:
                            warn("Timeout after 5 minutes")
                            break

                        if evt_type in ("done", "end", "stream_end"):
                            info(f"Stream completed ({elapsed:.1f}s, {result['events_received']} events)")
                            break

                # Summary
                total_time = time.time() - start_time
                info(f"Total stream time: {total_time:.1f}s")
                info(f"Event types seen: {json.dumps(event_type_counts, indent=2)}")

    except httpx.ReadTimeout:
        warn("Read timeout (this may be normal if sandbox takes long to create)")
        record("warn")
    except Exception as e:
        fail(f"Stream error: {e}")
        result["errors"].append(str(e))
        record("fail")

    # Evaluate results
    if not result["mcp_url"]:
        warn("MCP URL was not emitted in stream events")
        warn("This could mean: sandbox failed to create, or event format changed")
        record("warn")

    if result["tool_calls"]:
        ok(f"Agent used {len(result['tool_calls'])} tool(s): {result['tool_calls']}")
        record("pass")
    else:
        warn("No tool calls detected in stream (agent may not have used tools)")
        record("warn")

    return result


# =============================================================================
# Test 5: Direct MCP Connection → Tool Count
# =============================================================================
async def test_mcp_tool_count(mcp_url: str) -> int:
    header("TEST 5: Direct MCP Server → Tool Inventory")

    if not mcp_url:
        warn("No MCP URL available (skipping direct tool test)")
        record("warn")
        return 0

    info(f"Connecting to MCP server at {mcp_url}")

    # Health check
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{mcp_url}/health")
            if r.status_code == 200:
                ok(f"MCP server healthy (HTTP 200)")
                record("pass")
            else:
                fail(f"MCP server returned HTTP {r.status_code}")
                record("fail")
                return 0
    except Exception as e:
        fail(f"MCP server not reachable: {e}")
        record("fail")
        return 0

    # Try to list tools via MCP Streamable HTTP protocol
    tool_count = 0
    tool_names = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Initialize MCP session
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-test", "version": "1.0.0"},
                }
            }

            r = await client.post(
                f"{mcp_url}/mcp",
                json=init_payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )

            session_id = r.headers.get("Mcp-Session-Id", "")
            if session_id:
                info(f"MCP session established: {session_id[:20]}...")
            else:
                warn("No Mcp-Session-Id in response (may still work)")

            # Parse init response (could be SSE or JSON)
            init_ok = False
            response_text = r.text
            if response_text.startswith("event:") or "data:" in response_text:
                # SSE format
                for sse_line in response_text.split("\n"):
                    if sse_line.startswith("data: "):
                        try:
                            sse_data = json.loads(sse_line[6:])
                            if sse_data.get("result", {}).get("protocolVersion"):
                                init_ok = True
                        except json.JSONDecodeError:
                            pass
            else:
                try:
                    json_data = r.json()
                    if json_data.get("result", {}).get("protocolVersion"):
                        init_ok = True
                except Exception:
                    pass

            if init_ok:
                ok("MCP protocol initialized")
            else:
                warn(f"MCP init response unclear: {response_text[:200]}")

            # Send initialized notification
            await client.post(
                f"{mcp_url}/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={
                    "Content-Type": "application/json",
                    "Mcp-Session-Id": session_id,
                },
            )

            # List tools
            list_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }

            r = await client.post(
                f"{mcp_url}/mcp",
                json=list_payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id,
                },
            )

            # Parse tools response
            response_text = r.text
            tools = []

            if response_text.startswith("event:") or "data:" in response_text:
                for sse_line in response_text.split("\n"):
                    if sse_line.startswith("data: "):
                        try:
                            sse_data = json.loads(sse_line[6:])
                            tools_list = sse_data.get("result", {}).get("tools", [])
                            if tools_list:
                                tools = tools_list
                        except json.JSONDecodeError:
                            pass
            else:
                try:
                    json_data = r.json()
                    tools = json_data.get("result", {}).get("tools", [])
                except Exception:
                    pass

            tool_count = len(tools)
            tool_names = [t.get("name", "?") for t in tools]

    except Exception as e:
        fail(f"MCP tool listing failed: {e}")
        record("fail")
        return 0

    # Report
    if tool_count > 0:
        ok(f"MCP Server has {tool_count} tools registered!")
        record("pass")

        # Categorize using ACTUAL registered tool names from manager.py
        # Shell tools use "Bash*" names, file tools use "Read"/"Write"/"Edit" etc.
        SHELL_TOOLS = {"BashInit", "Bash", "BashView", "BashStop", "BashList", "BashWriteToProcess"}
        FILE_TOOLS = {"Read", "Write", "Edit", "apply_patch", "str_replace_based_edit_tool", "ASTGrep", "Grep", "Lsp"}
        BROWSER_TOOLS = {n for n in tool_names if n.startswith("browser_")}
        WEB_TOOLS = {"web_search", "web_visit", "web_visit_compress", "image_search", "read_remote_image", "web_batch_search"}
        MEDIA_TOOLS = {"generate_image", "generate_video"}
        EXCALIDRAW_TOOLS = {n for n in tool_names if n.startswith("excalidraw_")}
        SLIDE_TOOLS = {"SlideWrite", "SlideEdit", "slide_apply_patch", "slide_template_init"}
        DESIGN_TOOLS = {n for n in tool_names if n.startswith("design_")}
        DOCUMENT_TOOLS = {"document_template_init", "document_compile"}
        TODO_TOOLS = {"TodoRead", "TodoWrite"}
        DEV_TOOLS = {"fullstack_project_init", "save_checkpoint", "get_database_connection", "register_deployment", "message_user"}

        categories = {
            "shell": sorted([n for n in tool_names if n in SHELL_TOOLS]),
            "file": sorted([n for n in tool_names if n in FILE_TOOLS]),
            "browser": sorted([n for n in tool_names if n in BROWSER_TOOLS]),
            "web": sorted([n for n in tool_names if n in WEB_TOOLS]),
            "media": sorted([n for n in tool_names if n in MEDIA_TOOLS]),
            "excalidraw": sorted([n for n in tool_names if n in EXCALIDRAW_TOOLS]),
            "slide": sorted([n for n in tool_names if n in SLIDE_TOOLS]),
            "design": sorted([n for n in tool_names if n in DESIGN_TOOLS]),
            "document": sorted([n for n in tool_names if n in DOCUMENT_TOOLS]),
            "todo": sorted([n for n in tool_names if n in TODO_TOOLS]),
            "dev": sorted([n for n in tool_names if n in DEV_TOOLS]),
        }

        categorized = set()
        for cat, names in categories.items():
            categorized.update(names)
            if names:
                info(f"  {cat}: {len(names)} tools → {names}")

        # Show uncategorized tools
        uncategorized = sorted(set(tool_names) - categorized)
        if uncategorized:
            warn(f"  uncategorized: {len(uncategorized)} tools → {uncategorized}")

        # Check for critical tools using CORRECT names
        # Bash = shell command execution, Read = file read, Write = file write
        critical = {
            "Bash": "Shell command execution (ShellRunCommand)",
            "Read": "File read (FileReadTool)",
            "Write": "File write (FileWriteTool)",
            "Edit": "File edit (FileEditTool)",
            "Grep": "Code search (GrepTool)",
            "web_search": "Web search (WebSearchTool)",
        }
        for tool, desc in critical.items():
            if tool in tool_names:
                ok(f"  Critical tool present: {tool} — {desc}")
            else:
                warn(f"  Critical tool MISSING: {tool} — {desc}")

        # Expected total from get_sandbox_tools() + get_common_tools()
        EXPECTED_SANDBOX = 55  # from manager.py get_sandbox_tools()
        EXPECTED_COMMON = 2    # register_deployment + message_user
        EXPECTED_TOTAL = EXPECTED_SANDBOX + EXPECTED_COMMON
        info(f"  Expected: {EXPECTED_TOTAL} tools, Got: {tool_count} tools")
        if tool_count < EXPECTED_TOTAL:
            warn(f"  {EXPECTED_TOTAL - tool_count} tools fewer than expected!")
        elif tool_count > EXPECTED_TOTAL:
            info(f"  {tool_count - EXPECTED_TOTAL} extra tools (may include dynamically added tools)")
    else:
        fail("MCP Server has 0 tools!")
        fail("Tool registration did NOT happen.")
        fail("This means POST /tool-server-url was never called or failed.")
        fail("Check: Is PUBLIC_TOOL_SERVER_URL set correctly in the backend?")
        record("fail")

    return tool_count


# =============================================================================
# Test 6: Check Backend Logs for Tool Registration
# =============================================================================
async def test_backend_logs():
    header("TEST 6: Backend Container Logs (Tool Registration)")

    try:
        import subprocess
        result = subprocess.run(
            ["docker", "logs", "agents_backend_server", "--tail", "100"],
            capture_output=True, text=True, timeout=15
        )
        logs = result.stdout + result.stderr

        # Look for key indicators
        indicators = {
            "COLD START": "Cold start initiated",
            "Tool server URL set": "Tool server URL configured",
            "tool_server_url": "Tool server URL reference",
            "tools available": "Tools verified",
            "0 tools": "Zero tools warning",
            "PUBLIC_TOOL_SERVER_URL is EMPTY": "Empty URL error",
            "Tool registration verified": "Registration confirmed",
            "WARM START": "Warm start",
        }

        found_any = False
        for pattern, description in indicators.items():
            count = logs.count(pattern)
            if count > 0:
                found_any = True
                if "0 tools" in pattern or "EMPTY" in pattern:
                    warn(f"  Found '{pattern}' ({count}x) → {description}")
                else:
                    info(f"  Found '{pattern}' ({count}x) → {description}")

        if not found_any:
            warn("No tool-related log entries found in recent logs")
            warn("The agent may not have been invoked yet from the backend container")
            record("warn")
        else:
            record("pass")

    except Exception as e:
        warn(f"Could not check container logs: {e}")
        record("warn")


# =============================================================================
# Main
# =============================================================================
async def main():
    parser = argparse.ArgumentParser(description="End-to-End MCP Tool Verification")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--token", default=None, help="Existing JWT token")
    parser.add_argument("--skip-agent", action="store_true",
                        help="Skip agent stream test (just check infra)")
    parser.add_argument("--mcp-url", default=None,
                        help="Direct MCP URL to test (skip agent stream)")
    args = parser.parse_args()

    print(f"\n{B}End-to-End MCP Tool Pipeline Verification{X}")
    print(f"{'='*70}")
    print(f"Backend: {args.base_url}")
    print(f"Time:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    # Test 1: Backend health
    backend_ok = await test_backend_health(args.base_url)
    if not backend_ok:
        fail("Backend not available. Exiting.")
        return

    # Test 2: Tool server via ngrok
    ngrok_url = await test_tool_server_via_ngrok()

    # Test 3: Auth
    token = None
    if not args.skip_agent:
        token = await test_auth(args.base_url, args.token)

    # Test 4: Agent stream (triggers sandbox + tool registration)
    mcp_url = args.mcp_url
    agent_result = {}
    if token and not args.skip_agent and not mcp_url:
        agent_result = await test_agent_stream(args.base_url, token)
        mcp_url = agent_result.get("mcp_url")
    elif args.skip_agent:
        info("Skipping agent stream test (--skip-agent)")

    # Test 5: Direct MCP tool count
    tool_count = 0
    if mcp_url:
        tool_count = await test_mcp_tool_count(mcp_url)

    # Test 6: Backend logs
    await test_backend_logs()

    # ==========================================================================
    # FINAL REPORT
    # ==========================================================================
    header("FINAL REPORT")

    print(f"\n  Results: {G}{results['pass']} passed{X}, "
          f"{R}{results['fail']} failed{X}, "
          f"{Y}{results['warn']} warnings{X}\n")

    if ngrok_url:
        ok(f"ngrok tunnel: {ngrok_url}")
    else:
        fail("ngrok tunnel: NOT AVAILABLE")

    if token:
        ok(f"JWT token: obtained ({len(token)} chars)")
    elif not args.skip_agent:
        fail("JWT token: COULD NOT OBTAIN")

    if mcp_url:
        ok(f"MCP URL: {mcp_url}")
    else:
        warn("MCP URL: not discovered")

    if tool_count > 0:
        ok(f"Tool count: {tool_count} tools registered")
    elif mcp_url:
        fail(f"Tool count: 0 (PROBLEM - tools not registered)")
    else:
        warn("Tool count: could not verify (no MCP URL)")

    if agent_result.get("tool_calls"):
        ok(f"Agent used tools: {agent_result['tool_calls']}")

    # Overall verdict
    print()
    if results["fail"] == 0 and tool_count > 0:
        print(f"  {G}{B}VERDICT: ALL SYSTEMS OPERATIONAL{X}")
        print(f"  {G}The MCP tool pipeline is fully working.{X}")
    elif results["fail"] == 0 and tool_count == 0 and not mcp_url:
        print(f"  {Y}{B}VERDICT: INFRASTRUCTURE OK, AGENT TEST NEEDED{X}")
        print(f"  {Y}Run again with --token or allow registration to test full pipeline.{X}")
    else:
        print(f"  {R}{B}VERDICT: ISSUES FOUND{X}")
        if tool_count == 0 and mcp_url:
            print(f"  {R}The sandbox MCP server has 0 tools.{X}")
            print(f"  {R}This means POST /tool-server-url was never called or failed.{X}")
            print(f"  {R}Check that PUBLIC_TOOL_SERVER_URL is set in backend/.env AND{X}")
            print(f"  {R}the backend container was restarted after setting it.{X}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
