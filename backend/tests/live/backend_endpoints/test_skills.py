#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Skills Loading Test Script

This script tests that skills are properly loaded from the sandbox when using
the /agent/agent/stream endpoint. It verifies:

1. Sandbox is created with skills injected (via inject-skills.sh)
2. Agent endpoint loads skills from /workspace/.deepagents/skills/
3. SSE event "skills_loaded" is emitted with skill count and names
4. Agent can see and potentially use the loaded skills

Prerequisites:
    1. Backend server running at http://localhost:8000
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/live/create_test_user.py
    3. E2B_API_KEY configured in backend/.env
    4. E2B template rebuilt with skills baked in

Usage:
    python backend/tests/live/backend_endpoints/test_skills.py
    python backend/tests/live/backend_endpoints/test_skills.py --verbose
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

DEFAULT_BASE_URL = "http://127.0.0.1:8001"
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
    skill_count: int = 0
    skill_names: List[str] = field(default_factory=list)


# =============================================================================
# SSE Parser
# =============================================================================

def parse_sse_line(line: str) -> Optional[Tuple[str, str]]:
    """Parse a single SSE line."""
    line = line.strip()
    if not line or line.startswith(':'):
        return None
    
    if ':' in line:
        field, value = line.split(':', 1)
        return field.strip(), value.strip()
    return None


def parse_sse_chunk(chunk: str) -> List[SSEEvent]:
    """Parse an SSE chunk which may contain multiple events."""
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
# Skills Test Class
# =============================================================================

class SkillsLoadingTester:
    """
    Tests that skills are properly loaded from sandbox via /agent/agent/stream.
    
    This test:
    1. Authenticates with the backend
    2. Calls /agent/agent/stream with module=general
    3. Watches for the "skills_loaded" SSE event
    4. Verifies skills were loaded from sandbox
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
        self.log("🎯 Skills Loading Test")
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
                'User-Agent': 'SkillsLoadingTest/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        # Authenticate
        self.log("\n📋 Step 1: Authenticating...")
        if not await self._login():
            self.log("   ❌ Login failed. Make sure:")
            self.log(f"      - Backend is running at {self.base_url}")
            self.log("      - Test user exists (run: python backend/tests/live/create_test_user.py)")
            return False
        
        self.log("   ✅ Got JWT token")
        return True
    
    async def _login(self) -> bool:
        """Authenticate and get JWT token."""
        try:
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
    
    async def test_skills_loading(self) -> TestResult:
        """
        Test that skills are loaded from sandbox.
        
        Expected flow:
        1. status:processing
        2. status:sandbox_ready
        3. status:mcp_check
        4. status:skills_loaded  <-- THIS IS WHAT WE'RE TESTING
        5. status:agent_start
        6. message:chunk
        7. status:complete
        """
        self.log("\n📋 Step 2: Testing skills loading via /agent/agent/stream...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        skills_loaded_event = None
        skill_count = 0
        skill_names = []
        
        try:
            # Prepare request - using 'general' module (default skills)
            request_body = {
                "module": "general",
                "messages": [
                    {"role": "user", "content": "List the skills you have available. Just list them briefly."}
                ],
                "thread_id": f"skills-test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": False,
                "enable_web_search": False,
                "enable_deep_thinking": False,
                "max_plan_iterations": 1,
                "max_step_num": 2
            }
            
            self.log(f"   Request body:", "verbose")
            self.log(f"   {json.dumps(request_body, indent=2)}", "verbose")
            
            # Stream response and watch for skills_loaded event
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="skills_loading",
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
                            
                            # Capture sandbox_id for cleanup
                            if event.event_type == "status":
                                event_subtype = event.data.get("type", "")
                                
                                if event_subtype == "sandbox_ready":
                                    self.sandbox_id = event.data.get("sandbox_id")
                                
                                # THIS IS THE KEY EVENT WE'RE TESTING
                                if event_subtype == "skills_loaded":
                                    skills_loaded_event = event
                                    skill_count = event.data.get("skill_count", 0)
                                    skill_names = event.data.get("skill_names", [])
                                    self.log(f"   ✅ SKILLS LOADED: {skill_count} skills")
                                    for name in skill_names[:5]:
                                        self.log(f"      - {name}")
                                    if len(skill_names) > 5:
                                        self.log(f"      ... and {len(skill_names) - 5} more")
            
            # Validate results
            return self._validate_skills_result(
                events, skills_loaded_event, skill_count, skill_names, start_time
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="skills_loading",
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
            elif data_type == "skills_loaded":
                # Handled specially above
                pass
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
            self.log(f"   💬 Received message chunk: '{content}...'", "verbose")
        
        elif event_type == "warning":
            message = event.data.get("message", "?")
            self.log(f"   ⚠️ Warning: {message}")
        
        elif event_type == "error":
            message = event.data.get("message", "?")
            self.log(f"   ❌ Error: {message}")
    
    def _validate_skills_result(
        self,
        events: List[SSEEvent],
        skills_loaded_event: Optional[SSEEvent],
        skill_count: int,
        skill_names: List[str],
        start_time: datetime
    ) -> TestResult:
        """Validate that skills were loaded correctly."""
        duration = (datetime.now() - start_time).total_seconds()
        
        # Check for errors first
        has_error = any(e.event_type == "error" for e in events)
        if has_error:
            error_msgs = [e.data.get("message", "?") for e in events if e.event_type == "error"]
            return TestResult(
                name="skills_loading",
                passed=False,
                message=f"Received error event(s): {error_msgs}",
                events=events,
                duration_seconds=duration
            )
        
        # Check if skills_loaded event was received
        if skills_loaded_event is None:
            return TestResult(
                name="skills_loading",
                passed=False,
                message="Did not receive 'skills_loaded' SSE event. Skills may not be injected in sandbox.",
                events=events,
                duration_seconds=duration,
                skill_count=0,
                skill_names=[]
            )
        
        # Check skill count
        if skill_count == 0:
            return TestResult(
                name="skills_loading",
                passed=False,
                message="skills_loaded event received but skill_count is 0",
                events=events,
                duration_seconds=duration,
                skill_count=0,
                skill_names=[]
            )
        
        # Success!
        return TestResult(
            name="skills_loading",
            passed=True,
            message=f"Successfully loaded {skill_count} skills from sandbox",
            events=events,
            duration_seconds=duration,
            skill_count=skill_count,
            skill_names=skill_names
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
        
        # Print skill details
        for result in self.test_results:
            if result.skill_count > 0:
                self.log(f"\n📦 Skills Loaded: {result.skill_count}")
                for name in result.skill_names[:10]:
                    self.log(f"   - {name}")
                if len(result.skill_names) > 10:
                    self.log(f"   ... and {len(result.skill_names) - 10} more")
        
        total_duration = sum(r.duration_seconds for r in self.test_results)
        self.log(f"\n   Total duration: {total_duration:.1f}s")
        self.log("=" * 70)


# =============================================================================
# Main
# =============================================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Test skills loading from sandbox via /agent/agent/stream",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script tests that skills are properly injected into the sandbox
and loaded by the agent endpoint.

Example:
    python test_skills.py
    python test_skills.py --verbose
    python test_skills.py --base-url http://localhost:8001
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
    tester = SkillsLoadingTester(
        base_url=args.base_url,
        verbose=args.verbose
    )
    
    try:
        # Setup and authenticate
        if not await tester.setup():
            sys.exit(1)
        
        # Run skills loading test
        result = await tester.test_skills_loading()
        tester.test_results.append(result)
        
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
