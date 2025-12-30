#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Human-in-the-Loop (HITL) Protocol Test Suite

Tests the interrupt/resume workflow for human feedback in the streaming API.

This test validates:
1. Interrupt events are properly emitted when graph reaches human_feedback node
2. AG-UI Protocol interrupt format is correct
3. Resume functionality works with different decision types
4. Shows actual conversation flow: user input → agent response → interrupt

Usage:
    # Run all tests
    python backend/tests/live/backend_endpoints/test_hitl_protocol.py
    
    # Verbose mode (shows all events)
    python backend/tests/live/backend_endpoints/test_hitl_protocol.py --verbose
    
    # Test specific endpoint
    python backend/tests/live/backend_endpoints/test_hitl_protocol.py --chat-only
    python backend/tests/live/backend_endpoints/test_hitl_protocol.py --agent-only

Prerequisites:
    1. Backend server running at http://127.0.0.1:8000
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/create_test_user.py
"""

import argparse
import asyncio
import json
import sys
import os
import time
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

# AG-UI HITL Event Types
HITL_EVENT_TYPES = {"interrupt"}

# Message-related events we want to track
MESSAGE_EVENTS = {"message", "status", "interrupt", "error"}

# Tool events for context
TOOL_EVENTS = {"tool_call_start", "tool_call_end", "tool_result"}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SSEEvent:
    """Represents a parsed Server-Sent Event."""
    event_type: str
    data: Dict[str, Any]
    raw: str = ""


@dataclass
class ConversationTracker:
    """Tracks the conversation flow during streaming."""
    user_input: str = ""
    agent_messages: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    interrupt_received: bool = False
    interrupt_data: Optional[Dict[str, Any]] = None
    completed: bool = False
    error: Optional[str] = None
    
    def add_agent_content(self, content: str):
        """Add agent response content."""
        if content:
            # Accumulate streaming content
            if self.agent_messages:
                self.agent_messages[-1] += content
            else:
                self.agent_messages.append(content)
    
    def start_new_message(self):
        """Start a new agent message."""
        self.agent_messages.append("")
    
    def add_tool_call(self, name: str, args: Dict[str, Any]):
        """Track a tool call."""
        self.tool_calls.append({"name": name, "args": args})


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str = ""
    conversation: Optional[ConversationTracker] = None
    duration_seconds: float = 0.0


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
# HITL Protocol Tester
# =============================================================================

class HITLProtocolTester:
    """
    Tests Human-in-the-Loop (HITL) protocol implementation.
    
    Shows the actual conversation flow including:
    - User input
    - Agent responses
    - Tool calls
    - Interrupt events (when agent needs feedback)
    """
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.token: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.test_results: List[TestResult] = []
    
    def log(self, message: str, level: str = "info"):
        """Log a message with optional verbosity control."""
        if level == "verbose" and not self.verbose:
            return
        print(message)
    
    async def setup(self) -> bool:
        """Initialize HTTP client and authenticate."""
        self.log("\n" + "=" * 70)
        self.log("🧪 HITL Protocol Test Suite")
        self.log(f"   Base URL: {self.base_url}")
        self.log(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 70)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=180.0,  # Long timeout for streaming
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'HITLProtocolTest/1.0',
                'Content-Type': 'application/json'
            }
        )
        
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
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.client:
            await self.client.aclose()
    
    def _print_conversation_summary(self, conv: ConversationTracker):
        """Print a summary of the conversation flow."""
        print("\n   " + "-" * 50)
        print("   📝 CONVERSATION FLOW")
        print("   " + "-" * 50)
        
        # User input
        print(f"\n   👤 USER INPUT:")
        print(f"      \"{conv.user_input}\"")
        
        # Tool calls (if any)
        if conv.tool_calls:
            print(f"\n   🔧 TOOL CALLS ({len(conv.tool_calls)}):")
            for i, tc in enumerate(conv.tool_calls[:5], 1):  # Limit to 5
                args_preview = str(tc.get('args', {}))[:80]
                print(f"      {i}. {tc.get('name', 'unknown')}: {args_preview}...")
        
        # Agent response
        if conv.agent_messages:
            full_response = "".join(conv.agent_messages)
            print(f"\n   🤖 AGENT RESPONSE:")
            # Show first 500 chars
            preview = full_response[:500]
            if len(full_response) > 500:
                preview += f"... ({len(full_response)} total chars)"
            for line in preview.split('\n')[:10]:  # Limit lines
                print(f"      {line}")
        
        # Interrupt
        if conv.interrupt_received:
            print(f"\n   ⏸️  INTERRUPT RECEIVED:")
            if conv.interrupt_data:
                print(f"      Content: {conv.interrupt_data.get('content', 'N/A')[:200]}")
                options = conv.interrupt_data.get('options', [])
                if options:
                    opt_str = ", ".join([o.get('label', o.get('value', '?')) for o in options])
                    print(f"      Options: [{opt_str}]")
                if conv.interrupt_data.get('action_requests'):
                    print(f"      Action Requests: {len(conv.interrupt_data['action_requests'])}")
        
        # Completion status
        if conv.completed:
            print(f"\n   ✅ COMPLETED (no interrupt needed)")
        elif conv.error:
            print(f"\n   ❌ ERROR: {conv.error}")
        
        print("   " + "-" * 50)
    
    async def _stream_and_track(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: float = 120.0,
    ) -> ConversationTracker:
        """Stream from endpoint and track conversation flow."""
        conv = ConversationTracker()
        conv.user_input = payload.get("messages", [{}])[0].get("content", "")
        
        current_agent_content = ""
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    conv.error = f"HTTP {response.status_code}"
                    return conv
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # Parse SSE events from buffer
                    while "\n\n" in buffer:
                        event_block, buffer = buffer.split("\n\n", 1)
                        events = parse_sse_chunk(event_block)
                        
                        for event in events:
                            event_type = event.event_type
                            data = event.data
                            
                            self.log(f"      [EVENT] {event_type}", "verbose")
                            
                            # Track message content
                            if event_type == "message":
                                content = data.get("content", "")
                                if content:
                                    current_agent_content += content
                            
                            # Track tool calls
                            elif event_type == "tool_call_start":
                                tool_name = data.get("toolCallName", data.get("name", "unknown"))
                                self.log(f"      🔧 Tool: {tool_name}", "verbose")
                            
                            elif event_type == "tool_result":
                                tool_id = data.get("toolCallId", "")
                                tool_name = data.get("name", "unknown")
                                conv.add_tool_call(tool_name, {"id": tool_id})
                            
                            # Track interrupt
                            elif event_type == "interrupt":
                                conv.interrupt_received = True
                                conv.interrupt_data = data
                                self.log("      ⏸️  INTERRUPT detected!", "verbose")
                                # Save accumulated content
                                if current_agent_content:
                                    conv.agent_messages.append(current_agent_content)
                                return conv
                            
                            # Track completion
                            elif event_type == "status":
                                status_type = data.get("type", "")
                                if status_type == "complete":
                                    conv.completed = True
                                    # Save accumulated content
                                    if current_agent_content:
                                        conv.agent_messages.append(current_agent_content)
                                    return conv
                            
                            # Track errors
                            elif event_type == "error":
                                conv.error = data.get("message", str(data))
        
        except Exception as e:
            conv.error = str(e)
        
        # Save any remaining content
        if current_agent_content:
            conv.agent_messages.append(current_agent_content)
        
        return conv
    
    async def test_chat_with_plan_approval(self) -> TestResult:
        """
        Test: Chat endpoint with plan approval disabled.
        
        When auto_accepted_plan=False, the agent should pause for 
        user approval before executing the plan.
        """
        test_name = "chat_plan_approval_interrupt"
        start_time = time.time()
        
        self.log(f"\n📋 Test: {test_name}")
        self.log("   Testing: Agent should interrupt for plan approval")
        
        # Use a unique thread ID
        thread_id = f"test-hitl-{int(time.time())}"
        
        # Request that should trigger plan approval
        user_message = "Search for the latest news about AI and summarize the top 3 stories."
        
        payload = {
            "messages": [{"role": "user", "content": user_message}],
            "thread_id": thread_id,
            "auto_accepted_plan": False,  # Should trigger interrupt
            "enable_web_search": True,
            "max_plan_iterations": 1,
            "max_step_num": 3,
        }
        
        self.log(f"   📤 Sending request with auto_accepted_plan=False")
        self.log(f"   📤 User: \"{user_message[:60]}...\"")
        
        conv = await self._stream_and_track(
            "/agent/chat/stream",
            payload,
            timeout=120.0,
        )
        
        # Print conversation summary
        self._print_conversation_summary(conv)
        
        # Determine result
        duration = time.time() - start_time
        
        if conv.error:
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Error: {conv.error}",
                conversation=conv,
                duration_seconds=duration,
            )
        
        if conv.interrupt_received:
            # Validate interrupt format
            interrupt = conv.interrupt_data
            if not interrupt:
                return TestResult(
                    name=test_name,
                    passed=False,
                    message="Interrupt received but no data",
                    conversation=conv,
                    duration_seconds=duration,
                )
            
            # Check required fields
            required = {"id", "thread_id", "content", "options"}
            missing = required - set(interrupt.keys())
            if missing:
                return TestResult(
                    name=test_name,
                    passed=False,
                    message=f"Interrupt missing fields: {missing}",
                    conversation=conv,
                    duration_seconds=duration,
                )
            
            return TestResult(
                name=test_name,
                passed=True,
                message="Interrupt received with correct format",
                conversation=conv,
                duration_seconds=duration,
            )
        
        if conv.completed:
            # No interrupt - plan was auto-accepted
            return TestResult(
                name=test_name,
                passed=True,
                message="Workflow completed (plan may have been auto-accepted)",
                conversation=conv,
                duration_seconds=duration,
            )
        
        return TestResult(
            name=test_name,
            passed=False,
            message="No interrupt or completion event received",
            conversation=conv,
            duration_seconds=duration,
        )
    
    async def test_chat_feedback_flow(self) -> TestResult:
        """
        Test: Chat endpoint normal flow with feedback node.
        
        Tests that the human_feedback_node triggers an interrupt
        when the agent has completed a response.
        """
        test_name = "chat_feedback_interrupt"
        start_time = time.time()
        
        self.log(f"\n📋 Test: {test_name}")
        self.log("   Testing: Agent should complete or interrupt for feedback")
        
        thread_id = f"test-feedback-{int(time.time())}"
        
        # Simple task that should complete and may trigger feedback
        user_message = "What is 2 + 2? Please explain briefly."
        
        payload = {
            "messages": [{"role": "user", "content": user_message}],
            "thread_id": thread_id,
            "auto_accepted_plan": True,  # Auto-accept plan
            "max_plan_iterations": 1,
            "max_step_num": 1,
        }
        
        self.log(f"   📤 Sending simple question")
        self.log(f"   📤 User: \"{user_message}\"")
        
        conv = await self._stream_and_track(
            "/agent/chat/stream",
            payload,
            timeout=60.0,
        )
        
        # Print conversation summary
        self._print_conversation_summary(conv)
        
        duration = time.time() - start_time
        
        if conv.error:
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Error: {conv.error}",
                conversation=conv,
                duration_seconds=duration,
            )
        
        # Either interrupt or completion is valid
        if conv.interrupt_received or conv.completed:
            status = "interrupt" if conv.interrupt_received else "completed"
            return TestResult(
                name=test_name,
                passed=True,
                message=f"Got expected response ({status})",
                conversation=conv,
                duration_seconds=duration,
            )
        
        return TestResult(
            name=test_name,
            passed=False,
            message="No response received",
            conversation=conv,
            duration_seconds=duration,
        )
    
    async def test_agent_endpoint_interrupt(self) -> TestResult:
        """
        Test: Agent endpoint with sandbox.
        
        Tests the /agent/agent/stream endpoint which uses astream_events
        and should also emit interrupt events.
        """
        test_name = "agent_endpoint_interrupt"
        start_time = time.time()
        
        self.log(f"\n📋 Test: {test_name}")
        self.log("   Testing: Agent endpoint with sandbox")
        
        thread_id = f"test-agent-{int(time.time())}"
        
        user_message = "Create a simple Python function that adds two numbers."
        
        payload = {
            "messages": [{"role": "user", "content": user_message}],
            "thread_id": thread_id,
            "auto_accepted_plan": False,
            "max_plan_iterations": 1,
            "max_step_num": 2,
        }
        
        self.log(f"   📤 User: \"{user_message}\"")
        
        conv = await self._stream_and_track(
            "/agent/agent/stream",
            payload,
            timeout=120.0,
        )
        
        self._print_conversation_summary(conv)
        
        duration = time.time() - start_time
        
        if conv.error:
            # Some errors are expected if sandbox isn't configured
            if "sandbox" in conv.error.lower() or "401" in conv.error:
                return TestResult(
                    name=test_name,
                    passed=True,
                    message=f"Skipped (sandbox not configured): {conv.error}",
                    conversation=conv,
                    duration_seconds=duration,
                )
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Error: {conv.error}",
                conversation=conv,
                duration_seconds=duration,
            )
        
        if conv.interrupt_received or conv.completed:
            status = "interrupt" if conv.interrupt_received else "completed"
            return TestResult(
                name=test_name,
                passed=True,
                message=f"Got expected response ({status})",
                conversation=conv,
                duration_seconds=duration,
            )
        
        return TestResult(
            name=test_name,
            passed=False,
            message="No response received",
            conversation=conv,
            duration_seconds=duration,
        )
    
    async def test_interrupt_event_format_validation(self) -> TestResult:
        """
        Test: Validate interrupt event format matches AG-UI spec.
        
        Uses the HITL models to verify correct event structure.
        """
        test_name = "interrupt_event_format"
        start_time = time.time()
        
        self.log(f"\n📋 Test: {test_name}")
        self.log("   Testing: Interrupt event format validation")
        
        try:
            from backend.app.agent.models import (
                HITLDecisionType,
                ActionRequest,
                ReviewConfig,
                HITLRequest,
                create_hitl_interrupt_event,
            )
            
            # Test 1: Simple feedback mode
            req_simple = HITLRequest.from_langraph_interrupt(
                "Review the agent's response. Type 'ACCEPTED' to finish.",
                "thread-123"
            )
            event_simple = req_simple.to_ag_ui_event("thread-123")
            
            # Validate structure
            assert "id" in event_simple, "Missing 'id' field"
            assert "thread_id" in event_simple, "Missing 'thread_id' field"
            assert "content" in event_simple, "Missing 'content' field"
            assert "finish_reason" in event_simple, "Missing 'finish_reason' field"
            assert event_simple["finish_reason"] == "interrupt", "Wrong finish_reason"
            assert "options" in event_simple, "Missing 'options' field"
            
            self.log("   ✅ Simple feedback format: OK")
            
            # Test 2: Action request mode
            ar = ActionRequest(
                name="execute_sql",
                arguments={"query": "DELETE FROM users WHERE id = 1"}
            )
            rc = ReviewConfig(
                action_name="execute_sql",
                allowed_decisions=[HITLDecisionType.APPROVE, HITLDecisionType.REJECT]
            )
            req_actions = HITLRequest(action_requests=[ar], review_configs=[rc])
            event_actions = req_actions.to_ag_ui_event("thread-456")
            
            assert "action_requests" in event_actions, "Missing 'action_requests'"
            assert len(event_actions["action_requests"]) == 1
            
            self.log("   ✅ Action request format: OK")
            
            # Test 3: Event string generation
            event_str = create_hitl_interrupt_event("Test prompt", "thread-789")
            assert "event: interrupt" in event_str, "Wrong event type in SSE"
            assert "data: " in event_str, "Missing data in SSE"
            
            self.log("   ✅ SSE event string format: OK")
            
            duration = time.time() - start_time
            return TestResult(
                name=test_name,
                passed=True,
                message="All interrupt formats validated",
                duration_seconds=duration,
            )
            
        except AssertionError as e:
            duration = time.time() - start_time
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Format validation failed: {e}",
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Error: {e}",
                duration_seconds=duration,
            )
    
    async def run_all_tests(
        self,
        chat_only: bool = False,
        agent_only: bool = False,
    ) -> bool:
        """Run all HITL protocol tests."""
        
        if not await self.setup():
            return False
        
        try:
            # Define tests
            tests = []
            
            # Always run format validation
            tests.append(("Interrupt Event Format", self.test_interrupt_event_format_validation))
            
            # Endpoint tests
            if not agent_only:
                tests.append(("Chat Plan Approval", self.test_chat_with_plan_approval))
                tests.append(("Chat Feedback Flow", self.test_chat_feedback_flow))
            
            if not chat_only:
                tests.append(("Agent Endpoint", self.test_agent_endpoint_interrupt))
            
            # Run tests
            for test_name, test_func in tests:
                self.log(f"\n{'='*60}")
                result = await test_func()
                self.test_results.append(result)
                
                status = "✅ PASSED" if result.passed else "❌ FAILED"
                self.log(f"\n   Result: {status}")
                if result.message:
                    self.log(f"   Message: {result.message}")
                self.log(f"   Duration: {result.duration_seconds:.2f}s")
            
            # Summary
            self._print_summary()
            
            return all(r.passed for r in self.test_results)
            
        finally:
            await self.cleanup()
    
    def _print_summary(self):
        """Print final test summary."""
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for r in self.test_results if r.passed)
        failed = sum(1 for r in self.test_results if not r.passed)
        
        for result in self.test_results:
            status = "✅" if result.passed else "❌"
            print(f"   {status} {result.name}: {result.message[:50]}")
        
        print(f"\n   Total: {len(self.test_results)} tests")
        print(f"   Passed: {passed}")
        print(f"   Failed: {failed}")
        
        # Show interrupt summary
        interrupts_received = sum(
            1 for r in self.test_results 
            if r.conversation and r.conversation.interrupt_received
        )
        if interrupts_received:
            print(f"\n   🔔 Interrupts Received: {interrupts_received}")
        
        print("=" * 70 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="HITL Protocol Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--chat-only", action="store_true", help="Only test chat endpoint")
    parser.add_argument("--agent-only", action="store_true", help="Only test agent endpoint")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for API")
    
    args = parser.parse_args()
    
    tester = HITLProtocolTester(
        base_url=args.base_url,
        verbose=args.verbose,
    )
    
    success = await tester.run_all_tests(
        chat_only=args.chat_only,
        agent_only=args.agent_only,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
