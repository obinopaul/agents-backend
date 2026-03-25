#!/usr/bin/env python
"""
Create Test User Script

This script creates a test user directly in the database with proper password hashing.
It includes validation to prevent duplicate usernames or emails.

Usage:
    python backend/tests/create_test_user.py

Requirements:
    - PostgreSQL database must be running and accessible
    - Run from project root directory
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


async def create_test_user(
    username: str = "sandbox_test",
    password: str = "TestPass123!",
    email: str = "sandbox_test@example.com",
    nickname: str = "Sandbox Test",
    is_superuser: bool = True,
    is_staff: bool = True,
) -> None:
    """
    Create a test user in the database.

    Args:
        username: Unique username for the user
        password: Plain text password (will be hashed)
        email: Unique email address
        nickname: Display name
        is_superuser: Grant superuser privileges
        is_staff: Grant staff access to admin panel
    """
    # Import after path setup
    # Load all models first to ensure relationships (APIKey, etc.) are initialized
    from backend import load_all_models
    load_all_models()
    
    from sqlalchemy import select

    from backend.app.admin.model.user import User
    from backend.database.db import async_db_session

    print(f"\n{'='*60}")
    print("  CREATE TEST USER SCRIPT")
    print(f"{'='*60}\n")

    async with async_db_session() as session:
        # Check if username already exists
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"⚠️  WARNING: Username '{username}' already exists!")
            print(f"   User ID: {existing_user.id}")
            print(f"   Email: {existing_user.email}")
            print(f"   Status: {'Active' if existing_user.status == 1 else 'Inactive'}")
            print("\n   Skipping user creation.")
            return

        # Check if email already exists
        if email:
            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            existing_email = result.scalar_one_or_none()

            if existing_email:
                print(f"⚠️  WARNING: Email '{email}' already exists!")
                print(f"   Assigned to: {existing_email.username}")
                print("\n   Skipping user creation.")
                return

        # Hash the password using pwdlib directly (bcrypt auto-generates salt)
        print(f"📦 Creating user '{username}'...")
        from pwdlib import PasswordHash
        from pwdlib.hashers.bcrypt import BcryptHasher
        password_hasher = PasswordHash((BcryptHasher(),))
        hashed_password = password_hasher.hash(password)

        # Create new user
        new_user = User(
            username=username,
            nickname=nickname,
            password=hashed_password,
            salt=None,  # bcrypt embeds salt in hash, not stored separately
            email=email,
            status=1,  # Active
            is_superuser=is_superuser,
            is_staff=is_staff,
            is_multi_login=True,
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        print(f"\n✅ SUCCESS: Test user created!")
        print(f"\n{'─'*60}")
        print(f"   Username:    {username}")
        print(f"   Password:    {password}")
        print(f"   Email:       {email}")
        print(f"   User ID:     {new_user.id}")
        print(f"   UUID:        {new_user.uuid}")
        print(f"   Superuser:   {'Yes' if is_superuser else 'No'}")
        print(f"   Staff:       {'Yes' if is_staff else 'No'}")
        print(f"{'─'*60}")
        print(f"\n🔐 You can now log in at: http://localhost:8000/api/v1/auth/login")
        print(f"📖 API Docs available at: http://localhost:8000/docs")
        print()


def main() -> None:
    """Entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a test user in the agents-backend database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/tests/create_test_user.py
  python backend/tests/create_test_user.py --username admin --password Admin123!
  python backend/tests/create_test_user.py --email admin@company.com --no-superuser
        """,
    )
    parser.add_argument(
        "--username",
        default="sandbox_test",
        help="Username for the test user (default: sandbox_test)",
    )
    parser.add_argument(
        "--password",
        default="TestPass123!",
        help="Password for the test user (default: TestPass123!)",
    )
    parser.add_argument(
        "--email",
        default="sandbox_test@example.com",
        help="Email for the test user (default: sandbox_test@example.com)",
    )
    parser.add_argument(
        "--nickname",
        default="Sandbox Test",
        help="Display name (default: Sandbox Test)",
    )
    parser.add_argument(
        "--no-superuser",
        action="store_true",
        help="Do not grant superuser privileges",
    )
    parser.add_argument(
        "--no-staff",
        action="store_true",
        help="Do not grant staff access",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            create_test_user(
                username=args.username,
                password=args.password,
                email=args.email,
                nickname=args.nickname,
                is_superuser=not args.no_superuser,
                is_staff=not args.no_staff,
            )
        )
    except KeyboardInterrupt:
        print("\n\n❌ Aborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n   Make sure the database is running and accessible.")
        print("   Check your .env file for correct DATABASE_* settings.")
        sys.exit(1)


if __name__ == "__main__":
    main()
