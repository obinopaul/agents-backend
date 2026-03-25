import asyncio
import uuid
import requests
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
USER_ID = 1  # Assuming user ID 1 exists (admin)
# Helper to get auth token (requires admin user to exist)
def get_auth_token():
    try:
        # Try login (assuming existing admin credentials from previous contexts or default)
        # Endpoint: /api/v1/auth/login (JSON body)
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": "admin@example.com",
            "password": "admin"
        })
        if response.status_code == 200:
            return response.json()["data"]["access_token"]
        
        # If default admin fails, try signup/login flow or assume manual token if needed
        logger.warning(f"Login failed: {response.status_code}. Trying signup...")
        signup_data = {
           "email": f"stress_test_{uuid.uuid4().hex[:8]}@example.com",
           "password": "password123",
           "name": "Test User",
           "confirm_password": "password123" 
        }
        # Endpoint: /api/v1/auth/register (JSON body)
        resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json=signup_data)
        if resp.status_code == 200:
             # Register returns access_token directly in data
            return resp.json()["data"]["access_token"]
        else:
            logger.error(f"Signup failed: {resp.text}")
            
    except Exception as e:
        logger.error(f"Auth failed: {e}")
    return None

TOKEN = get_auth_token()
HEADER = {"Authorization": f"Bearer {TOKEN}"}

def test_race_condition():
    logger.info("--- Starting Race Condition Test ---")
    session_id = str(uuid.uuid4())
    logger.info(f"Target Session UUID: {session_id}")
    
    # Simulate concurrent requests:
    # 1. HTTP Stream Request (agent.py)
    # 2. HTTP Chat Stream Request (chat.py)
    # 3. WebSocket Join (simulated via API for simplicity or just another HTTP call to an endpoint that calls get_or_create)
    # We will use concurrent invocations of the chat/stream endpoint for simplicity as it calls get_or_create
    
    import threading

    def call_stream_endpoint(agent_type="chat"):
        url = f"{BASE_URL}/agent/chat/stream" if agent_type == "chat" else f"{BASE_URL}/agent/agent/stream"
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "session_id": session_id,
            "agent_type": agent_type,
            "model_id": "gpt-4"
        }
        if agent_type != "chat":
             # agent stream payload
             payload = {
                 "messages": [{"role": "user", "content": "Hello"}],
                 "thread_id": session_id,
                 "module": "general"
             }
        
        try:
            r = requests.post(url, json=payload, headers=HEADER, stream=True)
            logger.info(f"Req ({agent_type}) status: {r.status_code}")
            # Just read a bit to trigger processing
            for chunk in r.iter_content(chunk_size=1024):
                break 
        except Exception as e:
            logger.error(f"Req ({agent_type}) failed: {e}")

    threads = []
    # Launch 5 concurrent threads trying to create the same session
    for i in range(5):
        t = threading.Thread(target=call_stream_endpoint, args=("chat" if i % 2 == 0 else "general",))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
        
    # Verify Session Exists
    verify_url = f"{BASE_URL}/agent/chat-sessions/{session_id}/events"
    resp = requests.get(verify_url, headers=HEADER)
    if resp.status_code == 200:
        logger.info(f"SUCCESS: Session {session_id} exists and is accessible.")
    else:
        logger.error(f"FAILURE: Session verification returned {resp.status_code}")

def test_general_mode_persistence():
    logger.info("\n--- Starting General Mode Persistence Test ---")
    session_id = str(uuid.uuid4())
    logger.info(f"Target Session UUID: {session_id}")
    
    url = f"{BASE_URL}/agent/agent/stream"
    payload = {
        "messages": [{"role": "user", "content": "Hello General Agent"}],
        "thread_id": session_id,
        "module": "general"
    }
    
    try:
        r = requests.post(url, json=payload, headers=HEADER, stream=True)
        logger.info(f"Stream Status: {r.status_code}")
        # Read stream
        for line in r.iter_lines():
            if line:
                pass # logger.info(f"Stream: {line}")
                break
                
        # Immediately check persistence
        time.sleep(1) # Allow DB commit
        verify_url = f"{BASE_URL}/agent/chat-sessions/{session_id}/events"
        resp = requests.get(verify_url, headers=HEADER)
        
        if resp.status_code == 200:
            logger.info(f"SUCCESS: General Mode Session {session_id} persisted!")
        elif resp.status_code == 404:
            logger.error(f"FAILURE: General Mode Session {session_id} NOT FOUND (404)")
        else:
            logger.error(f"FAILURE: Verify returned {resp.status_code}")
            
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")

if __name__ == "__main__":
    if TOKEN:
        test_race_condition()
        test_general_mode_persistence()
    else:
        logger.error("Could not obtain auth token. Aborting.")
