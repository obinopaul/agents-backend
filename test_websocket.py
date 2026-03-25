import asyncio
import socketio
import httpx
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"
USERNAME = "sandbox_test"
PASSWORD = "TestPass123!"

async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Logging in to {API_URL}/auth/login...")
            response = await client.post(
                f"{API_URL}/auth/login",
                json={"username": USERNAME, "password": PASSWORD},
            )
            response.raise_for_status()
            # Handle wrapped response
            data = response.json()
            if "data" in data:
                return data["data"]["access_token"]
            return data["access_token"]
        except Exception as e:
            logger.error(f"Failed to get token: {e}")
            if 'response' in locals():
                logger.error(f"Response: {response.text}")
            raise

async def test_connect_without_session_uuid(token: str):
    sio = socketio.AsyncClient()
    
    @sio.event
    def connect():
        logger.info("Connected without session_uuid (Unexpected)")

    @sio.event
    def connect_error(data):
        logger.info(f"Connection failed as expected: {data}")

    @sio.event
    def disconnect():
        logger.info("Disconnected")

    try:
        url = f"{BASE_URL}"
        logger.info("Attempting connection WITHOUT session_uuid...")
        # Backend mounts at /ws and sets socketio_path='/ws/socket.io'
        # Request should go to http://localhost:8000/ws/socket.io/
        await sio.connect(
            url, 
            auth={"token": token}, 
            namespaces=['/ws'], 
            socketio_path='/ws/socket.io',
            wait_timeout=5
        )
        logger.info("Connected successfully? (Checking if active)")
        if sio.connected:
            logger.info("Socket is connected.")
            await sio.disconnect()
        else:
            logger.info("Socket failed to connect.")
            
    except Exception as e:
        logger.info(f"Connection failed/rejected (Expected): {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

async def test_connect_with_session_uuid(token: str):
    # Use a random UUID - server.py only checks if it's present, doesn't validate against DB during connect
    session_uuid = str(uuid.uuid4())
    
    sio = socketio.AsyncClient()
    
    @sio.event
    async def connect():
        logger.info("Connected WITH session_uuid")
        
    @sio.event
    def connect_error(data):
        logger.info(f"Connection failed: {data}")

    try:
        logger.info(f"Attempting connection WITH session_uuid={session_uuid}...")
        await sio.connect(
            BASE_URL, 
            auth={"token": token, "session_uuid": session_uuid}, 
            namespaces=['/ws'], 
            socketio_path='/ws/socket.io',
            wait_timeout=5
        )
        logger.info("Connected successfully!")
        await sio.disconnect()
    except Exception as e:
        logger.error(f"Connection failed (Unexpected): {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

async def main():
    try:
        token = await get_token()
        logger.info(f"Got token: {token[:10]}...")
        
        print("\n" + "="*50)
        await test_connect_without_session_uuid(token)
        print("="*50 + "\n")
        
        print("\n" + "="*50)
        await test_connect_with_session_uuid(token)
        print("="*50 + "\n")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
