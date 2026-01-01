#!/usr/bin/env python3
"""
MCP Server Investigation Test
=============================

This script properly tests the MCP server by:
1. Creating an E2B sandbox via the backend API
2. Waiting for MCP /health endpoint
3. **Properly initializing** by calling /credential and /tool-server-url
4. Connecting to get tools via both MCPClient and MultiServerMCPClient
5. Comparing results

This is the CORRECT way to connect to the MCP server - the test scripts that
skip steps 3 must be updated.

Usage:
    python backend/tests/live/test_mcp_investigation.py
"""

import asyncio
import httpx
import sys
import os
import uuid
import time
from datetime import datetime
from typing import Optional, List, Any, Dict

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class MCPInvestigation:
    """Comprehensive MCP server investigation with proper initialization."""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.token: Optional[str] = None
        self.sandbox_id: Optional[str] = None
        self.mcp_url: Optional[str] = None
        self.session_id = str(uuid.uuid4())
        self.results = {}
        self.timings: Dict[str, float] = {}
    
    def log(self, msg: str, success: Optional[bool] = None, indent: int = 0):
        """Log a message with optional success indicator."""
        prefix = "  " * indent
        if success is True:
            icon = "✅"
        elif success is False:
            icon = "❌"
        else:
            icon = "ℹ️"
        print(f"{prefix}{icon} {msg}")
    
    def header(self, title: str):
        """Print a section header."""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    
    async def setup(self):
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            timeout=180.0,
            headers={
                'User-Agent': 'MCPInvestigation/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
    
    async def teardown(self):
        """Cleanup resources."""
        if self.client:
            await self.client.aclose()
    
    async def login(self) -> bool:
        """Authenticate with the backend."""
        try:
            r = await self.client.post(
                f'{BASE_URL}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            if r.status_code == 200:
                self.token = r.json().get('access_token')
                self.client.headers['Authorization'] = f'Bearer {self.token}'
                self.log(f"Authenticated as {TEST_USER}", True)
                return True
            self.log(f"Login failed: {r.status_code} - {r.text[:200]}", False)
            return False
        except Exception as e:
            self.log(f"Login error: {e}", False)
            return False
    
    async def create_sandbox(self) -> bool:
        """Create an E2B sandbox via backend API."""
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/create',
                json={'user_id': 'mcp-investigation'}
            )
            if r.status_code == 200:
                data = r.json().get('data', {})
                self.sandbox_id = data.get('sandbox_id')
                self.mcp_url = data.get('mcp_url')
                self.log(f"Sandbox created: {self.sandbox_id}", True)
                self.log(f"MCP URL: {self.mcp_url}")
                return True
            self.log(f"Sandbox creation failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Sandbox error: {e}", False)
            return False
    
    async def wait_for_health(self, max_wait: int = 60) -> bool:
        """Wait for MCP /health endpoint to respond."""
        self.log(f"Waiting for MCP health endpoint (max {max_wait}s)...")
        start = datetime.now()
        
        while (datetime.now() - start).seconds < max_wait:
            try:
                r = await self.client.get(f"{self.mcp_url}/health", timeout=10.0)
                if r.status_code == 200:
                    elapsed = (datetime.now() - start).seconds
                    self.log(f"MCP /health ready in {elapsed}s", True)
                    return True
            except Exception:
                pass
            await asyncio.sleep(3)
        
        self.log(f"MCP /health not ready after {max_wait}s", False)
        return False
    
    async def initialize_mcp_tools(self) -> bool:
        """
        CRITICAL: Call /credential and /tool-server-url to register tools.
        
        This is the step that test scripts are missing!
        """
        self.header("Initializing MCP Tools (Previously Missing Step)")
        
        # Step 1: Set credentials
        self.log("Calling /credential endpoint...")
        try:
            credential_payload = {
                "user_api_key": self.token,  # Use auth token as API key
                "session_id": self.session_id
            }
            r = await self.client.post(
                f"{self.mcp_url}/credential",
                json=credential_payload,
                timeout=30.0
            )
            if r.status_code == 200:
                self.log(f"Credential set: {r.json()}", True, indent=1)
            else:
                self.log(f"Credential failed: {r.status_code} - {r.text[:200]}", False, indent=1)
                return False
        except Exception as e:
            self.log(f"Credential error: {e}", False, indent=1)
            return False
        
        # Step 2: Set tool server URL (triggers tool registration)
        self.log("Calling /tool-server-url endpoint (triggers registration)...")
        try:
            # The tool server URL is the MCP server itself
            r = await self.client.post(
                f"{self.mcp_url}/tool-server-url",
                json={"tool_server_url": self.mcp_url},
                timeout=120.0  # Tool registration can take a while
            )
            if r.status_code == 200:
                self.log(f"Tool server URL set: {r.json()}", True, indent=1)
                return True
            else:
                self.log(f"Tool server URL failed: {r.status_code} - {r.text[:300]}", False, indent=1)
                return False
        except Exception as e:
            self.log(f"Tool server URL error: {e}", False, indent=1)
            return False
    
    async def test_without_initialization(self) -> int:
        """Test getting tools WITHOUT the credential/tool-server-url calls."""
        self.header("Test A: Get Tools WITHOUT Initialization (Current Broken Behavior)")
        
        start_time = time.time()
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": f"{self.mcp_url}/mcp",
                    "transport": "http"
                },
            })
            
            self.log("Connecting via MultiServerMCPClient...")
            tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=30.0)
            
            count = len(tools)
            elapsed = time.time() - start_time
            self.timings['without_init'] = elapsed
            
            if count > 0:
                self.log(f"Got {count} tools (unexpected!) [{elapsed:.1f}s]", True)
                for t in tools[:5]:
                    self.log(f"  - {t.name}", indent=1)
            else:
                self.log(f"Got 0 tools (expected - tools not initialized) [{elapsed:.1f}s]", True)
            
            return count
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            self.timings['without_init'] = elapsed
            self.log(f"Connection timed out [{elapsed:.1f}s]", False)
            return -1
        except Exception as e:
            elapsed = time.time() - start_time
            self.timings['without_init'] = elapsed
            self.log(f"Error: {e} [{elapsed:.1f}s]", False)
            return -1
    
    async def test_with_initialization(self) -> int:
        """Test getting tools WITH proper credential/tool-server-url calls."""
        self.header("Test B: Get Tools WITH Proper Initialization (Fixed Behavior)")
        
        start_time = time.time()
        
        # First initialize
        if not await self.initialize_mcp_tools():
            elapsed = time.time() - start_time
            self.timings['with_init'] = elapsed
            self.log(f"Failed to initialize MCP tools [{elapsed:.1f}s]", False)
            return -1
        
        # Wait a moment for tools to be fully registered
        self.log("Waiting 5s for tools to finish registering...")
        await asyncio.sleep(5)
        
        # Now try to get tools
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": f"{self.mcp_url}/mcp",
                    "transport": "http"
                },
            })
            
            self.log("Connecting via MultiServerMCPClient...")
            tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=60.0)
            
            count = len(tools)
            elapsed = time.time() - start_time
            self.timings['with_init'] = elapsed
            
            if count > 0:
                self.log(f"Got {count} tools! [{elapsed:.1f}s]", True)
                self.log("Sample tools:")
                for t in tools[:10]:
                    self.log(f"  - {t.name}", indent=1)
                if count > 10:
                    self.log(f"  ... and {count - 10} more", indent=1)
            else:
                self.log(f"Got 0 tools (registration may have failed) [{elapsed:.1f}s]", False)
            
            return count
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            self.timings['with_init'] = elapsed
            self.log(f"Connection timed out [{elapsed:.1f}s]", False)
            return -1
        except Exception as e:
            elapsed = time.time() - start_time
            self.timings['with_init'] = elapsed
            self.log(f"Error: {e} [{elapsed:.1f}s]", False)
            import traceback
            traceback.print_exc()
            return -1
    
    async def test_mcp_client_class(self) -> int:
        """Test using the project's MCPClient class (proper way)."""
        self.header("Test C: Using MCPClient Class (Best Practice)")
        
        start_time = time.time()
        try:
            from backend.src.tool_server.mcp.client import MCPClient
            
            self.log(f"Connecting MCPClient to {self.mcp_url}...")
            
            async with MCPClient(self.mcp_url) as client:
                # Health check
                healthy = await client.health_check()
                self.log(f"Health check: {healthy}", healthy)
                
                # Get tools
                tools = await client.get_langchain_tools()
                count = len(tools)
                elapsed = time.time() - start_time
                self.timings['mcp_client'] = elapsed
                
                if count > 0:
                    self.log(f"Got {count} LangChain tools! [{elapsed:.1f}s]", True)
                    for t in tools[:5]:
                        self.log(f"  - {t.name}", indent=1)
                else:
                    self.log(f"Got 0 tools [{elapsed:.1f}s]", False)
                
                return count
                
        except Exception as e:
            elapsed = time.time() - start_time
            self.timings['mcp_client'] = elapsed
            self.log(f"MCPClient error: {e} [{elapsed:.1f}s]", False)
            import traceback
            traceback.print_exc()
            return -1
    
    async def cleanup(self):
        """Delete the test sandbox."""
        if self.sandbox_id and self.client:
            try:
                await self.client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                self.log(f"Sandbox {self.sandbox_id} deleted", True)
            except Exception as e:
                self.log(f"Cleanup failed: {e}", False)
    
    async def run(self):
        """Run all investigations."""
        print("\n" + "="*70)
        print("  🔬 MCP SERVER INVESTIGATION")
        print(f"     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        await self.setup()
        
        try:
            # Phase 1: Setup
            self.header("Phase 1: Authentication & Sandbox Creation")
            
            if not await self.login():
                self.log("Cannot proceed without authentication", False)
                return
            
            if not await self.create_sandbox():
                self.log("Cannot proceed without sandbox", False)
                return
            
            # Phase 2: Wait for health
            self.header("Phase 2: Wait for MCP Health")
            
            if not await self.wait_for_health():
                self.log("MCP server not healthy, cannot proceed", False)
                return
            
            # Phase 3: Test WITHOUT initialization (current broken behavior)
            tools_without_init = await self.test_without_initialization()
            self.results['without_init'] = tools_without_init
            
            # Phase 4: Test WITH initialization (fixed behavior)
            tools_with_init = await self.test_with_initialization()
            self.results['with_init'] = tools_with_init
            
            # Phase 5: Test MCPClient class
            tools_mcp_client = await self.test_mcp_client_class()
            self.results['mcp_client'] = tools_mcp_client
            
            # Summary
            self.header("RESULTS SUMMARY")
            print()
            t1 = self.timings.get('without_init', 0)
            t2 = self.timings.get('with_init', 0)
            t3 = self.timings.get('mcp_client', 0)
            print(f"  Without initialization: {tools_without_init:3} tools  ({t1:6.1f}s)")
            print(f"  With initialization:    {tools_with_init:3} tools  ({t2:6.1f}s)")
            print(f"  MCPClient class:        {tools_mcp_client:3} tools  ({t3:6.1f}s)")
            print()
            print(f"  ⏱️  TOTAL TEST TIME: {t1 + t2 + t3:.1f}s")
            print()
            
            if tools_without_init == 0 and tools_with_init > 0:
                print("  ✅ ROOT CAUSE CONFIRMED!")
                print("  The issue is that test scripts skip /credential and /tool-server-url.")
                print("  Fix: Add these calls before connecting to MCP.")
            elif tools_with_init == 0:
                print("  ⚠️ Tools still 0 after initialization - may be another issue")
            else:
                print("  ℹ️ Unexpected results - needs further investigation")
            
        finally:
            self.header("Cleanup")
            await self.cleanup()
            await self.teardown()
        
        print("\n" + "="*70)
        print("  Investigation Complete")
        print("="*70 + "\n")


async def main():
    investigation = MCPInvestigation()
    await investigation.run()


if __name__ == "__main__":
    asyncio.run(main())
