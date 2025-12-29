"""
Session-based sandbox manager for lazy initialization.

This follows the II-Agent pattern:
1. Check if session already has a sandbox
2. If yes, reconnect to it
3. If no, create new sandbox and link to session

The key insight is that sandbox creation is LAZY - it only happens
when get_sandbox() is called, not when the manager is created.
"""

import asyncio
from typing import Optional

from backend.src.services.sandbox_service import SandboxService
from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
from backend.common.log import log


class SessionSandboxManager:
    """
    Manages sandbox lifecycle for a user session with lazy initialization.
    
    This class ensures:
    - Sandbox is only created when actually needed (lazy)
    - Same session reuses the same sandbox (session-linked)
    - Thread-safe initialization (uses asyncio.Lock)
    - Error caching (failed creation is cached to avoid repeated attempts)
    
    Usage:
        manager = SessionSandboxManager(user_id="user-123", session_id="session-456")
        # No sandbox created yet
        
        sandbox = await manager.get_sandbox()
        # Now sandbox is created (or reused if session already had one)
        
        sandbox2 = await manager.get_sandbox()
        # Returns same sandbox (cached)
    """
    
    def __init__(self, user_id: str, session_id: str):
        """
        Initialize the manager. Does NOT create sandbox yet.
        
        Args:
            user_id: The user's ID (for sandbox ownership)
            session_id: The session/thread ID (for sandbox reuse across requests)
        """
        self.user_id = user_id
        self.session_id = session_id
        self._sandbox: Optional[BaseSandbox] = None
        self._lock = asyncio.Lock()
        self._creation_error: Optional[Exception] = None
        self._initialized = False
    
    async def get_sandbox(self) -> BaseSandbox:
        """
        Get or lazily create the sandbox for this session.
        
        First call: 
            - Checks if session already has a sandbox (via SandboxService)
            - If yes, reconnects to it
            - If no, creates new sandbox and links to session
            - Takes ~1-3 seconds
            
        Subsequent calls:
            - Returns cached sandbox (instant)
        
        Returns:
            BaseSandbox: The sandbox instance
            
        Raises:
            RuntimeError: If sandbox creation fails
        """
        async with self._lock:
            # Return cached sandbox if already created
            if self._sandbox is not None:
                return self._sandbox
            
            # Return cached error if creation already failed
            if self._creation_error is not None:
                raise self._creation_error
            
            # Create sandbox via SandboxService
            try:
                log.info(
                    f"SessionSandboxManager: Getting/creating sandbox for "
                    f"user={self.user_id}, session={self.session_id}"
                )
                
                service = SandboxService()
                
                # Ensure service is initialized
                if service._controller is None:
                    await service.initialize()
                
                # This will check for existing session sandbox first
                self._sandbox = await service.get_or_create_sandbox(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    write_mcp_credentials=True
                )
                
                self._initialized = True
                log.info(
                    f"SessionSandboxManager: Sandbox ready - "
                    f"id={self._sandbox.sandbox_id}"
                )
                return self._sandbox
                
            except Exception as e:
                error_msg = f"Sandbox creation failed: {e}"
                self._creation_error = RuntimeError(error_msg)
                log.error(f"SessionSandboxManager: {error_msg}")
                raise self._creation_error
    
    async def ensure_mcp_ready(self, timeout: int = 30) -> bool:
        """
        Ensure MCP server is ready in the sandbox.
        
        This should be called before using MCP-dependent tools.
        
        Args:
            timeout: Maximum seconds to wait for MCP health
            
        Returns:
            bool: True if MCP is ready, False if timeout
        """
        if self._sandbox is None:
            return False
        
        try:
            import httpx
            mcp_url = await self._sandbox.expose_port(6060)
            
            async with httpx.AsyncClient() as client:
                for attempt in range(timeout):
                    try:
                        resp = await client.get(
                            f"{mcp_url}/health",
                            timeout=2.0
                        )
                        if resp.status_code == 200:
                            log.info("SessionSandboxManager: MCP server is ready")
                            return True
                    except Exception:
                        pass
                    
                    if attempt < timeout - 1:
                        await asyncio.sleep(1)
            
            log.warning(
                f"SessionSandboxManager: MCP not ready after {timeout}s"
            )
            return False
            
        except Exception as e:
            log.error(f"SessionSandboxManager: MCP check failed: {e}")
            return False
    
    @property
    def is_initialized(self) -> bool:
        """Check if sandbox has been created/connected."""
        return self._initialized
    
    @property
    def sandbox_id(self) -> Optional[str]:
        """Get sandbox ID if initialized, None otherwise."""
        return self._sandbox.sandbox_id if self._sandbox else None
    
    @property
    def has_error(self) -> bool:
        """Check if sandbox creation failed."""
        return self._creation_error is not None
    
    @property
    def error_message(self) -> Optional[str]:
        """Get error message if creation failed."""
        return str(self._creation_error) if self._creation_error else None
