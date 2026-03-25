#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Tool Result Event Integration Tests

This test validates that tool_result events are correctly emitted with II-Agent protocol
field names that the frontend expects:
- tool_call_id (not toolCallId)
- tool_name (not toolName) 
- result (not content)
- is_error
- thread_id

Usage:
    # Run all tests
    python backend/tests/live/backend_endpoints/test_tool_result_events.py
    
    # Run with verbose output (shows all SSE events)
    python backend/tests/live/backend_endpoints/test_tool_result_events.py --verbose
    
    # Run specific test
    python backend/tests/live/backend_endpoints/test_tool_result_events.py --test web_search

Prerequisites:
    1. Backend server running at http://127.0.0.1:8000
    2. Test user exists: sandbox_test / TestPass123!
"""

import asyncio
import argparse
import json
import sys
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

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


# =============================================================================
# Test Results Tracking
# =============================================================================

@dataclass
class ToolResultValidation:
    """Validation result for a single tool_result event."""
    event_data: dict
    has_tool_call_id: bool = False
    has_tool_name: bool = False
    has_result: bool = False
    has_is_error: bool = False
    has_thread_id: bool = False
    
    # Legacy fields that should NOT be present (or should be secondary)
    has_legacy_toolCallId: bool = False
    has_legacy_toolName: bool = False
    has_legacy_content: bool = False
    
    # Data type validation
    tool_call_id_type: str = ""
    tool_name_type: str = ""
    result_type: str = ""
    
    @property
    def is_valid(self) -> bool:
        """Check if event has all required II-Agent fields."""
        return (
            self.has_tool_call_id and
            self.has_tool_name and
            self.has_result
        )
    
    @property
    def uses_legacy_format(self) -> bool:
        """Check if event uses legacy AG-UI format instead."""
        return self.has_legacy_toolCallId or self.has_legacy_content
    
    def summary(self) -> str:
        """Return a summary of validation results."""
        status = "✅ VALID" if self.is_valid else "❌ INVALID"
        legacy = " (⚠️ uses legacy fields)" if self.uses_legacy_format else ""
        return f"{status}{legacy}"


@dataclass
class TestResult:
    """Result of a single test case."""
    name: str
    prompt: str
    success: bool = False
    error_message: str = ""
    tool_calls_found: int = 0
    tool_results_found: int = 0
    tool_result_validations: list = field(default_factory=list)
    all_events: list = field(default_factory=list)
    
    def add_tool_result(self, validation: ToolResultValidation):
        """Add a tool_result validation."""
        self.tool_results_found += 1
        self.tool_result_validations.append(validation)
    
    @property
    def all_results_valid(self) -> bool:
        """Check if all tool_result events are valid."""
        if not self.tool_result_validations:
            return False
        return all(v.is_valid for v in self.tool_result_validations)


# =============================================================================
# Test Client
# =============================================================================

class ToolResultEventTester:
    """Test client for validating tool_result events."""
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.token: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        
    def log(self, message: str, level: str = "info"):
        """Log a message."""
        if level == "verbose" and not self.verbose:
            return
        print(message)
    
    async def setup(self) -> bool:
        """Initialize HTTP client and authenticate."""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=180.0,  # 3 minute timeout
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'ToolResultEventTester/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        self.log("🔐 Authenticating...")
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
                self.log("✅ Authentication successful!")
                return True
            else:
                self.log(f"❌ Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ Setup error: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.client:
            await self.client.aclose()
    
    def validate_tool_result(self, data: dict) -> ToolResultValidation:
        """Validate a tool_result event against II-Agent protocol."""
        validation = ToolResultValidation(event_data=data)
        
        # Check II-Agent protocol fields (snake_case)
        validation.has_tool_call_id = "tool_call_id" in data
        validation.has_tool_name = "tool_name" in data
        validation.has_result = "result" in data
        validation.has_is_error = "is_error" in data
        validation.has_thread_id = "thread_id" in data
        
        # Check legacy AG-UI fields (camelCase) - should NOT be primary
        validation.has_legacy_toolCallId = "toolCallId" in data
        validation.has_legacy_toolName = "toolName" in data
        validation.has_legacy_content = "content" in data and "result" not in data
        
        # Validate data types
        if validation.has_tool_call_id:
            validation.tool_call_id_type = type(data["tool_call_id"]).__name__
        if validation.has_tool_name:
            validation.tool_name_type = type(data["tool_name"]).__name__
        if validation.has_result:
            validation.result_type = type(data["result"]).__name__
        
        return validation
    
    async def run_test(
        self,
        name: str,
        prompt: str,
        endpoint: str = "/agent/agent/stream",
        expect_tool_calls: bool = True,
    ) -> TestResult:
        """
        Run a single test case.
        
        Args:
            name: Test name
            prompt: User prompt to send
            endpoint: Either /agent/agent/stream or /agent/chat/stream
            expect_tool_calls: Whether we expect tool calls
        """
        result = TestResult(name=name, prompt=prompt)
        thread_id = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}-{name}"
        
        self.log(f"\n{'='*70}")
        self.log(f"🧪 TEST: {name}")
        self.log(f"{'='*70}")
        self.log(f"📝 Prompt: {prompt[:100]}...")
        self.log(f"🔗 Endpoint: {endpoint}")
        
        # Prepare request based on endpoint
        if "chat" in endpoint:
            request_body = {
                "messages": [{"role": "user", "content": prompt}],
                "thread_id": thread_id,
                "enable_background_investigation": False,
                "enable_web_search": True,  # Enable tools
            }
        else:
            request_body = {
                "module": "general",
                "messages": [{"role": "user", "content": prompt}],
                "thread_id": thread_id,
                "enable_background_investigation": False,
                "enable_web_search": True,  # Enable tools
            }
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}{endpoint}",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    result.error_message = f"HTTP {response.status_code}: {error_text.decode()[:200]}"
                    self.log(f"❌ {result.error_message}")
                    return result
                
                event_type = "unknown"
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            result.all_events.append({
                                "type": event_type,
                                "data": data
                            })
                            
                            # Log all events in verbose mode
                            if self.verbose:
                                self.log(f"   [{event_type}] {str(data)[:200]}", "verbose")
                            
                            # Track tool_call events
                            if event_type == "tool_call_start":
                                result.tool_calls_found += 1
                                tool_name = data.get("toolCallName", data.get("tool_name", "?"))
                                self.log(f"   🔧 Tool started: {tool_name}")
                            
                            # Validate tool_result events
                            elif event_type == "tool_result":
                                validation = self.validate_tool_result(data)
                                result.add_tool_result(validation)
                                
                                tool_name = data.get("tool_name", data.get("toolName", "?"))
                                self.log(f"   📋 Tool result: {tool_name} - {validation.summary()}")
                                
                                if self.verbose:
                                    self.log(f"      Fields: tool_call_id={validation.has_tool_call_id}, tool_name={validation.has_tool_name}, result={validation.has_result}")
                                    self.log(f"      Types: tool_call_id={validation.tool_call_id_type}, tool_name={validation.tool_name_type}, result={validation.result_type}")
                                    if validation.uses_legacy_format:
                                        self.log(f"      ⚠️ Legacy fields: toolCallId={validation.has_legacy_toolCallId}, content={validation.has_legacy_content}")
                            
                        except json.JSONDecodeError:
                            pass
            
            # Determine success
            if expect_tool_calls:
                if result.tool_results_found == 0:
                    result.error_message = "No tool_result events received"
                    self.log(f"❌ {result.error_message}")
                elif not result.all_results_valid:
                    invalid_count = sum(1 for v in result.tool_result_validations if not v.is_valid)
                    result.error_message = f"{invalid_count}/{result.tool_results_found} tool_result events have invalid format"
                    self.log(f"❌ {result.error_message}")
                else:
                    result.success = True
                    self.log(f"✅ All {result.tool_results_found} tool_result events valid!")
            else:
                result.success = True
            
        except Exception as e:
            result.error_message = str(e)
            self.log(f"❌ Error: {e}")
        
        return result


# =============================================================================
# Test Cases
# =============================================================================

TEST_CASES = {
    "web_search": {
        "name": "Web Search Tool",
        "prompt": "Search the web for 'Python 3.13 new features' and summarize the top result",
        "endpoint": "/agent/agent/stream",
        "expect_tool_calls": True,
    },
    "simple_math": {
        "name": "Simple Math (no tools)",
        "prompt": "What is 2 + 2? Just give me the number.",
        "endpoint": "/agent/agent/stream",
        "expect_tool_calls": False,  # May or may not use tools
    },
    "chat_web_search": {
        "name": "Chat Endpoint Web Search",
        "prompt": "Search online for the weather in New York today",
        "endpoint": "/agent/chat/stream",
        "expect_tool_calls": True,
    },
    "thinking": {
        "name": "Reasoning/Thinking Test",
        "prompt": "Think step by step about how to solve: If a train travels at 60 mph for 2.5 hours, how far does it go?",
        "endpoint": "/agent/agent/stream",
        "expect_tool_calls": False,
    },
}


# =============================================================================
# Main Test Runner
# =============================================================================

async def run_all_tests(
    base_url: str,
    verbose: bool,
    test_filter: Optional[str] = None
):
    """Run all tool_result event tests."""
    
    print("\n" + "=" * 70)
    print("🧪 TOOL RESULT EVENT INTEGRATION TESTS")
    print("=" * 70)
    print(f"   Backend URL: {base_url}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Verbose: {verbose}")
    print("=" * 70)
    
    tester = ToolResultEventTester(base_url=base_url, verbose=verbose)
    
    if not await tester.setup():
        print("\n❌ Setup failed. Ensure:")
        print(f"   - Backend is running at {base_url}")
        print("   - Test user exists (run: python backend/tests/create_test_user.py)")
        return 1
    
    results: list[TestResult] = []
    
    try:
        # Filter test cases if specified
        tests_to_run = TEST_CASES
        if test_filter:
            tests_to_run = {k: v for k, v in TEST_CASES.items() if test_filter.lower() in k.lower()}
            if not tests_to_run:
                print(f"\n❌ No tests match filter: {test_filter}")
                print(f"   Available tests: {', '.join(TEST_CASES.keys())}")
                return 1
        
        # Run each test
        for test_key, test_config in tests_to_run.items():
            result = await tester.run_test(
                name=test_config["name"],
                prompt=test_config["prompt"],
                endpoint=test_config["endpoint"],
                expect_tool_calls=test_config["expect_tool_calls"],
            )
            results.append(result)
            
            # Small delay between tests
            await asyncio.sleep(1)
        
    finally:
        await tester.cleanup()
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    
    for result in results:
        status = "✅" if result.success else "❌"
        print(f"   {status} {result.name}")
        if result.tool_results_found > 0:
            valid = sum(1 for v in result.tool_result_validations if v.is_valid)
            print(f"      Tool results: {valid}/{result.tool_results_found} valid")
        if result.error_message:
            print(f"      Error: {result.error_message}")
    
    print("-" * 70)
    print(f"   Total: {passed}/{len(results)} tests passed")
    print("=" * 70)
    
    # Detailed validation report
    print("\n📋 TOOL_RESULT EVENT VALIDATION DETAILS")
    print("-" * 70)
    
    all_validations = [v for r in results for v in r.tool_result_validations]
    
    if all_validations:
        # Field presence statistics
        total = len(all_validations)
        has_tool_call_id = sum(1 for v in all_validations if v.has_tool_call_id)
        has_tool_name = sum(1 for v in all_validations if v.has_tool_name)
        has_result = sum(1 for v in all_validations if v.has_result)
        has_is_error = sum(1 for v in all_validations if v.has_is_error)
        has_thread_id = sum(1 for v in all_validations if v.has_thread_id)
        uses_legacy = sum(1 for v in all_validations if v.uses_legacy_format)
        
        print(f"   Total tool_result events: {total}")
        print(f"\n   II-Agent Protocol Fields (REQUIRED):")
        print(f"      tool_call_id: {has_tool_call_id}/{total} {'✅' if has_tool_call_id == total else '❌'}")
        print(f"      tool_name:    {has_tool_name}/{total} {'✅' if has_tool_name == total else '❌'}")
        print(f"      result:       {has_result}/{total} {'✅' if has_result == total else '❌'}")
        print(f"\n   Optional Fields:")
        print(f"      is_error:     {has_is_error}/{total}")
        print(f"      thread_id:    {has_thread_id}/{total}")
        print(f"\n   Legacy Format Usage: {uses_legacy}/{total} {'⚠️ Some events use legacy format' if uses_legacy > 0 else '✅ None'}")
        
        # Data type summary
        result_types = {}
        for v in all_validations:
            t = v.result_type
            result_types[t] = result_types.get(t, 0) + 1
        
        print(f"\n   Result Field Types:")
        for t, count in result_types.items():
            print(f"      {t}: {count} events")
    else:
        print("   No tool_result events captured")
    
    print("-" * 70)
    
    return 0 if failed == 0 else 1


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Test tool_result event format validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This test validates that tool_result events use II-Agent protocol field names:
- tool_call_id (not toolCallId)
- tool_name (not toolName)
- result (not content)

Example:
    python test_tool_result_events.py
    python test_tool_result_events.py --verbose
    python test_tool_result_events.py --test web_search
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
        help="Enable verbose output (show all SSE events)"
    )
    parser.add_argument(
        "--test", "-t",
        type=str,
        default=None,
        help=f"Run specific test (options: {', '.join(TEST_CASES.keys())})"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    try:
        exit_code = asyncio.run(run_all_tests(
            base_url=args.base_url,
            verbose=args.verbose,
            test_filter=args.test,
        ))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(1)
