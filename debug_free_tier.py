
import asyncio
import logging
import traceback
import sys
import os

# Set valid Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

async def debug_free_tier():
    try:
        from backend.tests.create_test_user import create_test_user
        from backend.src.billing.subscriptions import ensure_free_tier_subscription
        from backend.app.admin.model.user import User
        from backend.database.db import async_db_session
        from sqlalchemy import select

        print("Creating User...")
        username = "debug_user_001"
        try:
            await create_test_user(username, f"{username}@example.com", "Debug", False)
        except Exception:
            pass # Maybe exists

        async with async_db_session() as session:
            res = await session.execute(select(User).where(User.username == username))
            user = res.scalar_one()
            user_id = str(user.uuid)

        print(f"User ID: {user_id}")
        
        print("Calling ensure_free_tier_subscription...")
        result = await ensure_free_tier_subscription(user_id)
        print(f"Result: {result}")

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_free_tier())
