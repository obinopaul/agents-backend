import asyncio
import socketio
import os
from urllib.parse import urlparse

# Settings validation simulation
REDIS_HOST = "localhost" # simulating host access
REDIS_PORT = 6379
REDIS_PASSWORD = "" # simulating empty password from .env
REDIS_DATABASE = 0

async def check_redis_manager():
    print("--- Checking AsyncRedisManager URL Construction ---")
    
    # Logic from backend/common/socketio/server.py
    redis_url = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DATABASE}'
    print(f"[*] Constructed URL: {redis_url}")
    
    try:
        # Check URL parsing
        parsed = urlparse(redis_url)
        print(f"[*] Parsed - Source: {parsed.username}, Password: {parsed.password}, Host: {parsed.hostname}")
        
        # Initialize Manager
        mgr = socketio.AsyncRedisManager(redis_url)
        print("[+] Manager initialized. Attempting to emit (trigger connection)...")
        
        # Manager doesn't connect until used usually.
        # But let's try to see if it raises error immediately or on use.
        await mgr.emit('test', {'data': 'test'})
        print("[+] Emit successful (likely queued, but no immediate crash).")
        
        # We can't easily verify connection success without a client pairing, 
        # but if the URL is blatantly invalid, it might crash here.
        
    except Exception as e:
        print(f"[-] Manager test failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_redis_manager())
