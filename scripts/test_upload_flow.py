import requests
import os
import sys
import json

# Configuration - Adjust these if needed
API_BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "acobapaul@gmail.com"  # Replace with valid credentials if needed
PASSWORD = "Repent19$" # Replace with valid credentials if needed

def login():
    """Logs in and returns the access token using Swagger endpoint (bypasses captcha)."""
    print(f"[*] Logging in as {USERNAME}...")
    url = f"{API_BASE_URL}/auth/login/swagger"
    try:
        # Endpoint expects query params, NOT Basic Auth header
        response = requests.post(url, params={"username": USERNAME, "password": PASSWORD})
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print(f"[+] Login successful. Token obtained.")
                return token
            else:
                print(f"[-] Login failed. No token in response: {data}")
                return None
        else:
            print(f"[-] Login failed. Status: {response.status_code}")
            try:
                print(f"Response: {response.json()}")
            except:
                print(f"Response (text): {response.content.decode('utf-8', errors='ignore')}")
            return None
    except Exception as e:
        print(f"[-] Login failed: {e}")
        return None

def test_upload(token):
    """Tests the full upload flow."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Generate Upload URL
    print("\n[*] Step 1: Generating Upload URL...")
    # Agent routes are mounted at /agent, NOT /api/v1/agent
    AGENT_BASE_URL = "http://localhost:8000"
    gen_url = f"{AGENT_BASE_URL}/agent/chat/generate-upload-url"
    
    file_name = "test_upload_file.txt"
    file_content = b"This is a test file for upload verification."
    content_type = "text/plain"
    file_size = len(file_content)
    
    payload = {
        "file_name": file_name,
        "content_type": content_type,
        "file_size": file_size
    }
    
    try:
        response = requests.post(gen_url, json=payload, headers=headers)
        if response.status_code != 200:
             print(f"[-] Failed to generate URL. Status: {response.status_code}")
             print(f"Response: {response.text}")
             return

        data = response.json()
        upload_url = data.get("upload_url")
        file_id = data.get("id")
        
        if not upload_url or not file_id:
            print(f"[-] Invalid response from generate-upload-url: {data}")
            return
            
        print(f"[+] Upload URL generated: {upload_url[:50]}...")
        print(f"[+] File ID: {file_id}")
        
    except Exception as e:
        print(f"[-] Error generating upload URL: {e}")
        return

    # 2. Upload File to Signed URL
    print("\n[*] Step 2: Uploading file to Signed URL...")
    try:
        # Note: Validating if specific headers are needed by the provider (e.g. Content-Type)
        upload_headers = {
            "Content-Type": content_type
        }
        
        put_response = requests.put(upload_url, data=file_content, headers=upload_headers)
        
        if put_response.status_code in [200, 201]:
            print(f"[+] File upload to storage successful.")
        else:
            print(f"[-] File upload to storage failed. Status: {put_response.status_code}")
            print(f"Response: {put_response.text}")
            return
            
    except Exception as e:
        print(f"[-] Error uploading file to storage: {e}")
        return

    # 3. Complete Upload
    print("\n[*] Step 3: Completing Upload...")
    # AGENT_BASE_URL is defined locally in step 1, but we should define it globally or reuse
    AGENT_BASE_URL = "http://localhost:8000"
    complete_url = f"{AGENT_BASE_URL}/agent/chat/upload-complete"
    complete_payload = {
        "id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "content_type": content_type
    }
    
    try:
        comp_response = requests.post(complete_url, json=complete_payload, headers=headers)
        
        if comp_response.status_code == 200:
            print(f"[+] Upload completion verified. Response: {comp_response.json()}")
        else:
            print(f"[-] Upload completion failed. Status: {comp_response.status_code}")
            print(f"Response: {comp_response.text}")
            
    except Exception as e:
        print(f"[-] Error completing upload: {e}")

def register_user():
    """Registers a new user and returns the token."""
    import random
    import string
    
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email = f"testuser_{rnd}@example.com"
    password = "Password123!"
    name = f"Test User {rnd}"
    
    print(f"[*] Attempting registration for {email}...")
    url = f"{API_BASE_URL}/auth/register"
    payload = {
        "email": email,
        "password": password,
        "name": name,
        "confirm_password": password
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            # Check structure of response
            token = data.get("data", {}).get("access_token")
            if token:
                print(f"[+] Registration successful. Token obtained.")
                return token
            else:
                 print(f"[-] Registration response missing token: {data}")
        else:
            print(f"[-] Registration failed. Status: {response.status_code}")
            try:
                print(f"Response: {response.json()}")
            except:
                print(f"Response: {response.text}")
    except Exception as e:
        print(f"[-] Registration error: {e}")
    return None

if __name__ == "__main__":
    print("--- Starting Upload Flow Verification ---")
    
    # Try login first
    token = login()
    
    # If login fails, try registration
    if not token:
        print("\n[*] Login failed, attempting registration to get fresh token...")
        token = register_user()
        
    if token:
        test_upload(token)
    else:
        print("Skipping upload test due to auth failure.")
