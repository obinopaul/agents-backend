#!/usr/bin/env python3
"""
Frontend-to-Backend MCP Pipeline Audit
=======================================

Traces the ENTIRE path from frontend payload construction through
to the agent receiving MCP tools, checking for dropped/missing/
hardcoded parameters at every layer.

WHAT THIS TESTS:
  1. Frontend payload → Backend AgentRequest field mapping
  2. WebSocket (Socket.IO) path: query_handler.py → _agent_stream_generator()
  3. HTTP SSE path: agent.py → _agent_stream_generator()
  4. Configuration.from_runnable_config() boolean handling
  5. workflow_config → Configuration → nodes.py tool loading

RUN:
  python tests/test_frontend_backend_pipeline.py
"""

import ast
import os
import re
import sys
import inspect
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"

# ─── Colors (ASCII only for Windows compat) ───────────────────────
class C:
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    INFO = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"

passed = 0
failed = 0
warnings = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  {C.OK}[PASS]{C.END}  {msg}")

def warn(msg):
    global warnings
    warnings += 1
    print(f"  {C.WARN}[WARN]{C.END}  {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"  {C.FAIL}[FAIL]{C.END}  {msg}")

def info(msg):
    print(f"  {C.INFO}[INFO]{C.END}  {msg}")

def header(msg):
    print(f"\n{C.BOLD}{'='*70}\n{msg}\n{'='*70}{C.END}")


# =====================================================================
# TEST 1: Frontend Payload Analysis
# =====================================================================
def test_frontend_payload():
    """Check what the frontend sends and whether it includes MCP/tool params."""
    header("TEST 1: Frontend Payload Analysis")

    # Check ChatQueryPayload type
    chat_types = FRONTEND / "typings" / "chat.ts"
    if not chat_types.exists():
        warn("Cannot find frontend/src/typings/chat.ts")
        return {}

    content = chat_types.read_text(encoding="utf-8")

    # Check which fields are in ChatQueryPayload
    results = {}
    backend_fields = {
        "enable_added_tools": "Boolean to enable/disable MCP added tools",
        "enable_web_search": "Boolean to enable/disable web search",
        "enable_background_investigation": "Boolean for background research",
        "max_plan_iterations": "Plan iteration count",
        "max_step_num": "Max steps per plan",
        "max_search_results": "Max search results",
        "auto_accepted_plan": "Auto-accept plans",
        "mcp_settings": "User MCP server configurations",
        "locale": "User locale string",
        "module": "Agent module type",
    }

    for field, desc in backend_fields.items():
        # Check both snake_case and camelCase
        camel = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), field)
        if field in content or camel in content:
            ok(f"Frontend type includes '{field}' ({desc})")
            results[field] = "present"
        else:
            warn(f"Frontend type MISSING '{field}' ({desc})")
            results[field] = "missing"

    # Check what tools the frontend explicitly manages
    settings_file = FRONTEND / "state" / "slice" / "settings.ts"
    if settings_file.exists():
        settings_content = settings_file.read_text(encoding="utf-8")

        # ToolSettings (agent page toggles)
        tool_settings_fields = re.findall(r'(\w+):\s*(?:boolean|number)', settings_content)
        info(f"Frontend ToolSettings fields: {', '.join(tool_settings_fields)}")

        # chatToolSettings defaults
        chat_defaults = re.findall(r'(\w+):\s*(true|false)', settings_content)
        info(f"Frontend chatToolSettings defaults: {dict(chat_defaults)}")

    # Check chat.service.ts HTTP body
    service_file = FRONTEND / "services" / "chat.service.ts"
    if service_file.exists():
        svc = service_file.read_text(encoding="utf-8")

        # Extract the JSON.stringify body
        body_match = re.search(r'body:\s*JSON\.stringify\(\{(.*?)\}\)', svc, re.DOTALL)
        if body_match:
            body_text = body_match.group(1)
            info(f"HTTP SSE body fields: {[f.strip().split(':')[0].strip() for f in body_text.split(',') if ':' in f]}")

            if "enable_added_tools" in body_text or "enableAddedTools" in body_text:
                ok("HTTP body INCLUDES enable_added_tools")
            else:
                warn("HTTP body does NOT include enable_added_tools (relies on backend default=True)")

            if "module" in body_text:
                ok("HTTP body INCLUDES module")
            else:
                info("HTTP body uses endpoint routing instead of module field")
        else:
            warn("Could not parse HTTP body from chat.service.ts")

    # Check Socket.IO payload
    question_handler = FRONTEND / "hooks" / "use-question-handlers.tsx"
    if question_handler.exists():
        qh = question_handler.read_text(encoding="utf-8")

        if "enable_added_tools" in qh or "enableAddedTools" in qh:
            ok("Socket.IO payload INCLUDES enable_added_tools")
        else:
            warn("Socket.IO payload does NOT include enable_added_tools")

        if "tool_args" in qh:
            info("Socket.IO payload INCLUDES tool_args (frontend-side tool toggles)")
        if "agent_type" in qh:
            ok("Socket.IO payload INCLUDES agent_type")
        else:
            warn("Socket.IO payload MISSING agent_type")

    return results


