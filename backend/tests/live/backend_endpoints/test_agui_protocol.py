#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
AG-UI Protocol Comprehensive Test Script

This script tests all AG-UI protocol compatible events:

TOOL EVENTS:
- tool_call_start: When a tool call begins (toolCallId, toolCallName)
- tool_call_args: Tool arguments streaming (toolCallId, delta)
- tool_call_end: When tool call completes (toolCallId)
- tool_result: Tool output/result (role, content, toolCallId)

REASONING EVENTS (requires deep thinking mode or compatible model):
- reasoning_start: Reasoning session starts (messageId)
- reasoning_message_start: Reasoning message starts (messageId, role)
- reasoning_message_content: Reasoning content delta (messageId, delta)
- reasoning_message_end: Reasoning message ends (messageId)
- reasoning_end: Reasoning session ends (messageId)

MULTIMODAL SUPPORT:
- Image messages (URL and base64)
- Content blocks format (LangChain v1 standard)

Tests both endpoints:
1. /agent/agent/stream (with sandbox) - uses astream_events
2. /agent/chat/stream (no sandbox) - uses astream with messages mode

Prerequisites:
    1. Backend server running at http://localhost:8000
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/create_test_user.py

Usage:
    python backend/tests/live/backend_endpoints/test_agui_protocol.py

    # With verbose output
    python backend/tests/live/backend_endpoints/test_agui_protocol.py --verbose

    # Test specific features
    python backend/tests/live/backend_endpoints/test_agui_protocol.py --test-reasoning
    python backend/tests/live/backend_endpoints/test_agui_protocol.py --test-multimodal
    python backend/tests/live/backend_endpoints/test_agui_protocol.py --test-tools
    
    # Test only chat endpoint
    python backend/tests/live/backend_endpoints/test_agui_protocol.py --chat-only
