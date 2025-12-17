"""Daytona sandbox provider for the sandbox server."""

from datetime import datetime, timezone
from functools import wraps
import logging
from typing import IO, AsyncIterator, Literal, Optional, TYPE_CHECKING

from daytona_sdk import Daytona, DaytonaConfig, CreateWorkspaceParams, Workspace
from daytona_sdk.process import ExecuteResponse

from backend.src.sandbox.sandbox_server.config import SandboxConfig
from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
from backend.src.sandbox.sandbox_server.models.exceptions import (
    SandboxAuthenticationError,
    SandboxNotFoundException,
    SandboxTimeoutException,
    SandboxNotInitializedError,
    SandboxGeneralException,
)

if TYPE_CHECKING:
    from backend.src.sandbox.sandbox_server.lifecycle.queue import SandboxQueueScheduler

logger = logging.getLogger(__name__)

TIMEOUT_AFTER_PAUSE_SECONDS = 600
DEFAULT_TIMEOUT = 3600


def daytona_exception_handler(func):
    """Decorator to handle Daytona SDK exceptions and convert to sandbox exceptions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            # Map Daytona errors to sandbox exceptions
            if "unauthorized" in error_str or "401" in str(e) or "authentication" in error_str:
                raise SandboxAuthenticationError(str(e))
            elif "not found" in error_str or "404" in str(e):
                raise SandboxNotFoundException(str(args[0]) if args else "unknown")
            elif "timeout" in error_str or "timed out" in error_str:
                raise SandboxTimeoutException(str(args[0]) if args else "unknown", func.__name__)
            elif "quota" in error_str:
                raise SandboxGeneralException(f"Daytona quota exceeded: {e}")
            else:
                raise SandboxGeneralException(f"Daytona error in {func.__name__}: {e}")
    return wrapper


class DaytonaSandbox(BaseSandbox):
    """Daytona sandbox provider for managing remote code execution environments."""

    def __init__(
        self,
        workspace: Workspace,
        sandbox_id: str,
        queue: Optional["SandboxQueueScheduler"],
        daytona_client: Daytona,
    ):
        super().__init__()
        self._workspace = workspace
        self._sandbox_id = sandbox_id
        self._queue = queue
        self._daytona = daytona_client

    def _ensure_workspace(self):
        """Ensure workspace is initialized."""
        if not self._workspace:
            raise SandboxNotInitializedError(
                f"Workspace not initialized: {self._sandbox_id}"
            )

    @property
    def provider_sandbox_id(self) -> str:
        """Return the Daytona workspace ID."""
        self._ensure_workspace()
        return self._workspace.id

    @property
    def sandbox_id(self) -> str:
        """Return the internal sandbox ID."""
        return self._sandbox_id

    @classmethod
    def _ensure_credentials(cls, config: SandboxConfig):
        """Validate Daytona credentials are configured."""
        if not config.daytona_api_key:
            raise SandboxAuthenticationError("Daytona API key is required")

    @classmethod
    def _create_client(cls, config: SandboxConfig) -> Daytona:
        """Create a Daytona SDK client instance."""
        return Daytona(
            config=DaytonaConfig(
                api_key=config.daytona_api_key,
                server_url=config.daytona_server_url,
                target=config.daytona_target,
            )
        )

    @classmethod
    @daytona_exception_handler
    async def create(
        cls,
        config: SandboxConfig,
        queue: Optional["SandboxQueueScheduler"],
        sandbox_id: str,
        metadata: Optional[dict] = None,
        sandbox_template_id: Optional[str] = None,
    ) -> "DaytonaSandbox":
        """Create a new Daytona workspace."""
        cls._ensure_credentials(config)
        
        daytona = cls._create_client(config)
        
        # Create workspace with Python language support
        params = CreateWorkspaceParams(
            language="python",
            os_user="workspace"
        )
        
        workspace = daytona.create(params)
        
        instance = cls(
            workspace=workspace,
            sandbox_id=sandbox_id,
            queue=queue,
            daytona_client=daytona,
        )
        
        # Schedule timeout if queue is available
        await instance._set_timeout(
            config.timeout_seconds, config.pause_before_timeout_seconds
        )
        
        logger.info(f"Created Daytona workspace {workspace.id} for sandbox {sandbox_id}")
        return instance

    @classmethod
    @daytona_exception_handler
    async def connect(
        cls,
        provider_sandbox_id: str,
        config: SandboxConfig,
        queue: Optional["SandboxQueueScheduler"],
        sandbox_id: str,
    ) -> "DaytonaSandbox":
        """Connect to an existing Daytona workspace."""
        cls._ensure_credentials(config)
        
        daytona = cls._create_client(config)
        
        # Find the workspace by ID
        workspaces = daytona.list()
        workspace = None
        for ws in workspaces:
            if ws.id == provider_sandbox_id:
                workspace = ws
                break
        
        if not workspace:
            raise SandboxNotFoundException(provider_sandbox_id)
        
        instance = cls(
            workspace=workspace,
            sandbox_id=sandbox_id,
            queue=queue,
            daytona_client=daytona,
        )
        
        await instance._set_timeout(config.timeout_seconds)
        
        logger.debug(f"Connected to Daytona workspace {provider_sandbox_id}")
        return instance

    @classmethod
    @daytona_exception_handler
    async def resume(
        cls,
        provider_sandbox_id: str,
        config: SandboxConfig,
        queue: Optional["SandboxQueueScheduler"],
        sandbox_id: str,
    ) -> "DaytonaSandbox":
        """Resume a paused Daytona workspace.
        
        Note: Daytona doesn't have explicit pause/resume like E2B.
        This method connects to an existing workspace.
        """
        # Daytona workspaces don't have pause/resume - just connect
        return await cls.connect(
            provider_sandbox_id=provider_sandbox_id,
            config=config,
            queue=queue,
            sandbox_id=sandbox_id,
        )

    @classmethod
    @daytona_exception_handler
    async def delete(
        cls,
        provider_sandbox_id: str,
        config: SandboxConfig,
        queue: Optional["SandboxQueueScheduler"],
        sandbox_id: str,
    ):
        """Delete a Daytona workspace."""
        cls._ensure_credentials(config)
        
        daytona = cls._create_client(config)
        
        # Find and remove the workspace
        workspaces = daytona.list()
        for ws in workspaces:
            if ws.id == provider_sandbox_id:
                daytona.remove(ws)
                logger.info(f"Deleted Daytona workspace {provider_sandbox_id}")
                break
        
        # Cancel any scheduled messages
        if queue:
            await queue.cancel_message(sandbox_id)

    @classmethod
    @daytona_exception_handler
    async def stop(
        cls,
        provider_sandbox_id: str,
        config: SandboxConfig,
        queue: Optional["SandboxQueueScheduler"],
        sandbox_id: str,
    ):
        """Stop/pause a Daytona workspace.
        
        Note: Daytona doesn't support pause like E2B. This is a no-op
        that just cancels any scheduled timeout messages.
        """
        cls._ensure_credentials(config)
        
        # Daytona doesn't have pause functionality
        # Just cancel the timeout message
        if queue:
            await queue.cancel_message(sandbox_id)
        
        logger.info(f"Stop called for Daytona sandbox {sandbox_id} (no-op for Daytona)")

    @classmethod
    @daytona_exception_handler
    async def schedule_timeout(
        cls,
        provider_sandbox_id: str,
        sandbox_id: str,
        config: SandboxConfig,
        queue: Optional["SandboxQueueScheduler"],
        timeout_seconds: int,
    ):
        """Schedule a timeout for the workspace."""
        cls._ensure_credentials(config)
        
        if queue:
            # Cancel existing timeout first
            await queue.cancel_message(sandbox_id)
            
            # Schedule new timeout
            await queue.schedule_message(
                sandbox_id=sandbox_id,
                action="terminate",  # Daytona uses terminate instead of pause
                delay_seconds=timeout_seconds,
                metadata={
                    "reason": "timeout",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(f"Scheduled timeout for sandbox {sandbox_id} in {timeout_seconds // 60} minutes")

    async def _set_timeout(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        pause_before_timeout: int = TIMEOUT_AFTER_PAUSE_SECONDS,
    ):
        """Set timeout for the workspace using queue scheduler."""
        if self._queue and self._sandbox_id:
            await self._queue.schedule_message(
                sandbox_id=self._sandbox_id,
                action="terminate",  # Daytona uses terminate
                delay_seconds=timeout,
                metadata={
                    "reason": "idle",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(
                f"Scheduled timeout for sandbox {self._sandbox_id} in {timeout // 60} minutes"
            )

    async def get_host(self) -> str:
        """Get the host URL for the workspace."""
        self._ensure_workspace()
        # Daytona workspace host extraction
        try:
            import json
            provider_metadata = json.loads(self._workspace.instance.info.provider_metadata)
            node_domain = provider_metadata.get('nodeDomain', '')
            return f"{self._workspace.id}.{node_domain}"
        except Exception as e:
            logger.warning(f"Could not extract host from workspace: {e}")
            return self._workspace.id

    async def expose_port(self, port: int) -> str:
        """Expose a port and return the public URL."""
        self._ensure_workspace()
        try:
            import json
            provider_metadata = json.loads(self._workspace.instance.info.provider_metadata)
            node_domain = provider_metadata.get('nodeDomain', '')
            return f"https://{port}-{self._workspace.id}.{node_domain}"
        except Exception as e:
            logger.warning(f"Could not generate port URL: {e}")
            return f"https://{port}-{self._workspace.id}.daytona.io"

    @daytona_exception_handler
    async def read_file(self, file_path: str) -> str:
        """Read a file from the workspace."""
        self._ensure_workspace()
        content = self._workspace.fs.download_file(file_path)
        if isinstance(content, bytes):
            return content.decode('utf-8')
        return str(content)

    @daytona_exception_handler
    async def write_file(self, file_content: str | bytes | IO, file_path: str) -> bool:
        """Write content to a file in the workspace."""
        self._ensure_workspace()
        
        if isinstance(file_content, IO):
            file_content = file_content.read()
        
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
        
        self._workspace.fs.upload_file(file_path, file_content)
        return True

    @daytona_exception_handler
    async def upload_file(
        self, file_content: str | bytes | IO, remote_file_path: str
    ) -> bool:
        """Upload a file to the workspace."""
        return await self.write_file(file_content, remote_file_path)

    @daytona_exception_handler
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from the workspace."""
        self._ensure_workspace()
        # Use shell command to delete file
        result = self._workspace.process.exec(f"rm -f {file_path}")
        return result.exit_code == 0

    @daytona_exception_handler
    async def download_file(
        self, remote_file_path: str, format: Literal["text", "bytes"] = "text"
    ) -> Optional[str | bytes]:
        """Download a file from the workspace."""
        self._ensure_workspace()
        content = self._workspace.fs.download_file(remote_file_path)
        
        if format == "text" and isinstance(content, bytes):
            return content.decode('utf-8')
        elif format == "bytes" and isinstance(content, str):
            return content.encode('utf-8')
        return content

    async def download_file_stream(self, remote_file_path: str) -> AsyncIterator[bytes]:
        """Download a file as a stream."""
        self._ensure_workspace()
        # Daytona doesn't have native streaming, simulate with chunked download
        content = self._workspace.fs.download_file(remote_file_path)
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        # Yield content in chunks
        chunk_size = 8192
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]

    @daytona_exception_handler
    async def run_cmd(self, command: str, background: bool = False) -> str:
        """Run a command in the workspace."""
        self._ensure_workspace()
        
        if background:
            # Run in background with nohup
            command = f"nohup {command} > /dev/null 2>&1 &"
        
        result: ExecuteResponse = self._workspace.process.exec(command)
        
        if result.exit_code != 0 and not background:
            error_msg = str(result.result) if result.result else f"Exit code: {result.exit_code}"
            raise SandboxGeneralException(f"Command failed: {error_msg}")
        
        return str(result.result) if result.result else ""

    @daytona_exception_handler
    async def cancel_timeout(self):
        """Cancel any scheduled timeout for this workspace."""
        if self._queue and self._sandbox_id:
            await self._queue.cancel_message(self._sandbox_id)

    @daytona_exception_handler
    async def create_directory(
        self, directory_path: str, exist_ok: bool = False
    ) -> bool:
        """Create a directory in the workspace."""
        self._ensure_workspace()
        
        mkdir_flag = "-p" if exist_ok else ""
        result = self._workspace.process.exec(f"mkdir {mkdir_flag} {directory_path}")
        
        if result.exit_code != 0 and not exist_ok:
            raise SandboxGeneralException(f"Failed to create directory: {directory_path}")
        
        return True
