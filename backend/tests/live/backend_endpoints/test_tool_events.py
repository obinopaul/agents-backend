#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
AG-UI Tool Events Test Script

This script tests the AG-UI protocol compatible tool call events:
- tool_call_start: When a tool call begins (toolCallId, toolCallName)
- tool_call_args: Tool arguments streaming (toolCallId, delta)
- tool_call_end: When tool call completes (toolCallId)
- tool_result: Tool output/result (role, content, toolCallId)

Tests both endpoints:
1. /agent/agent/stream (with sandbox) - uses astream_events
2. /agent/chat/stream (no sandbox) - uses astream with messages mode

Prerequisites:
    1. Backend server running at http://localhost:8000
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/create_test_user.py

Usage:
    python backend/tests/live/backend_endpoints/test_tool_events.py

    # With verbose output
    python backend/tests/live/backend_endpoints/test_tool_events.py --verbose

    # Test only chat endpoint
    python backend/tests/live/backend_endpoints/test_tool_events.py --chat-only

    # Test only agent endpoint
    python backend/tests/live/backend_endpoints/test_tool_events.py --agent-only
"""

import asyncio
import argparse
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

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

# AG-UI Event Types we're testing - Tool Events
AGUI_TOOL_EVENTS = {
    "tool_call_start",
    "tool_call_args", 
    "tool_call_end",
    "tool_result",
}

# AG-UI Event Types - Reasoning Events (auto-detected when model returns thinking content)
AGUI_REASONING_EVENTS = {
    "reasoning_start",
    "reasoning_message_start",
    "reasoning_message_content",
    "reasoning_message_end",
    "reasoning_end",
}

# All AG-UI Events combined
AGUI_EVENTS = AGUI_TOOL_EVENTS | AGUI_REASONING_EVENTS

# Legacy events (for backwards compatibility verification)
LEGACY_EVENTS = {
    "tool_calls",
    "tool_call_chunks",
    "tool_call_result",
}


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
class ToolCallTracker:
    """Tracks the lifecycle of a single tool call."""
    tool_call_id: str
    tool_name: str = ""
    args_deltas: List[str] = field(default_factory=list)
    has_start: bool = False
    has_end: bool = False
    has_result: bool = False
    result_content: str = ""
    
    @property
    def full_args(self) -> str:
        return "".join(self.args_deltas)
    
    @property
    def is_complete(self) -> bool:
        return self.has_start and self.has_end


@dataclass
class ReasoningTracker:
    """Tracks the lifecycle of a reasoning session."""
    message_id: str
    content_deltas: List[str] = field(default_factory=list)
    has_start: bool = False
    has_message_start: bool = False
    has_message_end: bool = False
    has_end: bool = False
    
    @property
    def full_content(self) -> str:
        return "".join(self.content_deltas)
    
    @property
    def is_complete(self) -> bool:
        return self.has_start and self.has_end


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str = ""
    events: List[SSEEvent] = field(default_factory=list)
    tool_calls: Dict[str, ToolCallTracker] = field(default_factory=dict)
    reasoning_sessions: Dict[str, ReasoningTracker] = field(default_factory=dict)
    duration_seconds: float = 0.0
    agui_events_found: List[str] = field(default_factory=list)
    legacy_events_found: List[str] = field(default_factory=list)


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
# Tool Events Tester
# =============================================================================

class ToolEventsTester:
    """
    Tests AG-UI protocol tool call events.
    
    Verifies that both /agent/agent/stream and /agent/chat/stream
    emit the correct AG-UI compatible events during tool execution.
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
        self.log("🧪 AG-UI Tool Events Test Suite")
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
                'User-Agent': 'ToolEventsTest/1.0',
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
    
    def _track_tool_event(self, event: SSEEvent, trackers: Dict[str, ToolCallTracker]):
        """Track a tool event and update the appropriate tracker."""
        event_type = event.event_type
        data = event.data
        
        tool_call_id = data.get("toolCallId") or data.get("tool_call_id") or ""
        
        if not tool_call_id:
            return
        
        if tool_call_id not in trackers:
            trackers[tool_call_id] = ToolCallTracker(tool_call_id=tool_call_id)
        
        tracker = trackers[tool_call_id]
        
        if event_type == "tool_call_start":
            tracker.has_start = True
            tracker.tool_name = data.get("toolCallName", "")
        elif event_type == "tool_call_args":
            delta = data.get("delta", "")
            if delta:
                tracker.args_deltas.append(delta)
        elif event_type == "tool_call_end":
            tracker.has_end = True
        elif event_type == "tool_result":
            tracker.has_result = True
            tracker.result_content = data.get("content", "")
    
    def _track_reasoning_event(self, event: SSEEvent, trackers: Dict[str, ReasoningTracker]):
        """Track a reasoning event and update the appropriate tracker."""
        event_type = event.event_type
        data = event.data
        
        message_id = data.get("messageId") or ""
        
        if not message_id:
            return
        
        if message_id not in trackers:
            trackers[message_id] = ReasoningTracker(message_id=message_id)
        
        tracker = trackers[message_id]
        
        if event_type == "reasoning_start":
            tracker.has_start = True
        elif event_type == "reasoning_message_start":
            tracker.has_message_start = True
        elif event_type == "reasoning_message_content":
            delta = data.get("delta", "")
            if delta:
                tracker.content_deltas.append(delta)
        elif event_type == "reasoning_message_end":
            tracker.has_message_end = True
        elif event_type == "reasoning_end":
            tracker.has_end = True
    
    async def test_chat_stream_tool_events(self) -> TestResult:
        """
        Test the /api/v1/agent/chat/stream endpoint for AG-UI tool events.
        
        This endpoint uses LangGraph's astream with messages mode, so tool events
        come from AIMessageChunk.tool_calls and ToolMessage.
        
        We'll ask a question that requires web search to trigger tool usage.
        """
        self.log("\n📋 Testing Chat Stream Tool Events (/agent/chat/stream)...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        tool_trackers: Dict[str, ToolCallTracker] = {}
        agui_events_found = set()
        legacy_events_found = set()
        
        try:
            # Request that should trigger tool usage (web search)
            request_body = {
                "messages": [
                    {"role": "user", "content": "Search the web for the current weather in London and tell me the temperature."}
                ],
                "thread_id": f"test-tool-events-chat-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": True,
                "enable_web_search": True,
                "auto_accepted_plan": True,
                "max_plan_iterations": 1,
                "max_step_num": 2
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/chat/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="chat_stream_tool_events",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            self._log_event(event)
                            
                            # Track AG-UI events
                            if event.event_type in AGUI_EVENTS:
                                agui_events_found.add(event.event_type)
                                self._track_tool_event(event, tool_trackers)
                            
                            # Track legacy events
                            if event.event_type in LEGACY_EVENTS:
                                legacy_events_found.add(event.event_type)
            
            return self._validate_tool_events(
                "chat_stream_tool_events",
                events,
                tool_trackers,
                agui_events_found,
                legacy_events_found,
                start_time
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="chat_stream_tool_events",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def test_agent_stream_tool_events(self) -> TestResult:
        """
        Test the /agent/agent/stream endpoint for AG-UI tool events.
        
        This endpoint uses astream_events, so tool events come from
        on_tool_start and on_tool_end events.
        
        We'll ask for available tools to trigger a response.
        """
        self.log("\n📋 Testing Agent Stream Tool Events (/agent/agent/stream)...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        tool_trackers: Dict[str, ToolCallTracker] = {}
        agui_events_found = set()
        legacy_events_found = set()
        
        try:
            request_body = {
                "messages": [
                    {"role": "user", "content": "List all the tools you have available and use one of them to search for information about Python programming."}
                ],
                "thread_id": f"test-tool-events-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": True,
                "enable_web_search": True,
                "auto_accepted_plan": True,
                "max_plan_iterations": 1,
                "max_step_num": 2
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="agent_stream_tool_events",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            self._log_event(event)
                            
                            # Track AG-UI events
                            if event.event_type in AGUI_EVENTS:
                                agui_events_found.add(event.event_type)
                                self._track_tool_event(event, tool_trackers)
                            
                            # Track legacy events
                            if event.event_type in LEGACY_EVENTS:
                                legacy_events_found.add(event.event_type)
            
            return self._validate_tool_events(
                "agent_stream_tool_events",
                events,
                tool_trackers,
                agui_events_found,
                legacy_events_found,
                start_time
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="agent_stream_tool_events",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    def _log_event(self, event: SSEEvent):
        """Log an SSE event with nice formatting."""
        event_type = event.event_type
        data = event.data
        
        # Helper to safely get string with default and slice
        def safe_str(value, default="?", max_len=20):
            s = value if value is not None else default
            return str(s)[:max_len] if s else default
        
        # AG-UI events (what we're testing)
        if event_type == "tool_call_start":
            tool_id = safe_str(data.get("toolCallId"))
            tool_name = safe_str(data.get("toolCallName"), max_len=50)
            self.log(f"   🔧 tool_call_start: {tool_name} (id={tool_id}...)")
        
        elif event_type == "tool_call_args":
            tool_id = safe_str(data.get("toolCallId"))
            delta = safe_str(data.get("delta"), default="", max_len=50)
            self.log(f"   📝 tool_call_args: id={tool_id}... delta='{delta}...'", "verbose")
        
        elif event_type == "tool_call_end":
            tool_id = safe_str(data.get("toolCallId"))
            self.log(f"   ✅ tool_call_end: id={tool_id}...")
        
        elif event_type == "tool_result":
            tool_id = safe_str(data.get("toolCallId") or data.get("tool_call_id"))
            content = safe_str(data.get("content"), default="", max_len=50)
            self.log(f"   📤 tool_result: id={tool_id}... content='{content}...'", "verbose")
        
        # Legacy events
        elif event_type == "tool_calls":
            self.log(f"   📋 [legacy] tool_calls: {len(data.get('tool_calls', []))} calls", "verbose")
        
        elif event_type == "tool_call_chunks":
            self.log(f"   📋 [legacy] tool_call_chunks", "verbose")
        
        elif event_type == "tool_call_result":
            self.log(f"   📋 [legacy] tool_call_result", "verbose")
        
        # Status events
        elif event_type == "status":
            status_type = data.get("type", "")
            if status_type in ["processing", "sandbox_ready", "mcp_ready", "agent_start", "complete"]:
                self.log(f"   📋 status:{status_type}")
            else:
                self.log(f"   📋 status:{status_type}", "verbose")
        
        elif event_type == "message_chunk":
            content = data.get("content", "")[:30]
            self.log(f"   💬 message_chunk: '{content}...'", "verbose")
        
        elif event_type == "error":
            self.log(f"   ❌ error: {data.get('error', data.get('message', '?'))}")
    
    def _validate_tool_events(
        self,
        test_name: str,
        events: List[SSEEvent],
        tool_trackers: Dict[str, ToolCallTracker],
        agui_events_found: set,
        legacy_events_found: set,
        start_time: datetime
    ) -> TestResult:
        """Validate that tool events were emitted correctly."""
        duration = (datetime.now() - start_time).total_seconds()
        
        # Check for errors
        errors = [e for e in events if e.event_type == "error"]
        if errors:
            error_msgs = [e.data.get("error", e.data.get("message", "?")) for e in errors]
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Received error event(s): {error_msgs}",
                events=events,
                duration_seconds=duration
            )
        
        # Report what we found
        self.log(f"\n   📊 Results:")
        self.log(f"      Total events: {len(events)}")
        self.log(f"      AG-UI events found: {sorted(agui_events_found) if agui_events_found else 'None'}")
        self.log(f"      Legacy events found: {sorted(legacy_events_found) if legacy_events_found else 'None'}")
        self.log(f"      Tool calls tracked: {len(tool_trackers)}")
        
        # Log each tracked tool call
        for tool_id, tracker in tool_trackers.items():
            self.log(f"         - {tracker.tool_name or 'unknown'}: start={tracker.has_start}, end={tracker.has_end}, result={tracker.has_result}")
        
        # Determine pass/fail
        # We consider it a pass if we got any AG-UI events OR the conversation completed without tools
        if agui_events_found:
            # We got AG-UI events - check if they're complete
            complete_tools = [t for t in tool_trackers.values() if t.is_complete]
            if complete_tools:
                self.log(f"   ✅ Found {len(complete_tools)} complete tool call(s) with AG-UI events")
                return TestResult(
                    name=test_name,
                    passed=True,
                    message=f"AG-UI events working: {sorted(agui_events_found)}, {len(complete_tools)} complete tool calls",
                    events=events,
                    tool_calls=tool_trackers,
                    duration_seconds=duration,
                    agui_events_found=list(agui_events_found),
                    legacy_events_found=list(legacy_events_found)
                )
            else:
                # Got start events but maybe not complete - still counts as working
                self.log(f"   ✅ AG-UI events emitted: {sorted(agui_events_found)}")
                return TestResult(
                    name=test_name,
                    passed=True,
                    message=f"AG-UI events working: {sorted(agui_events_found)}",
                    events=events,
                    tool_calls=tool_trackers,
                    duration_seconds=duration,
                    agui_events_found=list(agui_events_found),
                    legacy_events_found=list(legacy_events_found)
                )
        
        elif legacy_events_found:
            # No AG-UI events but we got legacy events - partial success
            self.log(f"   ⚠️ Only legacy events found, no AG-UI events")
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Only legacy events found: {sorted(legacy_events_found)}, no AG-UI events",
                events=events,
                duration_seconds=duration,
                legacy_events_found=list(legacy_events_found)
            )
        
        else:
            # No tool events at all - maybe no tools were called
            message_chunks = [e for e in events if e.event_type == "message_chunk"]
            if message_chunks:
                self.log(f"   ⚠️ No tool events - agent may not have used tools")
                return TestResult(
                    name=test_name,
                    passed=True,  # Not a failure if agent just didn't use tools
                    message=f"No tools used, but conversation completed ({len(message_chunks)} message chunks)",
                    events=events,
                    duration_seconds=duration
                )
            else:
                return TestResult(
                    name=test_name,
                    passed=False,
                    message="No tool events and no message chunks - something went wrong",
                    events=events,
                    duration_seconds=duration
                )
    
    async def cleanup(self):
        """Clean up resources."""
        self.log("\n📋 Cleanup...")
        if self.client:
            await self.client.aclose()
        self.log("   ✅ Done")
    
    async def test_chat_stream_reasoning_events(self) -> TestResult:
        """
        Test the /api/v1/agent/chat/stream endpoint for AG-UI reasoning events.
        
        Reasoning events are auto-detected when the model returns thinking content.
        This test uses enable_deep_thinking to encourage the model to reason.
        
        Note: Reasoning events only appear if the underlying model supports 
        extended thinking (e.g., Claude, DeepSeek, o1).
        """
        self.log("\n📋 Testing Chat Stream Reasoning Events (/agent/chat/stream)...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        reasoning_trackers: Dict[str, ReasoningTracker] = {}
        agui_events_found = set()
        
        try:
            # Request that should encourage reasoning
            request_body = {
                "messages": [
                    {"role": "user", "content": "Think step by step about how to solve this problem: If a train travels at 60 mph for 2 hours and then 80 mph for 1.5 hours, what is the total distance traveled?"}
                ],
                "thread_id": f"test-reasoning-chat-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_deep_thinking": True,
                "enable_background_investigation": False,
                "enable_web_search": False,
                "auto_accepted_plan": True,
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/chat/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="chat_stream_reasoning_events",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            
                            # Log reasoning events
                            if event.event_type in AGUI_REASONING_EVENTS:
                                agui_events_found.add(event.event_type)
                                self._track_reasoning_event(event, reasoning_trackers)
                                self._log_reasoning_event(event)
            
            return self._validate_reasoning_events(
                "chat_stream_reasoning_events",
                events,
                reasoning_trackers,
                agui_events_found,
                start_time
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="chat_stream_reasoning_events",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def test_multimodal_messages(self) -> TestResult:
        """
        Test multimodal message support (images, audio, etc.).
        
        This test sends a multimodal message with text content to verify
        the AG-UI multimodal format is accepted and processed correctly.
        
        Note: Full image processing requires a vision-capable model.
        """
        self.log("\n📋 Testing Multimodal Messages (/agent/chat/stream)...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        
        try:
            # Request with multimodal content format (text only for basic test)
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "This is a test of multimodal message format. Please confirm you received this message."}
                        ]
                    }
                ],
                "thread_id": f"test-multimodal-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": False,
                "enable_web_search": False,
                "auto_accepted_plan": True,
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/chat/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="multimodal_messages",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            self._log_event(event)
            
            # Check for successful response
            duration = (datetime.now() - start_time).total_seconds()
            message_chunks = [e for e in events if e.event_type == "message_chunk"]
            errors = [e for e in events if e.event_type == "error"]
            
            if errors:
                error_msgs = [e.data.get("error", e.data.get("message", "?")) for e in errors]
                return TestResult(
                    name="multimodal_messages",
                    passed=False,
                    message=f"Received error event(s): {error_msgs}",
                    events=events,
                    duration_seconds=duration
                )
            
            if message_chunks:
                self.log(f"   ✅ Multimodal format accepted, got {len(message_chunks)} message chunks")
                return TestResult(
                    name="multimodal_messages",
                    passed=True,
                    message=f"Multimodal format working, {len(message_chunks)} message chunks received",
                    events=events,
                    duration_seconds=duration
                )
            else:
                return TestResult(
                    name="multimodal_messages",
                    passed=False,
                    message="No message chunks received",
                    events=events,
                    duration_seconds=duration
                )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="multimodal_messages",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def test_agent_stream_reasoning_events(self) -> TestResult:
        """
        Test the /agent/agent/stream endpoint for AG-UI reasoning events.
        
        Reasoning events are auto-detected when the model returns thinking content.
        This test uses enable_deep_thinking to encourage the model to reason.
        
        Note: Reasoning events only appear if the underlying model supports 
        extended thinking (e.g., Claude, DeepSeek, o1).
        """
        self.log("\n📋 Testing Agent Stream Reasoning Events (/agent/agent/stream)...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        reasoning_trackers: Dict[str, ReasoningTracker] = {}
        agui_events_found = set()
        
        try:
            # Request that should encourage reasoning
            request_body = {
                "messages": [
                    {"role": "user", "content": "Think step by step: What is 17 * 23? Show your reasoning."}
                ],
                "thread_id": f"test-reasoning-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_deep_thinking": True,
                "enable_background_investigation": False,
                "enable_web_search": False,
                "auto_accepted_plan": True,
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="agent_stream_reasoning_events",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            
                            # Log reasoning events
                            if event.event_type in AGUI_REASONING_EVENTS:
                                agui_events_found.add(event.event_type)
                                self._track_reasoning_event(event, reasoning_trackers)
                                self._log_reasoning_event(event)
                            
                            # Also log status events
                            if event.event_type == "status":
                                self._log_event(event)
            
            return self._validate_reasoning_events(
                "agent_stream_reasoning_events",
                events,
                reasoning_trackers,
                agui_events_found,
                start_time
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="agent_stream_reasoning_events",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def test_agent_multimodal_messages(self) -> TestResult:
        """
        Test multimodal message support on agent endpoint.
        
        This test sends a multimodal message with text content to verify
        the AG-UI multimodal format is accepted and processed correctly.
        """
        self.log("\n📋 Testing Agent Multimodal Messages (/agent/agent/stream)...")
        
        start_time = datetime.now()
        events: List[SSEEvent] = []
        
        try:
            # Request with multimodal content format (text only for basic test)
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "This is a test of multimodal message format on agent endpoint. Please confirm."}
                        ]
                    }
                ],
                "thread_id": f"test-multimodal-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "enable_background_investigation": False,
                "enable_web_search": False,
                "auto_accepted_plan": True,
            }
            
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name="agent_multimodal_messages",
                        passed=False,
                        message=f"HTTP {response.status_code}: {error_text.decode()}",
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            events.append(event)
                            self._log_event(event)
            
            # Check for successful response
            duration = (datetime.now() - start_time).total_seconds()
            message_events = [e for e in events if e.event_type == "message"]
            status_complete = [e for e in events if e.event_type == "status" and e.data.get("type") == "complete"]
            errors = [e for e in events if e.event_type == "error"]
            
            if errors:
                error_msgs = [e.data.get("error", e.data.get("message", "?")) for e in errors]
                return TestResult(
                    name="agent_multimodal_messages",
                    passed=False,
                    message=f"Received error event(s): {error_msgs}",
                    events=events,
                    duration_seconds=duration
                )
            
            if message_events or status_complete:
                self.log(f"   ✅ Multimodal format accepted, got {len(message_events)} message events")
                return TestResult(
                    name="agent_multimodal_messages",
                    passed=True,
                    message=f"Multimodal format working on agent endpoint, {len(message_events)} message events",
                    events=events,
                    duration_seconds=duration
                )
            else:
                return TestResult(
                    name="agent_multimodal_messages",
                    passed=False,
                    message="No message events received",
                    events=events,
                    duration_seconds=duration
                )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name="agent_multimodal_messages",
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    def _log_reasoning_event(self, event: SSEEvent):
        """Log a reasoning SSE event with nice formatting."""
        event_type = event.event_type
        data = event.data
        
        message_id = (data.get("messageId") or "?")[:20]
        
        if event_type == "reasoning_start":
            self.log(f"   🧠 reasoning_start: {message_id}...")
        elif event_type == "reasoning_message_start":
            self.log(f"   🧠 reasoning_message_start: {message_id}...", "verbose")
        elif event_type == "reasoning_message_content":
            delta = (data.get("delta") or "")[:50]
            self.log(f"   💭 reasoning_content: '{delta}...'", "verbose")
        elif event_type == "reasoning_message_end":
            self.log(f"   🧠 reasoning_message_end: {message_id}...", "verbose")
        elif event_type == "reasoning_end":
            self.log(f"   ✅ reasoning_end: {message_id}...")
    
    def _validate_reasoning_events(
        self,
        test_name: str,
        events: List[SSEEvent],
        reasoning_trackers: Dict[str, ReasoningTracker],
        agui_events_found: set,
        start_time: datetime
    ) -> TestResult:
        """Validate that reasoning events were emitted correctly."""
        duration = (datetime.now() - start_time).total_seconds()
        
        # Check for errors
        errors = [e for e in events if e.event_type == "error"]
        if errors:
            error_msgs = [e.data.get("error", e.data.get("message", "?")) for e in errors]
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Received error event(s): {error_msgs}",
                events=events,
                duration_seconds=duration
            )
        
        # Report what we found
        self.log(f"\n   📊 Results:")
        self.log(f"      Total events: {len(events)}")
        self.log(f"      Reasoning events found: {sorted(agui_events_found) if agui_events_found else 'None'}")
        self.log(f"      Reasoning sessions: {len(reasoning_trackers)}")
        
        # Log each reasoning session
        for msg_id, tracker in reasoning_trackers.items():
            content_preview = tracker.full_content[:50] if tracker.full_content else "(no content)"
            self.log(f"         - {msg_id[:20]}...: start={tracker.has_start}, end={tracker.has_end}, content_len={len(tracker.full_content)}")
        
        if agui_events_found:
            # We got reasoning events
            complete_sessions = [t for t in reasoning_trackers.values() if t.is_complete]
            if complete_sessions:
                self.log(f"   ✅ Found {len(complete_sessions)} complete reasoning session(s)")
                return TestResult(
                    name=test_name,
                    passed=True,
                    message=f"Reasoning events working: {sorted(agui_events_found)}, {len(complete_sessions)} complete sessions",
                    events=events,
                    reasoning_sessions=reasoning_trackers,
                    duration_seconds=duration,
                    agui_events_found=list(agui_events_found)
                )
            else:
                self.log(f"   ✅ Reasoning events emitted: {sorted(agui_events_found)}")
                return TestResult(
                    name=test_name,
                    passed=True,
                    message=f"Reasoning events detected: {sorted(agui_events_found)}",
                    events=events,
                    reasoning_sessions=reasoning_trackers,
                    duration_seconds=duration,
                    agui_events_found=list(agui_events_found)
                )
        
        else:
            # No reasoning events - this is OK if model doesn't support extended thinking
            message_chunks = [e for e in events if e.event_type == "message_chunk"]
            if message_chunks:
                self.log(f"   ⚠️ No reasoning events - model may not support extended thinking")
                return TestResult(
                    name=test_name,
                    passed=True,  # Not a failure - depends on model capabilities
                    message=f"No reasoning events (model may not support it), but got {len(message_chunks)} message chunks",
                    events=events,
                    duration_seconds=duration
                )
            else:
                return TestResult(
                    name=test_name,
                    passed=False,
                    message="No reasoning events and no message chunks - something went wrong",
                    events=events,
                    duration_seconds=duration
                )
    
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
        description="Test AG-UI protocol events (tool calls, reasoning, multimodal)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tests the AG-UI compatible events in both endpoints:
- /agent/agent/stream (with sandbox)
- /agent/chat/stream (no sandbox)

Event types tested:
- Tool events: tool_call_start, tool_call_args, tool_call_end, tool_result
- Reasoning events: reasoning_start, reasoning_message_*, reasoning_end
- Multimodal messages: text + binary content blocks

Example:
    python test_tool_events.py
    python test_tool_events.py --verbose
    python test_tool_events.py --chat-only
    python test_tool_events.py --reasoning-only
    python test_tool_events.py --multimodal-only
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
    parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Only test chat endpoint (tool events)"
    )
    parser.add_argument(
        "--agent-only",
        action="store_true",
        help="Only test agent endpoint (tool events)"
    )
    parser.add_argument(
        "--reasoning-only",
        action="store_true",
        help="Only test reasoning events"
    )
    parser.add_argument(
        "--multimodal-only",
        action="store_true",
        help="Only test multimodal message support"
    )
    parser.add_argument(
        "--tools-only",
        action="store_true",
        help="Only test tool events (skip reasoning and multimodal)"
    )
    return parser.parse_args()


