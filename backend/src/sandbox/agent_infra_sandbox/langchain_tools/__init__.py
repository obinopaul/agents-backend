"""AIO Sandbox LangChain Tools.

Production-ready LangChain tools for interacting with the AIO Sandbox Docker container.
Provides tools for file operations, shell execution, code running, browser automation, and MCP integration.

## Session-Based Usage (Recommended)

For isolated workspaces with automatic path scoping:

    from agent_infra_sandbox import SandboxSession
    
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

# Use shared client from root package
try:
    from backend.src.sandbox.agent_infra_sandbox.client import SandboxClient
    from backend.src.sandbox.agent_infra_sandbox.session import SandboxSession
except ImportError:
    # Fallback for local imports
    from ..client import SandboxClient
    from ..session import SandboxSession

# Direct access (no isolation)
from backend.src.sandbox.agent_infra_sandbox.langchain_tools.toolkit import SandboxToolkit, create_sandbox_tools

__all__ = [
    # Recommended
    "SandboxSession",
    # Direct access
    "SandboxToolkit",
    "SandboxClient", 
    "create_sandbox_tools",
]

__version__ = "0.3.0"

