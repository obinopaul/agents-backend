
import asyncio
import sys
import os

sys.path.append('/agents_backend')

try:
    from backend.core.conf import settings
    from backend.database.db import async_engine
    from sqlalchemy import text
    from redis.asyncio import Redis
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def check():
    print("--- ADVANCED DIAGNOSTICS ---")
    
    # 1. Inspect Users
    print("\n[Database: Users]")
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT id, username, email, status, is_superuser FROM sys_user"))
            users = result.fetchall()
            print(f"Found {len(users)} users:")
            for u in users:
                print(f" - ID: {u[0]}, Username: {u[1]}, Email: {u[2]}, Status: {u[3]}, Superuser: {u[4]}")
    except Exception as e:
        print(f"❌ User Query Failed: {e}")

    # 2. Check Redis
    print("\n[Redis]")
    print(f"Host: {settings.REDIS_HOST}")
    print(f"Port: {settings.REDIS_PORT}")
    try:
        r = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DATABASE,
            socket_timeout=5
        )
        await r.ping()
        print("✅ Redis Connection: OK")
        await r.close()
    except Exception as e:
        print(f"❌ Redis Connection FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(check())
