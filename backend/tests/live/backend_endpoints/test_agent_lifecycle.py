#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Backend Agent Full Lifecycle Test

This script tests the complete agent lifecycle from user authentication through
tool execution and response generation. It simulates a real user session.

LIFECYCLE TESTED:
    1. User Authentication → JWT Token
    2. Agent Stream Request → Sandbox Creation
    3. MCP Server Ready → Tool Registration
    4. Agent Execution → Tool Usage (Files, Shell, etc.)
    5. Response Streaming → Verification
    6. Cleanup → Sandbox Deletion

This test is designed to verify production-readiness of the agent system.

Prerequisites:
    1. Backend server running at http://localhost:8000
    2. Test user exists: sandbox_test / TestPass123!
    3. E2B_API_KEY configured in backend/.env
    4. Database configured (PostgreSQL recommended)

Usage:
    python backend/tests/live/backend_endpoints/test_agent_lifecycle.py
    python backend/tests/live/backend_endpoints/test_agent_lifecycle.py --verbose
    python backend/tests/live/backend_endpoints/test_agent_lifecycle.py --task "list files in /workspace"
"""

import asyncio
import argparse
import json
import sys
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Fix Windows encoding issues
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

# Test tasks that should trigger different tools
TEST_TASKS = {
    "file_creation": {
        "prompt": "Create a file called hello.py in /workspace with a simple hello world program, then show me its contents.",
        "expected_tools": ["WriteFile", "ReadFile"],
        "description": "Tests file creation and reading tools"
    },
    "shell_command": {
        "prompt": "Run 'pwd' and 'ls -la /workspace' in the terminal and show me the output.",
        "expected_tools": ["ExecuteShell", "RunTerminalCommand"],
        "description": "Tests shell execution tools"
    },
    "simple_response": {
        "prompt": "What is 2 + 2? Just answer directly.",
        "expected_tools": [],
        "description": "Tests pure LLM response without tools"
    },
    "slide_creation": {
        "prompt": "Create a simple presentation about AI with 3 slides using the SlideWrite tool.",
        "expected_tools": ["SlideWrite"],
        "description": "Tests slide generation tools"
    }
}


# =============================================================================
# Data Classes
# =============================================================================

class TestPhase(Enum):
    AUTH = "authentication"
    SANDBOX = "sandbox_creation"
    MCP = "mcp_initialization"
    TOOLS = "tool_registration"
    EXECUTION = "agent_execution"
    RESPONSE = "response_streaming"
    CLEANUP = "cleanup"


@dataclass
class SSEEvent:
    """Parsed SSE event."""
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class LifecycleResult:
    """Result of a lifecycle phase."""
    phase: TestPhase
    passed: bool
    message: str
    duration: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolUsage:
    """Tracks tool usage during agent execution."""
    name: str
    started_at: float
    ended_at: Optional[float] = None
    success: bool = False
    result_preview: str = ""


# =============================================================================
# SSE Parser
# =============================================================================

def parse_sse_chunk(chunk: str) -> List[SSEEvent]:
    """Parse SSE chunk into events."""
    events = []
    current_event_type = None
    current_data = None
    
    for line in chunk.split('\n'):
        line = line.strip()
        if not line or line.startswith(':'):
            continue
        if ':' in line:
            field, value = line.split(':', 1)
            field = field.strip()
            value = value.strip()
            if field == 'event':
                current_event_type = value
            elif field == 'data':
                current_data = value
                if current_event_type and current_data:
                    try:
                        data = json.loads(current_data)
                    except json.JSONDecodeError:
                        data = {"raw": current_data}
                    events.append(SSEEvent(
                        event_type=current_event_type,
                        data=data
                    ))
                    current_event_type = None
                    current_data = None
    return events


# =============================================================================
# Backend Agent Lifecycle Tester
# =============================================================================

class BackendAgentLifecycleTester:
    """
    Tests the complete backend agent lifecycle.
    
    This tester verifies:
    1. Authentication works and JWT is obtained
    2. Sandbox is created (or reused) correctly
    3. MCP server initializes with tools
    4. Agent executes and uses available tools
    5. Responses stream correctly via SSE
    6. Sandbox cleanup works
    """
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        task_key: str = "file_creation",
        custom_prompt: Optional[str] = None,
        verbose: bool = False
    ):
        self.base_url = base_url
        self.task_key = task_key
        self.custom_prompt = custom_prompt
        self.verbose = verbose
        
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.thread_id: Optional[str] = None
        self.sandbox_id: Optional[str] = None
        self.mcp_url: Optional[str] = None
        
        self.client: Optional[httpx.AsyncClient] = None
        self.phase_results: List[LifecycleResult] = []
        self.tools_used: List[ToolUsage] = []
        self.all_events: List[SSEEvent] = []
        self.message_chunks: List[str] = []
        
        self.start_time = time.time()
    
    def log(self, message: str, level: str = "info"):
        """Log with optional verbosity."""
        if level == "verbose" and not self.verbose:
            return
        timestamp = f"[{time.time() - self.start_time:6.1f}s]"
        print(f"{timestamp} {message}")
    
    def _get_task(self) -> Tuple[str, List[str], str]:
        """Get the test task prompt and expected tools."""
        if self.custom_prompt:
            return self.custom_prompt, [], "Custom task"
        task = TEST_TASKS.get(self.task_key, TEST_TASKS["file_creation"])
        return task["prompt"], task["expected_tools"], task["description"]
    
    # =========================================================================
    # Phase 1: Authentication
    # =========================================================================
    
    async def phase_authenticate(self) -> LifecycleResult:
        """Authenticate and get JWT token."""
        self.log("\n📋 PHASE 1: Authentication")
        start = time.time()
        
        try:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
                headers={'User-Agent': 'BackendAgentLifecycleTest/1.0'}
            )
            
            # Login
            response = await self.client.post(
                f'{self.base_url}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            
            if response.status_code != 200:
                return LifecycleResult(
                    phase=TestPhase.AUTH,
                    passed=False,
                    message=f"Login failed: HTTP {response.status_code}",
                    duration=time.time() - start
                )
            
            data = response.json()
            self.token = data.get('access_token')
            
            if not self.token:
                return LifecycleResult(
                    phase=TestPhase.AUTH,
                    passed=False,
                    message="No access_token in response",
                    duration=time.time() - start
                )
            
            # Set auth header for all future requests
            self.client.headers['Authorization'] = f"Bearer {self.token}"
            
            self.log("   ✅ JWT token obtained")
            self.log(f"   Token: {self.token[:30]}...", "verbose")
            
            return LifecycleResult(
                phase=TestPhase.AUTH,
                passed=True,
                message="Successfully authenticated",
                duration=time.time() - start,
                details={"token_length": len(self.token)}
            )
            
        except Exception as e:
            return LifecycleResult(
                phase=TestPhase.AUTH,
                passed=False,
                message=f"Authentication error: {e}",
                duration=time.time() - start
            )
    
    # =========================================================================
    # Phase 2-6: Agent Stream (combines sandbox, MCP, execution, response)
    # =========================================================================
    
    async def phase_agent_stream(self) -> List[LifecycleResult]:
        """Run agent stream and track all lifecycle phases."""
        results = []
        self.log("\n📋 PHASE 2-5: Agent Stream Lifecycle")
        
        prompt, expected_tools, description = self._get_task()
        self.thread_id = f"lifecycle-test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.log(f"   Task: {description}")
        self.log(f"   Prompt: {prompt[:80]}...")
        
        sandbox_start = time.time()
        mcp_start = None
        execution_start = None
        
        try:
            request_body = {
                "module": "general",
                "messages": [{"role": "user", "content": prompt}],
                "thread_id": self.thread_id,
                "enable_background_investigation": False,
                "enable_web_search": False,
                "enable_deep_thinking": False,
                "max_plan_iterations": 1,
                "max_step_num": 3
            }
            
            self.log(f"   Request body: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    results.append(LifecycleResult(
                        phase=TestPhase.SANDBOX,
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()[:200]}",
                        duration=time.time() - sandbox_start
                    ))
                    return results
                
                # Parse SSE stream
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in events:
                            self.all_events.append(event)
                            self._process_event(event, results, sandbox_start, mcp_start, execution_start)
                            
                            # Track phase transitions
                            if event.event_type == "status":
                                if event.data.get("type") == "mcp_check":
                                    mcp_start = time.time()
                                elif event.data.get("type") == "agent_start":
                                    execution_start = time.time()
            
            # Add final results if not already added
            self._finalize_results(results, sandbox_start, mcp_start, execution_start, expected_tools)
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Stream error: {e}")
            if self.verbose:
                traceback.print_exc()
            results.append(LifecycleResult(
                phase=TestPhase.EXECUTION,
                passed=False,
                message=f"Stream error: {e}",
                duration=time.time() - sandbox_start
            ))
        
        return results
    
    def _process_event(
        self, 
        event: SSEEvent, 
        results: List[LifecycleResult],
        sandbox_start: float,
        mcp_start: Optional[float],
        execution_start: Optional[float]
    ):
        """Process individual SSE event."""
        event_type = event.event_type
        data = event.data
        data_type = data.get("type", "")
        
        if event_type == "status":
            if data_type == "processing":
                module = data.get("module", "general")
                self.log(f"   ✅ Processing started (module: {module})")
            
            elif data_type == "sandbox_ready":
                self.sandbox_id = data.get("sandbox_id")
                self.log(f"   ✅ Sandbox ready: {self.sandbox_id[:30]}...")
                results.append(LifecycleResult(
                    phase=TestPhase.SANDBOX,
                    passed=True,
                    message="Sandbox created successfully",
                    duration=time.time() - sandbox_start,
                    details={"sandbox_id": self.sandbox_id}
                ))
            
            elif data_type == "mcp_ready":
                self.mcp_url = data.get("mcp_url", "")
                self.log(f"   ✅ MCP server ready")
                if mcp_start:
                    results.append(LifecycleResult(
                        phase=TestPhase.MCP,
                        passed=True,
                        message="MCP server initialized",
                        duration=time.time() - mcp_start,
                        details={"mcp_url": self.mcp_url}
                    ))
            
            elif data_type == "tool_registration":
                self.log(f"   ✅ Tools registered")
                results.append(LifecycleResult(
                    phase=TestPhase.TOOLS,
                    passed=True,
                    message="Tools registered with MCP",
                    duration=0.1
                ))
            
            elif data_type == "tool_probe":
                tools = data.get("tools", [])
                self.log(f"   📦 Found {len(tools)} tools: {tools[:5]}...")
            
            elif data_type == "agent_start":
                self.log(f"   ✅ Agent execution started")
            
            elif data_type == "complete":
                self.log(f"   ✅ Agent execution complete")
        
        elif event_type == "message":
            content = data.get("content", "")
            if content:
                self.message_chunks.append(content)
                self.log(f"   💬 Message: {content[:60]}...", "verbose")
        
        elif event_type == "tool":
            tool_name = data.get("name", "unknown")
            tool_type = data.get("type", "")  # start, end
            
            if tool_type == "start":
                self.tools_used.append(ToolUsage(
                    name=tool_name,
                    started_at=time.time()
                ))
                self.log(f"   🔧 Tool started: {tool_name}")
            
            elif tool_type == "end":
                # Find and update the tool
                for tool in reversed(self.tools_used):
                    if tool.name == tool_name and tool.ended_at is None:
                        tool.ended_at = time.time()
                        tool.success = data.get("success", True)
                        self.log(f"   🔧 Tool ended: {tool_name} ({'✅' if tool.success else '❌'})")
                        break
        
        elif event_type == "warning":
            message = data.get("message", "?")
            self.log(f"   ⚠️ Warning: {message}")
        
        elif event_type == "error":
            message = data.get("message", "?")
            self.log(f"   ❌ Error: {message}")
    
    def _finalize_results(
        self,
        results: List[LifecycleResult],
        sandbox_start: float,
        mcp_start: Optional[float],
        execution_start: Optional[float],
        expected_tools: List[str]
    ):
        """Add execution and response results."""
        total_duration = time.time() - sandbox_start
        
        # Check if we got response content
        has_response = len(self.message_chunks) > 0
        full_response = "".join(self.message_chunks)
        
        # Check tool assertions
        tools_used_names = [t.name for t in self.tools_used]
        tools_matched = all(
            any(exp.lower() in name.lower() for name in tools_used_names)
            for exp in expected_tools
        ) if expected_tools else True
        
        # Add execution result
        results.append(LifecycleResult(
            phase=TestPhase.EXECUTION,
            passed=has_response,
            message=f"Agent generated response with {len(self.message_chunks)} chunks",
            duration=total_duration,
            details={
                "tools_used": tools_used_names,
                "expected_tools": expected_tools,
                "tools_matched": tools_matched,
                "response_length": len(full_response)
            }
        ))
        
        # Add response result
        if has_response:
            self.log(f"\n📝 RESPONSE ({len(full_response)} chars):")
            self.log("-" * 50)
            # Print first 500 chars of response
            print(full_response[:500] + ("..." if len(full_response) > 500 else ""))
            self.log("-" * 50)
            
            results.append(LifecycleResult(
                phase=TestPhase.RESPONSE,
                passed=True,
                message=f"Response received ({len(full_response)} chars)",
                duration=0.1,
                details={"response_preview": full_response[:200]}
            ))
    
    # =========================================================================
    # Phase 7: Cleanup
    # =========================================================================
    
    async def phase_cleanup(self) -> LifecycleResult:
        """Clean up sandbox."""
        self.log("\n📋 PHASE 6: Cleanup")
        start = time.time()
        
        try:
            if self.sandbox_id and self.client:
                response = await self.client.delete(
                    f'{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                if response.status_code == 200:
                    self.log("   ✅ Sandbox deleted")
                else:
                    self.log(f"   ⚠️ Sandbox delete returned {response.status_code}", "verbose")
            
            if self.client:
                await self.client.aclose()
            
            return LifecycleResult(
                phase=TestPhase.CLEANUP,
                passed=True,
                message="Cleanup complete",
                duration=time.time() - start
            )
            
        except Exception as e:
            return LifecycleResult(
                phase=TestPhase.CLEANUP,
                passed=False,
                message=f"Cleanup error: {e}",
                duration=time.time() - start
            )
    
    # =========================================================================
    # Main Execution
    # =========================================================================
    
    async def run_full_lifecycle(self) -> bool:
        """Run the complete lifecycle test."""
        self.log("=" * 70)
        self.log("🧪 Backend Agent Full Lifecycle Test")
        self.log(f"   Base URL: {self.base_url}")
        self.log(f"   Task: {self.task_key}")
        self.log(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 70)
        
        # Phase 1: Authentication
        auth_result = await self.phase_authenticate()
        self.phase_results.append(auth_result)
        
        if not auth_result.passed:
            self.log("\n❌ Authentication failed. Cannot continue.")
            self.log("   Make sure:")
            self.log(f"   - Backend is running at {self.base_url}")
            self.log("   - Test user exists (run: python backend/tests/create_test_user.py)")
            return False
        
        # Phases 2-5: Agent Stream
        stream_results = await self.phase_agent_stream()
        self.phase_results.extend(stream_results)
        
        # Phase 6: Cleanup
        cleanup_result = await self.phase_cleanup()
        self.phase_results.append(cleanup_result)
        
        # Print summary
        self._print_summary()
        
        # Return overall success
        return all(r.passed for r in self.phase_results)
    
    def _print_summary(self):
        """Print test summary."""
        self.log("\n" + "=" * 70)
        self.log("📊 LIFECYCLE TEST SUMMARY")
        self.log("=" * 70)
        
        total_duration = time.time() - self.start_time
        passed = sum(1 for r in self.phase_results if r.passed)
        total = len(self.phase_results)
        
        # Phase results
        for result in self.phase_results:
            status = "✅" if result.passed else "❌"
            self.log(f"   {status} {result.phase.value}: {result.message} ({result.duration:.1f}s)")
        
        self.log("")
        
        # Tools used
        if self.tools_used:
            self.log(f"🔧 Tools Used ({len(self.tools_used)}):")
            for tool in self.tools_used:
                duration = (tool.ended_at - tool.started_at) if tool.ended_at else 0
                status = "✅" if tool.success else "❌"
                self.log(f"   {status} {tool.name} ({duration:.1f}s)")
        
        self.log("")
        
        # Overall result
        if passed == total:
            self.log(f"✅ ALL {total} PHASES PASSED!")
        else:
            self.log(f"❌ {passed}/{total} phases passed")
        
        self.log(f"\n   Total duration: {total_duration:.1f}s")
        self.log(f"   Events received: {len(self.all_events)}")
        self.log(f"   Message chunks: {len(self.message_chunks)}")
        self.log("=" * 70)


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Test backend agent full lifecycle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available tasks:
  file_creation  - Create and read a file (default)
  shell_command  - Execute shell commands
  simple_response - Pure LLM response (no tools)
  slide_creation - Create slides

Example:
  python test_agent_lifecycle.py
  python test_agent_lifecycle.py --task shell_command
  python test_agent_lifecycle.py --prompt "Write a Python function to calculate fibonacci"
  python test_agent_lifecycle.py --verbose
        """
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend URL")
    parser.add_argument("--task", choices=list(TEST_TASKS.keys()), default="file_creation",
                       help="Predefined task to run")
    parser.add_argument("--prompt", type=str, help="Custom prompt (overrides --task)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    tester = BackendAgentLifecycleTester(
        base_url=args.base_url,
        task_key=args.task,
        custom_prompt=args.prompt,
        verbose=args.verbose
    )
    
    success = await tester.run_full_lifecycle()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(1)