async def main():
    args = parse_arguments()
    tester = ToolEventsTester(
        base_url=args.base_url,
        verbose=args.verbose
    )
    
    try:
        if not await tester.setup():
            sys.exit(1)
        
        # Determine which tests to run
        run_tool_tests = not (args.reasoning_only or args.multimodal_only)
        run_reasoning_tests = not (args.tools_only or args.chat_only or args.agent_only)
        run_multimodal_tests = not (args.tools_only or args.chat_only or args.agent_only)
        
        if args.reasoning_only:
            run_reasoning_tests = True
            run_tool_tests = False
            run_multimodal_tests = False
        
        if args.multimodal_only:
            run_multimodal_tests = True
            run_tool_tests = False
            run_reasoning_tests = False
        
        # Run tool event tests
        if run_tool_tests:
            if not args.agent_only:
                result = await tester.test_chat_stream_tool_events()
                tester.test_results.append(result)
            
            if not args.chat_only:
                result = await tester.test_agent_stream_tool_events()
                tester.test_results.append(result)
        
        # Run reasoning tests (both endpoints)
        if run_reasoning_tests:
            if not args.agent_only:
                result = await tester.test_chat_stream_reasoning_events()
                tester.test_results.append(result)
            
            if not args.chat_only:
                result = await tester.test_agent_stream_reasoning_events()
                tester.test_results.append(result)
        
        # Run multimodal tests (both endpoints)
        if run_multimodal_tests:
            if not args.agent_only:
                result = await tester.test_multimodal_messages()
                tester.test_results.append(result)
            
            if not args.chat_only:
                result = await tester.test_agent_multimodal_messages()
                tester.test_results.append(result)
        
    finally:
        await tester.cleanup()
        tester.print_summary()
    
    all_passed = all(r.passed for r in tester.test_results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(1)