# =====================================================================
# TEST 2: WebSocket (Socket.IO) Path — query_handler.py
# =====================================================================
def test_websocket_path():
    """Check the Socket.IO path in query_handler.py."""
    header("TEST 2: WebSocket (Socket.IO) Path - query_handler.py")

    qh_file = BACKEND / "common" / "socketio" / "command" / "query_handler.py"
    if not qh_file.exists():
        fail("Cannot find query_handler.py")
        return {}

    source = qh_file.read_text(encoding="utf-8")
    results = {}

    # Check what fields are extracted from content (frontend payload)
    info("Fields extracted from frontend Socket.IO content:")
    extractions = re.findall(r"content\.get\(['\"](\w+)['\"]", source)
    for field in sorted(set(extractions)):
        info(f"  - content.get('{field}')")

    # Check if tool_args is ever read
    if "tool_args" in source:
        ok("query_handler reads 'tool_args' from frontend payload")
        results["tool_args_read"] = True
    else:
        warn("query_handler IGNORES 'tool_args' from frontend payload")
        results["tool_args_read"] = False

    # Check _agent_stream_generator call
    # Find the call block
    gen_call = re.search(
        r'_agent_stream_generator\((.*?)\):',
        source,
        re.DOTALL
    )
    if gen_call:
        call_body = gen_call.group(1)
        params_passed = re.findall(r'(\w+)\s*=', call_body)
        info(f"Params passed to _agent_stream_generator: {params_passed}")

        # Check critical params
        critical_params = [
            "enable_added_tools",
            "enable_web_search",
            "locale",
        ]
        for param in critical_params:
            if param in params_passed:
                ok(f"_agent_stream_generator receives '{param}'")
                results[param] = True

                # Check if hardcoded
                match = re.search(rf'{param}\s*=\s*(\w+)', call_body)
                if match:
                    value = match.group(1)
                    if value in ("True", "False"):
                        info(f"  '{param}' is HARDCODED to {value} (not from frontend)")
                    else:
                        info(f"  '{param}' = {value}")
            else:
                fail(f"_agent_stream_generator MISSING '{param}' -> will crash at runtime!")
                results[param] = False

    # Check _run_chat_no_sandbox
    chat_call = re.search(
        r'_astream_workflow_generator\((.*?)\):',
        source,
        re.DOTALL
    )
    if chat_call:
        chat_body = chat_call.group(1)
        info(f"\nChat (no sandbox) path - _astream_workflow_generator params:")
        chat_params = re.findall(r'(\w+)\s*=', chat_body)
        for p in chat_params:
            info(f"  - {p}")

        if "mcp_settings" in chat_params:
            match = re.search(r'mcp_settings\s*=\s*(\{[^}]*\})', chat_body)
            if match and match.group(1) == "{}":
                info("  mcp_settings is HARDCODED to empty dict {}")

    return results


