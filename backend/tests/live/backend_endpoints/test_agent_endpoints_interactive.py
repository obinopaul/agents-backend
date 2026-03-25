#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Interactive Agent Chat Test

This script provides an interactive chat interface to the agent backend,
displaying all sandbox URLs (VS Code, Codex, MCP) as they become available.

Features:
- Interactive REPL-style chat
- Displays VS Code URL prominently (click to view live code editing)
- Shows MCP and Codex URLs when available
- Streams agent responses in real-time
- Shows tool calls and their results

Usage:
    python backend/tests/live/backend_endpoints/test_agent_endpoints_interactive.py
    
    # With verbose output
    python backend/tests/live/backend_endpoints/test_agent_endpoints_interactive.py --verbose

Prerequisites:
    1. Backend server running at http://127.0.0.1:8000 (docker-compose up -d)
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/create_test_user.py
    3. E2B_API_KEY configured in backend/.env
"""

import asyncio
import argparse
import json
import sys
import os
from datetime import datetime
from typing import Optional

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
# Interactive Agent Chat
# =============================================================================

class InteractiveAgentChat:
    """
    Interactive chat with the agent backend via /agent/agent/stream.
    
    Displays all sandbox URLs and streams agent responses.
    """
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.token: Optional[str] = None
        self.token_type: str = "Bearer"
        self.client: Optional[httpx.AsyncClient] = None
        self.thread_id: str = f"interactive-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Sandbox URLs (captured from SSE events)
        self.sandbox_id: Optional[str] = None
        self.mcp_url: Optional[str] = None
        self.vscode_url: Optional[str] = None
        self.codex_url: Optional[str] = None
    
    def log(self, message: str, level: str = "info"):
        """Log a message."""
        if level == "verbose" and not self.verbose:
            return
        print(message)
    
    async def setup(self) -> bool:
        """Initialize HTTP client and authenticate."""
        self._print_header()
        
        # Initialize HTTP client with long timeout for streaming
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,  # 5 minute timeout for long agent operations
                write=10.0,
                pool=10.0
            ),
            headers={
                'User-Agent': 'InteractiveAgentChat/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        # Authenticate
        self.log("\n🔐 Authenticating...")
        if not await self._login():
            self.log("❌ Login failed. Make sure:")
            self.log(f"   - Backend is running at {self.base_url}")
            self.log("   - Test user exists (run: python backend/tests/create_test_user.py)")
            return False
        
        self.log("✅ Authentication successful!")
        self.log(f"📝 Thread ID: {self.thread_id}")
        return True
    
    async def _login(self) -> bool:
        """Authenticate and get JWT token."""
        try:
            login_url = f'{self.base_url}/api/v1/auth/login/swagger'
            print(f"   Trying: {login_url}")
            print(f"   User: {TEST_USER}")
            
            response = await self.client.post(
                login_url,
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            
            print(f"   Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                self.token_type = data.get('token_type', 'Bearer')
                self.client.headers['Authorization'] = f'{self.token_type} {self.token}'
                return True
            
            # Always show login errors for debugging
            print(f"   ❌ Login response: {response.status_code}")
            print(f"   Response body: {response.text[:500]}")
            return False
            
        except httpx.ConnectError as e:
            print(f"   ❌ Cannot connect to backend: {e}")
            print(f"   Is the server running? Try: docker-compose up -d")
            return False
        except Exception as e:
            print(f"   ❌ Login error: {type(e).__name__}: {e}")
            return False
    
    def _print_header(self):
        """Print welcome header."""
        print("\n" + "=" * 70)
        print("🤖 INTERACTIVE AGENT CHAT")
        print("=" * 70)
        print(f"   Backend URL: {self.base_url}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print("\nThis interactive chat connects to the agent backend and displays")
        print("all sandbox URLs (VS Code, MCP, Codex) when they become available.")
        print("\nType your message and press Enter. Type 'quit' or 'exit' to stop.")
        print("-" * 70)
    
    def _print_urls(self):
        """Print all captured URLs prominently."""
        print("\n" + "*" * 70)
        print("*" + " " * 68 + "*")
        print("*  📡 SANDBOX URLs (click to open)                                  *")
        print("*" + " " * 68 + "*")
        
        if self.sandbox_id:
            print(f"*  Sandbox ID: {self.sandbox_id[:50]:<52} *")
        
        print("*" + " " * 68 + "*")
        
        if self.vscode_url:
            print("*  🖥️  VS CODE (view live code editing):                           *")
            # Handle long URLs by truncating display but showing full
            if len(self.vscode_url) > 60:
                print(f"*  👉 {self.vscode_url[:60]}... *")
            else:
                print(f"*  👉 {self.vscode_url:<62}*")
        else:
            print("*  🖥️  VS Code: Not yet available                                   *")
        
        print("*" + " " * 68 + "*")
        
        if self.mcp_url:
            if len(self.mcp_url) > 60:
                print(f"*  🔧 MCP: {self.mcp_url[:55]}...   *")
            else:
                print(f"*  🔧 MCP: {self.mcp_url:<58}*")
        
        if self.codex_url:
            if len(self.codex_url) > 60:
                print(f"*  🤖 Codex: {self.codex_url[:53]}... *")
            else:
                print(f"*  🤖 Codex: {self.codex_url:<56}*")
        
        print("*" + " " * 68 + "*")
        print("*" * 70 + "\n")
    
    async def send_message(self, user_message: str) -> bool:
        """
        Send a message to the agent and stream the response.
        
        Returns True if successful, False otherwise.
        """
        print("\n" + "-" * 70)
        print(f"📤 YOU: {user_message}")
        print("-" * 70)
        
        # Prepare request
        request_body = {
            "module": "general",
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "thread_id": self.thread_id,
            "enable_background_investigation": False,
            "enable_web_search": False,  # Faster for testing
        }
        
        print("\n⏳ Connecting to agent...")
        
        response_content = []
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/agent/agent/stream",
                json=request_body
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"❌ Error: HTTP {response.status_code}")
                    print(f"   {error_text.decode()[:500]}")
                    return False
                
                # Parse SSE events
                event_type = "unknown"
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            await self._handle_event(event_type, data, response_content)
                        except json.JSONDecodeError:
                            pass
            
            # Print final response
            if response_content:
                full_response = "".join(response_content)
                print("\n" + "-" * 70)
                print("📥 AGENT RESPONSE:")
                print("-" * 70)
                print(full_response)
            
            # Always print URLs after first message
            if self.vscode_url or self.mcp_url:
                self._print_urls()
            
            return True
            
        except httpx.TimeoutException:
            print("⚠️ Request timed out. The agent may still be processing.")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    async def _handle_event(self, event_type: str, data: dict, response_content: list):
        """Handle an SSE event with real-time streaming output."""
        
        # Debug: print all events if verbose
        if self.verbose:
            print(f"\n[DEBUG] Event: {event_type} | Data: {str(data)[:500]}")
        
        # Status events
        if event_type == "status":
            status_type = data.get("type", "")
            
            if status_type == "processing":
                print("   🔄 Processing request...")
            
            elif status_type == "sandbox_ready":
                self.sandbox_id = data.get("sandbox_id")
                start_type = data.get("start_type", "")
                print(f"   📦 Sandbox ready: {self.sandbox_id[:30]}... ({start_type})")
            
            elif status_type == "skills_injection":
                category = data.get("category", "?")
                print(f"   📚 Injecting skills for category: {category}")
            
            elif status_type == "skills_loaded":
                count = data.get("skill_count", 0)
                names = data.get("skill_names", [])[:5]
                print(f"   ✅ Loaded {count} skills: {', '.join(names)}{'...' if count > 5 else ''}")
            
            elif status_type == "mcp_check":
                print("   🔧 Checking MCP server...")
            
            elif status_type == "mcp_ready":
                self.mcp_url = data.get("mcp_url")
                start_type = data.get("start_type", "")
                print(f"   ✅ MCP ready! ({start_type})")
                self.log(f"      URL: {self.mcp_url}", "verbose")
            
            elif status_type == "vscode_ready":
                self.vscode_url = data.get("vscode_url")
                print(f"\n   🖥️  VS CODE IS READY!")
                print(f"   👉 {self.vscode_url}")
                print(f"   ↑↑↑ Click to view live code editing ↑↑↑\n")
            
            elif status_type == "codex_ready":
                self.codex_url = data.get("codex_url")
                print(f"   🤖 Codex ready: {self.codex_url}")
            
            elif status_type == "agent_start":
                print("\n   🧠 Agent started thinking...")
                print("   " + "-" * 50)
            
            elif status_type == "complete":
                # Capture URLs from completion event too
                if data.get("vscode_url"):
                    self.vscode_url = data.get("vscode_url")
                if data.get("codex_url"):
                    self.codex_url = data.get("codex_url")
                print("\n   " + "-" * 50)
                print("   ✅ Complete!")
            
            elif status_type == "mcp_waiting":
                elapsed = data.get("elapsed_seconds", "?")
                if self.verbose:
                    print(f"   ⏳ Waiting for MCP... ({elapsed}s)")
            
            else:
                # Log any unknown status types for debugging
                if self.verbose:
                    print(f"   [Unknown status: {status_type}] {data.get('message', '')}")
        
        # =====================================================================
        # MESSAGE EVENTS - Stream actual content in real-time!
        # =====================================================================
        elif event_type == "message":
            content = data.get("content", "")
            if content:
                response_content.append(content)
                # STREAM THE ACTUAL CONTENT - not just dots!
                print(content, end="", flush=True)
        
        # AG-UI Protocol: text_message_content (alternative message format)
        elif event_type == "text_message_content":
            content = data.get("delta", "") or data.get("content", "")
            if content:
                response_content.append(content)
                # STREAM THE ACTUAL CONTENT - not just dots!
                print(content, end="", flush=True)
        
        # =====================================================================
        # TOOL EVENTS - Show tool calls with argument previews
        # =====================================================================
        
        # Legacy tool events
        elif event_type == "tool":
            tool_name = data.get("name", data.get("tool_name", "?"))
            tool_type = data.get("type", "?")
            
            if tool_type == "start":
                print(f"\n   🔧 Tool: {tool_name}", end="")
            elif tool_type == "end":
                print(" ✓")
            else:
                print(f"\n   🔧 Tool {tool_type}: {tool_name}")
        
        # AG-UI Protocol: tool_call_start
        elif event_type == "tool_call_start":
            tool_name = data.get("toolCallName", data.get("tool_name", data.get("name", "?")))
            tool_id = data.get("toolCallId", "?")[:12]
            print(f"\n   🔧 Tool started: {tool_name} (id: {tool_id}...)", flush=True)
        
        # AG-UI Protocol: tool_call_args - show argument preview
        elif event_type == "tool_call_args":
            args_delta = data.get("delta", "")
            if args_delta and self.verbose:
                # Show a preview of the args (truncated)
                preview = args_delta[:100].replace('\n', ' ')
                if len(args_delta) > 100:
                    preview += "..."
                print(f"\n      Args: {preview}", flush=True)
            else:
                # Just show a dot for non-verbose mode
                print(".", end="", flush=True)
        
        # AG-UI Protocol: tool_call_end
        elif event_type == "tool_call_end":
            tool_id = data.get("toolCallId", "?")[:12]
            print(f" ✓ (done)")
        
        # AG-UI Protocol: tool_result - show output preview
        elif event_type == "tool_result":
            tool_name = data.get("toolName", "?")
            result = data.get("content", data.get("result", ""))
            if result:
                result_str = str(result)
                # Always show at least a snippet of the result
                preview = result_str[:200].replace('\n', ' ').strip()
                if len(result_str) > 200:
                    preview += "..."
                print(f"   📋 {tool_name} result: {preview}")
        
        # =====================================================================
        # REASONING EVENTS - Show thinking content (especially in verbose mode)
        # =====================================================================
        elif event_type == "reasoning_start":
            print("\n   💭 Thinking...", flush=True)
            print("   " + "-" * 40)
        
        elif event_type == "reasoning_message_content":
            delta = data.get("delta", "")
            if delta:
                if self.verbose:
                    # In verbose mode, show the actual reasoning content
                    print(delta, end="", flush=True)
                else:
                    # In normal mode, just show dots for progress
                    print(".", end="", flush=True)
        
        elif event_type == "reasoning_end":
            print("\n   " + "-" * 40)
            print("   💭 (done thinking)")
        
        # =====================================================================
        # ERROR/WARNING EVENTS
        # =====================================================================
        elif event_type == "warning":
            message = data.get("message", "?")
            print(f"   ⚠️ Warning: {message}")
        
        elif event_type == "error":
            message = data.get("message", "?")
            error_type = data.get("type", "unknown")
            print(f"   ❌ Error [{error_type}]: {message}")
            # Log full error data in verbose mode
            if self.verbose:
                print(f"      Full error data: {data}")
        
        # HITL interrupt events
        elif event_type == "interrupt":
            content = data.get("content", "Human input needed")
            options = data.get("options", [])
            print(f"\n   🖐️ INTERRUPT: {content}")
            if options:
                print(f"      Options: {[o.get('text', o) for o in options]}")
        
        # Unknown events - always log in verbose mode
        elif self.verbose:
            print(f"   [Unknown event: {event_type}] Data keys: {list(data.keys())}")

    
    async def run_interactive_loop(self):
        """Run the interactive chat loop."""
        print("\n💬 Ready to chat! Type your message below.\n")
        
        # Optionally send initial message to trigger sandbox creation
        print("TIP: Ask the agent to 'build a calculator app' to see it code!\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ('quit', 'exit', 'q'):
                    print("\n👋 Goodbye!")
                    break
                
                if user_input.lower() == 'urls':
                    self._print_urls()
                    continue
                
                if user_input.lower() == 'help':
                    print("\nCommands:")
                    print("  quit/exit - Exit the chat")
                    print("  urls      - Show all sandbox URLs")
                    print("  help      - Show this help")
                    print("\nOr just type a message to chat with the agent!\n")
                    continue
                
                # Send message to agent
                await self.send_message(user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Goodbye!")
                break
    
    async def cleanup(self):
        """Cleanup resources including sandbox."""
        # Kill the sandbox to save resources (test-only behavior)
        if self.sandbox_id:
            try:
                print(f"\n   🗑️ Cleaning up sandbox {self.sandbox_id[:20]}...")
                response = await self.client.delete(
                    f"{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=30.0,
                )
                if response.status_code in (200, 204):
                    print(f"   ✅ Sandbox cleaned up successfully")
                else:
                    print(f"   ⚠️ Sandbox cleanup returned: {response.status_code}")
            except Exception as e:
                print(f"   ⚠️ Sandbox cleanup failed: {e}")
        
        if self.client:
            await self.client.aclose()


# =============================================================================
# Main
# =============================================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Interactive chat with the agent backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script provides an interactive chat interface to the agent.
It displays all sandbox URLs (VS Code, MCP, Codex) as they become available.

Example:
    python test_agent_endpoints_interactive.py
    python test_agent_endpoints_interactive.py --verbose
    python test_agent_endpoints_interactive.py --base-url http://localhost:8001
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
    chat = InteractiveAgentChat(
        base_url=args.base_url,
        verbose=args.verbose
    )
    
    try:
        if not await chat.setup():
            sys.exit(1)
        
        await chat.run_interactive_loop()
        
    finally:
        await chat.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(0)
