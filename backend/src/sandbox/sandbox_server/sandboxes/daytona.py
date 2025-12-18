"""
Daytona sandbox provider for the sandbox server.

This module provides a comprehensive implementation of the BaseSandbox interface
for Daytona workspaces, including:
- Workspace lifecycle management (create, connect, resume, delete, stop)
- File operations (read, write, upload, download with size limits and compression)
- Command execution (shell commands and Python code)
- Git repository cloning
- Web preview/port exposure
- Automatic timeout scheduling
"""

import asyncio
import base64
import json
import logging
import mimetypes
import os
import shlex
import tempfile
import time
import uuid

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import IO, Any, AsyncIterator, Dict, List, Literal, Optional, Tuple, TYPE_CHECKING, Union

# New daytona package imports (replaces deprecated daytona_sdk)
from daytona import (
    Daytona,
    DaytonaConfig,
    CreateSandboxFromSnapshotParams,
    Sandbox as DaytonaSandboxObj,
)

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

# Initialize mimetypes
mimetypes.init()

logger = logging.getLogger(__name__)

# Constants
TIMEOUT_AFTER_PAUSE_SECONDS = 600
DEFAULT_TIMEOUT = 3600
MAX_FILE_SIZE_MB = 5.0
DEFAULT_CHUNK_SIZE_KB = 100


# ============================================================================
# Custom Exception Classes
# ============================================================================

class DaytonaError(Exception):
    """Base exception class for all Daytona-related errors."""
    pass


class WorkspaceError(DaytonaError):
    """Exception raised for workspace-related errors."""
    pass


class WorkspaceInitializationError(WorkspaceError):
    """Exception raised when workspace initialization fails."""
    pass


class WorkspaceNotFoundError(WorkspaceError):
    """Exception raised when a workspace is not found."""
    pass


class WorkspaceQuotaExceededError(WorkspaceError):
    """Exception raised when CPU quota is exceeded."""
    pass

# Aliases for new naming convention
SandboxQuotaExceededError = WorkspaceQuotaExceededError
SandboxInitializationError = WorkspaceInitializationError


class FileSystemError(DaytonaError):
    """Exception raised for filesystem-related errors."""
    pass


class FileNotAccessibleError(FileSystemError):
    """Exception raised when a file cannot be accessed."""
    pass


class FileTooLargeError(FileSystemError):
    """Exception raised when a file is too large to process."""
    pass


class CommandExecutionError(DaytonaError):
    """Exception raised when a command execution fails."""
    pass


class NetworkError(DaytonaError):
    """Exception raised for network-related errors."""
    pass


# ============================================================================
# Decorators
# ============================================================================

def daytona_exception_handler(func):
    """Decorator to handle Daytona SDK exceptions and convert to sandbox exceptions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except SandboxAuthenticationError:
            raise
        except SandboxNotFoundException:
            raise
        except SandboxTimeoutException:
            raise
        except SandboxNotInitializedError:
            raise
        except SandboxGeneralException:
            raise
        except WorkspaceQuotaExceededError as e:
            raise SandboxGeneralException(f"Daytona quota exceeded: {e}")
        except WorkspaceNotFoundError as e:
            sandbox_id = args[0] if args else "unknown"
            if hasattr(args[0], '_sandbox_id'):
                sandbox_id = args[0]._sandbox_id
            raise SandboxNotFoundException(str(sandbox_id))
        except NetworkError as e:
            raise SandboxGeneralException(f"Daytona network error: {e}")
        except Exception as e:
            error_str = str(e).lower()
            if "unauthorized" in error_str or "401" in str(e) or "authentication" in error_str:
                raise SandboxAuthenticationError(str(e))
            elif "not found" in error_str or "404" in str(e):
                sandbox_id = "unknown"
                if args and hasattr(args[0], '_sandbox_id'):
                    sandbox_id = args[0]._sandbox_id
                raise SandboxNotFoundException(sandbox_id)
            elif "timeout" in error_str or "timed out" in error_str:
                sandbox_id = "unknown"
                if args and hasattr(args[0], '_sandbox_id'):
                    sandbox_id = args[0]._sandbox_id
                raise SandboxTimeoutException(sandbox_id, func.__name__)
            elif "quota" in error_str:
                raise SandboxGeneralException(f"Daytona quota exceeded: {e}")
            else:
                raise SandboxGeneralException(f"Daytona error in {func.__name__}: {e}")
    return wrapper


# ============================================================================
# Helper Functions
# ============================================================================

def get_content_type(file_path: str) -> str:
    """Determine the content type of a file based on its extension."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type

    ext = os.path.splitext(file_path.lower())[1]
    content_types = {
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.json': 'application/json',
        '.py': 'text/x-python',
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.pdf': 'application/pdf',
        '.zip': 'application/zip',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
    }
    return content_types.get(ext, 'application/octet-stream')