# =====================================================================
# TEST 3: HTTP SSE Path — agent.py
# =====================================================================
def test_http_path():
    """Check the HTTP /agent/stream path in agent.py."""
    header("TEST 3: HTTP SSE Path - agent.py")

    agent_file = BACKEND / "app" / "agent" / "api" / "v1" / "agent.py"
    if not agent_file.exists():
        fail("Cannot find agent.py")
        return {}

    source = agent_file.read_text(encoding="utf-8")
    results = {}

    # Check AgentRequest fields
    info("AgentRequest model fields:")
    # Find class body
    class_match = re.search(
        r'class AgentRequest\(BaseModel\):(.*?)(?=\nclass |\ndef |\n# ===)',
        source,
        re.DOTALL
    )
    if class_match:
        class_body = class_match.group(1)
        field_matches = re.findall(
            r'(\w+):\s*(\w+(?:\[.*?\])?)\s*=\s*Field\((?:default=)?(\w+|None)',
            class_body
        )
        for name, type_, default in field_matches:
            info(f"  {name}: {type_} = {default}")
            results[f"request_{name}"] = default

    # Check StreamingResponse call passes all fields
    stream_call = re.search(
        r'StreamingResponse\(\s*_agent_stream_generator\((.*?)\),',
        source,
        re.DOTALL
    )
    if stream_call:
        call_text = stream_call.group(1)
        params_in_call = re.findall(r'(\w+)=', call_text)
        info(f"\nParams passed to _agent_stream_generator from HTTP path:")
        for p in params_in_call:
            info(f"  - {p}")

        if "enable_added_tools" in params_in_call:
            ok("HTTP path passes enable_added_tools to stream generator")
            results["http_enable_added_tools"] = True

            # Check if from request
            if "request.enable_added_tools" in call_text:
                ok("  Value comes from request (frontend can control it)")
            else:
                warn("  Value does NOT come from request")
        else:
            fail("HTTP path MISSING enable_added_tools in stream generator call")
            results["http_enable_added_tools"] = False

    # Check _agent_stream_generator signature
    sig_match = re.search(
        r'async def _agent_stream_generator\((.*?)\):',
        source,
        re.DOTALL
    )
    if sig_match:
        sig_text = sig_match.group(1)
        sig_params = re.findall(r'(\w+)(?:\s*[:,])', sig_text)
        info(f"\n_agent_stream_generator signature params: {sig_params}")

    return results


# =====================================================================
# TEST 4: Configuration.from_runnable_config() Boolean Safety
# =====================================================================
def test_configuration_boolean_safety():
    """Check that Configuration.from_runnable_config() preserves False values."""
    header("TEST 4: Configuration.from_runnable_config() Boolean Safety")

    config_file = BACKEND / "src" / "config" / "configuration.py"
    if not config_file.exists():
        fail("Cannot find configuration.py")
        return {}

    source = config_file.read_text(encoding="utf-8")
    results = {}

    # Check if the filter uses 'if v' (drops False) or 'if v is not None' (preserves False)
    if "if v is not None" in source:
        ok("from_runnable_config() uses 'if v is not None' -- preserves False values")
        results["boolean_safe"] = True
    elif "if v}" in source or "if v)" in source:
        fail("from_runnable_config() uses 'if v' -- DROPS False values!")
        fail("  enable_added_tools=False would be silently converted to True")
        fail("  enable_web_search=False would be silently converted to True")
        results["boolean_safe"] = False
    else:
        info("Could not determine filter pattern")

    # Verify by importing and testing
    try:
        sys.path.insert(0, str(ROOT))
        from backend.src.config.configuration import Configuration

        # Test with False values
        config = {"configurable": {
            "enable_added_tools": False,
            "enable_web_search": False,
            "mcp_url": "http://test:6060",
        }}
        cfg = Configuration.from_runnable_config(config)

        if cfg.enable_added_tools is False:
            ok("LIVE TEST: enable_added_tools=False is correctly preserved")
            results["false_preserved_added_tools"] = True
        else:
            fail(f"LIVE TEST: enable_added_tools=False was converted to {cfg.enable_added_tools!r}")
            results["false_preserved_added_tools"] = False

        if cfg.enable_web_search is False:
            ok("LIVE TEST: enable_web_search=False is correctly preserved")
            results["false_preserved_web_search"] = True
        else:
            fail(f"LIVE TEST: enable_web_search=False was converted to {cfg.enable_web_search!r}")
            results["false_preserved_web_search"] = False

        if cfg.mcp_url == "http://test:6060":
            ok("LIVE TEST: mcp_url string value preserved")
        else:
            fail(f"LIVE TEST: mcp_url = {cfg.mcp_url!r}")

        # Test with True values (should still work)
        config2 = {"configurable": {
            "enable_added_tools": True,
            "enable_web_search": True,
        }}
        cfg2 = Configuration.from_runnable_config(config2)

        if cfg2.enable_added_tools is True and cfg2.enable_web_search is True:
            ok("LIVE TEST: True values still work correctly")
        else:
            fail("LIVE TEST: True values broken!")

        # Test with omitted values (should use defaults)
        config3 = {"configurable": {}}
        cfg3 = Configuration.from_runnable_config(config3)

        if cfg3.enable_added_tools is True and cfg3.enable_web_search is True:
            ok("LIVE TEST: Omitted values correctly default to True")
        else:
            fail(f"LIVE TEST: Defaults broken - added_tools={cfg3.enable_added_tools}, web_search={cfg3.enable_web_search}")

    except Exception as e:
        warn(f"Could not run live Configuration test: {e}")

    return results


