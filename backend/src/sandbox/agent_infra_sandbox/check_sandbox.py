#!/usr/bin/env python3
"""Check if Agent-Infra Sandbox is running and healthy.

This script:
1. Checks if the sandbox container is running
2. If not running, automatically starts it via docker-compose
3. Waits for the container to be ready
4. Verifies the sandbox is healthy

Usage:
    cd backend/src/sandbox/agent_infra_sandbox
    python check_sandbox.py
"""

import asyncio
import subprocess
import sys
import os
import time
from pathlib import Path


def get_script_dir() -> Path:
    """Get the directory containing this script."""
    return Path(__file__).parent.resolve()


def run_docker_compose() -> bool:
    """Run docker-compose up -d to start the sandbox container.
    
    Returns:
        True if successful, False otherwise
    """
    script_dir = get_script_dir()
    compose_file = script_dir / "docker-compose.yaml"
    
    if not compose_file.exists():
        print(f"❌ docker-compose.yaml not found at {compose_file}")
        return False
    
    print("🐳 Starting sandbox container with docker-compose...")
    print(f"   Working directory: {script_dir}")
    
    try:
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode == 0:
            print("✅ Docker container started successfully!")
            return True
        else:
            print(f"❌ docker-compose failed with exit code: {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ docker-compose timed out after 120 seconds")
        return False
    except FileNotFoundError:
        print("❌ docker-compose not found! Please install Docker Desktop.")
        return False
    except Exception as e:
        print(f"❌ Error running docker-compose: {e}")
        return False


async def check_sandbox_health(url: str, timeout: float) -> bool:
    """Check if sandbox is healthy and responding.
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        from agent_sandbox import AsyncSandbox
    except ImportError:
        print("❌ agent-sandbox package not installed!")
        print("   Install with: pip install agent-sandbox")
        return False
    
    try:
        client = AsyncSandbox(base_url=url, timeout=timeout)
        context = await client.sandbox.get_context()
        return True
    except Exception:
        return False


async def wait_for_sandbox(url: str, timeout: float, max_retries: int = 12, wait_seconds: int = 5) -> bool:
    """Wait for sandbox to become ready.
    
    Args:
        url: Sandbox URL
        timeout: Request timeout
        max_retries: Maximum number of retry attempts
        wait_seconds: Seconds to wait between retries
        
    Returns:
        True if sandbox became ready, False if timed out
    """
    print(f"⏳ Waiting for sandbox to be ready (max {max_retries * wait_seconds}s)...")
    
    for attempt in range(max_retries):
        if await check_sandbox_health(url, timeout):
            return True
        
        remaining = (max_retries - attempt - 1) * wait_seconds
        if remaining > 0:
            print(f"   Attempt {attempt + 1}/{max_retries} failed, retrying in {wait_seconds}s...")
            await asyncio.sleep(wait_seconds)
    
    return False


async def check_sandbox() -> bool:
    """Check sandbox health and print status."""
    try:
        from agent_sandbox import AsyncSandbox
    except ImportError:
        print("❌ agent-sandbox package not installed!")
        print("   Install with: pip install agent-sandbox")
        return False
    
    url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    timeout = float(os.environ.get("AGENT_INFRA_TIMEOUT", "60"))
    
    print(f"Checking Agent-Infra Sandbox at {url}...")
    print("-" * 50)
    
    # First check if sandbox is already running
    if await check_sandbox_health(url, timeout):
        return await print_sandbox_info(url, timeout)
    
    # Sandbox not running - try to start it
    print("⚠️  Sandbox is not running. Attempting to start automatically...")
    print()
    
    if not run_docker_compose():
        print()
        print("To start manually, run:")
        print("  cd backend/src/sandbox/agent_infra_sandbox")
        print("  docker-compose up -d")
        return False
    
    print()
    
    # Wait for sandbox to become ready
    if not await wait_for_sandbox(url, timeout):
        print("❌ Sandbox failed to start within expected time")
        print("   Check Docker logs: docker logs aio-sandbox")
        return False
    
    return await print_sandbox_info(url, timeout)


async def print_sandbox_info(url: str, timeout: float) -> bool:
    """Print sandbox information after successful health check."""
    try:
        from agent_sandbox import AsyncSandbox
        
        client = AsyncSandbox(base_url=url, timeout=timeout)
        context = await client.sandbox.get_context()
        home_dir = context.home_dir
        
        print("✅ Sandbox is running and healthy!")
        print(f"   Home directory: {home_dir}")
        
        try:
            result = await client.shell.exec_command(command="uname -a", timeout=30)
            if hasattr(result, 'data') and hasattr(result.data, 'output'):
                print(f"   System: {result.data.output.strip()}")
        except Exception:
            pass  # System info is optional
        
        print("-" * 50)
        print("Ready to run DeepAgent CLI:")
        print()
        print("  # Set your API key first:")
        print("  export OPENAI_API_KEY=your_key_here")
        print()
        print("  # Run the CLI:")
        print("  python -m deepagents_cli")
        print()
        return True
        
    except Exception as e:
        print(f"❌ Error getting sandbox info: {e}")
        return False


def main():
    """Entry point."""
    result = asyncio.run(check_sandbox())
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
