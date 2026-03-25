#!/usr/bin/env python3
"""
Interactive Slide System Test - Testing Slide Creation via Agent Endpoint

This script tests the slide system end-to-end by:
1. Using the /agent/agent/stream endpoint (which handles sandbox + MCP internally)
2. Asking the agent to create presentation slides
3. Verifying slides are accessible via API endpoints

Based on test_agent_endpoints.py pattern which uses the production agent workflow.

Prerequisites:
    - FastAPI backend running at localhost:8000
    - E2B API key configured
    - Test user created (python backend/tests/live/create_test_user.py)
    - Database with slide_content table (alembic upgrade head)

Usage:
    python backend/tests/live/slide_system/interactive_slide_test.py
    python backend/tests/live/slide_system/interactive_slide_test.py --auto
"""

import asyncio
import argparse
import json
import sys
import os
import uuid
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

BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


# =============================================================================
# SSE Event Parsing (from test_agent_endpoints.py)
# =============================================================================

@dataclass
class SSEEvent:
    """Represents a parsed Server-Sent Event."""
    event_type: str
    data: Dict[str, Any]
    raw: str = ""


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
# Slide System Tester
# =============================================================================

class InteractiveSlideTester:
    """
    Tests the slide system via the /agent/agent/stream endpoint.
    
    This uses the production agent workflow which handles sandbox creation
    and MCP setup internally via SessionSandboxManager.
    """
    
    def __init__(self, args):
        self.args = args
        self.token = None
        self.client = None
        self.sandbox_id = None
        self.thread_id = f"slide-test-{uuid.uuid4().hex[:8]}"
        self.events: List[SSEEvent] = []

    async def setup(self):
        """Initialize HTTP client and authenticate."""
        print("\n" + "=" * 70)
        print("🎨 Slide System Interactive Test")
        print(f"   Thread ID: {self.thread_id}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Initialize HTTP client with long timeout for agent streaming
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,  # 5 min for slide creation
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'SlideTester/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        # Authenticate
        print("\n📋 Step 1: Authenticating...")
        if not await self._login():
            print("   ❌ Login failed. Make sure backend is running and test user exists.")
            print("   Run: python backend/tests/live/create_test_user.py")
            sys.exit(1)
        
        print("   ✅ Authenticated as sandbox_test")
        return True

    async def _login(self) -> bool:
        """Authenticate and get JWT token."""
        try:
            response = await self.client.post(
                f'{BASE_URL}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                token_type = data.get('token_type', 'Bearer')
                self.client.headers['Authorization'] = f'{token_type} {self.token}'
                return True
            
            return False
            
        except Exception as e:
            print(f"   Login error: {e}")
            return False

    def _log_event(self, event: SSEEvent):
        """Log an SSE event with nice formatting."""
        event_type = event.event_type
        data_type = event.data.get("type", "")
        
        if event_type == "status":
            if data_type == "processing":
                module = event.data.get("module", "general")
                print(f"   ✅ Processing (module={module})")
            elif data_type == "sandbox_ready":
                self.sandbox_id = event.data.get("sandbox_id", "")
                print(f"   ✅ Sandbox ready: {self.sandbox_id[:20]}...")
            elif data_type == "mcp_check":
                print("   ⏳ Checking MCP server...")
            elif data_type == "mcp_ready":
                print("   ✅ MCP server ready")
            elif data_type == "mcp_waiting":
                elapsed = event.data.get("elapsed_seconds", "?")
                print(f"   ⏳ Waiting for MCP... ({elapsed}s)")
            elif data_type == "agent_start":
                print("   ✅ Agent workflow started")
            elif data_type == "complete":
                print("   ✅ Workflow complete")
            else:
                print(f"   📋 Status: {data_type}")
        
        elif event_type == "message":
            content = event.data.get("content", "")[:100]
            if content:
                print(f"   💬 {content}...")
        
        elif event_type == "tool":
            tool_name = event.data.get("name", "?")
            tool_type = event.data.get("type", "?")
            print(f"   🔧 Tool {tool_type}: {tool_name}")
        
        elif event_type == "warning":
            message = event.data.get("message", "?")
            print(f"   ⚠️ Warning: {message}")
        
        elif event_type == "error":
            message = event.data.get("message", "?")
            print(f"   ❌ Error: {message}")

    async def run_slide_creation(self, task: str, step_label: str = "Step 2") -> bool:
        """
        Run the agent to create slides using /agent/agent/stream endpoint.
        
        Args:
            task: The slide creation task description
            step_label: Log label for this step
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n📋 {step_label}: Running agent task...")
        print(f"   Task: {task}")
        
        start_time = datetime.now()
        self.events = []
        
        try:
            request_body = {
                "module": "general",  # Use general module with all tools
                "messages": [
                    {"role": "user", "content": task}
                ],
                "thread_id": self.thread_id,
                "enable_background_investigation": False,
                "enable_web_search": False,
                "max_plan_iterations": 1,
                "max_step_num": 5
            }
            
            async with self.client.stream(
                "POST",
                f"{BASE_URL}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"   ❌ HTTP {response.status_code}: {error_text.decode()}")
                    return False
                
                # Parse SSE events
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        parsed_events = parse_sse_chunk(event_text + '\n\n')
                        
                        for event in parsed_events:
                            self.events.append(event)
                            self._log_event(event)
            
            duration = (datetime.now() - start_time).total_seconds()
            print(f"\n   ✅ Agent completed in {duration:.1f}s")
            return True

        except Exception as e:
            import traceback
            print(f"   ❌ Error: {e}")
            traceback.print_exc()
            return False

    async def verify_slides_sandbox(self) -> bool:
        """Verify slides were created in sandbox."""
        print("\n📋 Step 3: Verifying slides in sandbox...")
        
        if not self.sandbox_id:
            print("   ⚠️ No sandbox ID captured")
            return False
        
        try:
            response = await self.client.get(
                f'{BASE_URL}/agent/sandboxes/{self.sandbox_id}/presentations'
            )
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                presentations = data.get('presentations', [])
                print(f"   ✅ Found {len(presentations)} presentation(s) in sandbox")
                for pres in presentations:
                    print(f"      • {pres.get('name')} ({pres.get('slide_count')} slides)")
                return len(presentations) > 0
            else:
                print(f"   ⚠️ Sandbox API returned: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            return False

    async def verify_slides_database(self) -> bool:
        """Verify slides were saved to database."""
        print("\n📋 Step 4: Verifying slides in database...")
        
        try:
            response = await self.client.get(
                f'{BASE_URL}/agent/sandboxes/db/presentations',
                params={'thread_id': self.thread_id}
            )
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                total = data.get('total', 0)
                presentations = data.get('presentations', [])
                print(f"   ✅ Found {total} presentation(s) in database")
                for pres in presentations:
                    print(f"      • {pres.get('name')} ({pres.get('slide_count')} slides)")
                return total > 0
            else:
                print(f"   ⚠️ Database API returned: {response.status_code}")
                # Note: This endpoint requires SlideEventSubscriber integration
                print("   ℹ️  Slides may not sync to DB without SlideEventSubscriber integration")
                return False
                
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            return False

    async def run_auto_test(self):
        """Run automated slide creation and verification test."""
        print("\n" + "=" * 70)
        print("🧪 Running Automated Slide System Test")
        print("=" * 70)

        # Step 1.5: Verify tools
        print("\n📋 Step 1.5: Verifying available tools...")
        tool_check_task = "List ONLY the tools you have access to. Do not explain, just list them."
        await self.run_slide_creation(tool_check_task, "Step 1.5")
        
        # Step 2: Create simple presentation
        task = """
You are a slide creation assistant. 
CRITICAL: You MUST use the 'SlideWrite' tool to create the slides. 
DO NOT simply print HTML. You MUST call the tool.

Task: Create a simple 2-slide presentation called "Demo Presentation" using the SlideWrite tool.

Slide 1 - Title: "Welcome"
Content: A simple HTML slide with a heading "Hello World" and text "This is a test."

Slide 2 - Title: "Thank You" 
Content: A closing slide with "Thank you".

Use proper HTML formatting. Each slide should be valid HTML with basic styling.
"""
        
        # Run agent to create slides
        success = await self.run_slide_creation(task, "Step 2")
        
        if success:
            # Verify slides
            sandbox_ok = await self.verify_slides_sandbox()
            db_ok = await self.verify_slides_database()
            
            print("\n" + "=" * 70)
            print("📊 Test Results")
            print("=" * 70)
            print(f"   Agent execution: {'✅ Pass' if success else '❌ Fail'}")
            print(f"   Sandbox slides:  {'✅ Pass' if sandbox_ok else '⚠️ Failed/Empty'}")
            print(f"   Database slides: {'✅ Pass' if db_ok else '⚠️ Requires SlideEventSubscriber'}")
            print("=" * 70)
        else:
            print("\n❌ Agent failed to create slides")

    async def run_interactive(self):
        """Run interactive session."""
        print("\n💬 Interactive Mode - Enter slide creation commands")
        print("-" * 70)
        print("Example: 'Create a 3-slide presentation about Python'")
        print("Type 'verify' to check slides, 'exit' to quit")
        print("-" * 70)
        
        while True:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "\nYou: "
                )
                
                cmd = user_input.strip().lower()
                
                if cmd in ["exit", "quit", "q"]:
                    break
                elif cmd == "verify":
                    await self.verify_slides_sandbox()
                    await self.verify_slides_database()
                elif cmd:
                    await self.run_slide_creation(user_input, "Interactive Step")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️ Interrupted")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")

    async def cleanup(self):
        """Cleanup resources."""
        print("\n📋 Cleanup...")
        
        # Delete sandbox if captured
        if self.sandbox_id and self.client:
            try:
                response = await self.client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                if response.status_code == 200:
                    print("   ✅ Sandbox deleted")
                else:
                    print(f"   ⚠️ Sandbox delete returned {response.status_code}")
            except Exception as e:
                print(f"   ⚠️ Sandbox cleanup error: {e}")
        
        # Close HTTP client
        if self.client:
            await self.client.aclose()
        
        print("👋 Done!")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Interactive Slide System Test - Create slides via agent and verify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Automated test
  python interactive_slide_test.py --auto
  
  # Interactive mode
  python interactive_slide_test.py
        """
    )
    parser.add_argument(
        "--auto", 
        action="store_true",
        help="Run automated test instead of interactive mode"
    )
    return parser.parse_args()


async def main():
    args = parse_arguments()
    tester = InteractiveSlideTester(args)
    
    try:
        await tester.setup()
        
        if args.auto:
            await tester.run_auto_test()
        else:
            await tester.run_interactive()
            
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
