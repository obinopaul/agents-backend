
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv(backend_path / ".env")

from backend.database.db import async_db_session
from backend.app.admin.model import User
from backend.app.agent.model.agent_models import APIKey
from backend.app.agent.model.staged_file import StagedFile
from backend.app.admin.utils.password_security import get_hash_password
from sqlalchemy import select

async def ensure_sandbox_test_user():
    async with async_db_session() as session:
        # Check specifically for sandbox_test
        result = await session.execute(select(User).where(User.username == "sandbox_test"))
        user = result.scalars().first()
        
        if user:
            print(f"User 'sandbox_test' already exists (id: {user.id})")
            # We don't know the password if it already exists, so maybe reset it?
            # Ideally we assume it's TestPass123! or we update it.
            # Let's update it to be sure.
            password = "TestPass123!"
            hashed_password = get_hash_password(password, None)
            user.password = hashed_password
            await session.commit()
            print("Password reset to 'TestPass123!'")
            return

        print("Creating user 'sandbox_test'...")
        password = "TestPass123!"
        hashed_password = get_hash_password(password, None)
        
        new_user = User(
            username="sandbox_test",
            password=hashed_password,
            salt=None,
            nickname="Sandbox Tester",
            email="sandbox_test@example.com",
            is_superuser=True,
            is_staff=True,
            status=1,
        )
        session.add(new_user)
        await session.commit()
        print(f"Created user 'sandbox_test' with password '{password}'")

if __name__ == "__main__":
    asyncio.run(ensure_sandbox_test_user())
