# Debug Commands - Run These One by One

## 1. Check Docker Services Are Running

```bash
docker compose ps
```

Expected output: All services should show "Up" or "running"


## 2. View Backend Server Logs

The service is named `agents_backend_server` (not `backend`):

```bash
docker compose logs agents_backend_server --tail=200
```

Or follow logs in real-time:

```bash
docker compose logs agents_backend_server -f
```


## 3. Check for Errors in Logs

```bash
docker compose logs agents_backend_server --tail=500 2>&1 | grep -iE "error|exception|failed|traceback"
```


## 4. Check Redis Connection

```bash
docker compose exec agents_backend_redis redis-cli ping
```

Expected: `PONG`


## 5. Test Backend API Directly (Run these in order)

### Step 5a: Check if backend is accessible
```bash
curl -s http://localhost:8000/docs | head -20
```

### Step 5b: Login and get token
```bash
curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "acobapaul", "password": "YOUR_PASSWORD"}' | python3 -m json.tool
```

Save the `access_token` from the response for next steps.

### Step 5c: List chat sessions (replace TOKEN with your access_token)
```bash
curl -s -X GET "http://localhost:8000/agent/chat-sessions" \
  -H "Authorization: Bearer TOKEN" | python3 -m json.tool
```

### Step 5d: Create a new session
```bash
curl -s -X POST "http://localhost:8000/agent/chat-sessions" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Debug Test", "agent_type": "chat"}' | python3 -m json.tool
```

### Step 5e: Test file upload endpoint
```bash
curl -s -X POST "http://localhost:8000/agent/chat/generate-upload-url" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_name": "test.txt", "content_type": "text/plain", "file_size": 100}' | python3 -m json.tool
```


## 6. Check WebSocket Connection (Manual Test)

Open browser DevTools (F12) → Network → WS tab, then try to connect in Agent mode.

Look for:
- Connection established? (status 101)
- Any error messages in the WebSocket frames
- `join_session` event sent?
- Response received?


## 7. SQL to Run After Testing

After running the curl commands above, check Supabase:

```sql
-- Check if new sessions were created
SELECT uuid, user_id, name, status, created_time
FROM agent_chat_sessions
WHERE user_id = 20
ORDER BY created_time DESC;

-- Check last 10 sessions regardless of user
SELECT uuid, user_id, name, status, created_time
FROM agent_chat_sessions
ORDER BY created_time DESC
LIMIT 10;
```


## 8. Quick All-in-One Test (Linux/WSL)

```bash
# Set your password
export PASSWORD="YOUR_PASSWORD"

# Login and save token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"acobapaul\", \"password\": \"$PASSWORD\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('access_token',''))")

echo "Token: $TOKEN"

# Test sessions endpoint
echo "=== List Sessions ==="
curl -s -X GET "http://localhost:8000/agent/chat-sessions" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Create session
echo "=== Create Session ==="
curl -s -X POST "http://localhost:8000/agent/chat-sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Debug Test", "agent_type": "chat"}' | python3 -m json.tool

# Test file upload
echo "=== File Upload ==="
curl -s -X POST "http://localhost:8000/agent/chat/generate-upload-url" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_name": "test.txt", "content_type": "text/plain", "file_size": 100}' | python3 -m json.tool
```


## Troubleshooting

### If docker compose logs shows "No such service"
Make sure you're in the correct directory containing `docker-compose.yml`

### If login fails
- Check username/password are correct
- Check backend is running: `curl http://localhost:8000/docs`

### If sessions endpoint returns 404
- The endpoint path is `/agent/chat-sessions` (not `/agents/` with an 's')
- Check Authorization header is included

### If file upload returns 500
- This was a bug I fixed - make sure you rebuilt the container
- Check: `docker compose build agents_backend_server --no-cache`
