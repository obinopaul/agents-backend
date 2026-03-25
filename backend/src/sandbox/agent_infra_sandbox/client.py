"""Unified Sandbox client for Agent-Infra Sandbox.

This client provides both sync and async access to the sandbox, with utilities
for creating isolated workspaces within a single sandbox instance.

Usage:
    from agent_infra_sandbox import SandboxClient
    
    client = SandboxClient(base_url="http://localhost:8080")
    
    # Async usage
    async with client:
        home_dir = await client.get_home_dir()
        await client.health_check()
    
    # Sync usage
    if client.health_check_sync():
        home_dir = client.get_home_dir_sync()
"""

import asyncio
from typing import Optional

import structlog
from agent_sandbox import Sandbox, AsyncSandbox

from .exceptions import SandboxConnectionError, SandboxNotRunningError

logger = structlog.get_logger(__name__)


class SandboxClient:
    """Client wrapper for Agent-Infra Sandbox with workspace/session management.
    
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
        base_url: str = "http://localhost:8090",
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
    
    async def ensure_running(self) -> None:
        """Ensure the sandbox is running, raise exception if not.
        
        Raises:
            SandboxNotRunningError: If sandbox is not running
        """
        if not await self.health_check():
            raise SandboxNotRunningError(url=self.base_url)
    
    def ensure_running_sync(self) -> None:
        """Ensure the sandbox is running (sync version).
        
        Raises:
            SandboxNotRunningError: If sandbox is not running
        """
        if not self.health_check_sync():
            raise SandboxNotRunningError(url=self.base_url)
    
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
    
    async def execute_command(self, command: str, timeout: Optional[float] = None) -> dict:
        """Execute a shell command in the sandbox.
        
        Args:
            command: Shell command to execute
            timeout: Optional timeout in seconds
            
        Returns:
            Dict with 'output', 'exit_code', and 'error' keys
        """
        try:
            result = await self.async_client.shell.exec_command(
                command=command,
                timeout=timeout or self.timeout,
            )
            return {
                "output": result.data.output if hasattr(result.data, 'output') else str(result.data),
                "exit_code": result.data.exit_code if hasattr(result.data, 'exit_code') else 0,
                "error": None,
            }
        except Exception as e:
            return {
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }
    
    def execute_command_sync(self, command: str, timeout: Optional[float] = None) -> dict:
        """Execute a shell command in the sandbox (sync version).
        
        Args:
            command: Shell command to execute
            timeout: Optional timeout in seconds
            
        Returns:
            Dict with 'output', 'exit_code', and 'error' keys
        """
        try:
            result = self.sync_client.shell.exec_command(
                command=command,
                timeout=timeout or self.timeout,
            )
            return {
                "output": result.data.output if hasattr(result.data, 'output') else str(result.data),
                "exit_code": result.data.exit_code if hasattr(result.data, 'exit_code') else 0,
                "error": None,
            }
        except Exception as e:
            return {
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }
    
    async def __aenter__(self) -> "SandboxClient":
        """Async context manager entry."""
        await self.ensure_running()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        pass  # No cleanup needed for the client itself
