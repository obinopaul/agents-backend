#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Interactive Design Tools Test

This script tests the design tools by asking the agent to create diagrams
using the Draw.io design module.

It demonstrates:
- design_init: Initialize a diagram session
- design_create_diagram: Create diagrams from AI-generated XML
- design_edit_diagram: Modify diagrams with operations
- design_get_diagram: Retrieve current diagram state
- design_export_diagram: Save diagrams to .drawio files

Features:
- Interactive REPL-style chat
- Displays all sandbox URLs including Design MCP viewer
- Streams agent responses in real-time
- Shows tool calls and their results
- Prints MCP tool URLs

Usage:
    python backend/tests/live/backend_endpoints/test_design_interactive.py
    
    # With verbose output
    python backend/tests/live/backend_endpoints/test_design_interactive.py --verbose

Prerequisites:
    1. Backend server running at http://127.0.0.1:8000 (docker-compose up -d)
    2. Test user exists: sandbox_test / TestPass123!
       Run: python backend/tests/create_test_user.py
    3. E2B_API_KEY configured in backend/.env
    4. Sandbox image built with Design MCP Server (e2b template build)
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

# Port configurations (matching backend/core/conf.py)
SANDBOX_PORTS = {
    "mcp_server": 6060,
    "code_server": 9000,
    "latex_editor": 9001,
    "design_mcp": 6002,
    "excalidraw": 6003,
    "codex_sse": 1324,
    "graphiti_mcp": 8500,  # Graphiti Knowledge Graph MCP Server
}


# =============================================================================
# Design Test Prompts
# =============================================================================

DESIGN_TEST_PROMPTS = [
    "Initialize a new diagram session and show me the viewer URL",
    "Create a simple flowchart with Start -> Process -> Decision -> End",
    "Create an AWS architecture diagram with EC2, RDS, and S3",
    "Get the current diagram XML and show me the cell IDs",
    "Add a new box labeled 'New Component' to the diagram",
    "Export the diagram to a file called 'my-architecture.drawio'",
]


# =============================================================================
# Interactive Design Chat
# =============================================================================

