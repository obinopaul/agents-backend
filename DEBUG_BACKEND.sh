#!/bin/bash
# =============================================================================
# BACKEND DEBUG SCRIPT
# =============================================================================
# This script tests the backend directly without the frontend
# Run from the agents-backend directory
# =============================================================================

set -e

# Configuration - UPDATE THESE VALUES
BASE_URL="http://localhost:8000"
USERNAME="acobapaul"  # Your username
PASSWORD="YOUR_PASSWORD_HERE"  # Replace with your actual password

echo "=============================================="
echo "BACKEND DEBUG SCRIPT"
echo "=============================================="
echo ""

# =============================================================================
# STEP 1: Check if backend is running
# =============================================================================
echo "STEP 1: Checking if backend is running..."
if curl -s --connect-timeout 5 "${BASE_URL}/docs" > /dev/null 2>&1; then
    echo "✅ Backend is running at ${BASE_URL}"
else
    echo "❌ Backend is NOT running at ${BASE_URL}"
    echo "   Please start the backend first"
    exit 1
fi
echo ""

# =============================================================================
# STEP 2: Login and get JWT token
# =============================================================================
echo "STEP 2: Logging in to get JWT token..."
echo "Request: POST ${BASE_URL}/api/v1/auth/login"

LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"${USERNAME}\", \"password\": \"${PASSWORD}\"}")

echo "Response:"
echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"

# Extract access token
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('access_token', ''))" 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" == "None" ]; then
    echo "❌ Failed to get access token"
    echo "   Check username/password and try again"
    exit 1
fi

echo "✅ Got access token: ${ACCESS_TOKEN:0:50}..."
echo ""

# =============================================================================
# STEP 3: List chat sessions (should work if auth is correct)
# =============================================================================
echo "STEP 3: Listing chat sessions..."
echo "Request: GET ${BASE_URL}/agent/chat-sessions"

SESSIONS_RESPONSE=$(curl -s -X GET "${BASE_URL}/agent/chat-sessions" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json")

echo "Response:"
echo "$SESSIONS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SESSIONS_RESPONSE"
echo ""

# =============================================================================
# STEP 4: Create a new chat session via REST API
# =============================================================================
echo "STEP 4: Creating a new chat session via REST API..."
echo "Request: POST ${BASE_URL}/agent/chat-sessions"

CREATE_SESSION_RESPONSE=$(curl -s -X POST "${BASE_URL}/agent/chat-sessions" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"name": "Debug Test Session", "agent_type": "chat"}')

echo "Response:"
echo "$CREATE_SESSION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CREATE_SESSION_RESPONSE"

# Extract session UUID
SESSION_UUID=$(echo "$CREATE_SESSION_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('id', ''))" 2>/dev/null)

if [ -n "$SESSION_UUID" ] && [ "$SESSION_UUID" != "None" ]; then
    echo "✅ Created session with UUID: ${SESSION_UUID}"
else
    echo "⚠️ Could not extract session UUID from response"
fi
echo ""

# =============================================================================
# STEP 5: Get the newly created session
# =============================================================================
if [ -n "$SESSION_UUID" ] && [ "$SESSION_UUID" != "None" ]; then
    echo "STEP 5: Getting the newly created session..."
    echo "Request: GET ${BASE_URL}/agent/chat-sessions/${SESSION_UUID}"

    GET_SESSION_RESPONSE=$(curl -s -X GET "${BASE_URL}/agent/chat-sessions/${SESSION_UUID}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json")

    echo "Response:"
    echo "$GET_SESSION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$GET_SESSION_RESPONSE"
    echo ""
fi

# =============================================================================
# STEP 6: Test Chat Stream endpoint (SSE)
# =============================================================================
echo "STEP 6: Testing Chat Stream endpoint (SSE)..."
echo "Request: POST ${BASE_URL}/agent/chat/stream"

# Note: This will timeout after 5 seconds since SSE streams continuously
CHAT_RESPONSE=$(timeout 5 curl -s -X POST "${BASE_URL}/agent/chat/stream" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello, this is a test", "session_uuid": "'"${SESSION_UUID}"'"}' 2>/dev/null || true)

echo "Response (first 500 chars):"
echo "${CHAT_RESPONSE:0:500}"
echo ""

# =============================================================================
# STEP 7: List sessions again to see if count changed
# =============================================================================
echo "STEP 7: Listing sessions again..."
echo "Request: GET ${BASE_URL}/agent/chat-sessions"

SESSIONS_RESPONSE_2=$(curl -s -X GET "${BASE_URL}/agent/chat-sessions" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json")

echo "Response:"
echo "$SESSIONS_RESPONSE_2" | python3 -m json.tool 2>/dev/null || echo "$SESSIONS_RESPONSE_2"
echo ""

# =============================================================================
# STEP 8: Test file upload endpoint
# =============================================================================
echo "STEP 8: Testing file upload endpoint..."
echo "Request: POST ${BASE_URL}/agent/chat/generate-upload-url"

UPLOAD_RESPONSE=$(curl -s -X POST "${BASE_URL}/agent/chat/generate-upload-url" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"file_name": "test.txt", "content_type": "text/plain", "file_size": 100}')

echo "Response:"
echo "$UPLOAD_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$UPLOAD_RESPONSE"
echo ""

# =============================================================================
# STEP 9: Test Google Drive status
# =============================================================================
echo "STEP 9: Testing Google Drive connector status..."
echo "Request: GET ${BASE_URL}/agent/connectors/google-drive/status"

GDRIVE_RESPONSE=$(curl -s -X GET "${BASE_URL}/agent/connectors/google-drive/status" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json")

echo "Response:"
echo "$GDRIVE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$GDRIVE_RESPONSE"
echo ""

# =============================================================================
# SUMMARY
# =============================================================================
echo "=============================================="
echo "DEBUG SUMMARY"
echo "=============================================="
echo "1. Backend running: ✅"
echo "2. Login: Check above for success/failure"
echo "3. Chat sessions list: Check above for 200/404"
echo "4. Create session: Check if UUID was returned"
echo "5. Get session: Check if 200/404"
echo "6. Chat stream: Check if response received"
echo "7. File upload: Check if URL or error"
echo "8. Google Drive: Check status"
echo ""
echo "Next: Run the SQL query in Supabase to check if sessions were created"
echo ""
echo "SQL to run:"
echo "SELECT uuid, user_id, name, created_time FROM agent_chat_sessions WHERE user_id = 20 ORDER BY created_time DESC;"
