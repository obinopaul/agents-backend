"""Basic usage example for LangChain Sandbox Tools."""

import asyncio
from backend.src.sandbox.agent_infra_sandbox.langchain_tools import create_sandbox_tools, SandboxToolkit, SandboxClient


async def basic_example():
    """Demonstrate basic usage of sandbox tools."""
    
    print("=" * 60)
    print("LangChain Sandbox Tools - Basic Usage Example")
    print("=" * 60)
    
    # Check sandbox health first
    client = SandboxClient()
    is_healthy = await client.health_check()
    
    if not is_healthy:
        print("\n❌ Sandbox is not running!")
        print("Start it with:")
        print("  docker run --security-opt seccomp=unconfined --rm -d -p 8080:8080 ghcr.io/agent-infra/sandbox:latest")
        return
    
    print("\n✅ Sandbox is healthy")
    
    # Get home directory
    home_dir = await client.get_home_dir()
    print(f"📁 Home directory: {home_dir}")
    
    # Create toolkit and get all tools
    toolkit = SandboxToolkit()
    all_tools = toolkit.get_tools()
    print(f"\n🔧 Created {len(all_tools)} tools:")
    for tool in all_tools:
        print(f"   - {tool.name}")
    
    # Create tool lookup
    tools = {t.name: t for t in all_tools}
    
    # Example 1: Shell execution
    print("\n" + "-" * 40)
    print("Example 1: Shell Execution")
    print("-" * 40)
    
    result = await tools["shell_exec"].ainvoke({
        "command": "echo 'Hello from sandbox!' && uname -a",
    })
    print(result)
    
    # Example 2: File operations  
    print("\n" + "-" * 40)
    print("Example 2: File Operations")
    print("-" * 40)
    
    # Write a file
    write_result = await tools["file_write"].ainvoke({
        "file": f"{home_dir}/hello.txt",
        "content": "Hello from LangChain!\nThis is a test file.",
    })
    print(f"Write: {write_result}")
    
    # Read it back
    read_result = await tools["file_read"].ainvoke({
        "file": f"{home_dir}/hello.txt",
    })
    print(f"Read:\n{read_result}")
    
    # List directory
    list_result = await tools["file_list"].ainvoke({
        "path": home_dir,
    })
    print(f"\n{list_result}")
    
    # Example 3: Python execution
    print("\n" + "-" * 40)
    print("Example 3: Python Execution (Jupyter)")
    print("-" * 40)
    
    code_result = await tools["jupyter_execute"].ainvoke({
        "code": """
import sys
print(f"Python version: {sys.version}")
print(f"2 + 2 = {2 + 2}")

# Variables persist in session
x = 42
print(f"x = {x}")
""",
    })
    print(code_result)
    
    # Example 4: Grep search
    print("\n" + "-" * 40)
    print("Example 4: Grep Search")
    print("-" * 40)
    
    # First create some files to search
    await tools["file_write"].ainvoke({
        "file": f"{home_dir}/sample.py",
        "content": """
# Sample Python file
def hello():
    print("Hello, world!")

def goodbye():
    print("Goodbye, world!")

if __name__ == "__main__":
    hello()
""",
    })
    
    grep_result = await tools["grep"].ainvoke({
        "pattern": "def .*:",
        "path": home_dir,
        "glob": "*.py",
    })
    print(grep_result)
    
    # Example 5: Sandbox info
    print("\n" + "-" * 40)
    print("Example 5: Sandbox Information")
    print("-" * 40)
    
    context_result = await tools["sandbox_context"].ainvoke({})
    print(context_result)
    
    print("\n" + "=" * 60)
    print("✅ All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(basic_example())
