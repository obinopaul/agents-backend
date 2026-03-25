#!/usr/bin/env python3
"""
Backend API Test Script

Run this script to test all critical backend endpoints.
It will show you exactly what's working and what's failing.

Usage:
    python test_backend.py --password YOUR_PASSWORD

Or edit the PASSWORD variable below.
"""

import argparse
import json
import sys
import requests

# =============================================================================
# CONFIGURATION - Edit these if needed
# =============================================================================
BASE_URL = "http://localhost:8000"
USERNAME = "acobapaul@gmail.com"
PASSWORD = "Repent19$"  # Set via command line or edit here

# =============================================================================
# Test Functions
# =============================================================================

def test_backend_running():
    """Test if backend is accessible."""
    print("\n" + "="*60)
    print("TEST 1: Backend Accessibility")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running and accessible")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {BASE_URL}")
        print("   Make sure the backend is running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_login(username, password):
    """Test login and get JWT token."""
    print("\n" + "="*60)
    print("TEST 2: Login / JWT Authentication")
    print("="*60)

    url = f"{BASE_URL}/api/v1/auth/login"
    print(f"POST {url}")

    try:
        response = requests.post(
            url,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"}
        )

        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)[:500]}")

        if response.status_code == 200 and data.get("code") in [0, 200]:
            token = data.get("data", {}).get("access_token")
            if token:
                print(f"✅ Login successful! Token: {token[:50]}...")
                return token
            else:
                print("❌ Login response missing access_token")
                return None
        else:
            print(f"❌ Login failed: {data.get('msg', 'Unknown error')}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_list_sessions(token):
    """Test listing chat sessions."""
    print("\n" + "="*60)
    print("TEST 3: List Chat Sessions")
    print("="*60)

    url = f"{BASE_URL}/agent/chat-sessions"
    print(f"GET {url}")

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:1000]}")
            sessions = data.get("data", {}).get("sessions", [])
            print(f"✅ Found {len(sessions)} sessions")
            return True
        elif response.status_code == 404:
            print(f"❌ 404 Not Found")
            print("   The endpoint might not be registered correctly")
            print(f"   Response: {response.text[:500]}")
            return False
        else:
            print(f"❌ Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_create_session(token):
    """Test creating a new chat session."""
    print("\n" + "="*60)
    print("TEST 4: Create Chat Session")
    print("="*60)

    url = f"{BASE_URL}/agent/chat-sessions"
    print(f"POST {url}")

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "name": "Test Session from Python Script",
                "agent_type": "chat"
            }
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:1000]}")
            session_id = data.get("data", {}).get("id")
            if session_id:
                print(f"✅ Created session: {session_id}")
                return session_id
            else:
                print("❌ Session created but no ID returned")
                return None
        else:
            print(f"❌ Error: {response.text[:500]}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_get_session(token, session_id):
    """Test getting a specific session."""
    print("\n" + "="*60)
    print("TEST 5: Get Specific Session")
    print("="*60)

    url = f"{BASE_URL}/agent/chat-sessions/{session_id}"
    print(f"GET {url}")

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:1000]}")
            print("✅ Session retrieved successfully")
            return True
        elif response.status_code == 404:
            print(f"❌ 404 Not Found - Session doesn't exist or belongs to different user")
            print(f"   Response: {response.text[:500]}")
            return False
        else:
            print(f"❌ Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_file_upload(token):
    """Test file upload URL generation."""
    print("\n" + "="*60)
    print("TEST 6: Generate Upload URL")
    print("="*60)

    url = f"{BASE_URL}/agent/chat/generate-upload-url"
    print(f"POST {url}")

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "file_name": "test.txt",
                "content_type": "text/plain",
                "file_size": 100
            }
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:500]}")
            print("✅ Upload URL generated successfully")
            return True
        elif response.status_code == 500:
            print(f"❌ 500 Internal Server Error")
            print(f"   Response: {response.text[:500]}")
            print("   This might be a storage configuration issue")
            return False
        else:
            print(f"❌ Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_google_drive_status(token):
    """Test Google Drive connector status."""
    print("\n" + "="*60)
    print("TEST 7: Google Drive Status")
    print("="*60)

    url = f"{BASE_URL}/agent/connectors/google-drive/status"
    print(f"GET {url}")

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        if response.status_code == 200:
            print("✅ Google Drive endpoint working")
            return True
        else:
            print(f"❌ Error")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def print_available_routes():
    """Try to list available routes (if openapi.json is accessible)."""
    print("\n" + "="*60)
    print("AVAILABLE ROUTES (from OpenAPI)")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        if response.status_code == 200:
            data = response.json()
            paths = data.get("paths", {})

            # Filter for agent routes
            agent_routes = [path for path in paths.keys() if "agent" in path.lower() or "chat" in path.lower()]

            print(f"Found {len(agent_routes)} agent/chat related routes:")
            for path in sorted(agent_routes)[:30]:
                methods = list(paths[path].keys())
                print(f"  {', '.join(m.upper() for m in methods)} {path}")

            if len(agent_routes) > 30:
                print(f"  ... and {len(agent_routes) - 30} more")
        else:
            print(f"Could not fetch OpenAPI spec: {response.status_code}")
    except Exception as e:
        print(f"Error fetching routes: {e}")


# =============================================================================
# Main
# =============================================================================

def main():
    global PASSWORD, BASE_URL, USERNAME

    parser = argparse.ArgumentParser(description="Test backend API endpoints")
    parser.add_argument("--password", "-p", required=False, help="Password for login")
    parser.add_argument("--base-url", "-u", default=BASE_URL, help="Base URL of backend")
    parser.add_argument("--username", default=USERNAME, help="Username for login")

    args = parser.parse_args()

    if args.password:
        PASSWORD = args.password

    if not PASSWORD:
        print("ERROR: Password required. Use --password YOUR_PASSWORD")
        print("Or edit the PASSWORD variable in this script")
        sys.exit(1)

    BASE_URL = args.base_url
    USERNAME = args.username

    print("="*60)
    print("BACKEND API TEST SCRIPT")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Username: {USERNAME}")

    # Run tests
    results = {}

    # Test 1: Backend running
    if not test_backend_running():
        print("\n❌ Backend is not running. Cannot continue tests.")
        sys.exit(1)
    results["backend_running"] = True

    # Print available routes
    print_available_routes()

    # Test 2: Login
    token = test_login(USERNAME, PASSWORD)
    results["login"] = token is not None

    if not token:
        print("\n❌ Login failed. Cannot continue tests.")
        sys.exit(1)

    # Test 3: List sessions
    results["list_sessions"] = test_list_sessions(token)

    # Test 4: Create session
    session_id = test_create_session(token)
    results["create_session"] = session_id is not None

    # Test 5: Get session
    if session_id:
        results["get_session"] = test_get_session(token, session_id)
    else:
        results["get_session"] = False

    # Test 6: File upload
    results["file_upload"] = test_file_upload(token)

    # Test 7: Google Drive
    results["google_drive"] = test_google_drive_status(token)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")

    total_passed = sum(1 for v in results.values() if v)
    total_tests = len(results)
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")

    if total_passed < total_tests:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        print("\nNow run this SQL in Supabase to verify sessions:")
        print("""
SELECT uuid, user_id, name, status, created_time
FROM agent_chat_sessions
WHERE user_id = 20
ORDER BY created_time DESC;
        """)


if __name__ == "__main__":
    main()
