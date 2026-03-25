"""LSP Server Manager - Manages language server lifecycle with keep-alive and health checking.

This module provides a singleton manager that pools LSP servers by (language, workspace) key,
implementing idle timeout, health checking, and graceful shutdown.
"""

import asyncio
import logging
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# Configuration
DEFAULT_IDLE_TIMEOUT = 300  # 5 minutes
DEFAULT_HEALTH_CHECK_TIMEOUT = 10  # seconds
MAX_RESTART_ATTEMPTS = 3


@dataclass
class ServerState:
    """State tracking for a managed LSP server."""
    
    server: Any  # LanguageServer instance
    language: str
    workspace: str
    last_used: float = field(default_factory=time.time)
    is_active: bool = False  # Currently in use
    start_time: float = field(default_factory=time.time)
    request_count: int = 0
    restart_count: int = 0
    _idle_task: Optional[asyncio.Task] = field(default=None, repr=False)
    _server_context: Optional[Any] = field(default=None, repr=False)  # Context manager


class LspServerManager:
    """Manages LSP server lifecycle with keep-alive, health checking, and idle timeout.
    
    This singleton manager pools language servers by (language, workspace) key, 
    keeping them alive between operations for better performance.
    
    Features:
    - Server pooling by (language, workspace) key
    - Idle timeout (default 5 minutes) - auto-shutdown unused servers
    - Health checking with automatic recovery
    - Graceful shutdown API
    - Thread-safe with asyncio.Lock
    
    Usage:
        manager = LspServerManager.get_instance()
        server = await manager.get_server("python", "/path/to/workspace")
        try:
            result = await server.request_definition(...)
        finally:
            await manager.release_server("python", "/path/to/workspace")
    """
    
    _instance: Optional["LspServerManager"] = None
    _instance_lock = asyncio.Lock()
    
    def __init__(self, idle_timeout: int = DEFAULT_IDLE_TIMEOUT):
        """Initialize the manager. Use get_instance() for singleton access."""
        self._servers: Dict[str, ServerState] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._idle_timeout = idle_timeout
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        
    @classmethod
    async def get_instance(cls, idle_timeout: int = DEFAULT_IDLE_TIMEOUT) -> "LspServerManager":
        """Get or create the singleton manager instance."""
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(idle_timeout)
            return cls._instance
    
    @classmethod
    def get_instance_sync(cls, idle_timeout: int = DEFAULT_IDLE_TIMEOUT) -> "LspServerManager":
        """Get or create the singleton manager instance (sync version for initialization)."""
        if cls._instance is None:
            cls._instance = cls(idle_timeout)
        return cls._instance
    
    def _get_cache_key(self, language: str, workspace: str) -> str:
        """Generate a unique cache key for a (language, workspace) pair."""
        return f"{language}:{workspace}"
    
    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for the specified key."""
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]
    
    async def _create_server(self, language: str, workspace: str) -> Tuple[Any, Any]:
        """Create a new language server instance.
        
        Returns:
            Tuple of (server, context_manager)
        """
        try:
            from multilspy import LanguageServer
            from multilspy.multilspy_config import MultilspyConfig
            from multilspy.multilspy_logger import MultilspyLogger
            
            config = MultilspyConfig.from_dict({"code_language": language})
            lsp_logger = MultilspyLogger()
            
            server = LanguageServer.create(config, lsp_logger, workspace)
            
            # Start the server and get the context manager
            context = server.start_server()
            await context.__aenter__()
            
            logger.info(f"Started LSP server for {language} in {workspace}")
            return server, context
            
        except ImportError as e:
            raise LspManagerError(
                f"multilspy is not installed. Please install it with: pip install multilspy\n"
                f"Error: {e}"
            )
        except Exception as e:
            raise LspManagerError(f"Failed to create language server for {language}: {e}")
    
    async def _stop_server(self, state: ServerState) -> None:
        """Stop a language server gracefully."""
        try:
            # Cancel idle timeout task if running
            if state._idle_task and not state._idle_task.done():
                state._idle_task.cancel()
                try:
                    await state._idle_task
                except asyncio.CancelledError:
                    pass
            
            # Exit the server context
            if state._server_context:
                try:
                    await state._server_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error during server context exit: {e}")
            
            logger.info(
                f"Stopped LSP server for {state.language} in {state.workspace} "
                f"(served {state.request_count} requests)"
            )
            
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
    
    async def _health_check(self, state: ServerState) -> bool:
        """Check if a server is healthy and responsive.
        
        Returns:
            True if server is healthy, False otherwise
        """
        if not state.server or not state._server_context:
            return False
            
        try:
            # Try a lightweight operation with timeout
            # Different servers may support different health check methods
            # We'll try to get document symbols on a simple query
            async with asyncio.timeout(DEFAULT_HEALTH_CHECK_TIMEOUT):
                # Just verify the server object exists and hasn't crashed
                # The actual LSP protocol doesn't have a standard ping
                if hasattr(state.server, 'server') and state.server.server:
                    return True
                return False
        except asyncio.TimeoutError:
            logger.warning(f"Health check timeout for {state.language} server")
            return False
        except Exception as e:
            logger.warning(f"Health check failed for {state.language} server: {e}")
            return False
    
    async def _schedule_idle_shutdown(self, key: str) -> None:
        """Schedule a server for shutdown after idle timeout."""
        try:
            await asyncio.sleep(self._idle_timeout)
            
            lock = await self._get_lock(key)
            async with lock:
                if key in self._servers:
                    state = self._servers[key]
                    # Only shutdown if still idle
                    if not state.is_active:
                        time_idle = time.time() - state.last_used
                        if time_idle >= self._idle_timeout:
                            logger.info(
                                f"Shutting down idle server {key} "
                                f"(idle for {time_idle:.1f}s)"
                            )
                            await self._stop_server(state)
                            del self._servers[key]
                            
        except asyncio.CancelledError:
            # Task was cancelled, server is being used again
            pass
        except Exception as e:
            logger.error(f"Error in idle shutdown task: {e}")
    
    async def get_server(
        self, 
        language: str, 
        workspace: str,
        force_restart: bool = False
    ) -> Any:
        """Get or create a language server for the specified language and workspace.
        
        Args:
            language: Programming language (e.g., 'python', 'typescript')
            workspace: Absolute path to the workspace directory
            force_restart: If True, restart the server even if one exists
            
        Returns:
            The language server instance ready for use
            
        Raises:
            LspManagerError: If server creation fails
        """
        if self._is_shutting_down:
            raise LspManagerError("Manager is shutting down")
        
        key = self._get_cache_key(language, workspace)
        lock = await self._get_lock(key)
        
        async with lock:
            state = self._servers.get(key)
            
            # Force restart if requested
            if state and force_restart:
                logger.info(f"Force restarting server for {key}")
                await self._stop_server(state)
                del self._servers[key]
                state = None
            
            # Check if existing server is healthy
            if state:
                # Cancel idle timeout since we're using it
                if state._idle_task and not state._idle_task.done():
                    state._idle_task.cancel()
                
                # Verify server is healthy
                if await self._health_check(state):
                    state.is_active = True
                    state.last_used = time.time()
                    state.request_count += 1
                    logger.debug(f"Reusing existing server for {key}")
                    return state.server
                else:
                    # Server unhealthy, restart it
                    logger.warning(f"Server unhealthy for {key}, restarting...")
                    await self._stop_server(state)
                    del self._servers[key]
                    state = None
            
            # Create new server
            if state is None:
                server, context = await self._create_server(language, workspace)
                state = ServerState(
                    server=server,
                    language=language,
                    workspace=workspace,
                    is_active=True,
                    request_count=1,
                    _server_context=context
                )
                self._servers[key] = state
            
            return state.server
    
    async def release_server(self, language: str, workspace: str) -> None:
        """Mark a server as no longer in active use.
        
        This starts the idle timeout countdown. The server will be shut down
        if not used again within the timeout period.
        
        Args:
            language: Programming language
            workspace: Workspace path
        """
        key = self._get_cache_key(language, workspace)
        lock = await self._get_lock(key)
        
        async with lock:
            if key in self._servers:
                state = self._servers[key]
                state.is_active = False
                state.last_used = time.time()
                
                # Schedule idle shutdown
                if state._idle_task and not state._idle_task.done():
                    state._idle_task.cancel()
                state._idle_task = asyncio.create_task(
                    self._schedule_idle_shutdown(key)
                )
    
    async def shutdown_server(self, language: str, workspace: str) -> None:
        """Force shutdown a specific server immediately.
        
        Args:
            language: Programming language
            workspace: Workspace path
        """
        key = self._get_cache_key(language, workspace)
        lock = await self._get_lock(key)
        
        async with lock:
            if key in self._servers:
                await self._stop_server(self._servers[key])
                del self._servers[key]
                logger.info(f"Force shutdown server for {key}")
    
    async def shutdown_all(self) -> None:
        """Gracefully shutdown all managed servers.
        
        This should be called when the application is shutting down.
        """
        self._is_shutting_down = True
        
        async with self._global_lock:
            keys = list(self._servers.keys())
            
        for key in keys:
            try:
                lock = await self._get_lock(key)
                async with lock:
                    if key in self._servers:
                        await self._stop_server(self._servers[key])
                        del self._servers[key]
            except Exception as e:
                logger.error(f"Error shutting down server {key}: {e}")
        
        logger.info(f"Shutdown complete. Stopped {len(keys)} servers.")
        self._shutdown_event.set()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about managed servers.
        
        Returns:
            Dictionary with server statistics
        """
        stats = {
            "active_servers": len(self._servers),
            "servers": {}
        }
        
        for key, state in self._servers.items():
            stats["servers"][key] = {
                "language": state.language,
                "workspace": state.workspace,
                "is_active": state.is_active,
                "request_count": state.request_count,
                "uptime_seconds": time.time() - state.start_time,
                "idle_seconds": time.time() - state.last_used if not state.is_active else 0,
            }
        
        return stats


class LspManagerError(Exception):
    """Exception raised by LspServerManager."""
    pass


# Module-level singleton accessor
_manager_instance: Optional[LspServerManager] = None


def get_lsp_manager(idle_timeout: int = DEFAULT_IDLE_TIMEOUT) -> LspServerManager:
    """Get the global LSP server manager singleton (sync version).
    
    This is a convenience function for getting the manager instance
    without needing async context.
    
    Args:
        idle_timeout: Idle timeout in seconds before shutting down unused servers
        
    Returns:
        The LspServerManager singleton instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = LspServerManager.get_instance_sync(idle_timeout)
    return _manager_instance


async def get_lsp_manager_async(idle_timeout: int = DEFAULT_IDLE_TIMEOUT) -> LspServerManager:
    """Get the global LSP server manager singleton (async version).
    
    Args:
        idle_timeout: Idle timeout in seconds before shutting down unused servers
        
    Returns:
        The LspServerManager singleton instance
    """
    return await LspServerManager.get_instance(idle_timeout)


async def shutdown_lsp_servers() -> None:
    """Shutdown all LSP servers gracefully.
    
    This should be called during application shutdown.
    """
    global _manager_instance
    if _manager_instance:
        await _manager_instance.shutdown_all()
        _manager_instance = None
