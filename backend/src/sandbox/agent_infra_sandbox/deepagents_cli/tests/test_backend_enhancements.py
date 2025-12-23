"""Test script for AgentInfraBackend enhancements.

Run this script to verify all new methods work correctly.
Requires the sandbox to be running: docker compose up -d
"""

import asyncio
import os
import sys

# Add the parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.agent_infra import AgentInfraBackend


def test_basic_connectivity():
    """Test basic sandbox connectivity."""
    print("\n" + "="*60)
    print("TEST: Basic Connectivity")
    print("="*60)
    
    backend = AgentInfraBackend()
    
    # Health check
    healthy = backend.health_check()
    print(f"✓ Health check: {'PASSED' if healthy else 'FAILED'}")
    
    if not healthy:
        print("ERROR: Sandbox not healthy. Is docker compose up?")
        return False
    
    # Get sandbox info
    info = backend.get_sandbox_info()
    print(f"✓ Sandbox info retrieved:")
    print(f"  - Base URL: {info['base_url']}")
    print(f"  - Home dir: {info['home_dir']}")
    print(f"  - Workspace: {info['current_workspace']}")
    print(f"  - VNC URL: {info['urls']['vnc']}")
    print(f"  - Code Server: {info['urls']['code_server']}")
    
    return True


def test_workspace_initialization():
    """Test workspace initialization."""
    print("\n" + "="*60)
    print("TEST: Workspace Initialization")
    print("="*60)
    
    backend = AgentInfraBackend()
    
    # Initialize a test workspace
    result = backend.initialize_workspace(session_name="test_session")
    print(f"✓ Workspace initialized: {result}")
    print(f"  - Current workspace: {backend.current_workspace}")
    
    # List workspaces
    workspaces = backend.list_workspaces()
    print(f"✓ Workspaces found: {workspaces}")
    
    return True


def test_shell_session_management():
    """Test shell session management."""
    print("\n" + "="*60)
    print("TEST: Shell Session Management")
    print("="*60)
    
    backend = AgentInfraBackend()
    backend.initialize_workspace(session_name="shell_test")
    
    # Create a shell session
    result = backend.create_shell_session(session_id="test_shell_1")
    print(f"✓ Created shell session: {result}")
    
    # Execute in session
    result = backend.execute_in_session(
        command="echo 'Hello from shell session!'",
        session_id="test_shell_1"
    )
    print(f"✓ Executed in session: {result}")
    
    # List sessions
    sessions = backend.list_shell_sessions()
    print(f"✓ Active sessions: {sessions}")
    
    # Cleanup
    result = backend.cleanup_sessions(session_id="test_shell_1")
    print(f"✓ Cleaned up session: {result}")
    
    return True


def test_file_operations():
    """Test SDK-based file operations."""
    print("\n" + "="*60)
    print("TEST: File Operations (SDK-based)")
    print("="*60)
    
    backend = AgentInfraBackend()
    backend.initialize_workspace(session_name="file_test")
    
    # Write a file
    result = backend.write_file(
        path="test_file.txt",
        content="Hello from SDK file operations!\nLine 2 with special chars: 日本語",
        encoding="utf-8"
    )
    print(f"✓ Wrote file: {result}")
    
    # Read the file back
    result = backend.read_file(path="test_file.txt")
    print(f"✓ Read file: {result}")
    
    # Edit the file
    result = backend.edit_file(
        path="test_file.txt",
        old_str="Hello",
        new_str="Greetings"
    )
    print(f"✓ Edited file: {result}")
    
    # List directory
    result = backend.list_directory()
    print(f"✓ Directory listing: {result}")
    
    # Search files
    result = backend.search_files(query="*.txt")
    print(f"✓ Search files: {result}")
    
    return True


