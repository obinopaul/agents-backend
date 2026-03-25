
import asyncio
import socketio
import requests
import json
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MockFrontend")

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "http://localhost:8000"
API_BASE_URL = f"{BASE_URL}/api/v1"

# Credentials
USERNAME = "acobapaul@gmail.com"
PASSWORD = "Repent19$" 

sio = socketio.AsyncClient(logger=True, engineio_logger=True)

# File to log events to
LOG_FILE = "frontend_event_log.jsonl"

async def get_token():
    logger.info(f"[*] Logging in as {USERNAME}...")
    try:
        url = f"{API_BASE_URL}/auth/login/swagger"
        response = requests.post(url, params={"username": USERNAME, "password": PASSWORD})
        if response.status_code == 200:
            token = response.json().get("access_token")
            logger.info("[+] Token obtained.")
            return token
        else:
            logger.error(f"[-] Login failed: {response.text}")
            return None
    except Exception as e:
        logger.error(f"[-] Login error: {e}")
        return None

def log_event_to_file(event_type, content):
    with open(LOG_FILE, "a") as f:
        entry = {
            "type": event_type,
            "content": content,
            "timestamp": asyncio.get_event_loop().time()
        }
        f.write(json.dumps(entry) + "\n")

@sio.event
async def connect():
    logger.info(f"[+] Connected to WebSocket! SID: {sio.sid}")

@sio.event
async def disconnect():
    logger.info("[-] Disconnected from WebSocket.")

@sio.event
async def connect_error(data):
    logger.error(f"[-] Connection Error: {data}")

@sio.on('chat_event', namespace='/ws')
async def on_chat_event(data):
    # Log all chat events
    event_type = data.get('type')
    content = data.get('content')
    logger.info(f"[<] Received Event: {event_type} | Content: {str(content)[:100]}...") # Truncate log
    log_event_to_file(event_type, content)

    if event_type == 'error':
        logger.error(f"!!! SERVER ERROR: {content.get('message')}")

async def main():
    # Clear log file
    open(LOG_FILE, "w").close()

    token = await get_token()
    if not token:
        return

    session_uuid = f"test-session-{uuid.uuid4()}"
    logger.info(f"[*] Test Session UUID: {session_uuid}")

    # 1. Connect
    logger.info(f"[*] Connecting to {WS_URL}...")
    auth_payload = {"token": token, "session_uuid": session_uuid}
    
    try:
        await sio.connect(
            WS_URL, 
            auth=auth_payload, 
            socketio_path='/ws/socket.io',
            transports=['websocket', 'polling'],
            namespaces=['/ws']
        )
    except Exception as e:
        logger.error(f"[-] Connect failed: {e}")
        return

    # 2. Join Session
    await asyncio.sleep(1)
    logger.info("[*] Joining session...")
    await sio.emit('join_session', {'session_uuid': session_uuid}, namespace='/ws')

    # 3. Send Chat Message (Trigger Agent)
    await asyncio.sleep(1)
    logger.info("[*] Sending chat message...")
    message_payload = {
        "type": "query",
        "session_uuid": session_uuid,
        "content": {
            "message": "What time is it? (Testing tool call if available, or just chat)",
            "agent_type": "general" # Use general to trigger agent.py logic
        }
    }
    await sio.emit('chat_message', message_payload, namespace='/ws')
    
    # 4. Wait for response flow
    logger.info("[*] Waiting for response events (30s)...")
    await asyncio.sleep(30)
    
    await sio.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
