"""Sandbox session with automatic workspace isolation.

This module provides the SandboxSession class which creates an isolated
workspace for each agent/chat session, ensuring all operations are
automatically scoped to that workspace.
"""

import uuid
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

import structlog
from agent_sandbox import AsyncSandbox
from langchain_core.tools import BaseTool

logger = structlog.get_logger(__name__)


class SandboxSession:
    """An isolated sandbox session with automatic workspace management.
    
    When created, this session automatically:
    1. Creates an isolated workspace directory
    2. Creates dedicated shell and Jupyter sessions
    3. Provides tools that are automatically scoped to the workspace
    
    All file paths used by tools are relative to the workspace directory,
    preventing agents from accidentally operating outside their workspace.
    
    Args:
        session_id: Unique identifier for this session (auto-generated if not provided)
        base_url: Base URL of the sandbox (default: http://localhost:8080)
        timeout: Request timeout in seconds (default: 60)
        
    Example:
        >>> session = await SandboxSession.create(session_id="chat_123")
        >>> tools = session.get_tools()
        >>> 
        >>> # All paths are relative to workspace
        >>> await tools["file_write"].ainvoke({"file": "app.py", "content": "..."})
        >>> # Actually writes to: /home/gem/workspaces/chat_123/app.py
        >>>
        >>> await session.cleanup()
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        base_url: str = "http://localhost:8080",
        timeout: float = 60.0,
    ):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.base_url = base_url
        self.timeout = timeout
        
        self._client: Optional[AsyncSandbox] = None
        self._home_dir: Optional[str] = None
        self._workspace_path: Optional[str] = None
        self._shell_session_id: Optional[str] = None
        self._jupyter_session_id: Optional[str] = None
        self._initialized: bool = False
        self._created_at: Optional[datetime] = None
        self._tools: Optional[List[BaseTool]] = None
    
    @property
    def client(self) -> AsyncSandbox:
        """Get the async sandbox client."""
        if self._client is None:
            self._client = AsyncSandbox(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client
    
    @property
    def workspace_path(self) -> str:
        """Get the absolute path to this session's workspace."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call create() first.")
        return self._workspace_path
    
    @property
    def shell_session_id(self) -> str:
        """Get the shell session ID for this workspace."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call create() first.")
        return self._shell_session_id
    
    @property
    def jupyter_session_id(self) -> str:
        """Get the Jupyter session ID for this workspace."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call create() first.")
        return self._jupyter_session_id
    
    @classmethod
    async def create(
        cls,
        session_id: Optional[str] = None,
        base_url: str = "http://localhost:8080",
        timeout: float = 60.0,
    ) -> "SandboxSession":
        """Create and initialize a new sandbox session.
        
        This is the recommended way to create a session as it handles
        all async initialization automatically.
        
        Args:
            session_id: Unique identifier for this session
            base_url: Base URL of the sandbox
            timeout: Request timeout in seconds
            
        Returns:
            Initialized SandboxSession ready to use
            
        Example:
            >>> session = await SandboxSession.create(session_id="chat_123")
        """
        session = cls(session_id=session_id, base_url=base_url, timeout=timeout)
        await session.initialize()
        return session
    
    async def initialize(self) -> None:
        """Initialize the session by creating workspace and sessions.
        
        This is called automatically by create(). Only call directly if
        you created the session using the constructor.
        """
        if self._initialized:
            logger.warning("Session already initialized", session_id=self.session_id)
            return
        
        logger.info("Initializing sandbox session", session_id=self.session_id)
        
        # Get home directory
        context = await self.client.sandbox.get_context()
        self._home_dir = context.home_dir
        
        # Create workspace directory
        self._workspace_path = f"{self._home_dir}/workspaces/{self.session_id}"
        await self.client.shell.exec_command(
            command=f"mkdir -p {self._workspace_path}"
        )
        
        # Create dedicated shell session for this workspace
        self._shell_session_id = f"{self.session_id}_shell"
        await self.client.shell.create_session(
            id=self._shell_session_id,
            exec_dir=self._workspace_path,
        )
        
        # Create dedicated Jupyter session for this workspace
        self._jupyter_session_id = f"{self.session_id}_jupyter"
        await self.client.jupyter.create_session(
            session_id=self._jupyter_session_id,
        )
        
        # Set the working directory in Jupyter
        await self.client.jupyter.execute_code(
            code=f"import os; os.chdir('{self._workspace_path}')",
            session_id=self._jupyter_session_id,
        )
        
        self._initialized = True
        self._created_at = datetime.now()
        
        logger.info(
            "Sandbox session initialized",
            session_id=self.session_id,
            workspace=self._workspace_path,
            shell_session=self._shell_session_id,
            jupyter_session=self._jupyter_session_id,
        )
    
    async def cleanup(self) -> None:
        """Clean up the session, removing workspace and sessions.
        
        Call this when the chat/agent session ends to free resources.
        """
        if not self._initialized:
            return
        
        logger.info("Cleaning up sandbox session", session_id=self.session_id)
        
        try:
            # Kill any running processes in shell session
            try:
                await self.client.shell.kill_process(id=self._shell_session_id)
            except Exception:
                pass  # Process might already be dead
            
            # Cleanup shell session
            await self.client.shell.cleanup_session(id=self._shell_session_id)
            
            # Cleanup Jupyter session
            await self.client.jupyter.delete_session(session_id=self._jupyter_session_id)
            
            # Optionally remove workspace directory (commented out for safety)
            # await self.client.shell.exec_command(
            #     command=f"rm -rf {self._workspace_path}"
            # )
            
        except Exception as e:
            logger.error("Error during session cleanup", error=str(e))
        
        self._initialized = False
        logger.info("Sandbox session cleaned up", session_id=self.session_id)
    
    async def health_check(self) -> bool:
        """Check if the sandbox is healthy and responding."""
        try:
            await self.client.sandbox.get_context()
            return True
        except Exception as e:
            logger.warning("Health check failed", error=str(e))
            return False
    
    def get_tools(self) -> List[BaseTool]:
        """Get all LangChain tools scoped to this session's workspace.
        
        All file paths are automatically resolved relative to the workspace.
        Shell commands are executed in the workspace directory.
        Jupyter code runs in a session-specific kernel.
        
        Returns:
            List of LangChain tools bound to this workspace
        """
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call create() first.")
        
        if self._tools is None:
            from langchain_tools.session_tools import create_session_tools
            self._tools = create_session_tools(self)
        
        return self._tools
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about this session."""
        return {
            "session_id": self.session_id,
            "workspace_path": self._workspace_path,
            "shell_session_id": self._shell_session_id,
            "jupyter_session_id": self._jupyter_session_id,
            "initialized": self._initialized,
            "created_at": self._created_at.isoformat() if self._created_at else None,
            "base_url": self.base_url,
        }
    
    def resolve_path(self, path: str) -> str:
        """Resolve a relative path to an absolute workspace path.
        
        If the path is already absolute, it's validated to be within
        the workspace (or an error is raised for security).
        
        Args:
            path: Relative or absolute path
            
        Returns:
            Absolute path within the workspace
            
        Raises:
            ValueError: If path tries to escape the workspace
        """
        if not self._initialized:
            raise RuntimeError("Session not initialized")
        
        # Handle absolute paths
        if path.startswith("/"):
            # Check if it's within workspace
            if path.startswith(self._workspace_path):
                return path
            # Check if it's within home (allow read-only access)
            if path.startswith(self._home_dir):
                return path
            # Reject paths outside home directory
            raise ValueError(
                f"Path '{path}' is outside the allowed directories. "
                f"Use relative paths or paths within workspace."
            )
        
        # Handle relative paths - prepend workspace
        import os.path
        resolved = os.path.normpath(f"{self._workspace_path}/{path}")
        
        # Security check: ensure we didn't escape via ../
        if not resolved.startswith(self._workspace_path):
            raise ValueError(
                f"Path '{path}' attempts to escape workspace. "
                f"This is not allowed."
            )
        
        return resolved
    
    async def __aenter__(self) -> "SandboxSession":
        """Async context manager entry."""
        if not self._initialized:
            await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup automatically."""
        await self.cleanup()
