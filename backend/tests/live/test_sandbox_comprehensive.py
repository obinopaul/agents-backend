#!/usr/bin/env python3
"""
Comprehensive Sandbox Server Test Suite

Tests all sandbox endpoints via the FastAPI backend to ensure full functionality.
"""
import asyncio
import httpx
import uuid
import sys
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"

class SandboxTestSuite:
    def __init__(self):
        self.client = None
        self.sandbox_id = None
        self.mcp_url = None
        self.vscode_url = None
        self.results = {}
    
    async def setup(self):
        self.client = httpx.AsyncClient(
            timeout=180.0,
            http2=False,
            headers={
                'User-Agent': 'SandboxTestSuite/1.0',
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
    
    async def test_login(self) -> bool:
        """Test authentication endpoint."""
        self.log("TEST: Login with JWT authentication")
        try:
            r = await self.client.post(
                f'{BASE_URL}/api/v1/auth/login/swagger',
                params={'username': TEST_USER, 'password': TEST_PASSWORD}
            )
            if r.status_code == 200:
                data = r.json()
                token = data.get('access_token')
                token_type = data.get('token_type', 'Bearer')
                self.client.headers['Authorization'] = f'{token_type} {token}'
                self.log(f"Login successful - Token: {token[:20]}...", True)
                return True
            else:
                self.log(f"Login failed: {r.status_code} - {r.text[:200]}", False)
                return False
        except Exception as e:
            self.log(f"Login error: {e}", False)
            return False
    
    async def test_create_sandbox(self) -> bool:
        """Test sandbox creation endpoint."""
        self.log("TEST: Create sandbox")
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/create',
                json={'user_id': 'test-user'}
            )
            if r.status_code == 200:
                data = r.json()
                if data.get('data'):
                    self.sandbox_id = data['data'].get('sandbox_id')
                    self.mcp_url = data['data'].get('mcp_url')
                    self.vscode_url = data['data'].get('vscode_url')
                    self.log(f"Sandbox created - ID: {self.sandbox_id}", True)
                    self.log(f"  MCP URL: {self.mcp_url}")
                    self.log(f"  VSCode URL: {self.vscode_url}")
                    return True
            self.log(f"Create failed: {r.status_code} - {r.text[:300]}", False)
            return False
        except Exception as e:
            self.log(f"Create error: {e}", False)
            return False
    
    async def test_get_status(self) -> bool:
        """Test sandbox status endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Get status (no sandbox)", None)
            return True
        
        self.log("TEST: Get sandbox status")
        try:
            r = await self.client.get(
                f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}/status'
            )
            if r.status_code == 200:
                data = r.json()
                status = data.get('data', {}).get('status', 'unknown')
                self.log(f"Sandbox status: {status}", True)
                return True
            self.log(f"Status check failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Status error: {e}", False)
            return False
    
    async def test_run_command(self) -> bool:
        """Test command execution endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Run command (no sandbox)", None)
            return True
        
        self.log("TEST: Run shell command")
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                json={
                    'sandbox_id': self.sandbox_id,
                    'command': 'echo "Hello from sandbox" && pwd && whoami && python3 --version'
                }
            )
            if r.status_code == 200:
                output = r.json().get('data', {}).get('output', '')
                self.log(f"Command output:\n{output}", True)
                return True
            self.log(f"Command failed: {r.status_code} - {r.text[:200]}", False)
            return False
        except Exception as e:
            self.log(f"Command error: {e}", False)
            return False
    
    async def test_write_file(self) -> bool:
        """Test file write endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Write file (no sandbox)", None)
            return True
        
        self.log("TEST: Write file to sandbox")
        try:
            content = f"Test file created at {datetime.now()}\nThis is a test from the sandbox server."
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
                json={
                    'sandbox_id': self.sandbox_id,
                    'file_path': '/tmp/test_file.txt',
                    'content': content
                }
            )
            if r.status_code == 200:
                self.log("File written successfully", True)
                return True
            self.log(f"Write failed: {r.status_code} - {r.text[:200]}", False)
            return False
        except Exception as e:
            self.log(f"Write error: {e}", False)
            return False
    
    async def test_read_file(self) -> bool:
        """Test file read endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Read file (no sandbox)", None)
            return True
        
        self.log("TEST: Read file from sandbox")
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/read-file',
                json={
                    'sandbox_id': self.sandbox_id,
                    'file_path': '/tmp/test_file.txt'
                }
            )
            if r.status_code == 200:
                content = r.json().get('data', {}).get('content', '')
                self.log(f"File content: {content[:100]}...", True)
                return True
            self.log(f"Read failed: {r.status_code} - {r.text[:200]}", False)
            return False
        except Exception as e:
            self.log(f"Read error: {e}", False)
            return False
    
    async def test_python_execution(self) -> bool:
        """Test Python code execution in sandbox."""
        if not self.sandbox_id:
            self.log("SKIP: Python execution (no sandbox)", None)
            return True
        
        self.log("TEST: Execute Python code in sandbox")
        try:
            # Write Python script
            python_code = '''
import sys
import os
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Environment: {os.environ.get('HOME', 'unknown')}")
result = sum(range(1, 101))
print(f"Sum of 1-100: {result}")
print("SUCCESS!")
'''
            await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/write-file',
                json={
                    'sandbox_id': self.sandbox_id,
                    'file_path': '/tmp/test_script.py',
                    'content': python_code
                }
            )
            
            # Execute script
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/run-cmd',
                json={
                    'sandbox_id': self.sandbox_id,
                    'command': 'python3 /tmp/test_script.py'
                }
            )
            if r.status_code == 200:
                output = r.json().get('data', {}).get('output', '')
                if 'SUCCESS!' in output:
                    self.log(f"Python execution successful:\n{output}", True)
                    return True
            self.log(f"Python execution failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Python execution error: {e}", False)
            return False
    
    async def test_expose_port(self) -> bool:
        """Test port exposure endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Expose port (no sandbox)", None)
            return True
        
        self.log("TEST: Expose port")
        try:
            r = await self.client.post(
                f'{BASE_URL}/agent/sandboxes/sandboxes/expose-port',
                json={
                    'sandbox_id': self.sandbox_id,
                    'port': 8080
                }
            )
            if r.status_code == 200:
                url = r.json().get('data', {}).get('url', '')
                self.log(f"Port 8080 exposed at: {url}", True)
                return True
            self.log(f"Expose port failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Expose port error: {e}", False)
            return False
    
    async def test_get_urls(self) -> bool:
        """Test get sandbox URLs endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Get URLs (no sandbox)", None)
            return True
        
        self.log("TEST: Get sandbox URLs")
        try:
            r = await self.client.get(
                f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}/urls'
            )
            if r.status_code == 200:
                data = r.json().get('data', {})
                self.log(f"MCP URL: {data.get('mcp_url')}", True)
                self.log(f"VSCode URL: {data.get('vscode_url')}")
                return True
            self.log(f"Get URLs failed: {r.status_code}", False)
            return False
        except Exception as e:
            self.log(f"Get URLs error: {e}", False)
            return False
    
    async def test_delete_sandbox(self) -> bool:
        """Test sandbox deletion endpoint."""
        if not self.sandbox_id:
            self.log("SKIP: Delete sandbox (no sandbox)", None)
            return True
        
        self.log("TEST: Delete sandbox")
        try:
            r = await self.client.delete(
                f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
            )
            if r.status_code in [200, 204]:
                self.log(f"Sandbox deleted: {self.sandbox_id}", True)
                self.sandbox_id = None
                return True
            self.log(f"Delete failed: {r.status_code} - {r.text[:200]}", False)
            return False
        except Exception as e:
            self.log(f"Delete error: {e}", False)
            return False
    
    async def run_all_tests(self):
        """Run all sandbox tests."""
        print("=" * 70)
        print("🚀 COMPREHENSIVE SANDBOX SERVER TEST SUITE")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Server: {BASE_URL}")
        print("=" * 70)
        
        await self.setup()
        
        tests = [
            ("Login", self.test_login),
            ("Create Sandbox", self.test_create_sandbox),
            ("Get Status", self.test_get_status),
            ("Run Command", self.test_run_command),
            ("Write File", self.test_write_file),
            ("Read File", self.test_read_file),
            ("Python Execution", self.test_python_execution),
            ("Expose Port", self.test_expose_port),
            ("Get URLs", self.test_get_urls),
            ("Delete Sandbox", self.test_delete_sandbox),
        ]
        
        for name, test_func in tests:
            print(f"\n{'─' * 50}")
            try:
                result = await test_func()
                self.results[name] = result
            except Exception as e:
                self.log(f"Test {name} crashed: {e}", False)
                self.results[name] = False
        
        await self.teardown()
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for name, result in self.results.items():
            icon = "✅" if result else "❌"
            print(f"   {icon} {name}")
        
        print("-" * 70)
        print(f"   PASSED: {passed}/{total}")
        print("=" * 70)
        
        return passed == total

if __name__ == '__main__':
    suite = SandboxTestSuite()
    success = asyncio.run(suite.run_all_tests())
    sys.exit(0 if success else 1)
