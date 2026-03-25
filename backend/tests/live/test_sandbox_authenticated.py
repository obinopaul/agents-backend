#!/usr/bin/env python3
"""
Full Authenticated Sandbox Server Test Suite

This script tests the complete sandbox functionality with authentication.
It logs in first, then tests all sandbox CRUD operations.

Requirements:
- FastAPI server running on port 8001
- E2B_API_KEY set in .env
- Database with admin user (admin/123456)

Usage:
    cd backend
    python tests/live/test_sandbox_authenticated.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
import uuid

import httpx

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv

load_dotenv(backend_path / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = os.environ.get("SANDBOX_SERVER_URL", "http://127.0.0.1:8001")
API_V1_PATH = "/api/v1"
SANDBOX_API = "/agent/sandboxes/sandboxes"

# Test credentials - matches sandbox_test user created by create_test_user.py
TEST_USERNAME = os.environ.get("TEST_USERNAME", "sandbox_test")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPass123!")


class AuthenticatedSandboxTester:
    """Authenticated test client for sandbox server endpoints."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.api_v1 = f"{base_url}{API_V1_PATH}"
        self.sandbox_base = f"{base_url}{SANDBOX_API}"
        
        # HTTP client with required headers
        self.client = httpx.AsyncClient(
            timeout=120.0,
            http2=False,  # Force HTTP/1.1
            headers={
                'User-Agent': 'AuthenticatedSandboxTester/1.0 (Python httpx)',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
        
        self.access_token = None
        self.token_type = None
        self.sandbox_id = None
    
    async def close(self):
        await self.client.aclose()
    
    async def login(self, username: str = TEST_USERNAME, password: str = TEST_PASSWORD) -> bool:
        """Login and get JWT token."""
        print("\n" + "=" * 60)
        print("🔐 Authenticating...")
        print("=" * 60)
        
        try:
            # Use swagger login endpoint (simpler)
            response = await self.client.post(
                f"{self.api_v1}/auth/login/swagger",
                params={'username': username, 'password': password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token_type = data.get('token_type', 'Bearer')
                self.access_token = data.get('access_token')
                
                # Update client headers with auth token
                self.client.headers['Authorization'] = f"{self.token_type} {self.access_token}"
                
                print(f"✅ Logged in as: {username}")
                print(f"   Token: {self.access_token[:20]}...")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    async def test_create_sandbox(self, provider: str = "e2b") -> bool:
        """Test sandbox creation."""
        print("\n" + "=" * 60)
        print("🏗️ Creating Sandbox...")
        print("=" * 60)
        
        try:
            response = await self.client.post(
                f"{self.sandbox_base}/create",
                json={
                    "user_id": TEST_USERNAME,
                    "provider": provider,
                    "template": "base"
                }
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # Handle nested response structure
                if 'data' in data:
                    data = data['data']
                
                self.sandbox_id = data.get('sandbox_id') or data.get('id')
                print(f"✅ Sandbox created: {self.sandbox_id}")
                print(f"   Provider: {provider}")
                return True
            else:
                print(f"❌ Create failed: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Create sandbox error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_get_status(self) -> bool:
        """Test getting sandbox status."""
        print("\n" + "=" * 60)
        print("📊 Getting Sandbox Status...")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping")
            return True
        
        try:
            response = await self.client.get(
                f"{self.sandbox_base}/{self.sandbox_id}/status"
            )
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Sandbox status: {data}")
                return True
            else:
                print(f"⚠️ Status check returned: {response.text[:300]}")
                return True  # Non-fatal
                
        except Exception as e:
            print(f"❌ Status check error: {e}")
            return False
    
    async def test_run_command(self, command: str = "echo 'Hello from sandbox!' && pwd") -> bool:
        """Test command execution."""
        print("\n" + "=" * 60)
        print("🐚 Running Command in Sandbox...")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping")
            return True
        
        try:
            response = await self.client.post(
                f"{self.sandbox_base}/run-cmd",
                json={
                    "sandbox_id": self.sandbox_id,
                    "command": command,
                    "timeout": 30
                }
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    data = data['data']
                output = data.get('output', data.get('stdout', str(data)))
                print(f"✅ Command output:\n{output[:500]}")
                return True
            else:
                print(f"❌ Command failed: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Command execution error: {e}")
            return False
    
    async def test_file_operations(self) -> bool:
        """Test file write and read."""
        print("\n" + "=" * 60)
        print("📁 Testing File Operations...")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping")
            return True
        
        try:
            # Write file
            test_content = f"Test file created at {datetime.now()}\nFrom authenticated sandbox test."
            
            print("   Writing file...")
            response = await self.client.post(
                f"{self.sandbox_base}/write-file",
                json={
                    "sandbox_id": self.sandbox_id,
                    "path": "/tmp/test_auth_sandbox.txt",
                    "content": test_content
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Write failed: {response.status_code} - {response.text[:300]}")
                return False
            
            print("✅ File written: /tmp/test_auth_sandbox.txt")
            
            # Read file
            print("   Reading file...")
            response = await self.client.post(
                f"{self.sandbox_base}/read-file",
                json={
                    "sandbox_id": self.sandbox_id,
                    "path": "/tmp/test_auth_sandbox.txt"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    data = data['data']
                content = data.get('content', str(data))
                print(f"✅ File read:\n{content[:200]}")
                return True
            else:
                print(f"❌ Read failed: {response.status_code} - {response.text[:300]}")
                return False
                
        except Exception as e:
            print(f"❌ File operation error: {e}")
            return False
    
    async def test_python_execution(self) -> bool:
        """Test Python code execution."""
        print("\n" + "=" * 60)
        print("🐍 Testing Python Execution...")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping")
            return True
        
        try:
            # Write Python file
            python_code = '''
import sys
import os
print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("2 + 2 =", 2 + 2)
print("Success from sandbox!")
'''
            
            print("   Writing Python file...")
            await self.client.post(
                f"{self.sandbox_base}/write-file",
                json={
                    "sandbox_id": self.sandbox_id,
                    "path": "/tmp/test_script.py",
                    "content": python_code
                }
            )
            
            # Run Python file
            print("   Executing Python...")
            response = await self.client.post(
                f"{self.sandbox_base}/run-cmd",
                json={
                    "sandbox_id": self.sandbox_id,
                    "command": "python3 /tmp/test_script.py",
                    "timeout": 30
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    data = data['data']
                output = data.get('output', data.get('stdout', str(data)))
                print(f"✅ Python output:\n{output[:500]}")
                return True
            else:
                print(f"❌ Python execution failed: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Python execution error: {e}")
            return False
    
    async def test_delete_sandbox(self) -> bool:
        """Test sandbox deletion."""
        print("\n" + "=" * 60)
        print("🗑️ Deleting Sandbox...")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping")
            return True
        
        try:
            response = await self.client.delete(
                f"{self.sandbox_base}/{self.sandbox_id}"
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code in [200, 204]:
                print(f"✅ Sandbox deleted: {self.sandbox_id}")
                self.sandbox_id = None
                return True
            else:
                print(f"⚠️ Delete returned: {response.text[:300]}")
                return True  # Non-fatal
                
        except Exception as e:
            print(f"❌ Delete error: {e}")
            return False


async def main():
    """Main test runner."""
    print("\n" + "=" * 70)
    print("🚀 Authenticated Sandbox Test Suite")
    print("=" * 70)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Server URL: {BASE_URL}")
    print(f"   User: {TEST_USERNAME}")
    print(f"   E2B API Key: {'Set' if os.getenv('E2B_API_KEY') else 'Not set'}")
    print("=" * 70)
    
    results = {}
    tester = AuthenticatedSandboxTester()
    
    try:
        # Step 1: Login
        results["Login"] = await tester.login()
        
        if results["Login"]:
            # Step 2: Create sandbox
            results["CreateSandbox"] = await tester.test_create_sandbox("e2b")
            
            if results["CreateSandbox"] and tester.sandbox_id:
                # Step 3: Test operations
                results["GetStatus"] = await tester.test_get_status()
                results["RunCommand"] = await tester.test_run_command()
                results["FileOps"] = await tester.test_file_operations()
                results["PythonExec"] = await tester.test_python_execution()
                
                # Step 4: Cleanup
                results["Delete"] = await tester.test_delete_sandbox()
    
    finally:
        await tester.close()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"   {icon} {test_name}")
    
    print("-" * 70)
    print(f"   Passed: {passed}/{total}")
    print("=" * 70)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
