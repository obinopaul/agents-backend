#!/usr/bin/env python3
"""Create a test user for authenticated sandbox testing."""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv(backend_path / ".env")


async def check_and_create_user():
    """Check for existing users and create test user if needed."""
    from backend.database.db import async_db_session
    from backend.app.admin.model import User
    from backend.app.admin.utils.password_security import get_hash_password
    from sqlalchemy import select
    
    async with async_db_session() as session:
        # Check for existing users
        result = await session.execute(select(User).limit(5))
        users = result.scalars().all()
        
        if users:
            print(f"Found {len(users)} existing users:")
            for u in users:
                print(f"  - {u.username} (id: {u.id})")
            print(f"\nYou can use existing user: {users[0].username}")
            return users[0].username
        
        # No users exist - create test user
        print("No users found. Creating test user 'sandbox_test'...")
        
        # Hash password with default salt (None lets bcrypt generate its own)
        password = "TestPass123!"
        hashed_password = get_hash_password(password, None)
        
        # Create user - salt can be None for bcrypt (salt is embedded in hash)
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
        await session.refresh(new_user)
        
        print(f"Created user: {new_user.username} (id: {new_user.id})")
        print(f"Password: {password}")
        
        return new_user.username


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    username = asyncio.run(check_and_create_user())
    print(f"\nTest user ready: {username}")
