#!/usr/bin/env python3
"""
Slide System Test - Testing Slide APIs Without Agent

This script tests the slide system directly via API endpoints, without waiting
for a real agent to create slides. It verifies:
1. Database endpoints work (/db/slide, /db/presentations)
2. Manual slide creation via POST /db/slide
3. Slide retrieval and listing

This is more reliable for CI testing since it doesn't depend on MCP server startup.

Prerequisites:
    - FastAPI backend running at localhost:8000
    - Test user created (python backend/tests/live/create_test_user.py)
    - Database with slide_content table (alembic upgrade head)

Usage:
    python backend/tests/live/slide_system/test_slide_api_live.py
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# Fix Windows encoding issues with emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import httpx

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER = "sandbox_test"
TEST_PASSWORD = "TestPass123!"


class SlideAPITester:
    """Tests slide API endpoints directly without requiring sandbox/agent."""
    
    def __init__(self):
        self.token = None
        self.client = None
        self.thread_id = f"api-test-{uuid.uuid4().hex[:8]}"
        self.test_results = []

    async def setup(self):
        """Initialize HTTP client and authenticate."""
        print("\n" + "=" * 70)
        print("🧪 Slide API Direct Test")
        print(f"   Thread ID: {self.thread_id}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'SlideAPITester/1.0',
                'Content-Type': 'application/json'
            }
        )
        
        print("\n📋 Authenticating...")
        if not await self._login():
            print("   ❌ Login failed")
            return False
        
        print("   ✅ Authenticated")
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
                self.client.headers['Authorization'] = f'Bearer {self.token}'
                return True
            return False
        except Exception as e:
            print(f"   Error: {e}")
            return False

    async def test_create_slide_via_api(self) -> bool:
        """Test creating a slide via POST /db/slide endpoint."""
        print("\n📝 Test 1: Creating slide via POST /db/slide...")
        
        slide_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Slide - Welcome</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            width: 1280px;
            height: 720px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .content {
            text-align: center;
        }
        h1 { font-size: 72px; margin-bottom: 20px; }
        p { font-size: 32px; opacity: 0.9; }
    </style>
</head>
<body>
    <div class="content">
        <h1>Hello World!</h1>
        <p>This is a test slide created via API</p>
    </div>
</body>
</html>
"""
        
        try:
            response = await self.client.post(
                f'{BASE_URL}/agent/slides/db/slide',
                params={'thread_id': self.thread_id},
                json={
                    'presentation_name': 'API Test Presentation',
                    'slide_number': 1,
                    'content': slide_html,
                    'title': 'Welcome'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data', {}).get('success'):
                    slide_id = data.get('data', {}).get('slide_id')
                    print(f"   ✅ Slide created (slide_id={slide_id})")
                    self.test_results.append(('create_slide', True))
                    return True
                else:
                    print(f"   ❌ API returned success=false: {data}")
                    self.test_results.append(('create_slide', False))
                    return False
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:200]}")
                self.test_results.append(('create_slide', False))
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.test_results.append(('create_slide', False))
            return False

    async def test_create_second_slide(self) -> bool:
        """Create a second slide to test multi-slide presentations."""
        print("\n📝 Test 2: Creating second slide...")
        
        slide_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test Slide - Thank You</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            width: 1280px;
            height: 720px;
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        h1 { font-size: 72px; }
    </style>
</head>
<body>
    <h1>Thank You!</h1>
</body>
</html>
"""
        
        try:
            response = await self.client.post(
                f'{BASE_URL}/agent/slides/db/slide',
                params={'thread_id': self.thread_id},
                json={
                    'presentation_name': 'API Test Presentation',
                    'slide_number': 2,
                    'content': slide_html,
                    'title': 'Thank You'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data', {}).get('success'):
                    print(f"   ✅ Second slide created")
                    self.test_results.append(('create_slide_2', True))
                    return True
            
            print(f"   ❌ Failed: {response.status_code}")
            self.test_results.append(('create_slide_2', False))
            return False
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.test_results.append(('create_slide_2', False))
            return False

    async def test_list_presentations(self) -> bool:
        """Test listing presentations via GET /db/presentations."""
        print("\n📝 Test 3: Listing presentations...")
        
        try:
            response = await self.client.get(
                f'{BASE_URL}/agent/slides/db/presentations',
                params={'thread_id': self.thread_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('data', {})
                total = result.get('total', 0)
                presentations = result.get('presentations', [])
                
                print(f"   ✅ Found {total} presentation(s)")
                for pres in presentations:
                    print(f"      • {pres.get('name')} ({pres.get('slide_count')} slides)")
                
                self.test_results.append(('list_presentations', total > 0))
                return total > 0
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:200]}")
                self.test_results.append(('list_presentations', False))
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.test_results.append(('list_presentations', False))
            return False

    async def test_get_slide_content(self) -> bool:
        """Test getting slide content via GET /db/slide."""
        print("\n📝 Test 4: Getting slide content...")
        
        try:
            response = await self.client.get(
                f'{BASE_URL}/agent/slides/db/slide',
                params={
                    'thread_id': self.thread_id,
                    'presentation_name': 'API Test Presentation',
                    'slide_number': 1
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('data', {})
                content = result.get('content', '')
                success = result.get('success', False)
                
                if success and content:
                    print(f"   ✅ Got slide content ({len(content)} bytes)")
                    print(f"      Title: {result.get('title', 'N/A')}")
                    self.test_results.append(('get_slide', True))
                    return True
                else:
                    print(f"   ❌ No content returned")
                    self.test_results.append(('get_slide', False))
                    return False
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:200]}")
                self.test_results.append(('get_slide', False))
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.test_results.append(('get_slide', False))
            return False

    async def run_all_tests(self):
        """Run all API tests."""
        print("\n" + "=" * 70)
        print("🧪 Running All Slide API Tests")
        print("=" * 70)
        
        await self.test_create_slide_via_api()
        await self.test_create_second_slide()
        await self.test_list_presentations()
        await self.test_get_slide_content()
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 Test Results")
        print("=" * 70)
        
        passed = sum(1 for _, success in self.test_results if success)
        total = len(self.test_results)
        
        for name, success in self.test_results:
            status = "✅ Pass" if success else "❌ Fail"
            print(f"   {status}: {name}")
        
        print("-" * 70)
        print(f"   Total: {passed}/{total} passed")
        print("=" * 70)
        
        return passed == total

    async def cleanup(self):
        """Cleanup resources."""
        if self.client:
            await self.client.aclose()
        print("\n👋 Done!")


async def main():
    tester = SlideAPITester()
    
    try:
        if not await tester.setup():
            sys.exit(1)
        
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
        
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
