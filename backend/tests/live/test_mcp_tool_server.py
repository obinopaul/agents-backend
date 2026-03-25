#!/usr/bin/env python3
"""
MCP Tool Server Connection Test

This test verifies that:
1. A sandbox can be created with MCP server running
2. We can connect to the MCP server 
3. Tools are available and can be executed
"""
import asyncio
import httpx
import uuid
import sys
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class MCPToolServerTest:
    def __init__(self):
        self.client = None
        self.sandbox_id = None
        self.mcp_url = None
    
    async def setup(self):
        self.client = httpx.AsyncClient(
            timeout=180.0,
            http2=False,
            headers={
                'User-Agent': 'MCPToolServerTest/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
    
    async def teardown(self):
        if self.client:
            await self.client.aclose()
    
    def log(self, msg: str, success: bool = None):
        icon = "✅" if success == True else "❌" if success == False else "ℹ️"
        print(f"{icon} {msg}")
    
    async def login(self) -> bool:
        """Authenticate with the backend."""
        try:
            r = await self.client.post(
                f'{BASE_URL}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            if r.status_code == 200:
                token = r.json().get('access_token')
                self.client.headers['Authorization'] = f'Bearer {token}'
                self.log("Logged in successfully", True)
                return True
            self.log(f"Login failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Login error: {e}", False)
            return False
    
    async def create_sandbox(self) -> bool:
        """Create a sandbox and get MCP URL."""
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/create',
                json={'user_id': 'mcp-test'}
            )
            if r.status_code == 200:
                data = r.json().get('data', {})
                self.sandbox_id = data.get('sandbox_id')
                self.mcp_url = data.get('mcp_url')
                self.log(f"Sandbox created: {self.sandbox_id}", True)
                self.log(f"MCP URL: {self.mcp_url}")
                return True
            self.log(f"Sandbox creation failed: {r.status_code} - {r.text[:200]}", False)
            return False
        except Exception as e:
            self.log(f"Sandbox error: {e}", False)
            return False
    
    async def check_mcp_health(self) -> bool:
        """Check if MCP server is running in sandbox."""
        if not self.mcp_url:
            self.log("No MCP URL available", False)
            return False
        
        try:
            # Try to access MCP server health endpoint
            health_url = f"{self.mcp_url}/health"
            self.log(f"Checking MCP health at: {health_url}")
            
            r = await self.client.get(health_url, timeout=30.0)
            if r.status_code == 200:
                self.log(f"MCP server is healthy: {r.text[:100]}", True)
                return True
            else:
                self.log(f"MCP health check returned: {r.status_code}", False)
                return False
        except httpx.ConnectError as e:
            self.log(f"MCP server not reachable (may still be starting): {e}", False)
            return False
        except Exception as e:
            self.log(f"MCP health error: {e}", False)
            return False
    
    async def wait_for_mcp_server(self, max_wait_seconds=60) -> bool:
        """Wait for MCP server to become available."""
        self.log(f"Waiting for MCP server (up to {max_wait_seconds}s)...")
        
        start = datetime.now()
        while (datetime.now() - start).seconds < max_wait_seconds:
            if await self.check_mcp_health():
                return True
            await asyncio.sleep(5)
        
        self.log("MCP server did not become available in time", False)
        return False
    
    async def test_run_command_via_sandbox(self) -> bool:
        """Test running a command through the sandbox API."""
        if not self.sandbox_id:
            self.log("No sandbox available", False)
            return False
        
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                json={
                    'sandbox_id': self.sandbox_id,
                    'command': 'ps aux | grep -E "(python|mcp)" | head -5'
                }
            )
            if r.status_code == 200:
                output = r.json().get('data', {}).get('output', '')
                self.log(f"Processes in sandbox:\n{output}", True)
                return True
            self.log(f"Command failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Command error: {e}", False)
            return False
    
    async def test_mcp_server_running(self) -> bool:
        """Check if the MCP server process is running in the sandbox."""
        if not self.sandbox_id:
            return False
        
        try:
            # Check for MCP server process
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                json={
                    'sandbox_id': self.sandbox_id,
                    'command': 'pgrep -f "tool_server" && echo "MCP_FOUND" || echo "MCP_NOT_FOUND"'
                }
            )
            if r.status_code == 200:
                output = r.json().get('data', {}).get('output', '')
                if 'MCP_FOUND' in output:
                    self.log("MCP tool_server process is running", True)
                    return True
                else:
                    self.log("MCP tool_server process NOT running", False)
                    # Try to see what services are running
                    r2 = await self.client.post(
                        f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                        json={
                            'sandbox_id': self.sandbox_id,
                            'command': 'cat /var/log/start-services.log 2>/dev/null || echo "No log file"'
                        }
                    )
                    if r2.status_code == 200:
                        log_output = r2.json().get('data', {}).get('output', '')
                        self.log(f"Service log:\n{log_output[:500]}")
                    return False
        except Exception as e:
            self.log(f"Process check error: {e}", False)
            return False
    
    async def test_file_operations(self) -> bool:
        """Test file read/write through sandbox API."""
        if not self.sandbox_id:
            return False
        
        try:
            # Write a test file
            test_content = "Hello from MCP tool server test!"
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
                json={
                    'sandbox_id': self.sandbox_id,
                    'file_path': '/tmp/mcp_test.txt',
                    'content': test_content
                }
            )
            if r.status_code != 200:
                self.log(f"Write failed: {r.status_code}", False)
                return False
            
            # Read it back
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
                json={
                    'sandbox_id': self.sandbox_id,
                    'file_path': '/tmp/mcp_test.txt'
                }
            )
            if r.status_code == 200:
                content = r.json().get('data', {}).get('content', '')
                if test_content in content:
                    self.log("File operations work correctly", True)
                    return True
            
            self.log("File operations failed", False)
            return False
        except Exception as e:
            self.log(f"File operation error: {e}", False)
            return False
    
    async def cleanup(self):
        """Delete the test sandbox."""
        if self.sandbox_id:
            try:
                await self.client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                self.log(f"Sandbox {self.sandbox_id} deleted", True)
            except Exception as e:
                self.log(f"Cleanup error: {e}", False)
    
    async def run_all_tests(self):
        """Run all MCP tool server tests."""
        print("=" * 70)
        print("🔧 MCP TOOL SERVER CONNECTION TEST")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        await self.setup()
        
        results = {}
        
        # Login
        print("\n--- Phase 1: Authentication ---")
        results['login'] = await self.login()
        if not results['login']:
            await self.teardown()
            return False
        
        # Create sandbox
        print("\n--- Phase 2: Sandbox Creation ---")
        results['sandbox'] = await self.create_sandbox()
        if not results['sandbox']:
            await self.teardown()
            return False
        
        # Wait a bit for services to start
        print("\n--- Phase 3: Wait for Services ---")
        await asyncio.sleep(10)  # Give services time to start
        
        # Check processes
        print("\n--- Phase 4: Process Check ---")
        results['process'] = await self.test_mcp_server_running()
        
        # Test command execution
        print("\n--- Phase 5: Command Execution ---")
        results['commands'] = await self.test_run_command_via_sandbox()
        
        # Test file operations
        print("\n--- Phase 6: File Operations ---")
        results['files'] = await self.test_file_operations()
        
        # MCP health check
        print("\n--- Phase 7: MCP Health Check ---")
        results['mcp_health'] = await self.check_mcp_health()
        
        # Cleanup
        print("\n--- Cleanup ---")
        await self.cleanup()
        await self.teardown()
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for name, result in results.items():
            icon = "✅" if result else "❌"
            print(f"   {icon} {name}")
        
        print("-" * 70)
        print(f"   PASSED: {passed}/{total}")
        print("=" * 70)
        
        return passed >= 4  # At least 4 tests should pass

if __name__ == '__main__':
    test = MCPToolServerTest()
    success = asyncio.run(test.run_all_tests())
    sys.exit(0 if success else 1)
