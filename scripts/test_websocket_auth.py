import socketio
import asyncio
import requests
import sys

# Constants
API_BASE_URL = "http://localhost:8000"
WS_URL = "http://localhost:8000/ws" # Connection URL for socket.io client
AUTHENTICATION_TIMEOUT = 5

async def register_user_for_token():
    """Helper to get a valid token."""
    import random
    import string
    
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email = f"ws_test_{rnd}@example.com"
    password = "Password123!"
    
    # Try admin login first to save creating users
    try:
        # Check if we can login as admin (if user updated env, but unlikely)
        # Using correct admin credentials if known, else register
        res = requests.post(f"{API_BASE_URL}/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "name": f"WS Test {rnd}",
            "confirm_password": password
        })
        if res.status_code == 200:
            return res.json().get("data", {}).get("access_token")
    except:
        pass
    return None

async def test_websocket_connection():
    token = await register_user_for_token()
    if not token:
        print("[-] Could not obtain token. Skipping WebSocket test.")
        return

    print(f"[+] Token obtained: {token[:10]}...")

    # Initialize Socket.IO client
    # Note: backend/core/registrar.py sets socketio_path='/ws/socket.io'
    # And mounts it at /ws
    # So the full path might be /ws/ws/socket.io OR /ws/socket.io depending on how mount works.
    # Frontend uses path: '/ws/socket.io' and connects to VITE_API_URL/ws? No..
    # Frontend: io(`${import.meta.env.VITE_API_URL}/ws`, { path: '/ws/socket.io' })
    # If VITE_API_URL is localhost:8000, then it connects to localhost:8000/ws
    # with path /ws/socket.io.
    # Effective URL: localhost:8000/ws/socket.io
    
    sio = socketio.AsyncClient(logger=True, engineio_logger=True)

    @sio.event
    def connect():
        print("[+] WebSocket Connected!")

    @sio.event
    def connect_error(data):
        # Use repr() to avoid UnicodeEncodeErrors on Windows consoles with Chinese characters
        print(f"[-] Connection Error: {repr(data)}")

    @sio.event
    def disconnect():
        print("[-] Disconnected")

    try:
        # Authenticate via 'auth' dictionary as per frontend
        # Reverting to use VALID TOKEN for final verification
        auth_payload = {"token": token, "session_uuid": "test-session-id"}
        
        print(f"[*] Connecting to {WS_URL} with path='/ws/socket.io'...")
        
        # We try to replicate Frontend exactly
        await sio.connect(
            WS_URL, 
            auth=auth_payload, 
            socketio_path='/ws/socket.io',
            transports=['websocket', 'polling']
        )
        
        await sio.sleep(2)
        if sio.connected:
            print("[+] Connection verified as stable (Authenticated).")
            # If this works, Server is UP and Redis is UP.
            await sio.disconnect()
        else:
            print("[-] Not connected after wait.")

    except Exception as e:
        print(f"[-] Exception during connection: {e}")
    finally:
        await sio.disconnect()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_websocket_connection())
