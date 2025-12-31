#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Endpoint Test Script

This script tests the /agent/agent/stream endpoint which:
1. Creates a sandbox lazily (only when tools need them)
2. Reuses sandboxes for the same session
3. Streams responses in real-time using SSE
4. Supports multiple agent modules via the 'module' parameter

This is different from /api/v1/agent/chat/stream which does NOT create sandboxes.

Available Modules:
    - general (default): MCP-enabled agent with sandbox tools
    - research: Multi-agent deep research workflow
    - podcast: Podcast generation (not yet implemented)
    - ppt: PowerPoint generation (not yet implemented)
    - prose: Prose writing operations (not yet implemented)

Flow tested:
    Client -> /agent/agent/stream
           -> SSE: status:processing (includes module name)
           -> SessionSandboxManager creates/reuses sandbox
           -> SSE: status:sandbox_ready (sandbox_id)
           -> Wait for MCP server health check
           -> SSE: status:mcp_ready OR warning:mcp_timeout
           -> LangGraph agent workflow runs
           -> SSE: status:agent_start
           -> SSE: message:chunk (multiple)
           -> SSE: tool:start / tool:end (if tools used)
           -> SSE: status:complete

Prerequisites:
    1. Backend server running at http://localhost:8000
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/create_test_user.py
    3. E2B_API_KEY configured in backend/.env

Usage:
    python backend/tests/live/backend_endpoints/test_agent_endpoints.py

    # With verbose output
    python backend/tests/live/backend_endpoints/test_agent_endpoints.py --verbose

    # Custom base URL
    python backend/tests/live/backend_endpoints/test_agent_endpoints.py --base-url http://localhost:8001

Example Request Body:
    {
        "module": "general",  # Optional, defaults to "general"
        "messages": [{"role": "user", "content": "Hello"}],
        "thread_id": "my-session-id"
    }