class InteractiveDesignChat:
    """
    Interactive chat with the agent backend for testing design tools.
    
    Displays all sandbox URLs including Design MCP viewer URL.
    """
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.token: Optional[str] = None
        self.token_type: str = "Bearer"
        self.client: Optional[httpx.AsyncClient] = None
        self.thread_id: str = f"design-test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Sandbox URLs (captured from SSE events)
        self.sandbox_id: Optional[str] = None
        self.mcp_url: Optional[str] = None
        self.vscode_url: Optional[str] = None
        self.codex_url: Optional[str] = None
        self.design_url: Optional[str] = None  # Design MCP viewer URL
        self.latex_url: Optional[str] = None
        self.excalidraw_url: Optional[str] = None
        self.graphiti_url: Optional[str] = None  # Graphiti Knowledge Graph MCP URL
    
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
                'User-Agent': 'DesignTestChat/1.0',
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
        print("🎨 INTERACTIVE DESIGN TOOLS TEST")
        print("=" * 70)
        print(f"   Backend URL: {self.base_url}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print("\nThis test exercises the design tools (Draw.io integration).")
        print("\nSandbox Ports:")
        for name, port in SANDBOX_PORTS.items():
            print(f"   - {name}: {port}")
        print("\nType your message and press Enter. Type 'quit' or 'exit' to stop.")
        print("Type 'prompts' to see suggested test prompts.")
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
        
        # Design MCP URL (most relevant for this test)
        if self.design_url:
            print("*  🎨 DESIGN VIEWER (draw.io):                                     *")
            if len(self.design_url) > 60:
                print(f"*  👉 {self.design_url[:60]}... *")
            else:
                print(f"*  👉 {self.design_url:<62}*")
        else:
            print("*  🎨 Design: Not yet available                                    *")
        
        # Excalidraw URL (for diagram editing)
        if self.excalidraw_url:
            if len(self.excalidraw_url) > 60:
                print(f"*  🎨 EXCALIDRAW: {self.excalidraw_url[:55]}...   *")
            else:
                print(f"*  🎨 EXCALIDRAW: {self.excalidraw_url:<56}*")
        else:
            print("*  🎨 Excalidraw: Not yet available                                *")
        
        print("*" + " " * 68 + "*")
        
        if self.vscode_url:
            if len(self.vscode_url) > 60:
                print(f"*  🖥️ VS Code: {self.vscode_url[:55]}...   *")
            else:
                print(f"*  🖥️ VS Code: {self.vscode_url:<56}*")
        
        if self.mcp_url:
            if len(self.mcp_url) > 60:
                print(f"*  🔧 MCP: {self.mcp_url[:55]}...   *")
            else:
                print(f"*  🔧 MCP: {self.mcp_url:<58}*")
        
        if self.latex_url:
            if len(self.latex_url) > 60:
                print(f"*  📄 LaTeX: {self.latex_url[:53]}... *")
            else:
                print(f"*  📄 LaTeX: {self.latex_url:<56}*")
        
        if self.codex_url:
            if len(self.codex_url) > 60:
                print(f"*  🤖 Codex: {self.codex_url[:53]}... *")
            else:
                print(f"*  🤖 Codex: {self.codex_url:<56}*")
        
        if self.graphiti_url:
            if len(self.graphiti_url) > 60:
                print(f"*  🧠 Graphiti: {self.graphiti_url[:51]}... *")
            else:
                print(f"*  🧠 Graphiti: {self.graphiti_url:<54}*")
        
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
            "module": "design",
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "thread_id": self.thread_id,
            "enable_background_investigation": False,
            "enable_web_search": False,
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
            if any([self.vscode_url, self.mcp_url, self.design_url]):
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
                
                # Build Design URL from sandbox public URL pattern
                # Note: The actual URL construction depends on your E2B setup
            
            elif status_type == "mcp_ready":
                self.mcp_url = data.get("mcp_url")
                start_type = data.get("start_type", "")
                print(f"   ✅ MCP ready! ({start_type})")
                print(f"      MCP URL: {self.mcp_url}")
            
            elif status_type == "design_ready":
                self.design_url = data.get("design_url")
                print(f"   🎨 Design MCP Server ready!")
                print(f"      Design URL: {self.design_url}")
            
            elif status_type == "vscode_ready":
                self.vscode_url = data.get("vscode_url")
                print(f"\n   🖥️  VS CODE IS READY!")
                print(f"   👉 {self.vscode_url}")
            
            elif status_type == "excalidraw_ready":
                self.excalidraw_url = data.get("excalidraw_url")
                print(f"   🎨 Excalidraw ready!")
                print(f"      Excalidraw URL: {self.excalidraw_url}")
            
            elif status_type == "latex_ready":
                self.latex_url = data.get("latex_url")
                print(f"   📄 LaTeX Editor ready!")
                print(f"      LaTeX URL: {self.latex_url}")
            
            elif status_type == "graphiti_ready":
                self.graphiti_url = data.get("graphiti_url")
                print(f"   🧠 Graphiti Knowledge Graph ready!")
                print(f"      Graphiti URL: {self.graphiti_url}")
            
            elif status_type == "agent_start":
                print("\n   🧠 Agent started thinking...")
            
            elif status_type == "complete":
                if data.get("vscode_url"):
                    self.vscode_url = data.get("vscode_url")
                if data.get("codex_url"):
                    self.codex_url = data.get("codex_url")
                if data.get("design_url"):
                    self.design_url = data.get("design_url")
                if data.get("excalidraw_url"):
                    self.excalidraw_url = data.get("excalidraw_url")
                if data.get("latex_url"):
                    self.latex_url = data.get("latex_url")
                if data.get("graphiti_url"):
                    self.graphiti_url = data.get("graphiti_url")
                print("\n   ✅ Complete!")
        
        # Message events
        elif event_type == "message":
            content = data.get("content", "")
            if content:
                response_content.append(content)
                print(content, end="", flush=True)
        
        elif event_type == "text_message_content":
            content = data.get("delta", "") or data.get("content", "")
            if content:
                response_content.append(content)
                print(content, end="", flush=True)
        
        # Tool events - IMPORTANT for design testing
        elif event_type == "tool_call_start":
            tool_name = data.get("toolCallName", data.get("tool_name", data.get("name", "?")))
            tool_id = data.get("toolCallId", "?")[:12]
            
            # Highlight design-specific tools
            if "design" in tool_name.lower():
                print(f"\n   🎨 DESIGN TOOL: {tool_name} (id: {tool_id}...)", flush=True)
            else:
                print(f"\n   🔧 Tool: {tool_name} (id: {tool_id}...)", flush=True)
        
        elif event_type == "tool_call_args":
            if self.verbose:
                args_delta = data.get("delta", "")
                if args_delta:
                    preview = args_delta[:200].replace('\n', ' ')
                    if len(args_delta) > 200:
                        preview += "..."
                    print(f"\n      Args: {preview}", flush=True)
            else:
                print(".", end="", flush=True)
        
        elif event_type == "tool_call_end":
            print(" ✓")
        
        elif event_type == "tool_result":
            tool_name = data.get("toolName", "?")
            result = data.get("content", data.get("result", ""))
            
            # Show more detail for design tools
            if "design" in tool_name.lower() and result:
                result_str = str(result)
                # Show session_id and viewer_url if present
                if "session_id" in result_str:
                    try:
                        result_data = json.loads(result_str) if isinstance(result_str, str) else result
                        if isinstance(result_data, dict):
                            if result_data.get("viewer_url"):
                                self.design_url = result_data["viewer_url"]
                                print(f"\n   🎨 Diagram Viewer: {self.design_url}")
                            if result_data.get("session_id"):
                                print(f"   📋 Session ID: {result_data['session_id']}")
                    except:
                        pass
                
                preview = result_str[:300].replace('\n', ' ').strip()
                if len(result_str) > 300:
                    preview += "..."
                print(f"   📋 {tool_name} result: {preview}")
            elif result:
                result_str = str(result)
                preview = result_str[:200].replace('\n', ' ').strip()
                if len(result_str) > 200:
                    preview += "..."
                print(f"   📋 {tool_name} result: {preview}")
        
        # Error events
        elif event_type == "error":
            message = data.get("message", "?")
            error_type = data.get("type", "unknown")
            print(f"   ❌ Error [{error_type}]: {message}")
    
    async def run_interactive_loop(self):
        """Run the interactive chat loop."""
        print("\n💬 Ready to test design tools! Type your message below.\n")
        print("TIP: Type 'prompts' to see suggested test prompts.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ('quit', 'exit', 'q'):
                    print("\n👋 Goodbye!")
                    break
                
                if user_input.lower() == 'urls':
                    self._print_urls()
                    continue
                
                if user_input.lower() == 'prompts':
                    print("\nSuggested test prompts:")
                    for i, prompt in enumerate(DESIGN_TEST_PROMPTS, 1):
                        print(f"  {i}. {prompt}")
                    print("\nYou can copy-paste these or type your own.\n")
                    continue
                
                if user_input.lower() == 'help':
                    print("\nCommands:")
                    print("  quit/exit - Exit the chat")
                    print("  urls      - Show all sandbox URLs")
                    print("  prompts   - Show suggested test prompts")
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
        description="Interactive test for design tools (Draw.io integration)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script tests the design tools which integrate Draw.io into the sandbox.

Example:
    python test_design_interactive.py
    python test_design_interactive.py --verbose
    python test_design_interactive.py --base-url http://localhost:8001
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
    chat = InteractiveDesignChat(
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
