#!/usr/bin/env python3
"""
Diagnostic script to trace OPENAI_API_KEY flow from .env to sandbox config.
Run this from the project root:
    python backend/tests/live/debug_api_key_flow.py
"""

import os
import sys

# Add the project to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

def main():
    print("=" * 70)
    print("OPENAI_API_KEY FLOW DIAGNOSTIC")
    print("=" * 70)
    
    # Step 1: Check raw environment variable
    print("\n[1] RAW ENVIRONMENT VARIABLE:")
    raw_env_key = os.getenv("OPENAI_API_KEY")
    if raw_env_key:
        print(f"    ✅ Found in os.environ: {raw_env_key[:25]}...")
    else:
        print("    ❌ NOT FOUND in os.environ")
    
    # Step 2: Check if .env file exists and contains the key
    print("\n[2] .ENV FILE CHECK:")
    env_file_path = os.path.join(project_root, "backend", ".env")
    print(f"    Looking for: {env_file_path}")
    
    if os.path.exists(env_file_path):
        print(f"    ✅ .env file exists")
        with open(env_file_path, 'r') as f:
            content = f.read()
            if "OPENAI_API_KEY" in content:
                # Find the line
                for line in content.split('\n'):
                    if line.startswith('OPENAI_API_KEY'):
                        key_value = line.split('=', 1)[1].strip().strip("'\"")
                        print(f"    ✅ OPENAI_API_KEY found in .env: {key_value[:25]}...")
                        break
            else:
                print("    ❌ OPENAI_API_KEY NOT FOUND in .env file")
    else:
        print(f"    ❌ .env file NOT FOUND at {env_file_path}")
    
    # Step 3: Check pydantic settings loading
    print("\n[3] PYDANTIC SETTINGS (backend.core.conf):")
    try:
        from backend.core.conf import settings
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            print(f"    ✅ settings.OPENAI_API_KEY: {settings.OPENAI_API_KEY[:25]}...")
        else:
            print("    ❌ settings.OPENAI_API_KEY is EMPTY or not set")
            print(f"    Value: {repr(getattr(settings, 'OPENAI_API_KEY', 'ATTRIBUTE_MISSING'))}")
    except Exception as e:
        print(f"    ❌ Error loading settings: {e}")
    
    # Step 4: Check SandboxConfig loading
    print("\n[4] SANDBOX CONFIG:")
    try:
        from backend.src.sandbox.sandbox_server.config import SandboxConfig
        config = SandboxConfig()
        if config.openai_api_key:
            print(f"    ✅ config.openai_api_key: {config.openai_api_key[:25]}...")
        else:
            print("    ❌ config.openai_api_key is EMPTY or None")
            print(f"    Value: {repr(config.openai_api_key)}")
    except Exception as e:
        print(f"    ❌ Error creating SandboxConfig: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 5: Check path configuration
    print("\n[5] PATH CONFIGURATION:")
    try:
        from backend.core.path_conf import BASE_PATH
        print(f"    BASE_PATH: {BASE_PATH}")
        expected_env = os.path.join(BASE_PATH, ".env")
        print(f"    Expected .env path: {expected_env}")
        print(f"    .env exists at expected path: {os.path.exists(expected_env)}")
    except Exception as e:
        print(f"    ❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
