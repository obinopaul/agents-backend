"""SandboxService for managing user sandboxes with MCP credential support."""

import json
from typing import Optional

from backend.src.sandbox.sandbox_server.config import SandboxConfig
from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
from backend.common.log import log


class SandboxService:
    """Singleton service for managing sandboxes with user-specific MCP credentials."""
    
    _instance: Optional["SandboxService"] = None
    _controller: Optional[SandboxController] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SandboxService, cls).__new__(cls)
        return cls._instance
    
    @property
    def controller(self) -> SandboxController:
        if self._controller is None:
            raise RuntimeError("SandboxService not initialized. Call initialize() first.")
        return self._controller
        
    async def initialize(self):
        """Initialize the sandbox controller."""
        if self._controller is None:
            try:
                config = SandboxConfig()
                self._controller = SandboxController(config)
                await self._controller.start()
                log.info("SandboxService initialized successfully")
            except Exception as e:
                log.error(f"Failed to initialize SandboxService: {e}")
                raise

    async def shutdown(self):
        """Shutdown the service."""
        if self._controller:
            await self._controller.shutdown()
            log.info("SandboxService shutdown successfully")

    async def get_or_create_sandbox(
        self, 
        user_id: str, 
        session_id: Optional[str] = None,
        template_id: Optional[str] = None,
        write_mcp_credentials: bool = True
    ) -> BaseSandbox:
        """
        Get an existing sandbox for the session or create a new one.
        
        This implements the II-Agent pattern:
        1. If session_id provided, check if session already has a linked sandbox
        2. If sandbox exists and is running, connect to it (reuse)
        3. If no sandbox, create a new one and link it to the session
        
        :param user_id: User ID
        :param session_id: Optional session ID (for session-based sandbox reuse)
        :param template_id: Optional sandbox template ID
        :param write_mcp_credentials: If True, write user's MCP credentials to sandbox
        :return: Sandbox instance
        """
        from backend.src.sandbox.sandbox_server.db.manager import Sandboxes
        
        # STEP 1: If session_id provided, check if session already has a sandbox
        if session_id:
            existing_sandbox = await Sandboxes.get_sandbox_for_session(session_id)
            if existing_sandbox:
                log.info(f"Reusing existing sandbox {existing_sandbox.id} for session {session_id}")
                # Connect to existing sandbox
                sandbox = await self.controller.connect(existing_sandbox.id)
                return sandbox
        
        # STEP 2: No existing sandbox - create a new one
        log.info(f"Creating new sandbox for user {user_id}" + (f" (session {session_id})" if session_id else ""))
        sandbox = await self.controller.create_sandbox(
            user_id=user_id, 
            sandbox_template_id=template_id
        )
        
        # STEP 3: Link sandbox to session for future reuse
        if session_id:
            await Sandboxes.update_session_sandbox(session_id, sandbox.sandbox_id)
            log.info(f"Linked sandbox {sandbox.sandbox_id} to session {session_id}")
        
        # STEP 4: Write MCP credentials if enabled
        if write_mcp_credentials:
            await self._write_mcp_credentials(user_id, sandbox)
        
        return sandbox

    async def _write_mcp_credentials(self, user_id: str, sandbox: BaseSandbox) -> None:
        """
        Write user's MCP tool credentials to the sandbox.
        
        This enables Claude Code and Codex to work with user's saved authentication.
        
        :param user_id: User ID to fetch credentials for
        :param sandbox: Sandbox to write credentials to
        """
        try:
            # Import here to avoid circular imports
            from backend.app.agent.crud.crud_mcp_setting import mcp_setting_dao
            from backend.app.agent.schema.mcp_setting import MCPToolType
            from backend.database.db import async_db_session
            
            async with async_db_session() as db:
                # Get all active MCP settings for user
                settings = await mcp_setting_dao.get_by_user_id(
                    db, 
                    int(user_id), 
                    only_active=True
                )
                
                for setting in settings:
                    if not setting.auth_json:
                        continue
                    
                    if setting.tool_type == MCPToolType.CLAUDE_CODE:
                        # Write Claude Code OAuth credentials
                        await self._write_sandbox_file(
                            sandbox,
                            "/home/pn/.claude/.credentials.json",
                            json.dumps(setting.auth_json, indent=2)
                        )
                        log.info(f"Wrote Claude Code credentials for user {user_id}")
                        
                    elif setting.tool_type == MCPToolType.CODEX:
                        # Write Codex authentication
                        await self._write_sandbox_file(
                            sandbox,
                            "/home/pn/.codex/auth.json",
                            json.dumps(setting.auth_json, indent=2)
                        )
                        log.info(f"Wrote Codex credentials for user {user_id}")
                        
        except ImportError:
            log.warning("MCP settings module not available, skipping credential writing")
        except Exception as e:
            log.warning(f"Failed to write MCP credentials for user {user_id}: {e}")
            # Don't fail sandbox creation if credential writing fails

    async def _write_sandbox_file(
        self, 
        sandbox: BaseSandbox, 
        path: str, 
        content: str
    ) -> None:
        """
        Write a file to the sandbox, creating parent directories if needed.
        
        :param sandbox: Sandbox instance
        :param path: File path in sandbox
        :param content: File content
        """
        try:
            # Ensure parent directory exists
            parent_dir = "/".join(path.split("/")[:-1])
            await sandbox.run_command(f"mkdir -p {parent_dir}")
            
            # Write file content (base64 encode to handle special characters)
            import base64
            encoded = base64.b64encode(content.encode()).decode()
            await sandbox.run_command(
                f'echo "{encoded}" | base64 -d > {path}'
            )
            
            # Set appropriate permissions
            await sandbox.run_command(f"chmod 600 {path}")
            
        except Exception as e:
            log.warning(f"Failed to write file {path} to sandbox: {e}")
            raise

    async def run_cmd(self, sandbox_id: str, command: str, background: bool = False) -> str:
        """Run a command in a sandbox."""
        return await self.controller.run_cmd(sandbox_id, command, background)

    async def terminate_sandbox(self, sandbox_id: str):
        """Terminate a sandbox."""
        await self.controller.delete_sandbox(sandbox_id)


sandbox_service = SandboxService()

