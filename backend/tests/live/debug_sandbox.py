from e2b import Sandbox
from dotenv import load_dotenv
import os
import time
import sys

# Load environment variables
load_dotenv()
E2B_API_KEY = os.getenv("E2B_API_KEY")
if not E2B_API_KEY:
    print("Error: E2B_API_KEY not found in environment variables")
    sys.exit(1)

TEMPLATE_ID = "vg6mdf4wgu5qoijamwb5"

print(f"Creating sandbox with template {TEMPLATE_ID}...")
sandbox = Sandbox.create(TEMPLATE_ID)
print(f"Sandbox object type: {type(sandbox)}")
print(f"Sandbox attributes: {dir(sandbox)}")
# print(f"Sandbox ID: {sandbox.id}") # Commented out to avoid crash

def run_command(cmd, description):
    print(f"\n=== {description} ===")
    try:
        result = sandbox.commands.run(cmd, timeout=10)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error: {e}")

try:
    # 1. Check Directory Structure
    run_command("ls -la /app/agents_backend/src/tool_server", "Checking tool_server structure")
    run_command("ls -la /app/agents_backend/src/tool_server/mcp", "Checking tool_server/mcp structure")
    
    # Check for __init__.py files
    print('\n=== Check for __init__.py files ===')
    try:
        result = sandbox.commands.run('find /app/agents_backend/src/tool_server -name "__init__.py"')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')

    # 2. Check Startup Scripts
    run_command("ls -l /app/entrypoint.sh /app/start-services.sh", "Checking startup scripts")
    run_command("cat /app/entrypoint.sh", "Entrypoint script content")
    
    # 3. Try to manually run start-services.sh
    print('\n=== Manually running start-services.sh ===')
    try:
        # Run in background
        result = sandbox.commands.run('bash /app/start-services.sh &', timeout=5)
        print(f'stdout: {result.stdout}')
    except Exception as e:
        print(f'Command sent (timeout expected for background process)')
    
    # Wait a bit for services
    print('\nWaiting 15 seconds...')
    time.sleep(15)
    
    # 4. Check Logs
    run_command("cat /tmp/mcp-server.log", "Reading /tmp/mcp-server.log")
    
    # 5. Check tmux sessions
    run_command('tmux list-sessions 2>&1 || echo "No tmux sessions"', "Checking tmux sessions")
    
    # Capture tmux pane output to see MCP server errors
    print('\n=== MCP Server tmux output ===')
    try:
        result = sandbox.commands.run('tmux capture-pane -t mcp-server-system-never-kill -p -S -100 2>&1')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
    
    # 6. Direct MCP Server Test
    print('\n=== Direct MCP server test ===')
    try:
        # Try running directly to capture stderr
        result = sandbox.commands.run(
            'cd /app/agents_backend/src && PYTHONPATH=/app/agents_backend/src WORKSPACE_DIR=/workspace timeout 5 python -m tool_server.mcp.server --port 6061 2>&1 || true',
            timeout=10
        )
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')

    # 7. Check Port
    print('\n=== Port 6060 status ===')
    try:
        result = sandbox.commands.run('netstat -tuln | grep 6060 || echo "Port 6060 not listening"')
        print(result.stdout)
    except Exception as e:
        print(f'Error: {e}')
        
    # Check symlinks
    run_command("ls -la /app/agents_backend/src/backend/src", "Checking backend/src structure")

    # 8. Test Python Imports
    print('\n=== Testing Python imports ===')
    try:
        cmd = """
python -c "
import sys
sys.path.append('/app/agents_backend/src')
try:
    from tool_server.mcp.server import main
    print('Import successful!')
except ImportError as e:
    print(f'Import failed: {e}')
    import os
    print(f'CWD: {os.getcwd()}')
    print(f'Path: {sys.path}')
"
"""
        result = sandbox.commands.run(cmd)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error: {e}")

except Exception as e:
    print(f"\nGlobal Error: {e}")
finally:
    sandbox.kill()
    print("\nSandbox killed.")