"""

import asyncio
import argparse
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Fix Windows encoding issues with emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import httpx

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


# =============================================================================
# Data Classes for SSE Events
# =============================================================================

@dataclass
class SSEEvent:
    """Represents a parsed Server-Sent Event."""
    event_type: str
    data: Dict[str, Any]
    raw: str = ""


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str = ""
    events: List[SSEEvent] = field(default_factory=list)
    duration_seconds: float = 0.0


# =============================================================================
# SSE Parser
# =============================================================================

def parse_sse_line(line: str) -> Optional[Tuple[str, str]]:
    """
    Parse a single SSE line.
    
    Returns:
        Tuple of (field, value) or None if not a valid SSE line.
    """
    line = line.strip()
    if not line or line.startswith(':'):
        return None
    
    if ':' in line:
        field, value = line.split(':', 1)
        return field.strip(), value.strip()
    return None


def parse_sse_chunk(chunk: str) -> List[SSEEvent]:
    """
    Parse an SSE chunk which may contain multiple events.
    
    SSE format:
        event: <event_type>
        data: <json_data>
        
        event: <event_type>
        data: <json_data>
    
    Events are separated by blank lines.
    """
    events = []
    current_event_type = None
    current_data = None
    
    lines = chunk.split('\n')
    for line in lines:
        parsed = parse_sse_line(line)
        if parsed:
            field, value = parsed
            if field == 'event':
                current_event_type = value
            elif field == 'data':
                current_data = value
                
                # If we have both event and data, create the event
                if current_event_type and current_data:
                    try:
                        data = json.loads(current_data)
                    except json.JSONDecodeError:
                        data = {"raw": current_data}
                    
                    events.append(SSEEvent(
                        event_type=current_event_type,
                        data=data,
                        raw=f"event: {current_event_type}\ndata: {current_data}"
                    ))
                    current_event_type = None
                    current_data = None
    
    return events


# =============================================================================
# Agent Endpoint Tester
# =============================================================================

class AgentEndpointTester:
    """
    Tests the /agent/agent/stream endpoint.
    
    This endpoint is special because it:
    1. Creates sandboxes lazily via SessionSandboxManager
    2. Waits for MCP server to be ready
    3. Runs LangGraph agent workflow
    4. Streams responses via SSE
    """
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.token: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.sandbox_id: Optional[str] = None
        self.test_results: List[TestResult] = []
    
    def log(self, message: str, level: str = "info"):
        """Log a message with optional verbosity control."""
        if level == "verbose" and not self.verbose:
            return
        print(message)
    
    async def setup(self):
        """Initialize HTTP client and authenticate."""
        self.log("\n" + "=" * 70)
        self.log("🧪 Agent Endpoint Test Suite")
        self.log(f"   Base URL: {self.base_url}")
        self.log(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 70)
        
        # Initialize HTTP client with longer timeout for sandbox creation
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=180.0,  # Long timeout for streaming
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'AgentEndpointTest/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        # Authenticate
        self.log("\n📋 Step 1: Authenticating...")
        if not await self._login():
            self.log("   ❌ Login failed. Make sure:")
            self.log(f"      - Backend is running at {self.base_url}")
            self.log("      - Test user exists (run: python backend/tests/create_test_user.py)")
            return False
        
        self.log("   ✅ Got JWT token")
        return True
    
    async def _login(self) -> bool:
        """Authenticate and get JWT token."""
        try:
            # The /login/swagger endpoint uses query parameters
            # See: backend/tests/live/test_sandbox_comprehensive.py
            response = await self.client.post(
                f'{self.base_url}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                token_type = data.get('token_type', 'Bearer')
                self.client.headers['Authorization'] = f'{token_type} {self.token}'
                return True
            
            self.log(f"   Login failed: {response.status_code} - {response.text}", "verbose")
            return False
            
        except Exception as e:
            self.log(f"   Login error: {e}", "verbose")
            return False
    
    async def test_agent_stream_basic(self) -> TestResult:
        """
        Test the /agent/agent/stream endpoint with a simple message.
        
        Expected SSE events:
        1. status:processing - Immediate feedback
        2. status:sandbox_ready - Sandbox created/connected
        3. status:mcp_check - Checking MCP server
        4. status:mcp_ready OR warning:mcp_timeout - MCP status
        5. status:agent_start - Agent workflow started
        6. message:chunk - One or more response chunks
        7. status:complete - Workflow complete
        """
        self.log("\n📋 Step 2: Testing /agent/agent/stream endpoint...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        
        try:
            # Prepare request - using 'general' module (default, MCP-enabled agent)
            request_body = {
                "module": "general",  # Specify the agent module (general, research, podcast, ppt, prose)
                "messages": [
                    {"role": "user", "content": "create a basic calculator app, deploy it in the terminal and give me the link to view."}
                ],
                "thread_id": f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": False,  # Faster test
                "enable_web_search": False,  # Faster test
                "enable_deep_thinking": False,
                "max_plan_iterations": 1,
                "max_step_num": 2
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            # Stream response
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="agent_stream_basic",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                # Parse SSE events
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # Parse complete events (separated by double newlines)
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            self._log_event(event)
                            
                            # Capture sandbox_id for cleanup
                            if event.event_type == "status":
                                if event.data.get("type") == "sandbox_ready":
                                    self.sandbox_id = event.data.get("sandbox_id")
            
            # Validate expected events were received
            return self._validate_events(events, start_time)
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="agent_stream_basic",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    def _log_event(self, event: SSEEvent):
        """Log an SSE event with nice formatting."""
        event_type = event.event_type
        data_type = event.data.get("type", "")
        
        if event_type == "status":
            if data_type == "processing":
                self.log("   ✅ Received status:processing")
            elif data_type == "sandbox_ready":
                sandbox_id = event.data.get("sandbox_id", "?")
                self.log(f"   ✅ Received status:sandbox_ready (sandbox_id={sandbox_id[:20]}...)")
            elif data_type == "mcp_check":
                self.log("   ⏳ Received status:mcp_check")
            elif data_type == "mcp_ready":
                self.log("   ✅ Received status:mcp_ready")
            elif data_type == "agent_start":
                self.log("   ✅ Received status:agent_start")
            elif data_type == "complete":
                self.log("   ✅ Received status:complete")
            elif data_type == "mcp_waiting":
                elapsed = event.data.get("elapsed_seconds", "?")
                self.log(f"   ⏳ Waiting for MCP... ({elapsed}s)", "verbose")
            else:
                self.log(f"   📋 Received status:{data_type}", "verbose")
        
        elif event_type == "message":
            content = event.data.get("content", "")[:50]
            self.log(f"   💬 Received message:chunk '{content}...'", "verbose")
        
        elif event_type == "tool":
            tool_name = event.data.get("name", "?")
            tool_type = event.data.get("type", "?")
            self.log(f"   🔧 Received tool:{tool_type} ({tool_name})", "verbose")
        
        elif event_type == "warning":
            message = event.data.get("message", "?")
            self.log(f"   ⚠️ Warning: {message}")
        
        elif event_type == "error":
            message = event.data.get("message", "?")
            self.log(f"   ❌ Error: {message}")
    
    def _validate_events(self, events: List[SSEEvent], start_time: datetime) -> TestResult:
        """Validate that all expected events were received."""
        duration = (datetime.now() - start_time).total_seconds()
        
        # Extract event types
        status_types = [e.data.get("type") for e in events if e.event_type == "status"]
        message_count = len([e for e in events if e.event_type == "message"])
        has_error = any(e.event_type == "error" for e in events)
        
        # Check for errors first
        if has_error:
            error_msgs = [e.data.get("message", "?") for e in events if e.event_type == "error"]
            return TestResult(
                name="agent_stream_basic",
                passed=False,
                message=f"Received error event(s): {error_msgs}",
                events=events,
                duration_seconds=duration
            )
        
        # Check required events
        required = ["processing", "sandbox_ready", "agent_start", "complete"]
        missing = [r for r in required if r not in status_types]
        
        if missing:
            return TestResult(
                name="agent_stream_basic",
                passed=False,
                message=f"Missing required status events: {missing}",
                events=events,
                duration_seconds=duration
            )
        
        # Check we got some message chunks
        if message_count == 0:
            self.log("   ⚠️ No message chunks received (agent may not have responded)")
        else:
            self.log(f"   ✅ Received {message_count} message chunks")
        
        return TestResult(
            name="agent_stream_basic",
            passed=True,
            message=f"All events received ({len(events)} total, {message_count} message chunks)",
            events=events,
            duration_seconds=duration
        )
    
    async def test_agent_stream_research(self) -> TestResult:
        """
        Test the /agent/agent/stream endpoint with the research module.
        
        The research module is a multi-agent workflow with coordinator, planner,
        researcher, and reporter nodes. This test verifies that the module parameter
        correctly routes to the research graph.
        """
        self.log("\n📋 Testing /agent/agent/stream with RESEARCH module...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        
        try:
            # Prepare request - using 'research' module for deep research workflow
            request_body = {
                "module": "research",  # Use the research multi-agent workflow
                "messages": [
                    {"role": "user", "content": "What are the latest trends in AI for 2025?"}
                ],
                "thread_id": f"test-research-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": False,
                "enable_web_search": True,  # Research module benefits from web search
                "enable_deep_thinking": False,
                "max_plan_iterations": 1,
                "max_step_num": 3,
                "max_search_results": 3
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            # Stream response
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="agent_stream_research",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                # Parse SSE events
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            self._log_event(event)
                            
                            # Verify module name in processing status
                            if event.event_type == "status":
                                if event.data.get("type") == "processing":
                                    module = event.data.get("module", "")
                                    if module == "research":
                                        self.log("   ✅ Confirmed research module in use")
                                if event.data.get("type") == "sandbox_ready":
                                    self.sandbox_id = event.data.get("sandbox_id")
            
            # Validate events - same as basic test
            duration = (datetime.now() - start_time).total_seconds()
            status_types = [e.data.get("type") for e in events if e.event_type == "status"]
            message_count = len([e for e in events if e.event_type == "message"])
            
            required = ["processing", "sandbox_ready", "agent_start", "complete"]
            missing = [r for r in required if r not in status_types]
            
            if missing:
                return TestResult(
                    name="agent_stream_research",
                    passed=False,
                    message=f"Missing required status events: {missing}",
                    events=events,
                    duration_seconds=duration
                )
            
            return TestResult(
                name="agent_stream_research",
                passed=True,
                message=f"Research module test passed ({len(events)} events, {message_count} messages)",
                events=events,
                duration_seconds=duration
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="agent_stream_research",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def test_module_not_implemented(self) -> TestResult:
        """
        Test that unimplemented modules return HTTP 501.
        
        This verifies proper error handling for modules like 'podcast' that
        are registered but not yet implemented.
        """
        self.log("\n📋 Testing unimplemented module (expect 501)...")
        
        start_time = datetime.now()
        
        try:
            request_body = {
                "module": "podcast",  # This module is stubbed (not implemented)
                "messages": [
                    {"role": "user", "content": "Create a podcast about AI"}
                ],
                "thread_id": f"test-notimpl-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
            response = await self.client.post(
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if response.status_code == 501:
                self.log("   ✅ Correctly received HTTP 501 Not Implemented")
                return TestResult(
                    name="module_not_implemented",
                    passed=True,
                    message="Unimplemented module correctly returns 501",
                    duration_seconds=duration
                )
            else:
                self.log(f"   ❌ Expected 501, got {response.status_code}")
                return TestResult(
                    name="module_not_implemented",
                    passed=False,
                    message=f"Expected HTTP 501, got {response.status_code}",
                    duration_seconds=duration
                )
                
        except Exception as e:
            return TestResult(
                name="module_not_implemented",
                passed=False,
                message=f"Exception: {e}",
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def cleanup(self):
        """Clean up sandbox and close connections."""
        self.log("\n📋 Step 3: Cleanup...")
        
        # Delete sandbox if created
        if self.sandbox_id and self.client:
            try:
                response = await self.client.delete(
                    f'{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                if response.status_code == 200:
                    self.log("   ✅ Sandbox deleted")
                else:
                    self.log(f"   ⚠️ Sandbox delete returned {response.status_code}", "verbose")
            except Exception as e:
                self.log(f"   ⚠️ Sandbox cleanup error: {e}", "verbose")
        
        # Close HTTP client
        if self.client:
            await self.client.aclose()
        
        self.log("   ✅ Cleanup complete")
    
    def print_summary(self):
        """Print test summary."""
        self.log("\n" + "=" * 70)
        
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        
        if passed == total:
            self.log(f"✅ All {total} tests passed!")
        else:
            self.log(f"❌ {passed}/{total} tests passed")
            
            for result in self.test_results:
                if not result.passed:
                    self.log(f"   FAILED: {result.name} - {result.message}")
        
        total_duration = sum(r.duration_seconds for r in self.test_results)
        self.log(f"\n   Total duration: {total_duration:.1f}s")
        self.log("=" * 70)


# =============================================================================
# Main
# =============================================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Test the /agent/agent/stream endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script tests the agent endpoint which creates sandboxes and streams
responses via SSE.

Example:
    python test_agent_endpoints.py
    python test_agent_endpoints.py --verbose
    python test_agent_endpoints.py --base-url http://localhost:8001
        """
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"Backend base URL (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()


async def main():
    args = parse_arguments()
    tester = AgentEndpointTester(
        base_url=args.base_url,
        verbose=args.verbose
    )
    
    try:
        # Setup and authenticate
        if not await tester.setup():
            sys.exit(1)
        
        # Run tests for different modules
        
        # Test 1: Basic test with 'general' module (default)
        result = await tester.test_agent_stream_basic()
        tester.test_results.append(result)
        
        # Test 2: Test unimplemented module returns 501
        result = await tester.test_module_not_implemented()
        tester.test_results.append(result)
        
        # Test 3: Research module (optional - takes longer)
        # Uncomment to run research module test:
        # result = await tester.test_agent_stream_research()
        # tester.test_results.append(result)
        
    finally:
        await tester.cleanup()
        tester.print_summary()
    
    # Exit with appropriate code
    all_passed = all(r.passed for r in tester.test_results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(1)