# ============================================================================
# Main Sandbox Class
# ============================================================================

class DaytonaSandbox(BaseSandbox):
    """
    Daytona sandbox provider for managing remote code execution environments.
    
    This class provides a comprehensive implementation of the BaseSandbox interface
    with full Daytona SDK integration, including advanced file operations, 
    command execution, and workspace lifecycle management.
    """

    def __init__(
        self,
        sandbox: DaytonaSandboxObj,
        sandbox_id: str,
        queue: Optional["SandboxQueueScheduler"],
        daytona_client: Daytona,
    ):
        super().__init__()
        self._sandbox = sandbox  # New daytona package uses Sandbox not Workspace
        self._sandbox_id = sandbox_id
        self._queue = queue
        self._daytona = daytona_client

    def _ensure_sandbox(self):
        """Ensure sandbox is initialized."""
        if not self._sandbox:
            raise SandboxNotInitializedError(
                f"Sandbox not initialized: {self._sandbox_id}"
            )

    # Kept for backwards compatibility, now just calls _ensure_sandbox
    def _ensure_workspace(self):
        """Ensure sandbox is initialized (legacy name)."""
        self._ensure_sandbox()

    def _ensure_filesystem(self):
        """Ensure sandbox is initialized (filesystem is accessed via sandbox.fs)."""
        self._ensure_sandbox()
        # In new daytona API, filesystem is accessed via sandbox.fs
        # No separate initialization needed

    @property
    def provider_sandbox_id(self) -> str:
        """Return the Daytona sandbox ID."""
        self._ensure_sandbox()
        return self._sandbox.id

    @property
    def sandbox_id(self) -> str:
        """Return the internal sandbox ID."""
        return self._sandbox_id

    # ========================================================================
    # Class Methods - Lifecycle Management
    # ========================================================================

    @classmethod
    def _ensure_credentials(cls, config: SandboxConfig):
        """Validate Daytona credentials are configured."""
        if not config.daytona_api_key:
            raise SandboxAuthenticationError("Daytona API key is required")

    @classmethod
    def _create_client(cls, config: SandboxConfig) -> Daytona:
        """Create a Daytona SDK client instance."""
        return Daytona(
            DaytonaConfig(
                api_key=config.daytona_api_key,
                api_url=config.daytona_server_url,  # Note: server_url deprecated, use api_url
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
        """
        Create a new Daytona workspace.
        
        Args:
            config: Sandbox configuration
            queue: Optional queue scheduler for timeout management
            sandbox_id: Internal sandbox ID
            metadata: Optional metadata for the sandbox
            sandbox_template_id: Optional template ID (not used for Daytona)
            
        Returns:
            DaytonaSandbox instance
        """
        cls._ensure_credentials(config)
        daytona = cls._create_client(config)

        # Clean up old sandboxes if quota is close
        try:
            existing = daytona.list()
            if len(existing.items) > 3:
                logger.info(f"Found {len(existing.items)} sandboxes, cleaning up oldest")
                try:
                    sorted_items = sorted(existing.items, key=lambda s: getattr(s, 'created_at', ''))
                    if sorted_items:
                        oldest = sorted_items[0]
                        logger.info(f"Removing oldest sandbox: {oldest.id}")
                        daytona.delete(oldest)
                except Exception as e:
                    logger.warning(f"Error cleaning old sandboxes: {e}")
        except Exception as e:
            logger.warning(f"Error listing sandboxes: {e}")

        # Create sandbox with retry mechanism
        max_retries = 3
        retry_count = 0
        retry_delay = 2.0
        last_error = None
        sandbox = None

        while retry_count < max_retries:
            try:
                params = CreateSandboxFromSnapshotParams(
                    language="python",
                    auto_stop_interval=config.timeout_seconds // 60 if config.timeout_seconds else 15,
                )
                sandbox = daytona.create(params, timeout=60)
                break
            except Exception as e:
                last_error = e
                error_str = str(e)

                if "Total CPU quota exceeded" in error_str or "quota" in error_str.lower():
                    raise SandboxQuotaExceededError(
                        f"Daytona CPU quota exceeded. Delete unused sandboxes or upgrade your plan."
                    )

                if "Unauthorized" in error_str or "401" in str(e):
                    raise SandboxAuthenticationError("Invalid Daytona API key")

                retry_count += 1
                if retry_count >= max_retries:
                    raise SandboxInitializationError(
                        f"Failed to create sandbox after {max_retries} attempts: {last_error}"
                    )

                logger.warning(f"Sandbox creation attempt {retry_count} failed: {e}, retrying...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5

        if not sandbox:
            raise SandboxInitializationError("Failed to create sandbox")

        # In new daytona API, filesystem is accessed via sandbox.fs - no separate init needed

        instance = cls(
            sandbox=sandbox,
            sandbox_id=sandbox_id,
            queue=queue,
            daytona_client=daytona,
        )

        await instance._set_timeout(
            config.timeout_seconds, config.pause_before_timeout_seconds
        )

        logger.info(f"Created Daytona sandbox {sandbox.id} for internal sandbox_id {sandbox_id}")
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
        """Connect to an existing Daytona sandbox."""
        cls._ensure_credentials(config)
        daytona = cls._create_client(config)

        # Use daytona.get() to retrieve sandbox by ID
        try:
            sandbox = daytona.get(provider_sandbox_id)
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                raise SandboxNotFoundException(provider_sandbox_id)
            raise

        instance = cls(
            sandbox=sandbox,
            sandbox_id=sandbox_id,
            queue=queue,
            daytona_client=daytona,
        )

        await instance._set_timeout(config.timeout_seconds)
        logger.debug(f"Connected to Daytona sandbox {provider_sandbox_id}")
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
        """
        Resume a paused Daytona workspace.
        
        Note: Daytona doesn't have explicit pause/resume like E2B.
        This method connects to an existing workspace.
        """
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
        """Delete a Daytona sandbox."""
        cls._ensure_credentials(config)
        daytona = cls._create_client(config)

        try:
            sandbox = daytona.get(provider_sandbox_id)
            daytona.delete(sandbox)
            logger.info(f"Deleted Daytona sandbox {provider_sandbox_id}")
        except Exception as e:
            if "not found" not in str(e).lower():
                logger.warning(f"Error deleting sandbox {provider_sandbox_id}: {e}")

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
        """
        Stop a Daytona sandbox.
        
        Note: New daytona SDK supports proper stop via daytona.stop(sandbox).
        """
        cls._ensure_credentials(config)
        daytona = cls._create_client(config)

        try:
            sandbox = daytona.get(provider_sandbox_id)
            daytona.stop(sandbox)
            logger.info(f"Stopped Daytona sandbox {provider_sandbox_id}")
        except Exception as e:
            logger.warning(f"Error stopping sandbox {provider_sandbox_id}: {e}")

        if queue:
            await queue.cancel_message(sandbox_id)

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
            await queue.cancel_message(sandbox_id)
            await queue.schedule_message(
                sandbox_id=sandbox_id,
                action="terminate",
                delay_seconds=timeout_seconds,
                metadata={
                    "reason": "timeout",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(f"Scheduled timeout for sandbox {sandbox_id} in {timeout_seconds // 60} minutes")

    # ========================================================================
    # Instance Methods - Timeout Management
    # ========================================================================

    async def _set_timeout(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        pause_before_timeout: int = TIMEOUT_AFTER_PAUSE_SECONDS,
    ):
        """Set timeout for the workspace using queue scheduler."""
        if self._queue and self._sandbox_id:
            await self._queue.schedule_message(
                sandbox_id=self._sandbox_id,
                action="terminate",
                delay_seconds=timeout,
                metadata={
                    "reason": "idle",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(f"Scheduled timeout for sandbox {self._sandbox_id} in {timeout // 60} minutes")

    async def cancel_timeout(self):
        """Cancel any scheduled timeout for this workspace."""
        if self._queue and self._sandbox_id:
            await self._queue.cancel_message(self._sandbox_id)

    # ========================================================================
    # Host and Port Operations
    # ========================================================================

    async def get_host(self) -> str:
        """Get the host URL for the workspace."""
        self._ensure_workspace()
        try:
            provider_metadata = json.loads(self._sandbox.instance.info.provider_metadata)
            node_domain = provider_metadata.get('nodeDomain', '')
            return f"{self._sandbox.id}.{node_domain}"
        except Exception as e:
            logger.warning(f"Could not extract host from workspace: {e}")
            return self._sandbox.id

    async def expose_port(self, port: int) -> str:
        """
        Expose a port and return the public URL.
        
        This generates a preview URL for web applications running in the workspace.
        """
        self._ensure_sandbox()
        # Use new daytona API get_preview_link
        try:
            preview = self._sandbox.get_preview_link(port)
            return preview.url
        except Exception as e:
            logger.warning(f"Could not get preview link: {e}")
            # Fallback to constructing URL manually
            return f"https://{port}-{self._sandbox.id}.daytona.io"

    # ========================================================================
    # File Operations
    # ========================================================================

    @daytona_exception_handler
    async def read_file(self, file_path: str) -> str:
        """Read a file from the sandbox."""
        self._ensure_sandbox()
        content = self._sandbox.fs.download_file(file_path)
        if isinstance(content, bytes):
            return content.decode('utf-8')
        return str(content)

    @daytona_exception_handler
    async def write_file(self, file_content: str | bytes | IO, file_path: str) -> bool:
        """Write content to a file in the sandbox."""
        self._ensure_sandbox()

        if isinstance(file_content, IO):
            file_content = file_content.read()

        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')

        # Create parent directories if needed
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            try:
                self._sandbox.fs.create_folder(parent_dir, "755")
            except Exception as e:
                logger.warning(f"Error creating parent directory: {e}")

        self._sandbox.fs.upload_file(file_content, file_path)
        return True

    @daytona_exception_handler
    async def upload_file(
        self,
        file_content: str | bytes | IO,
        remote_file_path: str,
        encoding: str = "text",
        overwrite: bool = True,
    ) -> bool:
        """
        Upload a file to the workspace with extended options.
        
        Args:
            file_content: Content to write (text, bytes, or file-like object)
            remote_file_path: Destination path in the workspace
            encoding: 'text' or 'base64'
            overwrite: Whether to overwrite existing files
        """
        self._ensure_filesystem()

        # Check if file exists when overwrite is False
        if not overwrite:
            try:
                self._sandbox.fs.get_file_info(remote_file_path)
                raise SandboxGeneralException(f"File '{remote_file_path}' already exists and overwrite=False")
            except Exception:
                pass  # File doesn't exist, continue

        # Process content based on encoding
        if isinstance(file_content, IO):
            file_content = file_content.read()

        if encoding.lower() == "base64":
            if isinstance(file_content, str):
                try:
                    file_content = base64.b64decode(file_content)
                except Exception as e:
                    raise SandboxGeneralException(f"Invalid base64 encoding: {e}")
        else:
            if isinstance(file_content, str):
                file_content = file_content.encode('utf-8')

        # Create parent directories
        parent_dir = os.path.dirname(remote_file_path)
        if parent_dir:
            try:
                self._sandbox.process.exec(f"mkdir -p {shlex.quote(parent_dir)}")
            except Exception as e:
                logger.warning(f"Error creating parent directory: {e}")

        self._sandbox.fs.upload_file(file_content, remote_file_path)
        logger.info(f"Uploaded file to {remote_file_path} ({len(file_content)} bytes)")
        return True

    @daytona_exception_handler
    async def download_file(
        self,
        remote_file_path: str,
        format: Literal["text", "bytes"] = "text",
        max_size_mb: float = MAX_FILE_SIZE_MB,
        download_option: Optional[str] = None,
        chunk_size_kb: int = DEFAULT_CHUNK_SIZE_KB,
    ) -> Optional[Union[str, bytes, Dict[str, Any]]]:
        """
        Download a file from the workspace with advanced handling.
        
        Args:
            remote_file_path: Path to the file in the workspace
            format: 'text' or 'bytes'
            max_size_mb: Maximum file size for automatic download
            download_option: 'download_partial', 'convert_to_text', 'compress_file', 'force_download'
            chunk_size_kb: Chunk size for partial downloads
            
        Returns:
            File content or dict with options for large files
        """
        self._ensure_filesystem()

        # Get file info
        try:
            file_info = self._sandbox.fs.get_file_info(remote_file_path)
            file_size = file_info.size
        except Exception:
            # Fallback to stat command
            try:
                result = self._sandbox.process.exec(f"stat -c %s {shlex.quote(remote_file_path)}")
                file_size = int(str(result.result).strip())
            except Exception as e:
                raise FileNotAccessibleError(f"File not found: {remote_file_path}")

        size_mb = file_size / (1024 * 1024)

        # Handle large files
        if size_mb > max_size_mb and download_option is None:
            return {
                "file_too_large": True,
                "file_size_mb": round(size_mb, 2),
                "max_size_mb": max_size_mb,
                "options": ["download_partial", "convert_to_text", "compress_file", "force_download"],
            }

        if size_mb > max_size_mb and download_option:
            if download_option == "download_partial":
                chunk_bytes = chunk_size_kb * 1024
                result = self._sandbox.process.exec(
                    f"head -c {chunk_bytes} {shlex.quote(remote_file_path)} | base64"
                )
                content = base64.b64decode(str(result.result).strip())
                return content if format == "bytes" else content.decode('utf-8', errors='replace')

            elif download_option == "convert_to_text":
                if remote_file_path.lower().endswith('.pdf'):
                    result = self._sandbox.process.exec(
                        f"pdftotext {shlex.quote(remote_file_path)} - 2>/dev/null"
                    )
                else:
                    result = self._sandbox.process.exec(
                        f"cat {shlex.quote(remote_file_path)} | head -c 100000"
                    )
                content = str(result.result)
                return content if format == "text" else content.encode('utf-8')

            elif download_option == "compress_file":
                temp_path = f"/tmp/compressed_{uuid.uuid4().hex}.gz"
                self._sandbox.process.exec(f"gzip -c {shlex.quote(remote_file_path)} > {temp_path}")
                content = self._sandbox.fs.download_file(temp_path)
                self._sandbox.process.exec(f"rm {temp_path}")
                return content

        # Normal download
        content = self._sandbox.fs.download_file(remote_file_path)

        if format == "text" and isinstance(content, bytes):
            return content.decode('utf-8')
        elif format == "bytes" and isinstance(content, str):
            return content.encode('utf-8')
        return content

    async def download_file_stream(self, remote_file_path: str) -> AsyncIterator[bytes]:
        """Download a file as a stream."""
        self._ensure_filesystem()
        content = self._sandbox.fs.download_file(remote_file_path)
        if isinstance(content, str):
            content = content.encode('utf-8')

        chunk_size = 8192
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]

    @daytona_exception_handler
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from the workspace."""
        self._ensure_workspace()
        result = self._sandbox.process.exec(f"rm -f {shlex.quote(file_path)}")
        return result.exit_code == 0

    @daytona_exception_handler
    async def create_directory(
        self, directory_path: str, exist_ok: bool = False
    ) -> bool:
        """Create a directory in the workspace."""
        self._ensure_workspace()
        mkdir_flag = "-p" if exist_ok else ""
        result = self._sandbox.process.exec(f"mkdir {mkdir_flag} {shlex.quote(directory_path)}")

        if result.exit_code != 0 and not exist_ok:
            raise SandboxGeneralException(f"Failed to create directory: {directory_path}")
        return True

    # ========================================================================
    # Command Execution
    # ========================================================================

    @daytona_exception_handler
    async def run_cmd(self, command: str, background: bool = False, timeout: int = 180) -> str:
        """
        Run a shell command in the workspace.
        
        Args:
            command: Shell command to execute
            background: Whether to run in background
            timeout: Command timeout in seconds
            
        Returns:
            Command output as JSON string with stdout, stderr, exit_code
        """
        self._ensure_workspace()

        if not command or not isinstance(command, str):
            raise ValueError("Command must be a non-empty string")

        # Handle compound commands
        if '&&' in command or command.strip().startswith('cd '):
            command = f'/bin/sh -c {shlex.quote(command)}'

        if background:
            command = f"nohup {command} > /dev/null 2>&1 &"

        try:
            result: ExecuteResponse = self._sandbox.process.exec(command)
            output = str(result.result).strip() if result.result else ""
            exit_code = result.exit_code if hasattr(result, 'exit_code') else -1

            if exit_code != 0 and not background:
                logger.warning(f"Command exited with code {exit_code}: {output[:200]}")

            return json.dumps({
                "stdout": output,
                "stderr": "",
                "exit_code": exit_code
            }, indent=2)

        except Exception as e:
            error_str = str(e)
            if "Connection" in error_str or "Timeout" in error_str:
                raise NetworkError(f"Network error during command execution: {error_str}")
            raise CommandExecutionError(f"Command execution failed: {error_str}")

    @daytona_exception_handler
    async def execute_python_code(self, code: str) -> str:
        """
        Execute Python code in the workspace with enhanced output handling.
        
        This method wraps the code with comprehensive error handling,
        environment diagnostics, and image processing for matplotlib plots.
        
        Args:
            code: Python code to execute
            
        Returns:
            JSON string with stdout, stderr, exit_code, and optional images
        """
        self._ensure_workspace()

        # Create wrapped code with robust error handling
        wrapped_code = f'''
import tempfile
import os
import base64
import json
import io
import sys
import platform
import shutil
import uuid
from pathlib import Path
import traceback

result_dict = {{
    "stdout": "",
    "stderr": "",
    "exit_code": 0,
    "environment": {{}},
    "images": []
}}

original_stdout = sys.stdout
original_stderr = sys.stderr
stdout_capture = io.StringIO()
stderr_capture = io.StringIO()
sys.stdout = stdout_capture
sys.stderr = stderr_capture

try:
    result_dict["environment"] = {{
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "pid": os.getpid()
    }}

    temp_dir = None
    temp_dirs_to_try = [
        os.path.expanduser("~/.daytona_tmp"),
        "/tmp/daytona_tmp",
        os.getcwd()
    ]

    for dir_path in temp_dirs_to_try:
        try:
            os.makedirs(dir_path, mode=0o777, exist_ok=True)
            tempfile.tempdir = dir_path
            temp_dir = tempfile.mkdtemp(prefix='daytona_execution_')
            break
        except Exception:
            pass

    original_dir = os.getcwd()
    if temp_dir and os.path.exists(temp_dir):
        try:
            os.chdir(temp_dir)
        except Exception:
            pass

    globals_dict = {{'__name__': '__main__'}}
    locals_dict = {{}}

    try:
        import datetime, math, random, re, collections, itertools
        globals_dict.update({{
            'datetime': datetime, 'math': math, 'random': random,
            're': re, 'collections': collections, 'itertools': itertools,
            'os': os, 'sys': sys, 'json': json, 'Path': Path
        }})

        try:
            import numpy as np
            globals_dict['np'] = np
        except ImportError:
            pass

        try:
            import pandas as pd
            globals_dict['pd'] = pd
        except ImportError:
            pass

        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            globals_dict['plt'] = plt
            globals_dict['matplotlib'] = matplotlib
        except ImportError:
            pass
    except Exception:
        pass

    try:
        exec(r\'\'\'{code}\'\'\', globals_dict, locals_dict)
    except Exception:
        traceback_str = traceback.format_exc()
        print(f"Error: {{traceback_str}}")
        result_dict["exit_code"] = 1

    if 'plt' in globals_dict and hasattr(globals_dict['plt'], 'get_fignums'):
        plt = globals_dict['plt']
        if plt.get_fignums():
            try:
                for fig_num in plt.get_fignums():
                    fig = plt.figure(fig_num)
                    img_path = f"figure_{{fig_num}}.png"
                    fig.savefig(img_path)
                plt.close('all')
            except Exception:
                pass

    image_files = [f for f in os.listdir('.') if f.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg'))]
    for img_file in image_files:
        try:
            with open(img_file, 'rb') as f:
                img_data = f.read()
                if img_data:
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                    mime_type = "image/png"
                    if img_file.endswith(('.jpg', '.jpeg')):
                        mime_type = "image/jpeg"
                    elif img_file.endswith('.gif'):
                        mime_type = "image/gif"
                    elif img_file.endswith('.svg'):
                        mime_type = "image/svg+xml"
                    result_dict["images"].append({{
                        "data": img_base64,
                        "mime_type": mime_type,
                        "filename": img_file,
                        "size": len(img_data)
                    }})
        except Exception:
            pass

    sys.stdout = original_stdout
    sys.stderr = original_stderr
    result_dict["stdout"] = stdout_capture.getvalue()
    result_dict["stderr"] = stderr_capture.getvalue()

    if temp_dir and os.path.exists(temp_dir):
        try:
            os.chdir(original_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    result_json = json.dumps(result_dict, indent=2)
    print("RESULT_JSON:" + result_json)

except Exception:
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    error_trace = traceback.format_exc()
    result_dict = {{
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue() + "\\n" + error_trace,
        "exit_code": 2,
        "images": []
    }}
    result_json = json.dumps(result_dict, indent=2)
    print("RESULT_JSON:" + result_json)
'''

        try:
            response = self._sandbox.process.code_run(wrapped_code)
            raw_result = str(response.result).strip() if response.result else ""
            exit_code = response.exit_code if hasattr(response, 'exit_code') else -1

            # Look for RESULT_JSON marker
            marker = "RESULT_JSON:"
            marker_pos = raw_result.find(marker)

            if marker_pos >= 0:
                json_str = raw_result[marker_pos + len(marker):].strip()
                try:
                    result_data = json.loads(json_str)
                    if result_data.get("images") and len(result_data["images"]) == 1:
                        img = result_data["images"][0]
                        result_data["image"] = img["data"]
                        result_data["metadata"] = {
                            "filename": img["filename"],
                            "size": img["size"],
                            "type": img["mime_type"].split("/")[-1]
                        }
                    return json.dumps(result_data, indent=2)
                except json.JSONDecodeError:
                    pass

            return json.dumps({
                "stdout": raw_result,
                "stderr": "",
                "exit_code": exit_code
            }, indent=2)

        except Exception as exc:
            return json.dumps({
                "stdout": "",
                "stderr": f"Error executing code: {str(exc)}",
                "exit_code": -1
            }, indent=2)

    # ========================================================================
    # Git Operations
    # ========================================================================

    @daytona_exception_handler
    async def git_clone(
        self,
        repo_url: str,
        target_path: Optional[str] = None,
        branch: Optional[str] = None,
        depth: int = 1,
        lfs: bool = False,
    ) -> Dict[str, Any]:
        """
        Clone a Git repository into the workspace.
        
        Args:
            repo_url: URL of the repository (https or ssh)
            target_path: Target directory (default: repo name)
            branch: Branch to checkout
            depth: Clone depth (1 for shallow)
            lfs: Enable Git LFS
            
        Returns:
            Dict with clone results and file list
        """
        self._ensure_workspace()

        import re
        repo_name_match = re.search(r"([^/]+)(?:\.git)?$", repo_url)
        repo_name = repo_name_match.group(1) if repo_name_match else "repo"
        target_dir = target_path or repo_name

        # Build clone command
        clone_cmd = "git clone"
        if depth > 0:
            clone_cmd += f" --depth {depth}"
        if branch:
            clone_cmd += f" --branch {branch}"
        clone_cmd += f" {shlex.quote(repo_url)}"
        if target_path:
            clone_cmd += f" {shlex.quote(target_path)}"

        result = self._sandbox.process.exec(clone_cmd)

        if result.exit_code != 0:
            return {
                "success": False,
                "error": f"Git clone failed: {result.result}",
                "exit_code": result.exit_code
            }

        # Git LFS
        if lfs:
            try:
                lfs_cmd = f"cd {shlex.quote(target_dir)} && git lfs install && git lfs pull"
                self._sandbox.process.exec(lfs_cmd)
            except Exception as e:
                logger.warning(f"Git LFS error: {e}")

        # Get file list and info
        try:
            ls_result = self._sandbox.process.exec(
                f"find {shlex.quote(target_dir)} -type f -not -path '*/\\.git/*' | sort | head -n 100"
            )
            file_list = str(ls_result.result).strip().split('\n')

            info_result = self._sandbox.process.exec(
                f"cd {shlex.quote(target_dir)} && git log -1 --pretty=format:'%h %an <%ae> %ad %s'"
            )
            repo_info = str(info_result.result).strip()

            count_result = self._sandbox.process.exec(
                f"find {shlex.quote(target_dir)} -type f -not -path '*/\\.git/*' | wc -l"
            )
            total_files = int(str(count_result.result).strip())

            return {
                "success": True,
                "repository": repo_url,
                "target_directory": target_dir,
                "branch": branch,
                "files_sample": file_list[:100],
                "total_files": total_files,
                "repository_info": repo_info,
            }
        except Exception as e:
            return {
                "success": True,
                "repository": repo_url,
                "target_directory": target_dir,
                "error_listing_files": str(e),
            }

    # ========================================================================
    # Workspace Utilities
    # ========================================================================

    @classmethod
    async def cleanup_stale_workspaces(
        cls,
        config: SandboxConfig,
        max_age_days: int = 1,
    ) -> Tuple[int, int, int]:
        """
        Clean up workspaces older than specified age.
        
        Args:
            config: Sandbox configuration
            max_age_days: Maximum age in days
            
        Returns:
            Tuple of (cleaned_count, error_count, remaining_count)
        """
        cls._ensure_credentials(config)
        daytona = cls._create_client(config)

        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        cleaned = 0
        errors = 0
        remaining = 0

        try:
            workspaces = daytona.list()
            for ws in workspaces:
                try:
                    if hasattr(ws, 'created_at'):
                        if isinstance(ws.created_at, (int, float)):
                            age = current_time - ws.created_at
                            if age > max_age_seconds:
                                daytona.remove(ws)
                                cleaned += 1
                            else:
                                remaining += 1
                        else:
                            remaining += 1
                    else:
                        remaining += 1
                except Exception as e:
                    logger.warning(f"Error processing workspace {ws.id}: {e}")
                    errors += 1

            logger.info(f"Cleanup: {cleaned} removed, {errors} errors, {remaining} remaining")
        except Exception as e:
            logger.error(f"Error during workspace cleanup: {e}")
            errors += 1

        return (cleaned, errors, remaining)
