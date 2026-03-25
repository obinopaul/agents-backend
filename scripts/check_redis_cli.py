import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.database.redis import RedisCli, redis_client
from backend.core.conf import settings

async def main():
    print(f"[*] Testing RedisCli connection to {settings.REDIS_HOST}:{settings.REDIS_PORT}...")
    
    # Manually open if needed, though RedisCli usually lazy connects or connects on init? 
    # Looking at code, 'open' just pings.
    await redis_client.open()
    
    test_key = "agents:debug:test_key"
    test_val = "hello_world"
    
    print(f"[*] Setting key {test_key}...")
    await redis_client.set(test_key, test_val)
    
    print(f"[*] Getting key {test_key}...")
    val = await redis_client.get(test_key)
    
    print(f"[*] Result: {val}")
    
    if val == test_val:
        print("[+] RedisCli works correctly!")
    else:
        print("[-] RedisCli returned wrong value!")

if __name__ == "__main__":
    asyncio.run(main())
