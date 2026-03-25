"""SandboxService for managing user sandboxes with MCP credential support.

This module implements the II-Agent cold/warm start pattern:
- Cold start (new sandbox): Full MCP configuration (credential + tool server URL + health check)
- Warm start (existing sandbox): Light reset (just tool server URL, ~200-500ms)

This optimization dramatically reduces the perceived "sandbox spin-up" for subsequent
messages in the same session.
"""

import asyncio
import json
from typing import Optional, Tuple, Dict, Any

from backend.src.sandbox.sandbox_server.config import SandboxConfig
from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
from backend.src.config.skill_config import get_skill_folder, AgentCategory
from backend.common.log import log
from backend.core.conf import settings


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
                from backend.core.conf import settings
                log.info(f"Initializing SandboxService: provider=e2b, E2B_API_KEY={'set' if settings.E2B_API_KEY else 'NOT SET'}")
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
        write_mcp_credentials: bool = True,
        agent_category: AgentCategory | None = None,
        user_api_key: Optional[str] = None,
    ) -> Tuple[BaseSandbox, bool]:
        """
        Get an existing sandbox for the session or create a new one.
        
        Implements the II-Agent cold/warm start pattern:
        - Cold start (new sandbox): Full MCP configuration (~30-60s)
        - Warm start (existing sandbox): Light reset (~200-500ms)
        
        1. If session_id provided, check if session already has a linked sandbox
        2. If sandbox exists and is running:
           - Connect to it (reuse)
           - Call reset_tool_server() for warm start (light)
        3. If no sandbox:
           - Create a new one and link it to the session
           - Call pre_configure_mcp_server() for cold start (heavy)
        
        :param user_id: User ID
        :param session_id: Optional session ID (for session-based sandbox reuse)
        :param template_id: Optional sandbox template ID
        :param write_mcp_credentials: If True, write user's MCP credentials to sandbox
        :param agent_category: Agent category for skill injection ("general", "scientific", "academic")
        :param user_api_key: User's JWT token for MCP authentication
        :return: Tuple of (Sandbox instance, is_cold_start)
        """
        from backend.src.sandbox.sandbox_server.db.manager import Sandboxes
        
        # STEP 1: If session_id provided, check if session already has a sandbox
        if session_id:
            existing_sandbox = await Sandboxes.get_sandbox_for_session(session_id)
            if existing_sandbox:
                log.info(f"WARM START: Reusing existing sandbox {existing_sandbox.id} for session {session_id}")
                # Connect to existing sandbox
                sandbox = await self.controller.connect(existing_sandbox.id)
                
                # WARM START: Reset tool server URL + credentials (~200-500ms)
                # We also send credentials because the MCP server process
                # may have restarted (losing in-memory credential state).
                effective_api_key = user_api_key if user_api_key else f"sandbox-{existing_sandbox.id}"
                credentials = {
                    "session_id": session_id,
                    "user_api_key": effective_api_key,
                }
                await self.reset_tool_server(sandbox, credentials=credentials)
                
                return sandbox, False  # is_cold_start = False
        
        # STEP 2: No existing sandbox - create a new one (COLD START)
        log.info(f"COLD START: Creating new sandbox for user {user_id}" + (f" (session {session_id})" if session_id else ""))
        sandbox = await self.controller.create_sandbox(
            user_id=user_id, 
            sandbox_template_id=template_id
        )
        
        # STEP 3: Link sandbox to session for future reuse
        if session_id:
            # user_id is a string, convert to int for SessionMetrics FK
            await Sandboxes.update_session_sandbox(session_id, sandbox.sandbox_id, user_id=int(user_id))
            log.info(f"Linked sandbox {sandbox.sandbox_id} to session {session_id}")
        
        # STEP 4: Write MCP credentials if enabled
        if write_mcp_credentials:
            await self._write_mcp_credentials(user_id, sandbox)
        
        # STEP 5: Inject skills based on agent category
        if agent_category is not None:
            await self._inject_skills(sandbox, agent_category)
        
        # STEP 6: COLD START - Full MCP configuration with health check
        # Generate a fallback user_api_key if none provided — the sandbox MCP
        # server rejects empty strings, so we use the sandbox ID as a token.
        effective_api_key = user_api_key if user_api_key else f"sandbox-{sandbox.sandbox_id}"
        credentials = {
            "session_id": session_id or str(sandbox.sandbox_id),
            "user_api_key": effective_api_key,
        }
        await self.pre_configure_mcp_server(sandbox, credentials)
        
        return sandbox, True  # is_cold_start = True
    
    # =========================================================================
    # MCP Cold/Warm Start Methods (II-Agent Pattern)
    # =========================================================================
    
    async def reset_tool_server(
        self, sandbox: BaseSandbox, credentials: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Light-weight reset for WARM START (~200-500ms).
        
        Resets credentials (in case MCP server process restarted and lost
        in-memory state) and the tool server URL. Skips health check
        polling and heavy tool verification.
        
        :param sandbox: Sandbox instance
        :param credentials: Optional dict with session_id and user_api_key.
            If provided, credentials are set before tool server URL (required
            if MCP server process restarted since cold start).
        :return: True if successful, False on error
        """
        mcp_port = settings.SANDBOX_MCP_SERVER_PORT
        try:
            sandbox_url = await sandbox.expose_port(mcp_port)
            log.info(f"WARM START: Resetting tool server at {sandbox_url}")
            
            from backend.src.tool_server.mcp.client import MCPClient
            
            async with MCPClient(sandbox_url) as client:
                # Always (re-)set credentials — the MCP server process may have
                # restarted inside the sandbox, losing in-memory credential
                # state.  POST /tool-server-url requires credentials to be set
                # first, so we must do this before setting the URL.
                if credentials:
                    try:
                        await client.set_credential(credentials)
                        log.info("WARM START: Credentials set")
                    except Exception as cred_err:
                        log.warning(f"WARM START: Failed to set credentials: {cred_err}")
                        # Continue anyway — maybe credentials are still in memory
                
                # Set Tool Server URL for external API tools (web search, image gen, etc.)
                # This URL must point to the Docker Tool Server, accessible from sandbox
                tool_server_url = settings.PUBLIC_TOOL_SERVER_URL
                if tool_server_url:
                    await client.set_tool_server_url(tool_server_url)
                    log.info(f"WARM START: Tool server URL set to {tool_server_url}")
                else:
                    log.error(
                        "WARM START: PUBLIC_TOOL_SERVER_URL is EMPTY — this means the sandbox "
                        "MCP server will have 0 tools registered. ALL sandbox tools (file_read, "
                        "shell_run_command, web_search, image_generate, excalidraw_*, slide_*, etc.) "
                        "are UNAVAILABLE. Set PUBLIC_TOOL_SERVER_URL in backend/.env to an ngrok "
                        "URL pointing to the Docker Tool Server on port 1237. "
                        "Example: PUBLIC_TOOL_SERVER_URL=https://xxxx.ngrok-free.app"
                    )
            
            log.info("WARM START: Tool server reset complete")
            return True
            
        except Exception as e:
            log.warning(f"WARM START: Failed to reset tool server: {e}")
            return False
    
    async def pre_configure_mcp_server(
        self, 
        sandbox: BaseSandbox, 
        credentials: Dict[str, Any],
        health_check_timeout: int = 90,
        poll_interval: int = 2,
    ) -> bool:
        """
        Full MCP configuration for COLD START (~30-60s).
        
        Performs complete MCP server initialization:
        1. Wait for MCP server health check (polling loop)
        2. Set credentials (user_api_key, session_id)
        3. Set tool server URL
        4. Verify tools are available (ping + list_tools)
        
        :param sandbox: Sandbox instance
        :param credentials: Dict with session_id and user_api_key
        :param health_check_timeout: Max seconds to wait for health check
        :param poll_interval: Seconds between health check polls
        :return: True if successful, False on error
        """
        mcp_port = settings.SANDBOX_MCP_SERVER_PORT
        
        try:
            sandbox_url = await sandbox.expose_port(mcp_port)
            log.info(f"COLD START: Configuring MCP server at {sandbox_url}")
            
            # STEP 1: Wait for MCP server to be healthy (polling loop)
            import httpx
            from datetime import datetime
            
            mcp_ready = False
            start_time = datetime.now()
            
            async with httpx.AsyncClient() as http_client:
                while (datetime.now() - start_time).seconds < health_check_timeout:
                    elapsed = (datetime.now() - start_time).seconds
                    try:
                        resp = await http_client.get(f"{sandbox_url}/health", timeout=8.0)
                        if resp.status_code == 200:
                            log.info(f"COLD START: MCP healthy after {elapsed}s")
                            mcp_ready = True
                            break
                    except Exception as e:
                        log.debug(f"COLD START: MCP not ready ({elapsed}s): {type(e).__name__}")
                    
                    await asyncio.sleep(poll_interval)
            
            if not mcp_ready:
                log.warning(f"COLD START: MCP not ready after {health_check_timeout}s, proceeding anyway")
            
            # STEP 2: Configure MCP server with credentials and tool server URL
            from backend.src.tool_server.mcp.client import MCPClient
            
            async with MCPClient(sandbox_url) as client:
                # Set credentials
                await client.set_credential(credentials)
                log.info("COLD START: Credentials set")
                
                # Set Tool Server URL for external API tools (web search, image gen, etc.)
                # This URL must point to the Docker Tool Server, accessible from sandbox via ngrok or production URL
                # CRITICAL: This call triggers tool registration on the sandbox MCP server.
                #   POST /tool-server-url on the sandbox MCP server:
                #   1. Validates credential is set (done above)
                #   2. Health-checks the tool server URL
                #   3. Calls get_sandbox_tools() to instantiate all 60+ tools
                #   4. Registers every tool with FastMCP
                #   Without this call, the sandbox MCP server has 0 tools.
                tool_server_url = settings.PUBLIC_TOOL_SERVER_URL
                tool_registration_success = False
                if tool_server_url:
                    try:
                        await client.set_tool_server_url(tool_server_url)
                        tool_registration_success = True
                        log.info(f"COLD START: Tool server URL set to {tool_server_url}")
                    except Exception as ts_error:
                        log.error(
                            f"COLD START: set_tool_server_url FAILED for '{tool_server_url}': {ts_error}. "
                            "This typically means the Docker Tool Server at that URL is not reachable "
                            "from the e2b sandbox (ngrok tunnel down? Docker container not running?). "
                            "The sandbox MCP server will have 0 tools registered."
                        )
                else:
                    log.error(
                        "COLD START: PUBLIC_TOOL_SERVER_URL is EMPTY — this means the sandbox "
                        "MCP server will have 0 tools registered. ALL sandbox tools (file_read, "
                        "shell_run_command, web_search, image_generate, excalidraw_*, slide_*, etc.) "
                        "are UNAVAILABLE. To fix: "
                        "1. Start Docker stack: docker compose up tool-server ngrok "
                        "2. Get ngrok URL from http://localhost:4040/api/tunnels "
                        "3. Set in backend/.env: PUBLIC_TOOL_SERVER_URL=https://xxxx.ngrok-free.app "
                        "4. Restart backend"
                    )
                
                # Verify tools are actually registered
                # This is the critical validation — if tool_server_url was set but the
                # sandbox MCP server still has 0 tools, something went wrong.
                if mcp_ready:
                    try:
                        await client.health_check()
                        tool_names = await client.get_tool_names()
                        tool_count = len(tool_names)
                        
                        if tool_count > 0:
                            log.info(
                                f"COLD START: Tool registration verified — {tool_count} tools available: "
                                f"{tool_names[:10]}{'...' if tool_count > 10 else ''}"
                            )
                        elif tool_registration_success:
                            # set_tool_server_url succeeded but 0 tools — unexpected
                            log.error(
                                f"COLD START: set_tool_server_url returned success but sandbox MCP "
                                f"server reports 0 tools! This is unexpected. The tool server at "
                                f"'{tool_server_url}' may have responded to health check but "
                                f"get_sandbox_tools() may have failed internally. Check sandbox logs."
                            )
                        else:
                            # Expected — tool_server_url was empty or set_tool_server_url failed
                            log.warning(
                                "COLD START: 0 tools available on sandbox MCP server "
                                "(expected because tool server URL was not set or failed)"
                            )
                    except Exception as verify_error:
                        log.warning(f"COLD START: Tool verification failed: {verify_error}")
                
                # STEP 3: Register Graphiti MCP Server for Knowledge Graph tools
                # Graphiti runs inside the sandbox on port 8500 with 10 tools:
                # add_memory, search_nodes, search_memory_facts, etc.
                graphiti_port = settings.SANDBOX_GRAPHITI_MCP_PORT
                try:
                    import httpx
                    # Expose Graphiti port to check health (returns external E2B URL)
                    graphiti_external_url = await sandbox.expose_port(graphiti_port)
                    
                    # Check if Graphiti MCP is running via exposed URL
                    async with httpx.AsyncClient() as http_client:
                        resp = await http_client.get(f"{graphiti_external_url}/health", timeout=10.0)
                        if resp.status_code == 200:
                            # Register Graphiti as a custom MCP server
                            # NOTE: We use localhost:8500 because ProxyClient runs INSIDE the sandbox
                            # (it's part of the MCP server on port 6060), so it can reach Graphiti
                            # at localhost:8500 within the same sandbox container.
                            graphiti_config = {
                                "mcpServers": {
                                    "graphiti": {
                                        "url": f"http://localhost:{graphiti_port}/mcp/"
                                    }
                                }
                            }
                            await client.register_custom_mcp(graphiti_config)
                            log.info("COLD START: Graphiti MCP registered (Knowledge Graph tools available)")
                        else:
                            log.debug(f"COLD START: Graphiti MCP not healthy: {resp.status_code}")
                except Exception as graphiti_error:
                    # Graphiti is optional - don't fail cold start if unavailable
                    log.debug(f"COLD START: Graphiti MCP not available: {graphiti_error}")
            
            log.info("COLD START: MCP configuration complete")
            return True
            
        except Exception as e:
            log.error(f"COLD START: Failed to configure MCP server: {e}")
            return False
    
    async def _inject_skills(
        self,
        sandbox: BaseSandbox,
        agent_category: AgentCategory,
    ) -> None:
        """
        Inject skills into the sandbox workspace.
        
        Runs /app/inject-skills.sh to copy the appropriate skill folder's
        contents to /workspace/.deepagents/skills/ (flat structure).
        
        :param sandbox: Sandbox instance
        :param agent_category: Agent category ("general", "scientific", "academic")
        """
        try:
            skill_folder = get_skill_folder(agent_category)
            log.info(f"[SKILLS] Starting injection: category='{agent_category}' -> folder='{skill_folder}'")
            print(f"DEBUG [SKILLS]: category='{agent_category}' -> folder='{skill_folder}'", flush=True)
            
            # Verify source folder exists in sandbox
            check_source_cmd = f"ls -la /app/skills/{skill_folder}/ 2>&1 | head -20"
            source_check = await sandbox.run_cmd(check_source_cmd)
            log.info(f"[SKILLS] Source folder check (/app/skills/{skill_folder}/): {source_check[:500] if source_check else 'empty'}")
            print(f"DEBUG [SKILLS] Source: {source_check[:300] if source_check else 'empty'}", flush=True)
            
            # Check if inject-skills.sh exists and is executable
            script_check = await sandbox.run_cmd("ls -la /app/inject-skills.sh 2>&1")
            log.info(f"[SKILLS] Script check: {script_check}")
            print(f"DEBUG [SKILLS] Script exists: {script_check}", flush=True)
            
            # Run the inject-skills.sh script
            log.info(f"[SKILLS] Running: /app/inject-skills.sh {skill_folder}")
            print(f"DEBUG [SKILLS] Running: /app/inject-skills.sh {skill_folder}", flush=True)
            result = await sandbox.run_cmd(f"/app/inject-skills.sh {skill_folder}")
            
            # Log the full output
            log.info(f"[SKILLS] inject-skills.sh output:\n{result if result else 'no output'}")
            print(f"DEBUG [SKILLS] Output:\n{result if result else 'no output'}", flush=True)
            
            # Verify skills were actually injected - list the target directory
            verify_cmd = "ls -la /workspace/.deepagents/skills/ 2>&1 | head -30"
            verify_result = await sandbox.run_cmd(verify_cmd)
            log.info(f"[SKILLS] Verification (/workspace/.deepagents/skills/): {verify_result[:500] if verify_result else 'empty'}")
            print(f"DEBUG [SKILLS] Verification: {verify_result[:300] if verify_result else 'empty'}", flush=True)
            
            # Count injected skills
            count_cmd = "ls -1 /workspace/.deepagents/skills/ 2>/dev/null | wc -l"
            count_result = await sandbox.run_cmd(count_cmd)
            skill_count = count_result.strip() if count_result else "0"
            log.info(f"[SKILLS] Injection complete: {skill_count} skills injected for category '{agent_category}'")
            print(f"DEBUG [SKILLS] Complete: {skill_count} skills injected", flush=True)

            
        except Exception as e:
            import traceback
            error_msg = f"Failed to inject skills for category '{agent_category}': {e}"
            log.error(f"[SKILLS] ERROR: {error_msg}")
            log.error(f"[SKILLS] Traceback: {traceback.format_exc()}")
            print(f"DEBUG [SKILLS] ERROR: {error_msg}", flush=True)
            print(f"DEBUG [SKILLS] Traceback: {traceback.format_exc()}", flush=True)
            # Don't fail sandbox creation if skill injection fails


    async def _write_mcp_credentials(self, user_id: str, sandbox: BaseSandbox) -> None:
        """
        Write user's MCP tool credentials to the sandbox and register MCP servers.
        
        This enables Claude Code and Codex to work with user's saved authentication.
        After writing credentials, it also:
        - Starts the Codex SSE server if Codex is configured
        - Registers custom MCP servers (codex-as-mcp, claude-code-mcp)
        
        :param user_id: User ID to fetch credentials for
        :param sandbox: Sandbox to write credentials to
        """
        mcp_settings = []  # Collect settings for registration
        
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
                mcp_settings = list(settings)  # Save for registration
                
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
            return
        except Exception as e:
            log.warning(f"Failed to write MCP credentials for user {user_id}: {e}")
            # Don't fail sandbox creation if credential writing fails
            return
        
        # STEP 2: Register Codex SSE server if user has Codex configured
        from backend.app.agent.schema.mcp_setting import MCPToolType
        codex_setting = next(
            (s for s in mcp_settings if s.tool_type == MCPToolType.CODEX and s.is_active),
            None
        )
        if codex_setting:
            await self._register_codex_server(sandbox)
        
        # STEP 3: Register custom MCP servers (codex-as-mcp, claude-code-mcp)
        await self._register_custom_mcp_servers(sandbox, mcp_settings)

    async def _register_codex_server(self, sandbox: BaseSandbox) -> None:
        """
        Start the Codex SSE server in the sandbox.
        
        This calls the MCP server's /register-codex endpoint which starts the
        sse-http-server subprocess on port 1324.
        
        :param sandbox: Sandbox instance
        """
        from backend.core.conf import settings
        
        try:
            # Get MCP server URL
            mcp_url = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)
            
            # Use MCPClient to register Codex
            from backend.src.tool_server.mcp.client import MCPClient
            
            async with MCPClient(mcp_url) as client:
                result = await client.register_codex()
                
                if result.get("status") == "success":
                    codex_url = result.get("url", f"http://0.0.0.0:{settings.SANDBOX_CODEX_SSE_PORT}")
                    log.info(f"Codex SSE server started successfully at {codex_url}")
                elif result.get("status") == "already_running":
                    log.info(f"Codex SSE server already running at {result.get('url')}")
                else:
                    log.warning(f"Codex SSE server registration returned: {result}")
                    
        except Exception as e:
            log.warning(f"Failed to register Codex SSE server: {e}")
            # Don't fail sandbox creation if Codex registration fails

    async def _register_custom_mcp_servers(
        self, 
        sandbox: BaseSandbox, 
        mcp_settings: list
    ) -> None:
        """
        Register custom MCP servers (codex-as-mcp, claude-code-mcp) with the sandbox.
        
        These are stdio-based MCP servers that run inside the sandbox and provide
        additional tools for the agent.
        
        :param sandbox: Sandbox instance
        :param mcp_settings: List of MCP settings from database
        """
        from backend.core.conf import settings
        
        if not mcp_settings:
            return
        
        try:
            # Get MCP server URL
            mcp_url = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)
            
            from backend.src.tool_server.mcp.client import MCPClient
            
            async with MCPClient(mcp_url) as client:
                for setting in mcp_settings:
                    # Skip settings without mcp_config
                    if not setting.mcp_config:
                        continue
                    
                    mcp_servers = setting.mcp_config.get("mcpServers", {})
                    if not mcp_servers:
                        continue
                    
                    # Register each MCP server configuration
                    try:
                        result = await client.register_custom_mcp(setting.mcp_config)
                        log.info(f"Registered custom MCP server for {setting.tool_type}: {result}")
                    except Exception as reg_error:
                        log.warning(f"Failed to register {setting.tool_type} MCP server: {reg_error}")
                        
        except Exception as e:
            log.warning(f"Failed to register custom MCP servers: {e}")
            # Don't fail sandbox creation if MCP registration fails

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

