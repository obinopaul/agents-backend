"""AIO Sandbox LangChain Tools.

Production-ready LangChain tools for interacting with the AIO Sandbox Docker container.
Provides tools for file operations, shell execution, code running, browser automation, and MCP integration.

## Session-Based Usage (Recommended)

For isolated workspaces with automatic path scoping:

    from langchain_tools import SandboxSession
    
    # Create an isolated session for a chat/agent
    async with await SandboxSession.create(session_id="chat_123") as session:
        tools = session.get_tools()
        
        # All paths are relative to workspace - can't escape!
        await tools["file_write"].ainvoke({"file": "app.py", "content": "..."})
        await tools["shell_exec"].ainvoke({"command": "python app.py"})

## Direct Usage (No isolation)

For simple use cases without isolation:

    from langchain_tools import create_sandbox_tools
    
    tools = create_sandbox_tools(base_url="http://localhost:8080")
"""

# Session-based (recommended)
from langchain_tools.session import SandboxSession

# Direct access (no isolation)
from langchain_tools.toolkit import SandboxToolkit, create_sandbox_tools
from langchain_tools.client import SandboxClient

__all__ = [
    # Recommended
    "SandboxSession",
    # Direct access
    "SandboxToolkit",
    "SandboxClient", 
    "create_sandbox_tools",
]

__version__ = "0.2.0"
