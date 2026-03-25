"""
Session-based sandbox manager for lazy initialization.

Implements the II-Agent cold/warm start pattern:
1. Check if session already has a sandbox
2. If yes, reconnect to it (WARM START - light reset ~200-500ms) 
3. If no, create new sandbox and link to session (COLD START - full init ~30-60s)

The key insight is that sandbox creation is LAZY - it only happens
when get_sandbox() is called, not when the manager is created.

The manager also tracks whether the last get_sandbox() call was a cold or warm start,
allowing callers to adjust their behavior accordingly.
"""

import asyncio
from typing import Optional, Tuple

from backend.src.services.sandbox_service import SandboxService
from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
from backend.src.config.skill_config import AgentCategory
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
    
    def __init__(
        self, 
        user_id: str, 
        session_id: str, 
        user_api_key: Optional[str] = None,
        agent_category: Optional[AgentCategory] = None,
    ):
        """
        Initialize the manager. Does NOT create sandbox yet.
        
        Args:
            user_id: The user's ID (for sandbox ownership)
            session_id: The session/thread ID (for sandbox reuse across requests)
            user_api_key: User's JWT token for MCP authentication (optional)
            agent_category: Agent category for skills injection ("general", "scientific", etc.)
        """
        self.user_id = user_id
        self.session_id = session_id
        self.user_api_key = user_api_key
        self.agent_category = agent_category
        self._sandbox: Optional[BaseSandbox] = None
        self._lock = asyncio.Lock()
        self._creation_error: Optional[Exception] = None
        self._initialized = False
        self._is_cold_start: Optional[bool] = None  # Track cold/warm start status
    
    async def get_sandbox(self) -> Tuple[BaseSandbox, bool]:
        """
        Get or lazily create the sandbox for this session.
        
        Implements the II-Agent cold/warm start pattern:
        
        First call (within this manager instance):
            - Checks if session already has a sandbox (via SandboxService)
            - If yes (WARM START): reconnects and does light reset (~200-500ms)
            - If no (COLD START): creates new sandbox with full MCP init (~30-60s)
            
        Subsequent calls:
            - Returns cached sandbox (instant), with original is_cold_start value
        
        Returns:
            Tuple[BaseSandbox, bool]: (sandbox, is_cold_start)
            - sandbox: The sandbox instance
            - is_cold_start: True if sandbox was newly created, False if reused
            
        Raises:
            RuntimeError: If sandbox creation fails
        """
        async with self._lock:
            # Return cached sandbox if already created
            if self._sandbox is not None:
                return self._sandbox, self._is_cold_start or False
            
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
                # Returns tuple (sandbox, is_cold_start)
                self._sandbox, self._is_cold_start = await service.get_or_create_sandbox(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    write_mcp_credentials=True,
                    user_api_key=self.user_api_key,
                    agent_category=self.agent_category,  # For skills injection on cold start
                )
                
                self._initialized = True
                start_type = "COLD START" if self._is_cold_start else "WARM START"
                log.info(
                    f"SessionSandboxManager: Sandbox ready ({start_type}) - "
                    f"id={self._sandbox.sandbox_id}"
                )
                return self._sandbox, self._is_cold_start
                
            except Exception as e:
                error_msg = f"Sandbox creation failed: {e}"
                self._creation_error = RuntimeError(error_msg)
                log.error(f"SessionSandboxManager: {error_msg}")
                raise self._creation_error
    
    async def ensure_mcp_ready(self, timeout: int = 60, mcp_url: str = None) -> bool:
        """
        Ensure MCP server is ready in the sandbox.
        
        This should be called before using MCP-dependent tools.
        Uses similar polling approach as test_custom_mcp_client.py.
        
        Args:
            timeout: Maximum seconds to wait for MCP health
            mcp_url: Optional pre-exposed MCP URL (if not provided, will expose port)
            
        Returns:
            bool: True if MCP is ready, False if timeout
        """
        if self._sandbox is None:
            log.warning("SessionSandboxManager: Cannot check MCP - sandbox is None")
            return False
        
        try:
            import httpx
            from datetime import datetime
            
            # Use provided URL or expose port
            if not mcp_url:
                mcp_url = await self._sandbox.expose_port(6060)
            
            log.info(f"SessionSandboxManager: Waiting for MCP at {mcp_url}/health (max {timeout}s)")
            
            start = datetime.now()
            poll_interval = 5  # Poll every 5 seconds like working tests
            
            async with httpx.AsyncClient() as client:
                while (datetime.now() - start).seconds < timeout:
                    elapsed = (datetime.now() - start).seconds
                    try:
                        resp = await client.get(
                            f"{mcp_url}/health",
                            timeout=10.0  # Longer timeout for slow networks
                        )
                        if resp.status_code == 200:
                            log.info(f"SessionSandboxManager: MCP ready after {elapsed}s")
                            return True
                        else:
                            log.debug(f"SessionSandboxManager: MCP returned {resp.status_code}")
                    except Exception as e:
                        log.debug(f"SessionSandboxManager: MCP not ready ({elapsed}s): {type(e).__name__}")
                    
                    await asyncio.sleep(poll_interval)
            
            log.warning(f"SessionSandboxManager: MCP not ready after {timeout}s")
            return False
            
        except Exception as e:
            log.error(f"SessionSandboxManager: MCP check failed: {e}")
            return False
    
    @property
    def is_initialized(self) -> bool:
        """Check if sandbox has been created/connected."""
        return self._initialized
    
    @property
    def is_cold_start(self) -> Optional[bool]:
        """Check if last get_sandbox() was a cold start.
        
        Returns:
            True if sandbox was newly created (cold start)
            False if sandbox was reused (warm start)
            None if get_sandbox() hasn't been called yet
        """
        return self._is_cold_start
    
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
