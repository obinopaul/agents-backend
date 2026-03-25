"""
MCP URL Propagation Diagnostic Test
====================================

This script tests whether the MCP URL (sandbox tool server) and related config
are actually passed through to the LangGraph agent nodes via the Configuration object.

It covers 3 levels of testing:

1. UNIT TEST:  Configuration.from_runnable_config() correctly extracts mcp_url, codex_url,
               mcp_settings, enable_added_tools from a configurable dict.

2. STATIC ANALYSIS: Checks the agent.py workflow_config to see what IS and IS NOT
                     being sent to the graph.

3. LIVE ENDPOINT TEST (optional): Hits the /agent/stream endpoint and reads SSE events
                                   to confirm mcp_url is emitted and the agent receives it.

Usage:
    # Unit + static analysis (no server needed):
    python tests/test_mcp_propagation.py

    # Include live endpoint test (requires running backend):
    python tests/test_mcp_propagation.py --live --base-url http://localhost:8000 --token YOUR_JWT
"""

import argparse
import asyncio
import inspect
import json
import os
import re
import sys
import textwrap

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# =============================================================================
# Colors for terminal output
# =============================================================================
class C:
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"
    INFO = "\033[94m"

def ok(msg):   print(f"  {C.OK}[PASS]{C.END}  {msg}")
def warn(msg): print(f"  {C.WARN}[WARN]{C.END}  {msg}")
def fail(msg): print(f"  {C.FAIL}[FAIL]{C.END}  {msg}")
def info(msg): print(f"  {C.INFO}[INFO]{C.END}  {msg}")
def header(msg): print(f"\n{C.BOLD}{'='*60}\n{msg}\n{'='*60}{C.END}")


# =============================================================================
# TEST 1: Configuration.from_runnable_config() unit test
# =============================================================================
def test_configuration_extraction():
    """Verify that Configuration correctly extracts MCP-related fields from config."""
    header("TEST 1: Configuration.from_runnable_config() extraction")

    from backend.src.config.configuration import Configuration

    test_config = {
        "configurable": {
            "thread_id": "test-thread-123",
            "mcp_url": "https://6060-sandbox-abc.e2b.app",
            "codex_url": "https://1324-sandbox-abc.e2b.app",
            "mcp_settings": {
                "servers": {
                    "my-custom-server": {
                        "transport": "http",
                        "url": "https://my-mcp.example.com/mcp",
                        "enabled_tools": ["tool_a", "tool_b"],
                        "add_to_agents": ["general"],
                    }
                }
            },
            "enable_web_search": True,
            "enable_added_tools": True,
            "sandbox_id": "sandbox-abc",
            "vscode_url": "https://9000-sandbox-abc.e2b.app",
        }
    }

    cfg = Configuration.from_runnable_config(test_config)
    
    results = {}
    
    # Check mcp_url
    if cfg.mcp_url == "https://6060-sandbox-abc.e2b.app":
        ok("mcp_url correctly extracted")
        results["mcp_url"] = True
    else:
        fail(f"mcp_url = {cfg.mcp_url!r} (expected 'https://6060-sandbox-abc.e2b.app')")
        results["mcp_url"] = False

    # Check codex_url
    if cfg.codex_url == "https://1324-sandbox-abc.e2b.app":
        ok("codex_url correctly extracted")
        results["codex_url"] = True
    else:
        fail(f"codex_url = {cfg.codex_url!r} (expected 'https://1324-sandbox-abc.e2b.app')")
        results["codex_url"] = False

    # Check mcp_settings
    if cfg.mcp_settings and "servers" in cfg.mcp_settings:
        ok("mcp_settings correctly extracted (has 'servers' key)")
        results["mcp_settings"] = True
    else:
        fail(f"mcp_settings = {cfg.mcp_settings!r} (expected dict with 'servers' key)")
        results["mcp_settings"] = False

    # Check thread_id
    if cfg.thread_id == "test-thread-123":
        ok("thread_id correctly extracted")
        results["thread_id"] = True
    else:
        fail(f"thread_id = {cfg.thread_id!r}")
        results["thread_id"] = False

    # Check enable_web_search
    if cfg.enable_web_search is True:
        ok("enable_web_search correctly extracted")
        results["enable_web_search"] = True
    else:
        fail(f"enable_web_search = {cfg.enable_web_search!r}")
        results["enable_web_search"] = False

    # Check enable_added_tools
    if cfg.enable_added_tools is True:
        ok("enable_added_tools correctly extracted")
        results["enable_added_tools"] = True
    else:
        fail(f"enable_added_tools = {cfg.enable_added_tools!r}")
        results["enable_added_tools"] = False

    return results


