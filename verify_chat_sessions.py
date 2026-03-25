import asyncio
import httpx
import logging
from typing import Dict, Any

# Configure logging
# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("verify.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
API_URL = "http://localhost:8000/api/v1"
USERNAME = "sandbox_test"
PASSWORD = "TestPass123!"

async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_URL}/auth/login",
                json={"username": USERNAME, "password": PASSWORD},
            )
            response.raise_for_status()
            return response.json()["data"]["access_token"]
        except httpx.HTTPStatusError as exc:
            logger.error(f"Login failed: {exc.response.text}")
            logger.error(f"Response headers: {exc.response.headers}")
            raise
        except Exception as exc:
            logger.error(f"An error occurred during login: {exc}")
            raise

async def create_session(token: str, name: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/agent/chat-sessions",
            json={"name": name, "agent_type": "chat"},
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()["data"]

async def list_sessions(token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/agent/chat-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()["data"]

async def main():
    try:
        # 1. Login
        logger.info(f"Logging in as {USERNAME}...")
        token = await get_token()
        logger.info("Login successful")

        # 2. Create a new session
        session_name = "Test Session " + str(asyncio.get_event_loop().time())
        logger.info(f"Creating session: {session_name}")
        created_session = await create_session(token, session_name)
        logger.info(f"Session created: {created_session['id']}")

        # 3. List sessions
        logger.info("Listing sessions...")
        sessions_list = await list_sessions(token)
        
        found = False
        for session in sessions_list["sessions"]:
            if session["id"] == created_session["id"]:
                found = True
                logger.info(f"Found created session in list: {session['name']} ({session['id']})")
                break
        
        if found:
            logger.info("SUCCESS: Chat history retrieval verified.")
        else:
            logger.error("FAILURE: Created session not found in list.")
            logger.info(f"Sessions found: {len(sessions_list['sessions'])}")

    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
