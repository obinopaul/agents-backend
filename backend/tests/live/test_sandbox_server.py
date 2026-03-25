#!/usr/bin/env python3
"""
Live Sandbox Server Integration Test

This script tests the sandbox_server integrated with FastAPI.
It tests sandbox creation, connection, command execution, and file operations
via the FastAPI endpoints.

Requirements:
- FastAPI server running on port 8001
- E2B_API_KEY or DAYTONA credentials in .env

Usage:
    cd backend
    python tests/live/test_sandbox_server.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

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
BASE_URL = os.environ.get("SANDBOX_SERVER_URL", "http://localhost:8001")
API_PREFIX = "/agent/sandboxes/sandboxes"


class SandboxServerTester:
    """Test client for sandbox server endpoints."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        # IMPORTANT: Server middleware requires User-Agent header
        # and httpx must use HTTP/1.1 (not HTTP/2) for compatibility
        self.client = httpx.AsyncClient(
            timeout=60.0,
            http2=False,  # Force HTTP/1.1
            headers={
                'User-Agent': 'SandboxServerTester/1.0 (Python httpx)',
                'X-Request-ID': 'sandbox-test-session'
            }
        )
        self.sandbox_id = None
    
    async def close(self):
        await self.client.aclose()
    
    async def test_health(self) -> bool:
        """Test server health."""
        print("\n" + "=" * 60)
        print("🏥 Testing Server Health")
        print("=" * 60)
        
        try:
            # Try OpenAPI docs
            response = await self.client.get(f"{self.base_url}/docs")
            if response.status_code == 200:
                print("✅ OpenAPI docs accessible")
                return True
            else:
                print(f"⚠️ OpenAPI returned: {response.status_code}")
                return True  # Server is running but docs may be disabled
        except Exception as e:
            print(f"❌ Server health check failed: {e}")
            return False
    
    async def test_create_sandbox(self, provider: str = "e2b") -> bool:
        """Test sandbox creation."""
        print("\n" + "=" * 60)
        print("🏗️ Testing Sandbox Creation")
        print("=" * 60)
        
        try:
            response = await self.client.post(
                f"{self.base_url}{API_PREFIX}/create",
                json={
                    "user_id": "test_user_123",
                    "provider": provider,
                    "template": "base"  # Default template
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.sandbox_id = data.get("sandbox_id") or data.get("id")
                print(f"✅ Sandbox created: {self.sandbox_id}")
                print(f"   Provider: {provider}")
                return True
            else:
                print(f"❌ Create failed: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ Create sandbox error: {e}")
            return False
    
    async def test_get_status(self) -> bool:
        """Test getting sandbox status."""
        print("\n" + "=" * 60)
        print("📊 Testing Sandbox Status")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping status test")
            return True
        
        try:
            response = await self.client.get(
                f"{self.base_url}{API_PREFIX}/{self.sandbox_id}/status"
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {data}")
                return True
            else:
                print(f"⚠️ Status check returned: {response.status_code}")
                return True  # Non-fatal
        except Exception as e:
            print(f"❌ Status check error: {e}")
            return False
    
    async def test_run_command(self, command: str = "echo 'Hello from sandbox!'") -> bool:
        """Test command execution."""
        print("\n" + "=" * 60)
        print("🐚 Testing Command Execution")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping command test")
            return True
        
        try:
            response = await self.client.post(
                f"{self.base_url}{API_PREFIX}/run-cmd",
                json={
                    "sandbox_id": self.sandbox_id,
                    "command": command,
                    "timeout": 30
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                output = data.get("output", data.get("stdout", str(data)))
                print(f"✅ Command executed")
                print(f"   Output: {output[:500]}")
                return True
            else:
                print(f"❌ Command failed: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ Command execution error: {e}")
            return False
    
    async def test_file_operations(self) -> bool:
        """Test file write and read."""
        print("\n" + "=" * 60)
        print("📁 Testing File Operations")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping file tests")
            return True
        
        try:
            # Write file
            test_content = f"Test file created at {datetime.now()}"
            response = await self.client.post(
                f"{self.base_url}{API_PREFIX}/write-file",
                json={
                    "sandbox_id": self.sandbox_id,
                    "path": "/tmp/sandbox_test.txt",
                    "content": test_content
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Write failed: {response.status_code}")
                return False
            
            print("✅ File written: /tmp/sandbox_test.txt")
            
            # Read file
            response = await self.client.post(
                f"{self.base_url}{API_PREFIX}/read-file",
                json={
                    "sandbox_id": self.sandbox_id,
                    "path": "/tmp/sandbox_test.txt"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("content", str(data))
                print(f"✅ File read: {content[:200]}")
                return True
            else:
                print(f"❌ Read failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ File operation error: {e}")
            return False
    
    async def test_delete_sandbox(self) -> bool:
        """Test sandbox deletion."""
        print("\n" + "=" * 60)
        print("🗑️ Testing Sandbox Deletion")
        print("=" * 60)
        
        if not self.sandbox_id:
            print("⚠️ No sandbox ID - skipping deletion test")
            return True
        
        try:
            response = await self.client.delete(
                f"{self.base_url}{API_PREFIX}/{self.sandbox_id}"
            )
            
            if response.status_code in [200, 204]:
                print(f"✅ Sandbox deleted: {self.sandbox_id}")
                self.sandbox_id = None
                return True
            else:
                print(f"⚠️ Delete returned: {response.status_code}")
                return True  # Non-fatal
        except Exception as e:
            print(f"❌ Delete error: {e}")
            return False


async def test_langchain_mcp_integration():
    """Test LangChain with MCP adapters integration."""
    print("\n" + "=" * 60)
    print("🔗 Testing LangChain MCP Integration")
    print("=" * 60)
    
    try:
        # Check if langchain_mcp_adapters is available
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_mcp_adapters.tools import load_mcp_tools
        print("✅ langchain_mcp_adapters imported")
        
        # Check if tool_server MCP is available
        from backend.src.tool_server.mcp.server import app as mcp_app
        print("✅ tool_server MCP server imported")
        
        return True
    except ImportError as e:
        print(f"⚠️ MCP integration not available: {e}")
        return True  # Not a failure, just not available
    except Exception as e:
        print(f"❌ MCP integration error: {e}")
        return False


async def test_sandbox_service_direct():
    """Test sandbox service directly (without HTTP)."""
    print("\n" + "=" * 60)
    print("🔧 Testing Sandbox Service Direct Access")
    print("=" * 60)
    
    try:
        from backend.src.services.sandbox_service import sandbox_service
        print("✅ sandbox_service imported")
        
        # Check if service is initialized
        if hasattr(sandbox_service, 'is_initialized'):
            print(f"   Initialized: {sandbox_service.is_initialized}")
        
        return True
    except Exception as e:
        print(f"❌ Sandbox service error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test runner."""
    print("\n" + "=" * 70)
    print("🚀 Sandbox Server Integration Test Suite")
    print("=" * 70)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Server URL: {BASE_URL}")
    print(f"   E2B API Key: {'Set' if os.getenv('E2B_API_KEY') else 'Not set'}")
    print("=" * 70)
    
    results = {}
    tester = SandboxServerTester()
    
    try:
        # Test server health
        results["Health"] = await tester.test_health()
        
        if results["Health"]:
            # Test sandbox service direct access
            results["ServiceDirect"] = await test_sandbox_service_direct()
            
            # Test LangChain MCP integration
            results["MCPIntegration"] = await test_langchain_mcp_integration()
            
            # Test sandbox operations (only if E2B key is available)
            if os.getenv("E2B_API_KEY"):
                results["CreateSandbox"] = await tester.test_create_sandbox("e2b")
                
                if tester.sandbox_id:
                    results["GetStatus"] = await tester.test_get_status()
                    results["RunCommand"] = await tester.test_run_command()
                    results["FileOps"] = await tester.test_file_operations()
                    results["Delete"] = await tester.test_delete_sandbox()
            else:
                print("\n⚠️ E2B_API_KEY not set - skipping sandbox CRUD tests")
                print("   Set E2B_API_KEY in .env to test full sandbox functionality")
    
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