# =============================================================================
# TEST 2: Static analysis of agent.py workflow_config
# =============================================================================
def test_agent_py_static_analysis():
    """Statically inspect agent.py to check what fields are in workflow_config."""
    header("TEST 2: Static analysis of agent.py workflow_config")

    agent_py_path = os.path.join(
        PROJECT_ROOT, "backend", "app", "agent", "api", "v1", "agent.py"
    )

    if not os.path.exists(agent_py_path):
        fail(f"agent.py not found at {agent_py_path}")
        return {}

    with open(agent_py_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Extract workflow_config block
    # Look for the pattern: workflow_config = { ... }
    config_match = re.search(
        r'workflow_config\s*=\s*\{[^}]*"configurable"\s*:\s*\{([^}]+)\}',
        source,
        re.DOTALL,
    )

    if not config_match:
        fail("Could not find workflow_config['configurable'] block in agent.py")
        return {}

    config_block = config_match.group(1)
    info(f"Found workflow_config['configurable'] block ({len(config_block)} chars)")

    # Check which critical fields are present
    critical_fields = {
        "mcp_url": "Sandbox MCP URL (for sandbox tools like file_read, shell_run, etc.)",
        "codex_url": "Codex SSE URL (for CodexAgentTool delegation)",
        "enable_web_search": "Web search toggle",
        "enable_added_tools": "External tools toggle (people_search, arxiv, etc.)",
        "thread_id": "Thread/session ID",
        "sandbox_id": "Sandbox ID",
    }

    # mcp_settings is handled via sandbox registration (not workflow_config)
    # User MCP servers are registered on the sandbox MCP server during cold start
    # via SandboxService._register_user_mcp_servers() -> MCPClient.register_custom_mcp()
    optional_fields = {
        "mcp_settings": "Static MCP server configs (handled via sandbox registration instead)",
    }

    results = {}
    for field_name, description in critical_fields.items():
        # Check if the field appears as a key in the config block
        pattern = rf'["\']?{field_name}["\']?\s*:'
        if re.search(pattern, config_block):
            ok(f"{field_name}: {description}")
            results[field_name] = True
        else:
            fail(f"{field_name}: {description} — NOT IN workflow_config!")
            results[field_name] = False

    for field_name, description in optional_fields.items():
        pattern = rf'["\']?{field_name}["\']?\s*:'
        if re.search(pattern, config_block):
            ok(f"{field_name}: {description} (present)")
            results[field_name] = True
        else:
            info(f"{field_name}: {description}")
            results[field_name] = True  # Not a failure

    # Additional: check if enable_added_tools is passed to the stream generator
    if "enable_added_tools" not in source.split("_agent_stream_generator")[1][:500] if "_agent_stream_generator" in source else True:
        warn("enable_added_tools is in AgentRequest but may not be passed to stream generator")
    
    return results


# =============================================================================
# TEST 3: Check _agent_stream_generator function signature
# =============================================================================
def test_stream_generator_params():
    """Check what parameters _agent_stream_generator accepts."""
    header("TEST 3: Stream generator function signature analysis")

    agent_py_path = os.path.join(
        PROJECT_ROOT, "backend", "app", "agent", "api", "v1", "agent.py"
    )

    with open(agent_py_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Find the function definition and its parameters
    sig_match = re.search(
        r'async def _agent_stream_generator\((.*?)\):',
        source,
        re.DOTALL,
    )

    if not sig_match:
        fail("Could not find _agent_stream_generator function signature")
        return

    sig = sig_match.group(1)
    params = [p.strip().split(":")[0].split("=")[0].strip() for p in sig.split(",")]
    params = [p for p in params if p and not p.startswith("#")]

    info(f"Parameters ({len(params)}): {', '.join(params)}")

    # Check which MCP-related params are accepted
    mcp_params = ["mcp_settings", "mcp_url", "enable_added_tools"]
    for p in mcp_params:
        if p in params:
            ok(f"Accepts '{p}' parameter")
        else:
            warn(f"Does NOT accept '{p}' parameter (it's injected in workflow_config internally)")

    # Check the StreamingResponse call to see what's actually passed
    call_match = re.search(
        r'_agent_stream_generator\((.*?)\)\s*,\s*\n\s*media_type',
        source,
        re.DOTALL,
    )
    if call_match:
        call_block = call_match.group(1)
        info("Parameters passed at call site:")
        # Extract keyword arguments
        for line in call_block.split("\n"):
            line = line.strip().rstrip(",")
            if "=" in line and not line.startswith("#"):
                key = line.split("=")[0].strip()
                value = line.split("=", 1)[1].strip()
                print(f"    {key} = {value}")


# =============================================================================
# TEST 4: Check nodes.py reads these fields correctly
# =============================================================================
def test_nodes_py_reads_from_config():
    """Verify that nodes.py reads mcp_url and mcp_settings from configurable."""
    header("TEST 4: nodes.py reads from Configuration")

    nodes_py_path = os.path.join(
        PROJECT_ROOT, "backend", "src", "graph", "nodes.py"
    )

    with open(nodes_py_path, "r", encoding="utf-8") as f:
        source = f.read()

    checks = {
        "configurable.mcp_url": "Reads MCP URL from config",
        "configurable.mcp_settings": "Reads MCP settings from config",
        "configurable.codex_url": "Reads Codex URL from config",
        "configurable.enable_web_search": "Reads web search toggle",
        "configurable.enable_added_tools": "Reads added tools toggle",
    }

    for pattern, description in checks.items():
        if pattern in source:
            ok(f"{description} ({pattern})")
        else:
            fail(f"{description} ({pattern}) — NOT FOUND in nodes.py!")


# =============================================================================
# TEST 5: Live endpoint test (optional)
# =============================================================================
async def test_live_endpoint(base_url: str, token: str):
    """Hit the /agent/stream endpoint and check MCP propagation in SSE events."""
    header("TEST 5: Live endpoint test (SSE stream)")

    try:
        import httpx
    except ImportError:
        fail("httpx not installed. Run: pip install httpx")
        return

    url = f"{base_url}/agent/stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "module": "general",
        "messages": [
            {"role": "user", "content": "Hello, what tools do you have available?"}
        ],
        "thread_id": f"mcp-test-{os.urandom(4).hex()}",
        "enable_web_search": True,
        "enable_added_tools": True,
    }

    info(f"POST {url}")
    info(f"Thread ID: {payload['thread_id']}")

    found_events = {
        "mcp_ready": False,
        "codex_ready": False,
        "agent_initialized": False,
        "mcp_url_value": None,
        "codex_url_value": None,
        "tool_call_events": 0,
        "all_events": [],
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    fail(f"HTTP {response.status_code}")
                    body = await response.aread()
                    info(f"Response: {body.decode()[:500]}")
                    return

                ok(f"HTTP 200 — SSE stream started")
                event_count = 0
                max_events = 200  # Don't read forever

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type", "")
                            found_events["all_events"].append(event_type)

                            if event_type == "mcp_ready":
                                found_events["mcp_ready"] = True
                                found_events["mcp_url_value"] = data.get("mcp_url")
                                ok(f"mcp_ready event: mcp_url={data.get('mcp_url')}")

                            elif event_type == "codex_ready":
                                found_events["codex_ready"] = True
                                found_events["codex_url_value"] = data.get("codex_url")
                                ok(f"codex_ready event: codex_url={data.get('codex_url')}")

                            elif event_type == "agent_initialized":
                                found_events["agent_initialized"] = True
                                mcp = data.get("mcp_url")
                                codex = data.get("codex_url")
                                ok(f"agent_initialized: mcp_url={mcp}, codex_url={codex}")

                        except json.JSONDecodeError:
                            pass

                    event_count += 1
                    if event_count > max_events:
                        info(f"Stopped after {max_events} events")
                        break

        # Summary
        print(f"\n{C.BOLD}Live Test Summary:{C.END}")
        if found_events["mcp_ready"]:
            ok(f"MCP URL emitted: {found_events['mcp_url_value']}")
        else:
            fail("mcp_ready event never emitted!")

        if found_events["codex_ready"]:
            ok(f"Codex URL emitted: {found_events['codex_url_value']}")
        else:
            warn("codex_ready event not emitted (Codex may not be available)")

        if found_events["agent_initialized"]:
            ok("agent_initialized event emitted with all URLs")
        else:
            fail("agent_initialized event never emitted!")

        info(f"Total events seen: {len(found_events['all_events'])}")
        unique_types = sorted(set(found_events["all_events"]))
        info(f"Unique event types: {unique_types}")

    except httpx.ConnectError:
        fail(f"Could not connect to {base_url}. Is the backend running?")
    except Exception as e:
        fail(f"Live test error: {e}")


# =============================================================================
# TEST 6: MCP Client tool extraction test
# =============================================================================
async def test_mcp_client_tools(mcp_url: str):
    """Use the MCPClient to connect to a live MCP URL and list available tools."""
    header("TEST 6: MCPClient tool extraction")

    if not mcp_url:
        warn("No MCP URL provided. Skipping MCPClient test.")
        warn("Usage: --mcp-url https://6060-sandbox-abc.e2b.app")
        return

    info(f"Connecting to MCP server: {mcp_url}")

    try:
        from backend.src.tool_server.mcp.client import MCPClient

        async with MCPClient(mcp_url) as client:
            # Health check
            healthy = await client.health_check()
            if healthy:
                ok("MCP server health check passed")
            else:
                fail("MCP server health check FAILED")
                return

            # List tools
            tools = await client.list_tools()
            ok(f"Retrieved {len(tools)} tools from MCP server")

            for i, tool in enumerate(tools):
                name = tool.name if hasattr(tool, "name") else str(tool)
                desc = (tool.description[:60] + "...") if hasattr(tool, "description") and tool.description else "N/A"
                print(f"    {i+1:3d}. {name:40s} {desc}")

            # Get tool names
            names = await client.get_tool_names()
            info(f"Tool names: {names[:20]}{'...' if len(names) > 20 else ''}")

    except Exception as e:
        fail(f"MCPClient error: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# TEST 7: MultiServerMCPClient test (same as nodes.py uses)
# =============================================================================
async def test_multi_server_mcp_client(mcp_url: str):
    """Test the exact MultiServerMCPClient pattern used in nodes.py."""
    header("TEST 7: MultiServerMCPClient (same as nodes.py)")

    if not mcp_url:
        warn("No MCP URL provided. Skipping MultiServerMCPClient test.")
        return

    info(f"Testing with MCP URL: {mcp_url}")

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        # This is the same config that nodes.py builds
        mcp_servers = {
            "sandbox": {
                "transport": "http",
                "url": f"{mcp_url}/mcp",
            }
        }

        info(f"Config: {json.dumps(mcp_servers, indent=2)}")

        client = MultiServerMCPClient(mcp_servers)
        all_tools = await client.get_tools()
        
        ok(f"MultiServerMCPClient returned {len(all_tools)} tools")

        for i, tool in enumerate(all_tools):
            name = getattr(tool, "name", "unknown")
            desc = getattr(tool, "description", "N/A")[:60]
            print(f"    {i+1:3d}. {name:40s} {desc}...")

    except Exception as e:
        fail(f"MultiServerMCPClient error: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# FINDINGS SUMMARY
# =============================================================================
def print_findings_summary(test1_results: dict, test2_results: dict):
    """Print a summary of all findings."""
    header("FINDINGS SUMMARY")

    all_good = True

    # Critical path: mcp_url
    if test2_results.get("mcp_url"):
        ok("mcp_url IS passed in workflow_config -> nodes.py gets it")
    else:
        fail("mcp_url is NOT in workflow_config -> sandbox MCP tools will NOT load!")
        all_good = False

    # Critical path: codex_url
    if test2_results.get("codex_url"):
        ok("codex_url IS passed in workflow_config -> CodexAgentTool will work")
    else:
        fail("codex_url is NOT in workflow_config -> Codex delegation will NOT work!")
        all_good = False

    # Missing: mcp_settings (not critical — handled via sandbox registration)
    if not test2_results.get("mcp_settings"):
        info("mcp_settings is handled via sandbox registration, not workflow_config")
        info("  -> User MCP servers are registered on sandbox during cold start")
        info("  -> SandboxService._register_user_mcp_servers() -> MCPClient.register_custom_mcp()")

    # Missing: enable_added_tools
    if not test2_results.get("enable_added_tools"):
        warn("enable_added_tools is NOT in workflow_config")
        warn("  -> base_node always defaults to enable_added_tools=True")
        warn("  -> Users cannot disable external tools (people_search, arxiv, etc.)")
        warn("  -> FIX: Add 'enable_added_tools': request.enable_added_tools to workflow_config")
        all_good = False

    if all_good:
        print(f"\n{C.OK}{C.BOLD}All critical MCP fields are correctly propagated!{C.END}")
    else:
        print(f"\n{C.WARN}{C.BOLD}Some fields are missing — see details above.{C.END}")


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MCP URL Propagation Diagnostic")
    parser.add_argument("--live", action="store_true", help="Run live endpoint test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--token", default=None, help="JWT token for authenticated requests")
    parser.add_argument("--mcp-url", default=None, help="Live MCP URL to test tool extraction")
    args = parser.parse_args()

    print(f"{C.BOLD}MCP URL Propagation Diagnostic{C.END}")
    print(f"{'='*60}")

    # Test 1: Configuration unit test
    test1_results = test_configuration_extraction()

    # Test 2: Static analysis
    test2_results = test_agent_py_static_analysis()

    # Test 3: Stream generator params
    test_stream_generator_params()

    # Test 4: nodes.py reads
    test_nodes_py_reads_from_config()

    # Summary
    print_findings_summary(test1_results, test2_results)

    # Optional live tests
    if args.live:
        if not args.token:
            fail("--token required for live test")
            return
        asyncio.run(test_live_endpoint(args.base_url, args.token))

    if args.mcp_url:
        asyncio.run(test_mcp_client_tools(args.mcp_url))
        asyncio.run(test_multi_server_mcp_client(args.mcp_url))


if __name__ == "__main__":
    main()
