import requests
import json
import redis
import jwt
import sys
import os

# Configuration
API_BASE_URL = "http://localhost:8000"
# Assumes Redis is exposed on localhost:6379 (standard Docker mapping)
REDIS_HOST = "localhost"
REDIS_PORT = 6379 
REDIS_DB = 0

# Try to load SECRET from .env if possible, else we might not be able to verify signature locally
# But we can still decode payload without verifying signature to inspect contents.

def debug_jwt_flow():
    print("--- Starting Deep JWT Debug ---")
    
    # 1. Register/Login to get Token
    import random
    import string
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email = f"debug_{rnd}@example.com"
    password = "Password123!"
    
    print(f"[*] Registering user: {email}")
    try:
        res = requests.post(f"{API_BASE_URL}/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "name": f"Debug User {rnd}",
            "confirm_password": password
        })
        if res.status_code != 200:
            print(f"[-] Registration failed: {res.text}")
            return
            
        data = res.json()
        token = data.get("data", {}).get("access_token")
        if not token:
            print(f"[-] No token in response: {data}")
            return
            
        print(f"[+] Token obtained: {token[:20]}...")
        
        # 2. Decode Token (Client Side Inspection)
        print("\n[*] Inspecting Token Payload...")
        try:
            # Decode without verification to see payload contents
            payload = jwt.decode(token, options={"verify_signature": False})
            print(f"    - User ID (sub): {payload.get('sub')}")
            print(f"    - Session UUID: {payload.get('session_uuid')}")
            print(f"    - Expires (exp): {payload.get('exp')}")
            
            user_id = payload.get('sub')
            session_uuid = payload.get('session_uuid')
            
        except Exception as e:
            print(f"[-] Failed to decode token locally: {e}")
            return

        # 3. Check Redis Persistence
        print("\n[*] Checking Redis Persistence...")
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
            r.ping()
            print(f"[+] Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            
            # Construct expected keys based on backend/common/security/jwt.py
            # settings.TOKEN_REDIS_PREFIX = 'agents_backend:token'
            token_key = f"agents_backend:token:{user_id}:{session_uuid}"
            
            print(f"    - Looking for Key: {token_key}")
            
            stored_token = r.get(token_key)
            if stored_token:
                print(f"[+] Key FOUND in Redis!")
                if stored_token == token:
                     print(f"[+] Stored token MATCHES client token.")
                else:
                     print(f"[-] Stored token MISMATCH.")
                     print(f"    Stored: {stored_token[:20]}...")
                     print(f"    Client: {token[:20]}...")
            else:
                print(f"[-] Key NOT FOUND in Redis.")
                print("    Potential causes: Redis DB mismatch, Prefix mismatch, or Expiry.")
                
                # List similar keys
                print("    - Listing all keys matching agents_backend:token:* ...")
                keys = r.keys(f"agents_backend:token:*")
                print(f"    - Found {len(keys)} tokens in Redis.")
                for k in keys[:5]:
                    print(f"      - {k}")
                    
        except Exception as e:
            print(f"[-] Redis connection failed: {e}")
            print("    (Expected if Redis is not exposed to Host on 6379)")

        # 4. Check API Access (Proxy for User/token validity)
        print("\n[*] Checking API Access (User Info)...")
        try:
            # /api/v1/sys/users/me requires DependsJwtAuth
            user_info_url = f"{API_BASE_URL}/api/v1/sys/users/me"
            headers = {"Authorization": f"Bearer {token}"}
            
            resp = requests.get(user_info_url, headers=headers)
            if resp.status_code == 200:
                print(f"[+] API Access Successful. User Info: {resp.json()}")
            else:
                print(f"[-] API Access Failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text}")
                
        except Exception as e:
            print(f"[-] API check failed: {e}")

    except Exception as e:
        print(f"[-] Unexpected error: {e}")

if __name__ == "__main__":
    debug_jwt_flow()
