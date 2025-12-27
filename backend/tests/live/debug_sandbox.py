#!/usr/bin/env python3
"""Debug script to inspect MCP server startup inside E2B sandbox."""

import asyncio
from e2b import AsyncSandbox
import os

async def debug():
    print('Creating sandbox with template vg6mdf4wgu5qoijamwb5...')
    sandbox = await AsyncSandbox.create('vg6mdf4wgu5qoijamwb5', api_key=os.getenv('E2B_API_KEY'))
    print(f'Sandbox ID: {sandbox.id}')
    
    # Wait for services to start (or fail)
    print('Waiting 30 seconds for services to start...')
    await asyncio.sleep(30)
    
    # Check if MCP server log exists
    print('\n=== Reading /tmp/mcp-server.log ===')
    try:
        result = await sandbox.commands.run('cat /tmp/mcp-server.log 2>&1 || echo "Log file not found"')
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f'Error reading log: {e}')
    
    # Check if tmux sessions exist
    print('\n=== Checking tmux sessions ===')
    try:
        result = await sandbox.commands.run('tmux list-sessions 2>&1 || echo "No tmux sessions"')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
    
    # Check running processes
    print('\n=== Running processes ===')
    try:
        result = await sandbox.commands.run('ps aux | grep -E "(python|tool_server)" | head -10')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
        
    # Check if port 6060 is listening
    print('\n=== Port 6060 status ===')
    try:
        result = await sandbox.commands.run('netstat -tlnp 2>&1 | grep 6060 || echo "Port 6060 not listening"')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
    
    # Check the directory structure
    print('\n=== Checking backend/src symlink ===')
    try:
        result = await sandbox.commands.run('ls -la /app/agents_backend/src/backend/src/ 2>&1')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
    
    # Try to import manually
    print('\n=== Testing Python imports ===')
    try:
        result = await sandbox.commands.run(
            'cd /app/agents_backend/src && PYTHONPATH=/app/agents_backend/src python -c "from backend.src.tool_server.tools.manager import get_sandbox_tools; print(\'Import successful!\')" 2>&1'
        )
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
    
    # Cleanup
    await sandbox.kill()
    print('\nSandbox killed.')

if __name__ == "__main__":
    asyncio.run(debug())
