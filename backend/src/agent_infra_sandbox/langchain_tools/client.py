"""Sandbox client wrapper with session/workspace isolation."""

import asyncio
from typing import Optional
from functools import cached_property

import structlog
from agent_sandbox import Sandbox, AsyncSandbox

logger = structlog.get_logger(__name__)


class SandboxClient:
    """Client wrapper for AIO Sandbox with workspace/session management.
    
    Provides both sync and async access to the sandbox, with utilities
    for creating isolated workspaces within a single sandbox instance.
    
    Args:
        base_url: Base URL of the sandbox (default: http://localhost:8080)
        timeout: Request timeout in seconds (default: 60)
        
    Example:
        >>> client = SandboxClient(base_url="http://localhost:8080")
        >>> home_dir = await client.get_home_dir()
        >>> await client.health_check()
    """
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8080",
        timeout: float = 60.0,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._sync_client: Optional[Sandbox] = None
        self._async_client: Optional[AsyncSandbox] = None
        
    @property
    def sync_client(self) -> Sandbox:
        """Get or create the synchronous SDK client."""
        if self._sync_client is None:
            self._sync_client = Sandbox(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._sync_client
    
    @property
    def async_client(self) -> AsyncSandbox:
        """Get or create the asynchronous SDK client."""
        if self._async_client is None:
            self._async_client = AsyncSandbox(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._async_client
    
    async def get_home_dir(self) -> str:
        """Get the sandbox home directory.
        
        Returns:
            The home directory path (typically /home/gem)
        """
        context = await self.async_client.sandbox.get_context()
        return context.home_dir
    
    def get_home_dir_sync(self) -> str:
        """Get the sandbox home directory (sync version).
        
        Returns:
            The home directory path (typically /home/gem)
        """
        context = self.sync_client.sandbox.get_context()
        return context.home_dir
    
    async def health_check(self) -> bool:
        """Check if the sandbox is healthy and responding.
        
        Returns:
            True if sandbox is healthy, False otherwise
        """
        try:
            await self.async_client.sandbox.get_context()
            return True
        except Exception as e:
            logger.warning("Sandbox health check failed", error=str(e))
            return False
    
    def health_check_sync(self) -> bool:
        """Check if the sandbox is healthy (sync version).
        
        Returns:
            True if sandbox is healthy, False otherwise
        """
        try:
            self.sync_client.sandbox.get_context()
            return True
        except Exception as e:
            logger.warning("Sandbox health check failed", error=str(e))
            return False
    
    async def create_workspace(self, workspace_name: str) -> str:
        """Create an isolated workspace directory in the sandbox.
        
        Args:
            workspace_name: Name for the workspace directory
            
        Returns:
            Full path to the created workspace
        """
        home_dir = await self.get_home_dir()
        workspace_path = f"{home_dir}/workspaces/{workspace_name}"
        
        # Create the workspace directory
        await self.async_client.shell.exec_command(
            command=f"mkdir -p {workspace_path}"
        )
        
        logger.info("Created workspace", workspace=workspace_path)
        return workspace_path
    
    async def create_shell_session(
        self, 
        session_id: Optional[str] = None,
        exec_dir: Optional[str] = None,
    ) -> str:
        """Create a new isolated shell session.
        
        Args:
            session_id: Optional custom session ID
            exec_dir: Optional working directory for the session
            
        Returns:
            The session ID
        """
        result = await self.async_client.shell.create_session(
            id=session_id,
            exec_dir=exec_dir,
        )
        return result.data.id
    
    async def create_jupyter_session(
        self,
        session_id: Optional[str] = None,
        kernel_name: str = "python3",
    ) -> str:
        """Create a new isolated Jupyter session.
        
        Args:
            session_id: Optional custom session ID
            kernel_name: Kernel to use (default: python3)
            
        Returns:
            The session ID
        """
        result = await self.async_client.jupyter.create_session(
            session_id=session_id,
            kernel_name=kernel_name,
        )
        return result.data.session_id
    
    async def cleanup_sessions(self) -> None:
        """Cleanup all active shell and Jupyter sessions."""
        await self.async_client.shell.cleanup_all_sessions()
        await self.async_client.jupyter.delete_sessions()
        logger.info("Cleaned up all sessions")
