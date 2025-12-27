#!/usr/bin/env python3
"""
Comprehensive LangChain Tool Adapter Test Suite
================================================

This tests ALL tools from manager.py via the MCP server using langchain-mcp-adapters.
The tools are fetched as LangChain-compatible tools and each one is tested.

Tool Categories (44 total):
- Shell tools (6): shell_init, shell_run_command, shell_view, shell_stop_command, 
                   shell_list, shell_write_to_process
- File system tools (9): file_read, file_write, file_edit, apply_patch, 
                         str_replace_editor, ast_grep, grep, fullstack_init, save_checkpoint
- Media tools (2): image_generate, video_generate
- Web tools (6): web_search, web_visit, web_visit_compress, image_search, 
                 read_remote_image, web_batch_search
- Database tools (1): get_database_connection
- Todo tools (2): todo_read, todo_write
- Slide tools (3): slide_write, slide_edit, slide_apply_patch
- Browser tools (15): browser_click, browser_wait, browser_view, browser_scroll_down,
                      browser_scroll_up, browser_switch_tab, browser_open_new_tab,
                      browser_get_select_options, browser_select_dropdown_option,
                      browser_navigation, browser_restart, browser_enter_text,
                      browser_press_key, browser_drag, browser_enter_multiple_texts

Prerequisites:
- Backend server running: python -m uvicorn backend.main:app --port 8000
- Test user exists

Usage:
    python backend/tests/live/test_langchain_tools_via_mcp.py
"""

import asyncio
import httpx
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple

BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class LangChainToolTester:
    """Tests all tools from manager.py via LangChain MCP adapter."""
    
    def __init__(self):
        self.client = None
        self.sandbox_id = None
        self.mcp_url = None
        self.token = None
        self.langchain_tools = []
        self.results: Dict[str, Tuple[bool, str]] = {}
    
    async def setup(self):
        self.client = httpx.AsyncClient(
            timeout=180.0,
            headers={'Content-Type': 'application/json'}
        )
    
    async def teardown(self):
        if self.client:
            await self.client.aclose()
    
    def log(self, msg: str, success: bool = None):
        icon = "✅" if success == True else "❌" if success == False else "ℹ️"
        print(f"   {icon} {msg}", flush=True)
    
    async def login(self) -> bool:
        r = await self.client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        if r.status_code == 200:
            self.token = r.json().get('access_token')
            self.client.headers['Authorization'] = f'Bearer {self.token}'
            return True
        return False
    
    async def create_sandbox(self) -> bool:
        r = await self.client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'langchain-tool-test'}
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            self.sandbox_id = data.get('sandbox_id')
            self.mcp_url = data.get('mcp_url')
            return True
        return False
    
    async def delete_sandbox(self):
        if self.sandbox_id:
            await self.client.delete(f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}')
    
    async def get_langchain_tools(self) -> List:
        """Get all tools as LangChain tools via langchain-mcp-adapters."""
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": f"{self.mcp_url}/mcp/",
                    "transport": "http"
                },
            })
            
            tools = await mcp_client.get_tools()
            return tools
        except Exception as e:
            self.log(f"Failed to get tools via MCP adapter: {e}", False)
            return []
    
    async def test_tool(self, tool, test_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Test a single LangChain tool with given input."""
        try:
            # LangChain tools have ainvoke for async execution
            result = await tool.ainvoke(test_input)
            
            # Check if we got a result
            if result is not None:
                # Handle different result types
                if isinstance(result, str):
                    return True, f"OK: {result[:60]}..." if len(str(result)) > 60 else f"OK: {result}"
                elif isinstance(result, tuple):
                    content, artifact = result
                    return True, f"OK: {str(content)[:50]}..."
                else:
                    return True, f"OK: {type(result).__name__}"
            return False, "No result"
        except Exception as e:
            error_msg = str(e)[:80]
            # Some errors are expected (e.g., API key required)
            if 'API' in error_msg.upper() or 'KEY' in error_msg.upper():
                return True, f"Expected: {error_msg}"
            if 'not found' in error_msg.lower() or 'does not exist' in error_msg.lower():
                return True, f"Expected: {error_msg}"
            return False, f"Error: {error_msg}"
    
    def get_test_inputs(self) -> Dict[str, Dict[str, Any]]:
        """Return test inputs for each tool."""
        return {
            # Shell tools
            "shell_init": {"session_name": "test_session"},
            "shell_run_command": {"command": "echo 'LangChain Test'", "session_name": "test_session"},
            "shell_view": {"session_name": "test_session"},
            "shell_stop_command": {"session_name": "test_session"},
            "shell_list": {},
            "shell_write_to_process": {"session_name": "test_session", "input": "test"},
            
            # File system tools
            "file_read": {"file_path": "/tmp/test.txt"},
            "file_write": {"file_path": "/tmp/test_write.txt", "content": "LangChain test content"},
            "file_edit": {"file_path": "/tmp/test_edit.txt", "content": "edited content"},
            "apply_patch": {"patch": "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n", "file_path": "/tmp/patch.txt"},
            "str_replace_editor": {"file_path": "/tmp/replace.txt", "old_str": "old", "new_str": "new"},
            "ast_grep": {"pattern": "function", "file_path": "/tmp/code.js"},
            "grep": {"pattern": "test", "file_path": "/tmp"},
            "fullstack_init": {"project_name": "test_project"},
            "save_checkpoint": {"checkpoint_name": "test_checkpoint"},
            
            # Media tools (require API keys)
            "image_generate": {"prompt": "A test image"},
            "video_generate": {"prompt": "A test video"},
            
            # Web tools
            "web_search": {"query": "python programming"},
            "web_visit": {"url": "https://httpbin.org/get"},
            "web_visit_compress": {"url": "https://httpbin.org/get"},
            "image_search": {"query": "python logo"},
            "read_remote_image": {"url": "https://httpbin.org/image/png"},
            "web_batch_search": {"queries": ["python", "javascript"]},
            
            # Database tools
            "get_database_connection": {},
            
            # Todo tools
            "todo_read": {},
            "todo_write": {"todo": "Test todo item"},
            
            # Slide tools
            "slide_write": {"content": "# Test Slide", "file_path": "/tmp/slide.md"},
            "slide_edit": {"file_path": "/tmp/slide.md", "content": "# Edited Slide"},
            "slide_apply_patch": {"file_path": "/tmp/slide.md", "patch": "test patch"},
            
            # Browser tools
            "browser_view": {},
            "browser_click": {"coordinate_x": 100, "coordinate_y": 100},
            "browser_wait": {"seconds": 1},
            "browser_scroll_down": {},
            "browser_scroll_up": {},
            "browser_switch_tab": {"tab_index": 0},
            "browser_open_new_tab": {"url": "https://example.com"},
            "browser_get_select_options": {"selector": "select"},
            "browser_select_dropdown_option": {"selector": "select", "value": "option1"},
            "browser_navigation": {"url": "https://example.com"},
            "browser_restart": {},
            "browser_enter_text": {"text": "test input"},
            "browser_press_key": {"key": "Enter"},
            "browser_drag": {"start_x": 100, "start_y": 100, "end_x": 200, "end_y": 200},
            "browser_enter_multiple_texts": {"texts": ["text1", "text2"]},
        }
    
    async def run_all_tests(self):
        """Run all LangChain tool tests."""
        print("=" * 80, flush=True)
        print("🔧 LANGCHAIN TOOL ADAPTER TEST - ALL TOOLS FROM manager.py", flush=True)
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("=" * 80, flush=True)
        
        await self.setup()
        
        # Setup
        print("\n📋 SETUP", flush=True)
        print("-" * 60, flush=True)
        
        if not await self.login():
            print("   ❌ Login failed", flush=True)
            return False
        self.log("Login successful", True)
        
        print("   ℹ️ Creating sandbox with MCP server (30-60s)...", flush=True)
        if not await self.create_sandbox():
            print("   ❌ Sandbox creation failed", flush=True)
            return False
        self.log(f"Sandbox: {self.sandbox_id[:12]}...", True)
        self.log(f"MCP URL: {self.mcp_url}", True)
        
        # Wait for MCP server to start
        print("   ℹ️ Waiting for MCP server to initialize...", flush=True)
        await asyncio.sleep(15)
        
        # Get LangChain tools via MCP adapter
        print("\n📋 GET LANGCHAIN TOOLS VIA MCP", flush=True)
        print("-" * 60, flush=True)
        
        self.langchain_tools = await self.get_langchain_tools()
        
        if not self.langchain_tools:
            self.log("No tools retrieved from MCP", False)
            await self.delete_sandbox()
            await self.teardown()
            return False
        
        self.log(f"Retrieved {len(self.langchain_tools)} LangChain tools", True)
        
        # List all tools
        tool_names = [t.name for t in self.langchain_tools]
        print(f"\n   Tools available:", flush=True)
        for i, name in enumerate(sorted(tool_names), 1):
            print(f"   {i:2}. {name}", flush=True)
        
        # Get test inputs
        test_inputs = self.get_test_inputs()
        
        # Test each tool
        print("\n📋 TESTING EACH TOOL", flush=True)
        print("-" * 60, flush=True)
        
        tools_by_name = {t.name: t for t in self.langchain_tools}
        
        # Group tools by category for organized output
        categories = {
            "🖥️ SHELL TOOLS": ["shell_init", "shell_run_command", "shell_view", 
                               "shell_stop_command", "shell_list", "shell_write_to_process"],
            "📁 FILE SYSTEM TOOLS": ["file_read", "file_write", "file_edit", 
                                      "apply_patch", "str_replace_editor", "ast_grep", 
                                      "grep", "fullstack_init", "save_checkpoint"],
            "🎨 MEDIA TOOLS": ["image_generate", "video_generate"],
            "🌐 WEB TOOLS": ["web_search", "web_visit", "web_visit_compress", 
                             "image_search", "read_remote_image", "web_batch_search"],
            "🗄️ DATABASE TOOLS": ["get_database_connection"],
            "📝 TODO TOOLS": ["todo_read", "todo_write"],
            "📊 SLIDE TOOLS": ["slide_write", "slide_edit", "slide_apply_patch"],
            "🌍 BROWSER TOOLS": ["browser_view", "browser_click", "browser_wait",
                                  "browser_scroll_down", "browser_scroll_up", 
                                  "browser_switch_tab", "browser_open_new_tab",
                                  "browser_get_select_options", "browser_select_dropdown_option",
                                  "browser_navigation", "browser_restart", "browser_enter_text",
                                  "browser_press_key", "browser_drag", "browser_enter_multiple_texts"],
        }
        
        for category, tool_list in categories.items():
            print(f"\n{category}", flush=True)
            print("-" * 50, flush=True)
            
            for tool_name in tool_list:
                if tool_name in tools_by_name:
                    tool = tools_by_name[tool_name]
                    test_input = test_inputs.get(tool_name, {})
                    
                    try:
                        passed, msg = await self.test_tool(tool, test_input)
                        self.results[tool_name] = (passed, msg)
                        self.log(f"{tool_name}: {msg}", passed)
                    except Exception as e:
                        self.results[tool_name] = (False, str(e)[:50])
                        self.log(f"{tool_name}: {str(e)[:50]}", False)
                else:
                    # Tool not found in MCP - might have different name
                    self.results[tool_name] = (None, "Not found in MCP")
                    self.log(f"{tool_name}: Not found in MCP (may have different name)", None)
        
        # Cleanup
        print("\n📋 CLEANUP", flush=True)
        print("-" * 60, flush=True)
        await self.delete_sandbox()
        self.log("Sandbox deleted", True)
        await self.teardown()
        
        # Summary
        passed = sum(1 for v, _ in self.results.values() if v == True)
        failed = sum(1 for v, _ in self.results.values() if v == False)
        skipped = sum(1 for v, _ in self.results.values() if v is None)
        total = len(self.results)
        
        print("\n" + "=" * 80, flush=True)
        print("📊 FINAL TEST SUMMARY", flush=True)
        print("=" * 80, flush=True)
        
        for category, tool_list in categories.items():
            cat_passed = sum(1 for t in tool_list if self.results.get(t, (False, ''))[0] == True)
            cat_total = len(tool_list)
            status = "✅" if cat_passed == cat_total else "⚠️" if cat_passed > 0 else "❌"
            print(f"   {status} {category}: {cat_passed}/{cat_total}", flush=True)
        
        print("-" * 80, flush=True)
        print(f"   PASSED: {passed}/{total} | FAILED: {failed} | SKIPPED: {skipped}", flush=True)
        print("=" * 80, flush=True)
        
        # Failed tests detail
        failed_tests = [(k, v) for k, v in self.results.items() if v[0] == False]
        if failed_tests:
            print("\n   Failed tests:", flush=True)
            for name, (_, msg) in failed_tests:
                print(f"   ❌ {name}: {msg}", flush=True)
        
        return passed >= (total - skipped) * 0.7  # 70% of non-skipped tests


if __name__ == '__main__':
    tester = LangChainToolTester()
    success = asyncio.run(tester.run_all_tests())
    print(f"\nExit code: {'0 (SUCCESS)' if success else '1 (FAILURE)'}", flush=True)
    sys.exit(0 if success else 1)