# =====================================================================
# TEST 5: workflow_config Propagation Chain
# =====================================================================
def test_workflow_config_chain():
    """Check the full chain: workflow_config -> Configuration -> node tools."""
    header("TEST 5: workflow_config -> Configuration -> Node Tools Chain")

    agent_file = BACKEND / "app" / "agent" / "api" / "v1" / "agent.py"
    nodes_file = BACKEND / "src" / "graph" / "nodes.py"
    config_file = BACKEND / "src" / "config" / "configuration.py"

    results = {}

    # Step 1: Check workflow_config construction in agent.py
    if agent_file.exists():
        source = agent_file.read_text(encoding="utf-8")

        # Find workflow_config block
        wc_match = re.search(r'workflow_config\s*=\s*\{(.*?)\}', source, re.DOTALL)
        if wc_match:
            wc_text = wc_match.group(1)

            critical_fields = {
                "mcp_url": "Sandbox MCP server URL (tools endpoint)",
                "codex_url": "Codex SSE URL (delegation)",
                "enable_added_tools": "External tools toggle",
                "enable_web_search": "Web search toggle",
                "thread_id": "Session/thread ID",
            }

            for field, desc in critical_fields.items():
                if field in wc_text:
                    ok(f"workflow_config includes '{field}' ({desc})")
                    results[field] = True
                else:
                    fail(f"workflow_config MISSING '{field}' ({desc})")
                    results[field] = False

    # Step 2: Check nodes.py reads these from Configuration
    if nodes_file.exists():
        nodes_src = nodes_file.read_text(encoding="utf-8")

        reads = {
            "mcp_url": "configurable.mcp_url",
            "mcp_settings": "configurable.mcp_settings",
            "enable_added_tools": "configurable.enable_added_tools",
            "enable_web_search": "configurable.enable_web_search",
        }

        for field, pattern in reads.items():
            if pattern in nodes_src:
                ok(f"nodes.py reads {pattern}")
            else:
                warn(f"nodes.py does NOT read {pattern}")

    return results


# =====================================================================
# TEST 6: Frontend-Backend Field Mismatch Report
# =====================================================================
def test_field_mapping():
    """Generate a comprehensive mapping of frontend -> backend fields."""
    header("TEST 6: Frontend-to-Backend Field Mapping Report")

    print(f"""
  {C.BOLD}Socket.IO Path (frontend/hooks/use-question-handlers.tsx -> query_handler.py):{C.END}
  
  Frontend sends              Backend reads                 Forwarded?
  ========================    ============================  ==========
  text                   ->   content.get('message/text')   Yes
  files                  ->   content.get('files')          Yes
  agent_type             ->   content.get('agent_type')     Yes
  model_id               ->   content.get('model_id')       Yes (billing only)
  tool_args.*            ->   NOT READ                      NO (dropped)
  thinking_tokens        ->   NOT READ                      NO (dropped)
  metadata               ->   NOT READ                      NO (dropped)
  
  {C.BOLD}HTTP SSE Path (frontend/services/chat.service.ts -> agent.py AgentRequest):{C.END}
  
  Frontend sends              Backend field                 Default
  ========================    ============================  ============
  messages               ->   messages                      (required)
  agent_type             ->   (endpoint routing)            general
  tools.web_search       ->   NOT MAPPED                    True
  tools.web_visit        ->   NOT MAPPED                    -
  tools.image_search     ->   NOT MAPPED                    -
  tools.code_interpreter ->   NOT MAPPED                    -
  (not sent)                  enable_added_tools            True
  (not sent)                  enable_web_search             True
  (not sent)                  enable_background_investigation  True
  (not sent)                  max_plan_iterations           1
  (not sent)                  max_step_num                  3
  (not sent)                  max_search_results            3
  (not sent)                  auto_accepted_plan            True
  (not sent)                  locale                        en-US
  
  {C.WARN}Key Observations:{C.END}
  - Frontend has NO toggle for 'enable_added_tools' -- always defaults True
  - Frontend 'tools' object is NOT mapped to backend 'enable_*' fields
  - Socket.IO 'tool_args' object is completely ignored by backend
  - Frontend cannot control max_plan_iterations, max_step_num, etc.
""")


