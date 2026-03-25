#!/usr/bin/env python3
"""
MCP Tools Diagnostic Script
============================
Run this to check:
  1. Ngrok tunnel status (is it up? what's the public URL?)
  2. Tool Server reachability (can backend reach it?)
  3. MCP server inside sandbox (is port 6060 exposed?)
  4. Backend log analysis (grep for [MCP_TOOLS] entries)

Usage:
  python scripts/diagnose_mcp.py              # Run all checks
  python scripts/diagnose_mcp.py --logs-only  # Only scan backend logs
  python scripts/diagnose_mcp.py --ngrok-only # Only check ngrok
"""

import asyncio
import json
import os
import re
import sys
import glob
from pathlib import Path
from datetime import datetime

# ── Colours for terminal output ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg): print(f"  {CYAN}ℹ{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{'─'*60}\n  {msg}\n{'─'*60}{RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. NGROK CHECK
# ═══════════════════════════════════════════════════════════════════════════════
def check_ngrok():
    """Check if ngrok tunnel is running and get the public URL."""
    header("1. NGROK TUNNEL STATUS")
    
    import urllib.request
    import urllib.error
    
    ngrok_api = "http://localhost:4040/api/tunnels"
    
    try:
        req = urllib.request.Request(ngrok_api, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        
        tunnels = data.get("tunnels", [])
        if not tunnels:
            fail("Ngrok is running but has NO active tunnels!")
            warn("Try restarting the ngrok container: docker restart <ngrok_container>")
            return None
        
        ok(f"Ngrok is running with {len(tunnels)} tunnel(s)")
        
        public_url = None
        for t in tunnels:
            name = t.get("name", "?")
            pub = t.get("public_url", "?")
            local = t.get("config", {}).get("addr", "?")
            print(f"      Tunnel: {name}")
            print(f"      Public: {CYAN}{pub}{RESET}")
            print(f"      Local:  {local}")
            print()
            if pub.startswith("https://"):
                public_url = pub
        
        # Check if .env PUBLIC_TOOL_SERVER_URL matches
        env_url = _get_env_var("PUBLIC_TOOL_SERVER_URL")
        if env_url and public_url:
            if env_url.rstrip("/") == public_url.rstrip("/"):
                ok(f".env PUBLIC_TOOL_SERVER_URL matches ngrok URL")
            else:
                fail(f".env PUBLIC_TOOL_SERVER_URL MISMATCH!")
                print(f"      .env:   {RED}{env_url}{RESET}")
                print(f"      ngrok:  {GREEN}{public_url}{RESET}")
                warn("Update PUBLIC_TOOL_SERVER_URL in .env and restart backend")
        elif env_url:
            info(f".env PUBLIC_TOOL_SERVER_URL = {env_url}")
            warn("Could not verify against ngrok (no https tunnel found)")
        
        return public_url
        
    except urllib.error.URLError:
        fail("Cannot connect to ngrok API at localhost:4040")
        warn("Is ngrok running? Check: docker ps | findstr ngrok")
        warn("Or start it manually: ngrok http 1237")
        return None
    except Exception as e:
        fail(f"Ngrok check error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TOOL SERVER CHECK
# ═══════════════════════════════════════════════════════════════════════════════
def check_tool_server():
    """Check if the local tool server is reachable."""
    header("2. LOCAL TOOL SERVER")
    
    import urllib.request
    import urllib.error
    
    port = _get_env_var("TOOL_SERVER_PORT", "1237")
    url = f"http://localhost:{port}"
    
    try:
        req = urllib.request.Request(f"{url}/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            ok(f"Tool server responding on port {port} (status {resp.status})")
            return True
    except urllib.error.HTTPError as e:
        # Some servers return 404 on /health but are still up
        if e.code < 500:
            ok(f"Tool server responding on port {port} (status {e.code}, no /health endpoint)")
            return True
        fail(f"Tool server error: HTTP {e.code}")
        return False
    except urllib.error.URLError:
        fail(f"Tool server NOT reachable on localhost:{port}")
        warn("Is the tool server container running?")
        warn(f"  docker ps | findstr tool")
        return False
    except Exception as e:
        fail(f"Tool server check error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PUBLIC TOOL SERVER URL CHECK (via ngrok)
# ═══════════════════════════════════════════════════════════════════════════════
def check_public_tool_server(ngrok_url=None):
    """Check if the public tool server URL (ngrok) is reachable."""
    header("3. PUBLIC TOOL SERVER (via ngrok)")
    
    import urllib.request
    import urllib.error
    
    url = ngrok_url or _get_env_var("PUBLIC_TOOL_SERVER_URL")
    if not url:
        warn("No PUBLIC_TOOL_SERVER_URL set in .env and ngrok URL not detected")
        return False
    
    info(f"Testing: {url}")
    
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok(f"Public URL reachable (status {resp.status})")
            return True
    except urllib.error.HTTPError as e:
        if e.code < 500:
            ok(f"Public URL reachable (status {e.code})")
            return True
        fail(f"Public URL returned HTTP {e.code}")
        return False
    except urllib.error.URLError as e:
        fail(f"Public URL NOT reachable: {e.reason}")
        warn("The ngrok tunnel may have expired or restarted with a new URL")
        return False
    except Exception as e:
        fail(f"Public URL check error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BACKEND LOG ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
def check_backend_logs():
    """Scan backend logs for MCP-related entries."""
    header("4. BACKEND LOG ANALYSIS")
    
    # Find log files
    log_paths = [
        "backend_logs.txt",
        "backend/log/*.log",
        "backend/log/**/*.log",
        "logs/*.log",
        "log/*.log",
    ]
    
    workspace = Path(__file__).parent.parent
    found_logs = []
    for pattern in log_paths:
        found_logs.extend(glob.glob(str(workspace / pattern), recursive=True))
    
    if not found_logs:
        warn("No log files found. Checking common locations...")
        info(f"Searched in: {workspace}")
        for p in log_paths:
            info(f"  - {p}")
        warn("Run the backend and try again, or check Docker logs:")
        warn("  docker logs <backend_container> 2>&1 | findstr MCP")
        return
    
    ok(f"Found {len(found_logs)} log file(s)")
    
    # Patterns to search for
    patterns = {
        "MCP tool loading":     r"\[MCP_TOOLS\]",
        "MCP URL":              r"mcp_url|MCP URL|mcp URL",
        "Sandbox ready":        r"sandbox_ready|get_sandbox|sandbox.*created",
        "MCP health check":     r"health.check",
        "MCP retry/failure":    r"Failed to load MCP|0 MCP tools|retry|WARNING.*mcp",
        "Tool count":           r"Total tools count|loaded \d+ MCP|tools count",
        "Sandbox MCP server":   r"sandbox.*MCP|MCP.*sandbox|port 6060",
        "DEBUG_SLIDES":         r"DEBUG_SLIDES",
        "Ngrok/public URL":     r"ngrok|PUBLIC_TOOL_SERVER|tool.server.*url",
    }
    
    for log_file in found_logs:
        print(f"\n  📄 {os.path.basename(log_file)} ({_file_size(log_file)})")
        
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            fail(f"Cannot read {log_file}: {e}")
            continue
        
        # Only look at recent lines (last 2000)
        recent_lines = lines[-2000:]
        
        for label, pattern in patterns.items():
            matches = []
            for i, line in enumerate(recent_lines):
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append((len(lines) - len(recent_lines) + i + 1, line.strip()))
            
            if matches:
                # Show category with count
                color = RED if "fail" in label.lower() or "retry" in label.lower() else GREEN
                print(f"      {color}{label}: {len(matches)} match(es){RESET}")
                # Show last 3 matches
                for lineno, text in matches[-3:]:
                    # Truncate long lines
                    display = text[:120] + "..." if len(text) > 120 else text
                    print(f"        L{lineno}: {display}")
            # Don't print anything for no matches — keeps output clean


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LIVE MCP CONNECTION TEST
# ═══════════════════════════════════════════════════════════════════════════════
async def check_mcp_live():
    """Try to actually connect to MCP and list tools (requires langchain_mcp_adapters)."""
    header("5. LIVE MCP TOOL LOADING TEST")
    
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        warn("langchain_mcp_adapters not installed — skipping live MCP test")
        info("Install with: pip install langchain-mcp-adapters")
        return
    
    # Check if there's an active sandbox with MCP
    # We can't easily get the sandbox URL without the full backend running,
    # but we can test the public tool server URL
    public_url = _get_env_var("PUBLIC_TOOL_SERVER_URL")
    if not public_url:
        warn("No PUBLIC_TOOL_SERVER_URL — can't test MCP without a sandbox URL")
        info("This test works best when run while the backend is actively serving a session")
        return
    
    mcp_endpoint = f"{public_url}/mcp"
    info(f"Attempting MCP connection to: {mcp_endpoint}")
    
    try:
        mcp_servers = {
            "tool_server": {
                "transport": "http",
                "url": mcp_endpoint,
            }
        }
        
        client = MultiServerMCPClient(mcp_servers)
        tools = await client.get_tools()
        
        if tools:
            ok(f"Successfully loaded {len(tools)} MCP tools!")
            print(f"\n      {BOLD}Tool List:{RESET}")
            for i, t in enumerate(tools, 1):
                print(f"        {i:3d}. {t.name}")
        else:
            fail("MCP connection succeeded but returned 0 tools")
            warn("The MCP server may not have any tools registered")
    except Exception as e:
        fail(f"MCP connection failed: {e}")
        warn("This could mean:")
        warn("  - Ngrok URL has changed (free tier rotates on restart)")
        warn("  - Tool server is not running")
        warn("  - MCP endpoint is not /mcp")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DOCKER CONTAINER STATUS
# ═══════════════════════════════════════════════════════════════════════════════
def check_docker():
    """Check relevant Docker containers."""
    header("6. DOCKER CONTAINER STATUS")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            fail(f"docker ps failed: {result.stderr.strip()}")
            return
        
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 1:
            warn("No Docker containers running")
            return
        
        # Print header
        print(f"      {lines[0]}")
        
        # Highlight relevant containers
        keywords = ["ngrok", "redis", "tool", "backend", "mcp", "sandbox"]
        for line in lines[1:]:
            is_relevant = any(k in line.lower() for k in keywords)
            color = CYAN if is_relevant else ""
            reset = RESET if is_relevant else ""
            print(f"      {color}{line}{reset}")
        
    except FileNotFoundError:
        warn("Docker CLI not found — skipping container check")
    except subprocess.TimeoutExpired:
        fail("Docker command timed out")
    except Exception as e:
        fail(f"Docker check error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _get_env_var(name, default=None):
    """Read from os.environ first, then .env file."""
    val = os.environ.get(name)
    if val:
        return val
    
    env_file = Path(__file__).parent.parent / "backend" / ".env"
    if not env_file.exists():
        env_file = Path(__file__).parent.parent / ".env"
    
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{name}=") or line.startswith(f"{name} ="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        return val if val else default
        except Exception:
            pass
    
    return default


def _file_size(path):
    """Human-readable file size."""
    size = os.path.getsize(path)
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print(f"\n{BOLD}{'═'*60}")
    print(f"  MCP TOOLS DIAGNOSTIC — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}{RESET}")
    
    args = sys.argv[1:]
    
    if "--logs-only" in args:
        check_backend_logs()
        return
    
    if "--ngrok-only" in args:
        ngrok_url = check_ngrok()
        if ngrok_url:
            check_public_tool_server(ngrok_url)
        return
    
    # Run all checks
    ngrok_url = check_ngrok()
    check_tool_server()
    check_public_tool_server(ngrok_url)
    check_docker()
    check_backend_logs()
    
    # Live MCP test (async)
    if "--skip-live" not in args:
        try:
            asyncio.run(check_mcp_live())
        except Exception as e:
            fail(f"Live MCP test crashed: {e}")
    
    # Summary
    header("QUICK FIXES")
    print(f"""
  If ngrok URL changed (free tier):
    1. Get new URL:  (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels[0].public_url
    2. Update .env:  PUBLIC_TOOL_SERVER_URL=<new_url>
    3. Restart backend

  If tool server is down:
    docker compose up -d tool_server

  If MCP tools load as 0:
    Check that the e2b sandbox MCP server is running on port 6060.
    The sandbox MCP server starts via start_sandbox_server.sh inside the sandbox.

  To watch MCP logs in real-time after restart:
    docker logs -f <backend_container> 2>&1 | Select-String "MCP_TOOLS|mcp_url|sandbox"
    """)


if __name__ == "__main__":
    main()