"""

import asyncio
import argparse
import json
import sys
import os
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

# Fix Windows encoding issues with emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import httpx

# Import our structured models for validation
try:
    from backend.app.agent.models import (
        AgentMessage,
        ChatMessage,
        TextBlock,
        ImageBlock,
        ReasoningState,
        ToolCall,
        ToolResult,
        MessageRole,
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    print("Warning: Could not import agent models. Model validation will be skipped.")


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"

# Sample base64 encoded 1x1 red pixel PNG for testing multimodal
SAMPLE_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
)


class AGUIEventType(str, Enum):
    """AG-UI Protocol event types."""
    # Tool events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"
    
    # Reasoning events
    REASONING_START = "reasoning_start"
    REASONING_MESSAGE_START = "reasoning_message_start"
    REASONING_MESSAGE_CONTENT = "reasoning_message_content"
    REASONING_MESSAGE_END = "reasoning_message_end"
    REASONING_END = "reasoning_end"
    
    # Message events
    MESSAGE = "message"
    MESSAGE_CHUNK = "message_chunk"
    
    # Status events
    STATUS = "status"
    ERROR = "error"
    WARNING = "warning"
    INTERRUPT = "interrupt"


# Event sets for categorization
AGUI_TOOL_EVENTS = {
    AGUIEventType.TOOL_CALL_START.value,
    AGUIEventType.TOOL_CALL_ARGS.value,
    AGUIEventType.TOOL_CALL_END.value,
    AGUIEventType.TOOL_RESULT.value,
}

AGUI_REASONING_EVENTS = {
    AGUIEventType.REASONING_START.value,
    AGUIEventType.REASONING_MESSAGE_START.value,
    AGUIEventType.REASONING_MESSAGE_CONTENT.value,
    AGUIEventType.REASONING_MESSAGE_END.value,
    AGUIEventType.REASONING_END.value,
}

ALL_AGUI_EVENTS = AGUI_TOOL_EVENTS | AGUI_REASONING_EVENTS


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SSEEvent:
    """Represents a parsed Server-Sent Event."""
    event_type: str
    data: Dict[str, Any]
    raw: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


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
    
    def validate_lifecycle(self) -> Tuple[bool, List[str]]:
        """Validate the tool call follows AG-UI protocol."""
        issues = []
        if not self.has_start:
            issues.append(f"Missing tool_call_start for {self.tool_call_id}")
        if not self.has_end:
            issues.append(f"Missing tool_call_end for {self.tool_call_id}")
        if not self.tool_name:
            issues.append(f"Missing tool name for {self.tool_call_id}")
        return len(issues) == 0, issues


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
    
    def validate_lifecycle(self) -> Tuple[bool, List[str]]:
        """Validate the reasoning session follows AG-UI protocol."""
        issues = []
        if not self.has_start:
            issues.append(f"Missing reasoning_start for {self.message_id}")
        if not self.has_end:
            issues.append(f"Missing reasoning_end for {self.message_id}")
        if self.has_message_start and not self.has_message_end:
            issues.append(f"reasoning_message_start without reasoning_message_end for {self.message_id}")
        return len(issues) == 0, issues


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
    agui_events_found: Set[str] = field(default_factory=set)
    warnings: List[str] = field(default_factory=list)


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
# AG-UI Protocol Tester
# =============================================================================

class AGUIProtocolTester:
    """
    Comprehensive AG-UI Protocol test suite.
    
    Tests tool calls, reasoning events, multimodal messages, and
    overall protocol compliance.
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
        self.log("🧪 AG-UI Protocol Comprehensive Test Suite")
        self.log(f"   Base URL: {self.base_url}")
        self.log(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"   Models available: {MODELS_AVAILABLE}")
        self.log("=" * 70)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,  # Long timeout for streaming with reasoning
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'AGUIProtocolTest/1.0',
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
        """Clean up resources."""
        if self.client:
            await self.client.aclose()
    
    def _log_event(self, event: SSEEvent):
        """Log an event with optional verbosity."""
        if event.event_type in ALL_AGUI_EVENTS:
            self.log(f"   🔔 AG-UI: {event.event_type}", "verbose")
            self.log(f"      Data: {json.dumps(event.data, indent=2)}", "verbose")
        elif event.event_type in ["status", "error", "warning"]:
            symbol = "📊" if event.event_type == "status" else "❌" if event.event_type == "error" else "⚠️"
            self.log(f"   {symbol} {event.event_type}: {event.data.get('message', event.data)}", "verbose")
    
    def _track_tool_event(self, event: SSEEvent, trackers: Dict[str, ToolCallTracker]):
        """Track a tool event and update the appropriate tracker."""
        data = event.data
        tool_call_id = data.get("toolCallId") or data.get("tool_call_id") or ""
        
        if not tool_call_id:
            return
        
        if tool_call_id not in trackers:
            trackers[tool_call_id] = ToolCallTracker(tool_call_id=tool_call_id)
        
        tracker = trackers[tool_call_id]
        
        if event.event_type == "tool_call_start":
            tracker.has_start = True
            tracker.tool_name = data.get("toolCallName", "")
        elif event.event_type == "tool_call_args":
            delta = data.get("delta", "")
            if delta:
                tracker.args_deltas.append(delta)
        elif event.event_type == "tool_call_end":
            tracker.has_end = True
        elif event.event_type == "tool_result":
            tracker.has_result = True
            tracker.result_content = data.get("content", "")
    
    def _track_reasoning_event(self, event: SSEEvent, trackers: Dict[str, ReasoningTracker]):
        """Track a reasoning event and update the appropriate tracker."""
        data = event.data
        message_id = data.get("messageId") or ""
        
        if not message_id:
            return
        
        if message_id not in trackers:
            trackers[message_id] = ReasoningTracker(message_id=message_id)
        
        tracker = trackers[message_id]
        
        if event.event_type == "reasoning_start":
            tracker.has_start = True
        elif event.event_type == "reasoning_message_start":
            tracker.has_message_start = True
        elif event.event_type == "reasoning_message_content":
            delta = data.get("delta", "")
            if delta:
                tracker.content_deltas.append(delta)
        elif event.event_type == "reasoning_message_end":
            tracker.has_message_end = True
        elif event.event_type == "reasoning_end":
            tracker.has_end = True
    
    async def _stream_request(
        self,
        endpoint: str,
        request_body: Dict[str, Any],
        test_name: str,
    ) -> TestResult:
        """Make a streaming request and collect events."""
        start_time = datetime.now()
        events: List[SSEEvent] = []
        tool_trackers: Dict[str, ToolCallTracker] = {}
        reasoning_trackers: Dict[str, ReasoningTracker] = {}
        agui_events_found: Set[str] = set()
        warnings: List[str] = []
        
        try:
            self.log(f"   Request: {json.dumps(request_body, indent=2)}", "verbose")
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}{endpoint}",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    return TestResult(
                        name=test_name,
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
                            if event.event_type in AGUI_TOOL_EVENTS:
                                agui_events_found.add(event.event_type)
                                self._track_tool_event(event, tool_trackers)
                            
                            if event.event_type in AGUI_REASONING_EVENTS:
                                agui_events_found.add(event.event_type)
                                self._track_reasoning_event(event, reasoning_trackers)
            
            return TestResult(
                name=test_name,
                passed=True,
                events=events,
                tool_calls=tool_trackers,
                reasoning_sessions=reasoning_trackers,
                agui_events_found=agui_events_found,
                warnings=warnings,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            import traceback
            self.log(f"   ❌ Error: {e}", "verbose")
            if self.verbose:
                traceback.print_exc()
            return TestResult(
                name=test_name,
                passed=False,
                message=f"Exception: {e}",
                events=events,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    # =========================================================================
    # Tool Call Tests
    # =========================================================================
    
    async def test_chat_tool_calls(self) -> TestResult:
        """Test tool call events via /agent/chat/stream."""
        self.log("\n📋 Test: Chat Stream Tool Calls")
        
        request_body = {
            "messages": [
                {"role": "user", "content": "Search the web for the current weather in Tokyo and tell me the temperature."}
            ],
            "thread_id": f"test-tools-chat-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "enable_web_search": True,
            "auto_accepted_plan": True,
            "max_plan_iterations": 1,
            "max_step_num": 2
        }
        
        result = await self._stream_request(
            "/agent/chat/stream",
            request_body,
            "chat_tool_calls"
        )
        
        # Validate tool events
        if result.passed and result.tool_calls:
            issues = []
            for tc_id, tracker in result.tool_calls.items():
                valid, tc_issues = tracker.validate_lifecycle()
                if not valid:
                    issues.extend(tc_issues)
            
            if issues:
                result.warnings.extend(issues)
                self.log(f"   ⚠️  Tool lifecycle issues: {issues}")
            else:
                self.log(f"   ✅ {len(result.tool_calls)} tool calls validated")
        
        self._print_test_summary(result)
        return result
    
    async def test_agent_tool_calls(self) -> TestResult:
        """Test tool call events via /agent/agent/stream."""
        self.log("\n📋 Test: Agent Stream Tool Calls")
        
        request_body = {
            "messages": [
                {"role": "user", "content": "Use a tool to search for information about Python programming language."}
            ],
            "thread_id": f"test-tools-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "enable_web_search": True,
            "auto_accepted_plan": True,
            "max_plan_iterations": 1,
            "max_step_num": 2
        }
        
        result = await self._stream_request(
            "/agent/agent/stream",
            request_body,
            "agent_tool_calls"
        )
        
        self._print_test_summary(result)
        return result

    # =========================================================================
    # Reasoning Tests
    # =========================================================================
    
    async def test_chat_reasoning(self) -> TestResult:
        """Test reasoning events via /agent/chat/stream with deep thinking enabled."""
        self.log("\n📋 Test: Chat Stream Reasoning (Deep Thinking)")
        
        request_body = {
            "messages": [
                {"role": "user", "content": "What is 15 * 23 + 47? Think step by step before answering."}
            ],
            "thread_id": f"test-reasoning-chat-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "enable_deep_thinking": True,  # Enable deep thinking mode
            "auto_accepted_plan": True,
            "max_plan_iterations": 1,
            "max_step_num": 1
        }
        
        result = await self._stream_request(
            "/agent/chat/stream",
            request_body,
            "chat_reasoning"
        )
        
        # Check if reasoning events were found
        reasoning_found = any(e in result.agui_events_found for e in AGUI_REASONING_EVENTS)
        
        if reasoning_found:
            self.log(f"   ✅ Reasoning events detected!")
            for session_id, tracker in result.reasoning_sessions.items():
                valid, issues = tracker.validate_lifecycle()
                content_preview = tracker.full_content[:100] + "..." if len(tracker.full_content) > 100 else tracker.full_content
                self.log(f"      Session {session_id[:20]}...: {len(tracker.content_deltas)} chunks, valid={valid}")
                self.log(f"      Content preview: {content_preview}", "verbose")
        else:
            result.warnings.append("No reasoning events detected (model may not support thinking)")
            self.log(f"   ⚠️  No reasoning events detected")
            self.log(f"      This is expected if the model doesn't support thinking/reasoning")
        
        self._print_test_summary(result)
        return result
    
    async def test_agent_reasoning(self) -> TestResult:
        """Test reasoning events via /agent/agent/stream."""
        self.log("\n📋 Test: Agent Stream Reasoning (Deep Thinking)")
        
        request_body = {
            "messages": [
                {"role": "user", "content": "Solve this logic puzzle step by step: If all bloops are razzies and all razzies are lazzies, are all bloops lazzies?"}
            ],
            "thread_id": f"test-reasoning-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "enable_deep_thinking": True,
            "auto_accepted_plan": True,
            "max_plan_iterations": 1,
            "max_step_num": 1
        }
        
        result = await self._stream_request(
            "/agent/agent/stream",
            request_body,
            "agent_reasoning"
        )
        
        self._print_test_summary(result)
        return result

    # =========================================================================
    # Multimodal Tests
    # =========================================================================
    
    async def test_chat_multimodal_url(self) -> TestResult:
        """Test multimodal image message with URL via /agent/chat/stream."""
        self.log("\n📋 Test: Chat Stream Multimodal (Image URL)")
        
        # Use a public test image
        image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"
        
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What do you see in this image? Describe it briefly."},
                        {"type": "image", "url": image_url}
                    ]
                }
            ],
            "thread_id": f"test-multimodal-url-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "auto_accepted_plan": True,
            "max_plan_iterations": 1,
            "max_step_num": 1
        }
        
        result = await self._stream_request(
            "/agent/chat/stream",
            request_body,
            "chat_multimodal_url"
        )
        
        # Check if we got a response (model processed the image)
        message_events = [e for e in result.events if e.event_type in ["message", "message_chunk"]]
        if message_events:
            self.log(f"   ✅ Got {len(message_events)} message events from multimodal request")
        else:
            result.warnings.append("No message events received for multimodal request")
        
        self._print_test_summary(result)
        return result
    
    async def test_chat_multimodal_base64(self) -> TestResult:
        """Test multimodal image message with base64 via /agent/chat/stream."""
        self.log("\n📋 Test: Chat Stream Multimodal (Base64 Image)")
        
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "I'm sending you a tiny test image. What color is it?"},
                        {
                            "type": "image",
                            "data": SAMPLE_IMAGE_BASE64,
                            "mime_type": "image/png"
                        }
                    ]
                }
            ],
            "thread_id": f"test-multimodal-b64-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "auto_accepted_plan": True,
            "max_plan_iterations": 1,
            "max_step_num": 1
        }
        
        result = await self._stream_request(
            "/agent/chat/stream",
            request_body,
            "chat_multimodal_base64"
        )
        
        self._print_test_summary(result)
        return result

    # =========================================================================
    # Model Validation Tests
    # =========================================================================
    
    async def test_model_serialization(self) -> TestResult:
        """Test that our Pydantic models serialize correctly for the API."""
        self.log("\n📋 Test: Model Serialization")
        
        if not MODELS_AVAILABLE:
            return TestResult(
                name="model_serialization",
                passed=False,
                message="Models not available for import"
            )
        
        start_time = datetime.now()
        issues = []
        
        try:
            # Test simple message
            msg1 = AgentMessage(role=MessageRole.USER, content="Hello!")
            lc1 = msg1.to_langchain_format()
            if lc1 != {"role": "user", "content": "Hello!"}:
                issues.append(f"Simple message format mismatch: {lc1}")
            
            # Test multimodal message with structured blocks
            msg2 = AgentMessage(
                role=MessageRole.USER,
                content=[
                    TextBlock(text="Describe this"),
                    ImageBlock(url="https://example.com/img.jpg")
                ]
            )
            lc2 = msg2.to_langchain_format()
            if len(lc2.get("content", [])) != 2:
                issues.append(f"Multimodal message block count mismatch: {lc2}")
            
            # Test ToolCall
            tc = ToolCall(
                tool_call_id="test_123",
                tool_name="web_search",
                tool_input={"query": "test"}
            )
            start_event = tc.to_ag_ui_start_event()
            if start_event.get("toolCallId") != "test_123":
                issues.append(f"ToolCall start event mismatch: {start_event}")
            
            # Test ReasoningState
            rs = ReasoningState()
            msg_id = rs.start_reasoning()
            if not msg_id.startswith("reasoning-"):
                issues.append(f"ReasoningState ID format mismatch: {msg_id}")
            rs.end_reasoning()
            if rs.is_active:
                issues.append("ReasoningState still active after end")
            
            passed = len(issues) == 0
            message = "All model serializations valid" if passed else f"Issues: {issues}"
            
            self.log(f"   {'✅' if passed else '❌'} {message}")
            
            return TestResult(
                name="model_serialization",
                passed=passed,
                message=message,
                warnings=issues,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            return TestResult(
                name="model_serialization",
                passed=False,
                message=f"Exception: {e}",
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _print_test_summary(self, result: TestResult):
        """Print a summary of a test result."""
        status = "✅ PASSED" if result.passed else "❌ FAILED"
        self.log(f"\n   {status} - {result.name}")
        self.log(f"   Duration: {result.duration_seconds:.2f}s")
        self.log(f"   Total events: {len(result.events)}")
        
        if result.agui_events_found:
            self.log(f"   AG-UI events: {sorted(result.agui_events_found)}")
        
        if result.tool_calls:
            self.log(f"   Tool calls: {len(result.tool_calls)}")
            for tc_id, tracker in result.tool_calls.items():
                self.log(f"      - {tracker.tool_name} ({tc_id[:20]}...): complete={tracker.is_complete}", "verbose")
        
        if result.reasoning_sessions:
            self.log(f"   Reasoning sessions: {len(result.reasoning_sessions)}")
        
        if result.warnings:
            self.log(f"   ⚠️  Warnings: {result.warnings}")
        
        if not result.passed and result.message:
            self.log(f"   Message: {result.message}")
    
    def print_final_summary(self):
        """Print final summary of all tests."""
        self.log("\n" + "=" * 70)
        self.log("📊 FINAL SUMMARY")
        self.log("=" * 70)
        
        passed = sum(1 for r in self.test_results if r.passed)
        failed = len(self.test_results) - passed
        
        for result in self.test_results:
            status = "✅" if result.passed else "❌"
            self.log(f"   {status} {result.name}: {result.duration_seconds:.2f}s")
        
        self.log(f"\n   Total: {len(self.test_results)} tests")
        self.log(f"   Passed: {passed}")
        self.log(f"   Failed: {failed}")
        
        # AG-UI events coverage
        all_events_found = set()
        for result in self.test_results:
            all_events_found.update(result.agui_events_found)
        
        self.log(f"\n   AG-UI Tool Events Covered: {all_events_found & AGUI_TOOL_EVENTS}")
        self.log(f"   AG-UI Reasoning Events Covered: {all_events_found & AGUI_REASONING_EVENTS}")
        
        missing_tool = AGUI_TOOL_EVENTS - all_events_found
        missing_reasoning = AGUI_REASONING_EVENTS - all_events_found
        
        if missing_tool:
            self.log(f"   ⚠️  Missing tool events: {missing_tool}")
        if missing_reasoning:
            self.log(f"   ⚠️  Missing reasoning events: {missing_reasoning}")
        
        self.log("=" * 70)
        
        return failed == 0

    # =========================================================================
    # Main Test Runner
    # =========================================================================
    
    async def run_all_tests(
        self,
        test_tools: bool = True,
        test_reasoning: bool = True,
        test_multimodal: bool = True,
        chat_only: bool = False,
        agent_only: bool = False,
    ) -> bool:
        """Run all selected tests."""
        
        if not await self.setup():
            return False
        
        try:
            # Model validation (always run)
            result = await self.test_model_serialization()
            self.test_results.append(result)
            
            # Tool call tests
            if test_tools:
                if not agent_only:
                    result = await self.test_chat_tool_calls()
                    self.test_results.append(result)
                
                if not chat_only:
                    result = await self.test_agent_tool_calls()
                    self.test_results.append(result)
            
            # Reasoning tests
            if test_reasoning:
                if not agent_only:
                    result = await self.test_chat_reasoning()
                    self.test_results.append(result)
                
                if not chat_only:
                    result = await self.test_agent_reasoning()
                    self.test_results.append(result)
            
            # Multimodal tests
            if test_multimodal:
                if not agent_only:
                    result = await self.test_chat_multimodal_url()
                    self.test_results.append(result)
                    
                    result = await self.test_chat_multimodal_base64()
                    self.test_results.append(result)
            
            return self.print_final_summary()
            
        finally:
            await self.cleanup()


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="AG-UI Protocol Comprehensive Test Suite"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Backend base URL (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--test-tools",
        action="store_true",
        help="Test tool call events only"
    )
    parser.add_argument(
        "--test-reasoning",
        action="store_true",
        help="Test reasoning events only"
    )
    parser.add_argument(
        "--test-multimodal",
        action="store_true",
        help="Test multimodal messages only"
    )
    parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Test only chat endpoint"
    )
    parser.add_argument(
        "--agent-only",
        action="store_true",
        help="Test only agent endpoint"
    )
    
    args = parser.parse_args()
    
    # If no specific tests are selected, run all
    test_tools = args.test_tools
    test_reasoning = args.test_reasoning
    test_multimodal = args.test_multimodal
    
    if not (test_tools or test_reasoning or test_multimodal):
        test_tools = test_reasoning = test_multimodal = True
    
    tester = AGUIProtocolTester(
        base_url=args.base_url,
        verbose=args.verbose
    )
    
    success = await tester.run_all_tests(
        test_tools=test_tools,
        test_reasoning=test_reasoning,
        test_multimodal=test_multimodal,
        chat_only=args.chat_only,
        agent_only=args.agent_only,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
