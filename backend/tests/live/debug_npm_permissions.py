#!/usr/bin/env python3
"""
Debug NPM Permissions in E2B Sandbox
=====================================

Comprehensive diagnostic for npm cache and permission issues.
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


def header(msg):
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}")


def run_cmd(sandbox, cmd, desc, timeout=15):
    """Run a command and display results."""
    print(f"\n--- {desc} ---")
    print(f"$ {cmd}")
    try:
        result = sandbox.commands.run(cmd, timeout=timeout)
        if result.stdout:
            print(result.stdout[:1500] if len(result.stdout) > 1500 else result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr[:500]}")
        return result.stdout or ""
    except Exception as e:
        print(f"ERROR: {e}")
        return ""


def main():
    header("NPM PERMISSIONS DEBUG")
    print("Creating sandbox...")
    sandbox = Sandbox.create(TEMPLATE_ID)
    print(f"Sandbox ID: {sandbox.sandbox_id}")
    
    try:
        header("1. USER IDENTITY")
        run_cmd(sandbox, "whoami", "Current user")
        run_cmd(sandbox, "id", "User ID details")
        run_cmd(sandbox, "echo $HOME", "HOME environment")
        
        header("2. DIRECTORY OWNERSHIP")
        run_cmd(sandbox, "ls -la /home/", "List /home directory")
        run_cmd(sandbox, "ls -la /workspace", "List /workspace")
        run_cmd(sandbox, "stat /workspace", "Workspace permissions")
        
        header("3. NPM CACHE ANALYSIS")
        run_cmd(sandbox, "ls -la /home/pn/.npm 2>/dev/null || echo 'npm cache not found'", "NPM cache directory")
        run_cmd(sandbox, "find /home/pn/.npm -maxdepth 2 -ls 2>/dev/null | head -20 || echo 'Cannot list npm cache'", "NPM cache contents")
        run_cmd(sandbox, "stat /home/pn/.npm 2>/dev/null || echo 'Cannot stat npm cache'", "NPM cache permissions")
        
        header("4. NPM CONFIGURATION")
        run_cmd(sandbox, "npm config get cache", "npm cache location")
        run_cmd(sandbox, "npm config list", "npm config")
        run_cmd(sandbox, "echo $npm_config_cache", "npm_config_cache env var")
        
        header("5. BUN CACHE ANALYSIS")
        run_cmd(sandbox, "ls -la /home/pn/.bun 2>/dev/null || echo 'bun not found'", "Bun directory")
        run_cmd(sandbox, "which bun", "Bun location")
        
        header("6. WRITE TESTS")
        run_cmd(sandbox, "touch /workspace/test_write.txt && ls -la /workspace/test_write.txt && rm /workspace/test_write.txt && echo 'WORKSPACE WRITE: OK'", 
                "Test write to /workspace")
        run_cmd(sandbox, "touch /home/pn/.npm/test_write.txt 2>/dev/null && rm /home/pn/.npm/test_write.txt && echo 'NPM CACHE WRITE: OK' || echo 'NPM CACHE WRITE: FAILED'", 
                "Test write to npm cache")
        run_cmd(sandbox, "mkdir -p /home/user/test_dir && rmdir /home/user/test_dir && echo 'HOME/USER WRITE: OK' || echo 'HOME/USER WRITE: FAILED'", 
                "Test write to /home/user")
        
        header("7. NPM CREATE TEST")
        run_cmd(sandbox, "cd /workspace && npm init -y 2>&1 | head -20", "npm init in workspace", timeout=30)
        
        header("8. CREATE-NEXT-APP TEST")
        print("Attempting to create Next.js app (may take a while)...")
        run_cmd(sandbox, "cd /workspace && timeout 60 npx -y create-next-app@latest test-app --typescript --tailwind --eslint --app --src-dir --no-git --use-npm 2>&1 | head -40", 
                "Create Next.js app", timeout=90)
        
        header("9. ROOT-OWNED FILES CHECK")
        run_cmd(sandbox, "find /home/pn/.npm -user root 2>/dev/null | head -10 || echo 'No root-owned files found'", 
                "Find root-owned files in npm cache")
        run_cmd(sandbox, "find /home/pn -user root 2>/dev/null | head -10 || echo 'No root-owned files in /home/pn'", 
                "Find root-owned files in /home/pn")
        
        header("10. START-SERVICES.SH CHECK")
        run_cmd(sandbox, "grep -A5 'Runtime permission fix' /app/start-services.sh || echo 'Runtime fix not found in start-services.sh'", 
                "Check if runtime fix is present")
        
    finally:
        print("\n" + "="*70)
        print("Cleaning up...")
        sandbox.kill()
        print("Done.")


if __name__ == "__main__":
    main()
