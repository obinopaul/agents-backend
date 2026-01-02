#!/usr/bin/env python3
"""
Persistent Slide System Test - Creates Sandbox and Keeps It Alive

This script is for DEBUGGING database slide storage issues.
It creates slides via agent, then KEEPS THE SANDBOX ALIVE for manual testing.

Key differences from interactive_slide_test.py:
1. Does NOT delete sandbox at end
2. Outputs all credentials for manual testing (JWT, sandbox_id, thread_id)
3. Waits for user to press Enter before exiting
4. Keeps sandbox alive for extended testing

Use this to:
- Create slides in sandbox
- Manually test database endpoints
- Debug SlideEventSubscriber flow
- Query PostgreSQL directly

Prerequisites:
    - FastAPI backend running at localhost:8000
    - E2B API key configured
    - Test user created (python backend/tests/live/create_test_user.py)
    - Database with slide_content table (alembic upgrade head)

Usage:
    python backend/tests/live/slide_system/persistent_slide_test.py
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
# SSE Event Parsing
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
# Persistent Slide Tester
# =============================================================================

class PersistentSlideTester:
    """
    Creates slides and keeps sandbox ALIVE for debugging.
    
    Unlike InteractiveSlideTester, this:
    - Does NOT delete the sandbox
    - Outputs all credentials for manual testing
    - Waits indefinitely for user to finish testing
    """
    
    def __init__(self):
        self.token = None
        self.client = None
        self.sandbox_id = None
        self.mcp_url = None
        self.thread_id = f"persistent-test-{uuid.uuid4().hex[:8]}"
        self.events: List[SSEEvent] = []
        self.tool_events: List[Dict] = []  # Track tool calls for debugging

    async def setup(self):
        """Initialize HTTP client and authenticate."""
        print("\n" + "=" * 70)
        print("🔧 PERSISTENT Slide System Test (Debug Mode)")
        print(f"   Thread ID: {self.thread_id}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Initialize HTTP client with long timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'PersistentSlideTester/1.0',
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
                print(f"   ✅ Sandbox ready: {self.sandbox_id}")
            elif data_type == "mcp_check":
                print("   ⏳ Checking MCP server...")
            elif data_type == "mcp_ready":
                self.mcp_url = event.data.get("mcp_url", "")
                print(f"   ✅ MCP server ready: {self.mcp_url}")
            elif data_type == "mcp_waiting":
                elapsed = event.data.get("elapsed_seconds", "?")
                print(f"   ⏳ Waiting for MCP... ({elapsed}s)")
            elif data_type == "agent_start":
                print("   ✅ Agent workflow started")
            elif data_type == "tool_registration":
                print("   📋 Tools registered")
            elif data_type == "tool_probe":
                tools = event.data.get("tools", [])
                print(f"   📋 Found {len(tools)} tools")
            elif data_type == "complete":
                print("   ✅ Workflow complete")
            else:
                print(f"   📋 Status: {data_type}")
        
        elif event_type == "message":
            content = event.data.get("content", "")[:80]
            if content:
                print(f"   💬 {content}...")
        
        elif event_type == "tool_call_start":
            tool_name = event.data.get("toolName", "?")
            tool_id = event.data.get("toolCallId", "?")[:8]
            print(f"   🔧 Tool START: {tool_name} (id={tool_id}...)")
            self.tool_events.append({
                "type": "start",
                "name": tool_name,
                "id": event.data.get("toolCallId", "?")
            })
        
        elif event_type == "tool_call_end":
            tool_id = event.data.get("toolCallId", "?")[:8]
            print(f"   🔧 Tool END: (id={tool_id}...)")
            self.tool_events.append({
                "type": "end",
                "id": event.data.get("toolCallId", "?")
            })
        
        elif event_type == "tool_result":
            tool_name = event.data.get("toolName", "?")
            content = str(event.data.get("content", ""))[:100]
            print(f"   🔧 Tool RESULT ({tool_name}): {content}...")
        
        elif event_type == "warning":
            message = event.data.get("message", "?")
            print(f"   ⚠️ Warning: {message}")
        
        elif event_type == "error":
            message = event.data.get("message", "?")
            print(f"   ❌ Error: {message}")

    async def run_slide_creation(self, task: str) -> bool:
        """Run the agent to create slides."""
        print(f"\n📋 Step 2: Creating slides via agent...")
        print(f"   Task: {task[:100]}...")
        
        start_time = datetime.now()
        self.events = []
        self.tool_events = []
        
        try:
            request_body = {
                "module": "general",
                "messages": [
                    {"role": "user", "content": task}
                ],
                "thread_id": self.thread_id,
                "enable_background_investigation": False,
                "enable_web_search": False,
                "enable_deep_thinking": False,
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
            
            # Summary of tool events
            print(f"\n   📊 Tool Events Summary:")
            print(f"      Total tool calls: {len([e for e in self.tool_events if e['type'] == 'start'])}")
            for e in self.tool_events:
                if e['type'] == 'start':
                    print(f"      - {e['name']}")
            
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
                print(f"   {'✅' if total > 0 else '❌'} Found {total} presentation(s) in database")
                for pres in presentations:
                    print(f"      • {pres.get('name')} ({pres.get('slide_count')} slides)")
                return total > 0
            else:
                print(f"   ⚠️ Database API returned: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            return False

    async def test_manual_db_write(self) -> bool:
        """Test writing a slide directly to database (bypasses agent)."""
        print("\n📋 Step 5: Testing direct database write...")
        
        try:
            # Write a test slide directly via POST /db/slide endpoint
            test_slide = {
                "presentation_name": "DirectWriteTest",
                "slide_number": 1,
                "title": "Test Slide",
                "content": "<html><body><h1>Direct Write Test</h1><p>This slide was written directly to DB.</p></body></html>"
            }
            
            response = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/db/slide',
                params={'thread_id': self.thread_id},
                json=test_slide
            )
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                if data.get('success'):
                    print(f"   ✅ Direct write successful! slide_id={data.get('slide_id')}")
                    return True
                else:
                    print(f"   ❌ Write failed: {data.get('error')}")
                    return False
            else:
                print(f"   ❌ API returned: {response.status_code}")
                resp_text = response.text[:200]
                print(f"   Response: {resp_text}")
                return False
                
        except Exception as e:
            import traceback
            print(f"   ❌ Error: {e}")
            traceback.print_exc()
            return False

    def print_credentials(self):
        """Print all credentials for manual testing."""
        print("\n" + "=" * 70)
        print("🔑 CREDENTIALS FOR MANUAL TESTING")
        print("=" * 70)
        print(f"   Thread ID:    {self.thread_id}")
        print(f"   Sandbox ID:   {self.sandbox_id or 'N/A'}")
        print(f"   MCP URL:      {self.mcp_url or 'N/A'}")
        print(f"\n   JWT Token (first 50 chars):")
        print(f"   {self.token[:50] if self.token else 'N/A'}...")
        print(f"\n   Full JWT Token (for curl/httpie):")
        print(f"   Authorization: Bearer {self.token}")
        print("=" * 70)
        
        print("\n📋 MANUAL TEST COMMANDS:")
        print("-" * 70)
        print(f"# List presentations from database:")
        print(f"curl -H 'Authorization: Bearer {self.token[:30]}...' \\")
        print(f"     '{BASE_URL}/agent/sandboxes/db/presentations?thread_id={self.thread_id}'")
        print()
        print(f"# List presentations from sandbox:")
        if self.sandbox_id:
            print(f"curl -H 'Authorization: Bearer {self.token[:30]}...' \\")
            print(f"     '{BASE_URL}/agent/sandboxes/{self.sandbox_id}/presentations'")
        print()
        print("# Check PostgreSQL directly:")
        print("docker exec -it agents_backend_postgres psql -U postgres -d agents_backend \\")
        print(f"    -c \"SELECT * FROM slide_content WHERE thread_id='{self.thread_id}';\"")
        print("-" * 70)

    async def run(self):
        """Main test flow."""
        # Step 2: Create slides
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
        
        success = await self.run_slide_creation(task)
        
        # Step 3 & 4: Verify
        sandbox_ok = await self.verify_slides_sandbox()
        db_ok = await self.verify_slides_database()
        
        # Step 5: Test direct DB write
        direct_write_ok = await self.test_manual_db_write()
        
        # After direct write, check DB again
        if direct_write_ok:
            print("\n📋 Step 6: Re-checking database after direct write...")
            await self.verify_slides_database()
        
        # Print results
        print("\n" + "=" * 70)
        print("📊 Test Results")
        print("=" * 70)
        print(f"   Agent execution:     {'✅ Pass' if success else '❌ Fail'}")
        print(f"   Sandbox slides:      {'✅ Pass' if sandbox_ok else '⚠️ Failed/Empty'}")
        print(f"   Database slides:     {'✅ Pass' if db_ok else '❌ NOT SYNCED'}")
        print(f"   Direct DB write:     {'✅ Pass' if direct_write_ok else '❌ Failed'}")
        print("=" * 70)
        
        # Print credentials
        self.print_credentials()
        
        # Wait for user
        print("\n" + "=" * 70)
        print("⏸️  SANDBOX IS STILL RUNNING - Use credentials above for manual testing")
        print("   Press Enter when done to exit (sandbox will remain active)...")
        print("=" * 70)
        
        try:
            await asyncio.get_event_loop().run_in_executor(None, input)
        except KeyboardInterrupt:
            pass

    async def cleanup(self):
        """Cleanup - but DO NOT delete sandbox!"""
        print("\n📋 Cleanup...")
        print("   ⚠️ NOTE: Sandbox is LEFT RUNNING for manual testing!")
        print(f"   ⚠️ Sandbox ID: {self.sandbox_id}")
        print("   ⚠️ You can delete it later via API or it will auto-expire")
        
        # Close HTTP client
        if self.client:
            await self.client.aclose()
        
        print("👋 Done! (Sandbox still active)")


async def main():
    tester = PersistentSlideTester()
    
    try:
        await tester.setup()
        await tester.run()
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