# =====================================================================
# TEST 7: Verify No Accidental Disabling in Middleware/Interceptors
# =====================================================================
def test_middleware():
    """Check if any middleware or interceptor modifies agent parameters."""
    header("TEST 7: Middleware / Interceptor Check")

    middleware_dir = BACKEND / "middleware"
    if middleware_dir.exists():
        for mw_file in middleware_dir.rglob("*.py"):
            content = mw_file.read_text(encoding="utf-8")
            if "enable_added_tools" in content or "mcp_url" in content:
                warn(f"Middleware {mw_file.name} references MCP/tool params -- investigate!")
            else:
                ok(f"Middleware {mw_file.name} does NOT modify MCP/tool params")
    else:
        info("No middleware directory found")

    # Check CORS / auth middleware
    for pattern in ["**/cors*", "**/auth*", "**/jwt*"]:
        for f in BACKEND.rglob(pattern):
            if f.suffix == ".py":
                content = f.read_text(encoding="utf-8")
                if "enable_added_tools" in content or "mcp_url" in content or "mcp_settings" in content:
                    warn(f"{f.name} references MCP/tool params")


# =====================================================================
# MAIN
# =====================================================================
def main():
    print(f"\n{C.BOLD}{'#'*70}")
    print(f"  Frontend-to-Backend MCP Pipeline Audit")
    print(f"  Tracing: Frontend -> WebSocket/HTTP -> agent.py -> workflow_config")
    print(f"           -> Configuration -> nodes.py -> MCP tools")
    print(f"{'#'*70}{C.END}")

    frontend_results = test_frontend_payload()
    ws_results = test_websocket_path()
    http_results = test_http_path()
    bool_results = test_configuration_boolean_safety()
    chain_results = test_workflow_config_chain()
    test_field_mapping()
    test_middleware()

    # ── Summary ──
    header("OVERALL SUMMARY")

    print(f"""
  {C.BOLD}Results:{C.END} {C.OK}{passed} passed{C.END}, {C.WARN}{warnings} warnings{C.END}, {C.FAIL}{failed} failed{C.END}

  {C.BOLD}Critical Findings:{C.END}
""")

    # Check key issues
    issues = []

    if not ws_results.get("enable_added_tools"):
        issues.append(
            "WebSocket path does NOT pass enable_added_tools to _agent_stream_generator (crash bug)"
        )

    if not bool_results.get("boolean_safe"):
        issues.append(
            "Configuration.from_runnable_config() drops False values (can't disable features)"
        )

    if not http_results.get("http_enable_added_tools"):
        issues.append(
            "HTTP path does NOT pass enable_added_tools to stream generator"
        )

    if frontend_results.get("enable_added_tools") == "missing":
        issues.append(
            "Frontend has NO enable_added_tools field (always relies on backend default=True)"
        )

    if not ws_results.get("tool_args_read"):
        issues.append(
            "Frontend sends tool_args via Socket.IO but backend ignores them (wasted data)"
        )

    if issues:
        for i, issue in enumerate(issues, 1):
            print(f"  {C.FAIL}  {i}. {issue}{C.END}")
    else:
        print(f"  {C.OK}  No critical issues found!{C.END}")

    print(f"""
  {C.BOLD}Architecture Note:{C.END}
  The frontend does NOT send enable_added_tools in ANY path.
  The backend defaults it to True in both paths:
    - HTTP:      AgentRequest.enable_added_tools = Field(default=True)
    - Socket.IO: hardcoded enable_added_tools=True in query_handler.py

  This means MCP tools are ALWAYS enabled -- there is currently
  no way to disable them from the frontend. This is by design
  (no UI toggle exists), but if a toggle is added later, the
  backend is now ready to respect it.
""")

    # Exit code
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
