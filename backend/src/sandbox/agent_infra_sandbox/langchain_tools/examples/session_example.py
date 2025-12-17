"""Session-based example demonstrating automatic workspace isolation."""

import asyncio
from backend.src.sandbox.agent_infra_sandbox.langchain_tools import SandboxSession


async def session_example():
    """Demonstrate session-based workspace isolation."""
    
    print("=" * 60)
    print("LangChain Sandbox Tools - Session-Based Workspace Example")
    print("=" * 60)
    
    # Create a session - automatically creates isolated workspace
    print("\n📦 Creating isolated sandbox session...")
    
    session = await SandboxSession.create(session_id="demo_chat_123")
    
    print(f"✅ Session created!")
    info = session.get_info()
    print(f"   Session ID: {info['session_id']}")
    print(f"   Workspace: {info['workspace_path']}")
    print(f"   Shell Session: {info['shell_session_id']}")
    print(f"   Jupyter Session: {info['jupyter_session_id']}")
    
    # Get workspace-scoped tools
    tools = session.get_tools()
    tool_map = {t.name: t for t in tools}
    
    print(f"\n🔧 Got {len(tools)} workspace-scoped tools")
    
    # =========================================================================
    # Example 1: File operations (paths are relative to workspace!)
    # =========================================================================
    print("\n" + "-" * 40)
    print("Example 1: File Operations (Relative Paths)")
    print("-" * 40)
    
    # Write a Python file - just use "app.py", not full path!
    await tool_map["file_write"].ainvoke({
        "file": "app.py",  # Goes to /home/gem/workspaces/demo_chat_123/app.py
        "content": '''"""Simple demo app."""

def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
''',
    })
    print("✅ Wrote app.py (relative path)")
    
    # Create a subdirectory and file
    await tool_map["file_write"].ainvoke({
        "file": "src/utils.py",  # Subdirectory created automatically
        "content": '''"""Utility functions."""

def add(a: int, b: int) -> int:
    return a + b
''',
    })
    print("✅ Wrote src/utils.py (created src/ automatically)")
    
    # List workspace contents
    listing = await tool_map["file_list"].ainvoke({"path": "."})
    print(f"\n📁 Workspace contents:\n{listing}")
    
    # Read file back
    content = await tool_map["file_read"].ainvoke({"file": "app.py"})
    print(f"\n📄 Read app.py:\n{content}")
    
    # =========================================================================
    # Example 2: Shell execution (runs in workspace directory)
    # =========================================================================
    print("\n" + "-" * 40)
    print("Example 2: Shell Execution (In Workspace)")
    print("-" * 40)
    
    # Run Python file - no need to specify path!
    result = await tool_map["shell_exec"].ainvoke({
        "command": "python app.py",  # Runs from workspace directory
    })
    print(f"Python output:\n{result}")
    
    # Check current directory
    result = await tool_map["shell_exec"].ainvoke({"command": "pwd"})
    print(f"\nWorking directory: {result}")
    
    # =========================================================================
    # Example 3: Python execution (session-specific kernel)
    # =========================================================================
    print("\n" + "-" * 40)
    print("Example 3: Jupyter Execution (Persistent Session)")
    print("-" * 40)
    
    # Execute Python - variables persist
    result = await tool_map["python_execute"].ainvoke({
        "code": """
import os
print(f"Working in: {os.getcwd()}")

# Define a variable
data = [1, 2, 3, 4, 5]
print(f"Created data: {data}")
""",
    })
    print(f"Jupyter output:\n{result}")
    
    # Use the variable from previous call
    result = await tool_map["python_execute"].ainvoke({
        "code": """
# Variable persists from last call!
print(f"Sum of data: {sum(data)}")
print(f"Mean: {sum(data) / len(data)}")
""",
    })
    print(f"\nVariables persisted:\n{result}")
    
    # =========================================================================
    # Example 4: Search with grep
    # =========================================================================
    print("\n" + "-" * 40)
    print("Example 4: Grep Search")
    print("-" * 40)
    
    result = await tool_map["grep"].ainvoke({
        "pattern": "def .*:",
        "glob": "*.py",
    })
    print(result)
    
    # =========================================================================
    # Example 5: Workspace info
    # =========================================================================
    print("\n" + "-" * 40)
    print("Example 5: Workspace Info")
    print("-" * 40)
    
    info_result = await tool_map["workspace_info"].ainvoke({})
    print(info_result)
    
    health = await tool_map["workspace_health"].ainvoke({})
    print(f"\n{health}")
    
    # =========================================================================
    # Example 6: Security - paths can't escape
    # =========================================================================
    print("\n" + "-" * 40)
    print("Example 6: Security (Path Escape Prevention)")
    print("-" * 40)
    
    # Try to read outside workspace
    result = await tool_map["file_read"].ainvoke({
        "file": "../../../etc/passwd"  # Attempt to escape
    })
    print(f"Escape attempt result: {result}")  # Should show error
    
    # Cleanup
    print("\n" + "-" * 40)
    print("Cleaning up...")
    print("-" * 40)
    
    await session.cleanup()
    print("✅ Session cleaned up")
    
    print("\n" + "=" * 60)
    print("✅ Session-based example completed!")
    print("=" * 60)


async def multi_session_example():
    """Show multiple concurrent sessions with isolation."""
    
    print("\n" + "=" * 60)
    print("Multi-Session Isolation Example")
    print("=" * 60)
    
    # Create two concurrent sessions
    session_a = await SandboxSession.create(session_id="chat_alice")
    session_b = await SandboxSession.create(session_id="chat_bob")
    
    tools_a = {t.name: t for t in session_a.get_tools()}
    tools_b = {t.name: t for t in session_b.get_tools()}
    
    print(f"\n📦 Session A workspace: {session_a.workspace_path}")
    print(f"📦 Session B workspace: {session_b.workspace_path}")
    
    # Each writes to "secret.txt" - but they're isolated!
    await tools_a["file_write"].ainvoke({
        "file": "secret.txt",
        "content": "Alice's secret data",
    })
    
    await tools_b["file_write"].ainvoke({
        "file": "secret.txt", 
        "content": "Bob's secret data",
    })
    
    # Read back - each sees only their own
    alice_secret = await tools_a["file_read"].ainvoke({"file": "secret.txt"})
    bob_secret = await tools_b["file_read"].ainvoke({"file": "secret.txt"})
    
    print(f"\n🔐 Alice's secret.txt: {alice_secret}")
    print(f"🔐 Bob's secret.txt: {bob_secret}")
    print("\n✅ Files are completely isolated!")
    
    # Cleanup
    await session_a.cleanup()
    await session_b.cleanup()
    
    print("✅ Both sessions cleaned up")


if __name__ == "__main__":
    asyncio.run(session_example())
    asyncio.run(multi_session_example())