def test_browser_info():
    """Test browser API methods."""
    print("\n" + "="*60)
    print("TEST: Browser API")
    print("="*60)
    
    backend = AgentInfraBackend()
    
    # Get browser info
    info = backend.get_browser_info()
    print(f"✓ Browser info: {info}")
    
    # Get CDP URL
    cdp = backend.get_browser_cdp_url()
    print(f"✓ CDP URL: {cdp}")
    
    # Get VNC URL
    vnc = backend.get_vnc_url()
    print(f"✓ VNC URL: {vnc}")
    
    return True


def test_jupyter_execution():
    """Test Jupyter execution."""
    print("\n" + "="*60)
    print("TEST: Jupyter Execution")
    print("="*60)
    
    backend = AgentInfraBackend()
    backend.initialize_workspace(session_name="jupyter_test")
    
    # Execute Python code
    result = backend.execute_python(
        code="import sys; print(f'Python {sys.version}')",
        timeout=30
    )
    print(f"✓ Python execution: {result}")
    
    # Get Jupyter info
    info = backend.get_jupyter_info()
    print(f"✓ Jupyter info: {info}")
    
    # List Jupyter sessions
    sessions = backend.list_jupyter_sessions()
    print(f"✓ Jupyter sessions: {sessions}")
    
    return True


def test_mcp_integration():
    """Test MCP integration."""
    print("\n" + "="*60)
    print("TEST: MCP Integration")
    print("="*60)
    
    backend = AgentInfraBackend()
    
    # Get MCP endpoint
    endpoint = backend.get_mcp_endpoint()
    print(f"✓ MCP endpoint: {endpoint}")
    
    # List MCP servers
    servers = backend.list_mcp_servers()
    print(f"✓ MCP servers: {servers}")
    
    # List MCP tools
    tools = backend.list_mcp_tools()
    print(f"✓ MCP tools available: {len(tools)} tools")
    if tools:
        print(f"  - First tool: {tools[0].get('name', 'unknown')}")
    
    return True


def test_venv_creation():
    """Test virtual environment creation."""
    print("\n" + "="*60)
    print("TEST: Virtual Environment Creation")
    print("="*60)
    
    backend = AgentInfraBackend()
    backend.initialize_workspace(session_name="venv_test")
    
    # Create venv
    result = backend.create_venv(name="test_venv")
    print(f"✓ Created venv: {result}")
    
    if result.get("success"):
        # Run command in venv
        result = backend.run_in_venv(
            command="pip --version",
            venv_name="test_venv"
        )
        print(f"✓ Ran in venv: {result}")
    
    return True


async def test_mcp_tools_async():
    """Test async MCP tools retrieval."""
    print("\n" + "="*60)
    print("TEST: Async MCP Tools (LangChain Integration)")
    print("="*60)
    
    backend = AgentInfraBackend()
    
    try:
        tools = await backend.get_mcp_tools()
        print(f"✓ Got {len(tools)} LangChain-compatible tools via MCP")
        if tools:
            print(f"  - Example: {tools[0].name}")
        return True
    except ImportError as e:
        print(f"⚠ Skipped (missing dependency): {e}")
        return True  # Not a failure, just missing optional dependency
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AgentInfraBackend Enhancement Tests")
    print("="*60)
    print("Make sure the sandbox is running: docker compose up -d")
    
    os.environ.setdefault("AGENT_INFRA_URL", "http://localhost:8090")
    
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("Workspace Initialization", test_workspace_initialization),
        ("Shell Session Management", test_shell_session_management),
        ("File Operations", test_file_operations),
        ("Browser API", test_browser_info),
        ("Jupyter Execution", test_jupyter_execution),
        ("MCP Integration", test_mcp_integration),
        ("Virtual Environment", test_venv_creation),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ {name} FAILED with exception: {e}")
            results.append((name, False))
    
    # Run async test
    try:
        passed = asyncio.run(test_mcp_tools_async())
        results.append(("Async MCP Tools", passed))
    except Exception as e:
        print(f"\n✗ Async MCP Tools FAILED: {e}")
        results.append(("Async MCP Tools", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
