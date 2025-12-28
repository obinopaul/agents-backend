#!/usr/bin/env python3
"""
Debug workspace permissions in E2B sandbox.
"""

import sys
import os
from e2b import Sandbox
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

TEMPLATE_ID = "vg6mdf4wgu5qoijamwb5"

print("Creating sandbox...")
sandbox = Sandbox.create(TEMPLATE_ID)
print(f"Sandbox ID: {sandbox.sandbox_id}")

def run_cmd(cmd, desc):
    print(f"\n=== {desc} ===")
    try:
        result = sandbox.commands.run(cmd, timeout=10)
        if result.stdout:
            print(result.stdout[:500])
        if result.stderr:
            print(f"STDERR: {result.stderr[:200]}")
    except Exception as e:
        print(f"Error: {e}")

try:
    # Check who owns /workspace
    run_cmd("ls -la / | grep workspace", "Check /workspace ownership")
    run_cmd("ls -la /workspace", "List /workspace contents")
    
    # Check current user running the MCP server
    run_cmd("whoami", "Current user")
    run_cmd("id", "User ID info")
    
    # Check the tmux session user
    run_cmd("ps aux | grep -E '(python|mcp)' | head -5", "MCP server process")
    
    # Try to write a file directly
    run_cmd("touch /workspace/test_write.txt && echo 'Write successful' || echo 'Write failed'", "Direct write test")
    
    # Check /workspace permissions
    run_cmd("stat /workspace", "Workspace stat")
    
    # Try as pn user explicitly
    run_cmd("su pn -c 'touch /workspace/pn_test.txt' && echo 'pn write OK' || echo 'pn write FAILED'", "Write as pn user")
    
finally:
    sandbox.kill()
    print("\nSandbox killed.")
