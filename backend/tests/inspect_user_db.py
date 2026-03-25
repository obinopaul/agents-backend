
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.database.db import async_db_session
from backend.app.admin.model import User
from backend.app.agent.model.agent_models import APIKey
from backend.app.agent.model.staged_file import StagedFile
from sqlalchemy import select

async def inspect_user():
    async with async_db_session() as session:
        result = await session.execute(select(User).where(User.username == "sandbox_test"))
        user = result.scalars().first()
        if user:
            print(f"User: {user.username}")
            print(f"ID: {user.id}")
            print(f"Password Hash: {user.password!r}")  # !r to see quotes and potential hidden chars
            print(f"Salt: {user.salt}")
        else:
            print("User sandbox_test NOT found!")

if __name__ == "__main__":
    asyncio.run(inspect_user())
