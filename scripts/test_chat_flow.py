import asyncio
import socketio
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ChatTest")

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "http://localhost:8000"
API_BASE_URL = f"{BASE_URL}/api/v1"

# Credentials (use the ones that work)
USERNAME = "acobapaul@gmail.com"
PASSWORD = "Repent19$" 

sio = socketio.AsyncClient(logger=True, engineio_logger=True)

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
    logger.info(f"[<] Received Event: {event_type} | Content: {content}")

    if event_type == 'error':
        logger.error(f"!!! SERVER ERROR: {content.get('message')}")

async def main():
    token = await get_token()
    if not token:
        return

    # 1. Connect
    logger.info(f"[*] Connecting to {WS_URL}...")
    auth_payload = {"token": token, "session_uuid": "test-chat-session-1"}
    
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

    # 2. Join Session (Wait a bit for connection to settle)
    await asyncio.sleep(1)
    logger.info("[*] Joining session...")
    await sio.emit('join_session', {'session_uuid': 'test-chat-session-1'}, namespace='/ws')

    # 3. Send Chat Message
    await asyncio.sleep(1)
    logger.info("[*] Sending chat message...")
    message_payload = {
        "type": "query",
        "session_uuid": "test-chat-session-1",
        "content": {
            "message": "Hello from Test Script!",
            "agent_type": "chat"
        }
    }
    await sio.emit('chat_message', message_payload, namespace='/ws')
    
    # 4. Wait for response
    logger.info("[*] Waiting for response...")
    await asyncio.sleep(5)
    
    await sio.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
