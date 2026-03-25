#!/usr/bin/env python3
"""
Comprehensive LangChain Tools Test

This script tests all 44+ LangChain tools from the langchain_tools registry:
1. First tests tool creation for each category
2. Then tests a real LangChain agent with available tools

Usage:
    python backend/tests/live/test_langchain_tools_comprehensive.py
"""

import asyncio
import time
import httpx
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple


class ComprehensiveLangChainToolsTest:
    """Comprehensive test suite for all LangChain tools."""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.test_user = {"username": "test@example.com", "password": "P@ssw0rd123!"}
        self.access_token = None
        self.sandbox_id = None
        self.sandbox_url = None
        self.results: Dict[str, Tuple[bool, str]] = {}
    
    def log(self, msg: str, level: str = "info"):
        icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
        icon = icons.get(level, "•")
        print(f"   {icon} {msg}", flush=True)
    
    def log_section(self, title: str):
        print(f"\n{'='*60}", flush=True)
        print(f"📋 {title}", flush=True)
        print(f"{'='*60}", flush=True)
    
    # =========================================================================
    # PHASE 1: Test Tool Creation (No Sandbox Required)
    # =========================================================================
    
    async def test_tool_creation(self):
        """Test that all tool categories can be created."""
        self.log_section("PHASE 1: Tool Creation Tests")
        
        # Test 1: Import the registry
        try:
            start = time.time()
            from backend.src.tool_server.tools.langchain_tools import (
                get_langchain_agent_tools,
                get_langchain_web_tools,
                get_langchain_media_tools,
            )
            self.log(f"Registry import: {time.time()-start:.2f}s", "success")
            self.results["import_registry"] = (True, f"{time.time()-start:.2f}s")
        except Exception as e:
            self.log(f"Registry import failed: {e}", "error")
            self.results["import_registry"] = (False, str(e))
            return False
        
        # Test 2: Agent tools (no dependencies)
        try:
            start = time.time()
            agent_tools = get_langchain_agent_tools()
            self.log(f"Agent tools: {len(agent_tools)} tools in {time.time()-start:.2f}s", "success")
            for tool in agent_tools:
                self.log(f"  → {tool.name}: {tool.description[:50]}...")
            self.results["agent_tools"] = (True, f"{len(agent_tools)} tools")
        except Exception as e:
            self.log(f"Agent tools failed: {e}", "error")
            self.results["agent_tools"] = (False, str(e))
        
        # Test 3: Web tools (credential-based, may need API keys)
        try:
            start = time.time()
            mock_credential = {"session_id": "test", "user_api_key": "test"}
            web_tools = get_langchain_web_tools(mock_credential)
            self.log(f"Web tools: {len(web_tools)} tools in {time.time()-start:.2f}s", "success")
            for tool in web_tools:
                self.log(f"  → {tool.name}")
            self.results["web_tools"] = (True, f"{len(web_tools)} tools")
        except Exception as e:
            self.log(f"Web tools failed: {e}", "error")
            self.results["web_tools"] = (False, str(e))
        
        # Test 4: Media tools (credential-based)
        try:
            start = time.time()
            mock_credential = {"session_id": "test", "user_api_key": "test"}
            media_tools = get_langchain_media_tools(mock_credential)
            self.log(f"Media tools: {len(media_tools)} tools in {time.time()-start:.2f}s", "success")
            for tool in media_tools:
                self.log(f"  → {tool.name}")
            self.results["media_tools"] = (True, f"{len(media_tools)} tools")
        except Exception as e:
            self.log(f"Media tools failed: {e}", "error")
            self.results["media_tools"] = (False, str(e))
        
        return True
    
    # =========================================================================
    # PHASE 2: Sandbox Integration Test
    # =========================================================================
    
    async def login(self) -> bool:
        """Login to get access token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    data=self.test_user,
                    timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    self.access_token = data.get("access_token")
                    self.log("Login successful", "success")
                    self.results["login"] = (True, "")
                    return True
                else:
                    self.log(f"Login failed: {response.status_code}", "error")
                    self.results["login"] = (False, f"Status {response.status_code}")
                    return False
        except Exception as e:
            self.log(f"Login error: {e}", "error")
            self.results["login"] = (False, str(e))
            return False
    
    async def create_sandbox(self) -> bool:
        """Create a sandbox for testing."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/agent/sandboxes/sandboxes",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json={},
                    timeout=120.0
                )
                if response.status_code == 200:
                    data = response.json()
                    self.sandbox_id = data.get("sandbox_id")
                    self.sandbox_url = data.get("sandbox_url")
                    self.log(f"Sandbox created: {self.sandbox_id}", "success")
                    self.results["sandbox_create"] = (True, self.sandbox_id)
                    return True
                else:
                    self.log(f"Sandbox creation failed: {response.status_code}", "error")
                    self.results["sandbox_create"] = (False, f"Status {response.status_code}")
                    return False
        except Exception as e:
            self.log(f"Sandbox error: {e}", "error")
            self.results["sandbox_create"] = (False, str(e))
            return False
    
    async def test_sandbox_tools(self):
        """Test tools that require sandbox."""
        self.log_section("PHASE 2: Sandbox Integration Tests")
        
        # Login and create sandbox
        if not await self.login():
            self.log("Cannot proceed without login", "warning")
            return
        
        if not await self.create_sandbox():
            self.log("Cannot proceed without sandbox", "warning")
            return
        
        # Test shell/file/productivity tools via REST API
        await self.test_shell_via_rest()
        await self.test_file_via_rest()
        
        # Cleanup
        await self.delete_sandbox()
    
    async def test_shell_via_rest(self):
        """Test shell commands via sandbox REST API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}/run-cmd",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json={"command": "echo 'Hello from LangChain test'"},
                    timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json()
                    output = data.get("output", "")[:100]
                    self.log(f"Shell test: {output}", "success")
                    self.results["shell_via_rest"] = (True, output)
                else:
                    self.log(f"Shell test failed: {response.status_code}", "error")
                    self.results["shell_via_rest"] = (False, f"Status {response.status_code}")
        except Exception as e:
            self.log(f"Shell test error: {e}", "error")
            self.results["shell_via_rest"] = (False, str(e))
    
    async def test_file_via_rest(self):
        """Test file operations via sandbox REST API."""
        try:
            async with httpx.AsyncClient() as client:
                # Write file
                response = await client.post(
                    f"{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}/write-file",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json={"path": "/tmp/langchain_test.txt", "content": "LangChain test file"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    # Read file back
                    response = await client.post(
                        f"{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}/read-file",
                        headers={"Authorization": f"Bearer {self.access_token}"},
                        json={"path": "/tmp/langchain_test.txt"},
                        timeout=30.0
                    )
                    if response.status_code == 200:
                        self.log("File read/write test passed", "success")
                        self.results["file_via_rest"] = (True, "read/write OK")
                        return
                
                self.log(f"File test failed: {response.status_code}", "error")
                self.results["file_via_rest"] = (False, f"Status {response.status_code}")
        except Exception as e:
            self.log(f"File test error: {e}", "error")
            self.results["file_via_rest"] = (False, str(e))
    
    async def delete_sandbox(self):
        """Clean up sandbox."""
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{self.base_url}/agent/sandboxes/sandboxes/{self.sandbox_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=30.0
                )
                self.log("Sandbox deleted", "success")
        except Exception as e:
            self.log(f"Sandbox deletion error: {e}", "warning")
    
    # =========================================================================
    # PHASE 3: LangChain Agent Test
    # =========================================================================
    
    async def test_langchain_agent(self):
        """Test a LangChain agent with the tools."""
        self.log_section("PHASE 3: LangChain Agent Test")
        
        try:
            # Import LangChain components
            from langgraph.prebuilt import create_react_agent
            from backend.src.llms.llm import get_llm
            from backend.src.tool_server.tools.langchain_tools import get_langchain_agent_tools
            
            # Get LLM
            start = time.time()
            llm = get_llm()
            self.log(f"LLM loaded in {time.time()-start:.2f}s", "success")
            
            # Get tools
            tools = get_langchain_agent_tools()
            self.log(f"Loaded {len(tools)} tools for agent", "success")
            
            # Create agent
            start = time.time()
            agent = create_react_agent(llm, tools)
            self.log(f"Agent created in {time.time()-start:.2f}s", "success")
            
            # Test agent invocation
            self.log("Invoking agent with test task...", "info")
            start = time.time()
            messages = [{"role": "user", "content": "Say hello to the user using the message_user tool"}]
            
            response = await asyncio.wait_for(
                asyncio.to_thread(agent.invoke, {"messages": messages}),
                timeout=60.0
            )
            
            # Check response
            if response and "messages" in response:
                self.log(f"Agent responded in {time.time()-start:.2f}s", "success")
                self.results["agent_invoke"] = (True, f"{time.time()-start:.2f}s")
                
                # Log the response
                for msg in response["messages"][-3:]:
                    if hasattr(msg, 'content'):
                        content = str(msg.content)[:200]
                        self.log(f"  → {type(msg).__name__}: {content}...", "info")
            else:
                self.log("Agent returned unexpected response", "warning")
                self.results["agent_invoke"] = (False, "Unexpected response")
            
        except asyncio.TimeoutError:
            self.log("Agent invocation timed out (60s)", "error")
            self.results["agent_invoke"] = (False, "Timeout")
        except ImportError as e:
            self.log(f"Missing dependency: {e}", "error")
            self.results["agent_invoke"] = (False, str(e))
        except Exception as e:
            self.log(f"Agent test error: {e}", "error")
            import traceback
            traceback.print_exc()
            self.results["agent_invoke"] = (False, str(e))
    
    # =========================================================================
    # Summary
    # =========================================================================
    
    def print_summary(self):
        """Print test summary."""
        self.log_section("TEST SUMMARY")
        
        passed = sum(1 for v, _ in self.results.values() if v)
        total = len(self.results)
        
        print(f"\n   Results: {passed}/{total} passed ({100*passed//total if total else 0}%)\n")
        
        for test_name, (success, detail) in self.results.items():
            icon = "✅" if success else "❌"
            detail_str = f" - {detail}" if detail else ""
            print(f"   {icon} {test_name}{detail_str}")
        
        print(f"\n{'='*60}\n")
        return passed == total
    
    async def run_all_tests(self):
        """Run all test phases."""
        print("=" * 60, flush=True)
        print("🔧 COMPREHENSIVE LANGCHAIN TOOLS TEST", flush=True)
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("=" * 60, flush=True)
        
        # Phase 1: Tool creation tests
        await self.test_tool_creation()
        
        # Phase 2: Sandbox integration tests
        await self.test_sandbox_tools()
        
        # Phase 3: LangChain agent test
        await self.test_langchain_agent()
        
        # Summary
        return self.print_summary()


if __name__ == "__main__":
    tester = ComprehensiveLangChainToolsTest()
    success = asyncio.run(tester.run_all_tests())
    print(f"Exit code: {'0 (SUCCESS)' if success else '1 (FAILURE)'}", flush=True)
    sys.exit(0 if success else 1)
