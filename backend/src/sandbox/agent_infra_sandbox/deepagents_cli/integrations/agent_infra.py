"""Agent-Infra sandbox backend implementation.

This module implements the SandboxBackendProtocol for the local Docker-based 
Agent-Infra sandbox, allowing DeepAgents CLI to use it for code execution
and file operations.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

if TYPE_CHECKING:
    from agent_sandbox import AsyncSandbox, Sandbox


class AgentInfraBackend(BaseSandbox):
    """Agent-Infra backend implementing SandboxBackendProtocol.
    
    Uses the local Docker-based Agent-Infra sandbox for:
    - Command execution via shell API
    - File operations via filesystem API
    - Jupyter code execution
    
    This is the default sandbox backend for DeepAgents CLI when running
    with the agent_infra_sandbox project.
    
    Args:
        base_url: Base URL of the sandbox (default: from AGENT_INFRA_URL env or localhost:8080)
        timeout: Request timeout in seconds (default: 60)
    """

    def __init__(
        self, 
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the AgentInfraBackend.

        Args:
            base_url: Base URL of the Agent-Infra sandbox
            timeout: Request timeout in seconds
        """
        self._base_url = base_url or os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
        self._timeout = timeout
        self._sync_client: Optional[Sandbox] = None
        self._async_client: Optional[AsyncSandbox] = None
        self._home_dir: Optional[str] = None
        self._current_session: Optional[str] = None  # Session name for workspace path

    @property
    def current_workspace(self) -> str:
        """Get the current session workspace path."""
        home_dir = self._get_home_dir()
        if self._current_session:
            return f"{home_dir}/workspaces/{self._current_session}"
        return home_dir  # Fallback if no session

    def get_preview_url(self, port: int, is_frontend: bool = True) -> str:
        """Get a URL to access a service running on the given port inside the sandbox.
        
        The sandbox has built-in reverse proxy endpoints:
        - /absproxy/{port}/ - For frontend applications (Next.js, Vite, React)
        - /proxy/{port}/ - For backend API services
        
        Frontend apps need /absproxy because they use absolute paths for assets,
        and this endpoint rewrites paths correctly.
        
        Args:
            port: The internal port number where the service is running (e.g., 3000)
            is_frontend: True for frontend apps (Next.js, Vite), False for backend APIs
            
        Returns:
            A URL that can be opened in the host browser to access the service.
            
        Examples:
            >>> backend.get_preview_url(3000)  # Next.js frontend
            'http://localhost:8090/absproxy/3000/'
            
            >>> backend.get_preview_url(8000, is_frontend=False)  # FastAPI backend
            'http://localhost:8090/proxy/8000/'
        """
        proxy_type = "absproxy" if is_frontend else "proxy"
        return f"{self._base_url}/{proxy_type}/{port}/"

    @property
    def sync_client(self) -> Sandbox:
        """Get or create the synchronous SDK client."""
        if self._sync_client is None:
            from agent_sandbox import Sandbox
            self._sync_client = Sandbox(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._sync_client

    @property
    def async_client(self) -> AsyncSandbox:
        """Get or create the asynchronous SDK client."""
        if self._async_client is None:
            from agent_sandbox import AsyncSandbox
            self._async_client = AsyncSandbox(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._async_client

    @property
    def id(self) -> str:
        """Unique identifier for the sandbox backend."""
        return f"agent-infra-{self._base_url.replace('http://', '').replace(':', '-')}"

    def _get_home_dir(self) -> str:
        """Get the sandbox home directory (cached)."""
        if self._home_dir is None:
            context = self.sync_client.sandbox.get_context()
            self._home_dir = context.home_dir
        return self._home_dir

    def _resolve_workspace_path(self, path: str) -> str:
        """Resolve a path relative to current workspace.
        
        Security: All file operations are sandboxed to the workspace directory.
        
        - Absolute paths starting with workspace are kept as-is
        - Relative paths are resolved against workspace
        - Other absolute paths are sandboxed inside workspace
        
        Args:
            path: Path to resolve
            
        Returns:
            Absolute path within the workspace
        """
        workspace = self.current_workspace
        if path.startswith(workspace):
            return path
        elif path.startswith('/'):
            # Sandbox to workspace for security
            return f"{workspace}/{path.lstrip('/')}"
        else:
            return f"{workspace}/{path}"

    def _extract_result_data(self, result, default_value=None):
        """Extract data from SDK result object.
        
        The SDK returns different result structures. This helper
        normalizes the extraction.
        """
        if hasattr(result, 'data'):
            return result.data
        elif hasattr(result, 'success') and result.success:
            return result
        return default_value

    def initialize_workspace(
        self, 
        session_name: str = "default",
        agent_name: str = "agent",
    ) -> bool:
        """Initialize a workspace for a session in the sandbox.
        
        Creates the required directory structure and default agent.md file
        for the given session. Each session has its own isolated workspace.
        
        Directory structure:
        /home/gem/workspaces/{session_name}/
        ├── .deepagents/
        │   └── agent/
        │       └── agent.md
        └── memories/
        
        Args:
            session_name: Name of the session/workspace
            agent_name: Name of the agent (default: "agent")
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        from pathlib import Path
        
        # Store session name for workspace path resolution
        self._current_session = session_name
        
        home_dir = self._get_home_dir()
        workspace_base = f"{home_dir}/workspaces/{session_name}"
        agent_dir = f"{workspace_base}/.deepagents/{agent_name}"
        agent_md_path = f"{agent_dir}/agent.md"
        memories_dir = f"{workspace_base}/memories"
        
        try:
            # Create directory structure
            self.sync_client.shell.exec_command(
                command=f"mkdir -p {agent_dir} {memories_dir}",
                timeout=self._timeout,
            )
            
            # Check if agent.md already exists
            check_result = self.sync_client.shell.exec_command(
                command=f"test -f {agent_md_path} && echo 'exists' || echo 'missing'",
                timeout=self._timeout,
            )
            
            file_exists = False
            if hasattr(check_result, 'data') and hasattr(check_result.data, 'output'):
                file_exists = 'exists' in check_result.data.output
            elif hasattr(check_result, 'output'):
                file_exists = 'exists' in check_result.output
                
            # Only create agent.md if it doesn't exist
            if not file_exists:
                # Load default agent prompt from bundled file
                default_prompt = self._get_default_agent_prompt(session_name, workspace_base)
                
                # Write the agent.md file using base64 to handle special chars
                import base64
                encoded = base64.b64encode(default_prompt.encode()).decode()
                self.sync_client.shell.exec_command(
                    command=f"echo '{encoded}' | base64 -d > {agent_md_path}",
                    timeout=self._timeout,
                )
            
            # Store current workspace path
            self._current_workspace = workspace_base
            
            return True
            
        except Exception as e:
            # Log but don't fail - the CLI can work without this
            import sys
            print(f"Warning: Failed to initialize workspace: {e}", file=sys.stderr)
            return False
    
    @property
    def current_workspace(self) -> str:
        """Get the current workspace path."""
        return getattr(self, '_current_workspace', f"{self._get_home_dir()}/workspaces/default")
    
    def list_workspaces(self) -> list[str]:
        """List all workspaces in the sandbox.
        
        Returns:
            List of workspace names
        """
        home_dir = self._get_home_dir()
        workspace_base = f"{home_dir}/workspaces"
        
        try:
            result = self.sync_client.shell.exec_command(
                command=f"ls -1 {workspace_base} 2>/dev/null || echo ''",
                timeout=self._timeout,
            )
            
            output = ""
            if hasattr(result, 'data') and hasattr(result.data, 'output'):
                output = result.data.output
            elif hasattr(result, 'output'):
                output = result.output
            
            return [w.strip() for w in output.split('\n') if w.strip()]
        except Exception:
            return []
    
    def delete_workspace(self, session_name: str, force: bool = False) -> bool:
        """Delete a workspace from the sandbox.
        
        Args:
            session_name: Name of the workspace to delete
            force: If True, delete even if workspace has files
            
        Returns:
            True if deleted, False otherwise
        """
        home_dir = self._get_home_dir()
        workspace_path = f"{home_dir}/workspaces/{session_name}"
        
        try:
            if force:
                self.sync_client.shell.exec_command(
                    command=f"rm -rf {workspace_path}",
                    timeout=self._timeout,
                )
            else:
                # Only delete if empty or just has .deepagents
                self.sync_client.shell.exec_command(
                    command=f"rmdir {workspace_path} 2>/dev/null || rm -rf {workspace_path}/.deepagents && rmdir {workspace_path}",
                    timeout=self._timeout,
                )
            return True
        except Exception:
            return False
    
    def _get_default_agent_prompt(self, session_name: str, workspace_path: str) -> str:
        """Load the default agent prompt from the bundled file.
        
        Args:
            session_name: Name of the current session
            workspace_path: Path to the workspace directory
        
        Returns:
            Default agent.md content with session context
        """
        from pathlib import Path
        
        # Try to load from bundled file in deepagents_cli package
        base_prompt = ""
        try:
            # Get the directory of this file
            this_dir = Path(__file__).parent.parent  # Go up from integrations/ to deepagents_cli/
            prompt_file = this_dir / "default_agent_prompt.md"
            
            if prompt_file.exists():
                base_prompt = prompt_file.read_text()
        except Exception:
            pass
        
        if not base_prompt:
            # Fallback minimal prompt if file not found
            base_prompt = """# Agents Backend Sandbox

You are an AI assistant that helps users with coding, research, and analysis.

## Core Capabilities
- Execute shell commands in a secure Docker sandbox
- Read, write, and edit files
- Search the web for documentation
- Run Python code and tests

## Memory System
Store persistent notes in the memories/ directory within your workspace.
Check `ls memories/` at session start to recall saved context.

## Guidelines
- Be concise and direct
- Use absolute paths for file operations
- Execute commands from the working directory
"""
        
        # Add session-specific context WITHOUT hardcoded paths
        # The agent should discover its environment by running commands
        session_context = f"""

## Session: {session_name}

**Environment Discovery:**
- Run `pwd` to see your current working directory
- Run `ls` to explore the directory structure
- Your session has its own isolated workspace
- A `memories/` folder is available for storing persistent notes

**Best Practices:**
- Use `pwd` to confirm your location before file operations
- Use relative paths from your workspace when possible
- Check `ls memories/` to recall saved context from previous interactions
"""
        
        return base_prompt + session_context

    def execute(self, command: str) -> ExecuteResponse:
        """Execute a command in the sandbox.

        All commands automatically run in the session workspace directory.
        This ensures 'pwd' returns the correct path and relative paths work
        relative to the workspace.

        Args:
            command: Full shell command string to execute.

        Returns:
            ExecuteResponse with output, exit code, and truncation flag.
        """
        try:
            # Automatically run all commands in session workspace
            # This is NOT an optional parameter - workspace is ALWAYS used
            if self._current_session:
                workspace = self.current_workspace
                # Wrap command: cd to workspace first, then run the actual command
                # This ensures pwd returns the workspace, not /home/gem
                wrapped_command = f"cd {workspace} && {command}"
            else:
                wrapped_command = command
            
            result = self.sync_client.shell.exec_command(
                command=wrapped_command,
                timeout=self._timeout,
            )
            
            # Extract output and exit code from response
            output = ""
            exit_code = 0
            
            if hasattr(result, 'data'):
                if hasattr(result.data, 'output'):
                    output = result.data.output
                if hasattr(result.data, 'exit_code'):
                    exit_code = result.data.exit_code
            elif hasattr(result, 'output'):
                output = result.output
                if hasattr(result, 'exit_code'):
                    exit_code = result.exit_code
            else:
                output = str(result)

            return ExecuteResponse(
                output=output,
                exit_code=exit_code,
                truncated=False,
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command: {str(e)}",
                exit_code=-1,
                truncated=False,
            )

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the Agent-Infra sandbox.

        Args:
            paths: List of file paths to download.

        Returns:
            List of FileDownloadResponse objects, one per input path.
        """
        responses = []
        
        # Get workspace path for resolving relative paths
        workspace = self.current_workspace if self._current_session else None
        
        for path in paths:
            try:
                # SECURITY: ALL file operations go through the session workspace
                # The agent CANNOT read outside the workspace
                if workspace:
                    if path.startswith(workspace):
                        # Already a valid workspace path
                        resolved_path = path
                    elif path.startswith('/'):
                        # Absolute path - strip leading / and resolve in workspace
                        # This prevents reading from /home/gem/.deepagents, /tmp, etc.
                        resolved_path = f"{workspace}/{path.lstrip('/')}"
                    else:
                        # Relative path - resolve in workspace
                        resolved_path = f"{workspace}/{path}"
                else:
                    resolved_path = path
                
                # Read file content using shell command in workspace context
                result = self.sync_client.shell.exec_command(
                    command=f"cat {resolved_path}",
                    timeout=self._timeout,
                    exec_dir=workspace,
                )
                
                # Extract output and exit code
                content = ""
                exit_code = 0
                
                if hasattr(result, 'data'):
                    if hasattr(result.data, 'output'):
                        content = result.data.output
                    if hasattr(result.data, 'exit_code'):
                        exit_code = result.data.exit_code
                elif hasattr(result, 'output'):
                    content = result.output
                    if hasattr(result, 'exit_code'):
                        exit_code = result.exit_code
                else:
                    content = str(result)
                
                # Check if file exists (cat returns non-zero if file not found)
                if exit_code != 0:
                    responses.append(FileDownloadResponse(
                        path=path,
                        content=b"",
                        error=f"File '{path}' not found",
                    ))
                else:
                    responses.append(FileDownloadResponse(
                        path=path,
                        content=content.encode() if isinstance(content, str) else content,
                        error=None,
                    ))
            except Exception as e:
                responses.append(FileDownloadResponse(
                    path=path,
                    content=b"",
                    error=str(e),
                ))
        
        return responses

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the Agent-Infra sandbox.

        Args:
            files: List of (path, content) tuples to upload.

        Returns:
            List of FileUploadResponse objects, one per input file.
        """
        responses = []
        
        # Get workspace path for resolving relative paths  
        workspace = self.current_workspace if self._current_session else None
        
        for path, content in files:
            try:
                # SECURITY: ALL file operations go through the session workspace
                # The agent CANNOT write outside the workspace
                if workspace:
                    if path.startswith(workspace):
                        # Already a valid workspace path
                        resolved_path = path
                    elif path.startswith('/'):
                        # Absolute path - strip leading / and resolve in workspace
                        # This prevents writing to /home/gem/.deepagents, /tmp, etc.
                        resolved_path = f"{workspace}/{path.lstrip('/')}"
                    else:
                        # Relative path - resolve in workspace
                        resolved_path = f"{workspace}/{path}"
                else:
                    resolved_path = path
                
                # Ensure parent directory exists
                parent_dir = os.path.dirname(resolved_path)
                if parent_dir:
                    self.sync_client.shell.exec_command(
                        command=f"mkdir -p {parent_dir}",
                        timeout=self._timeout,
                        exec_dir=workspace,
                    )
                
                # Write file content using heredoc for better handling
                content_str = content.decode() if isinstance(content, bytes) else content
                # Escape single quotes in content
                escaped_content = content_str.replace("'", "'\"'\"'")
                
                self.sync_client.shell.exec_command(
                    command=f"printf '%s' '{escaped_content}' > {resolved_path}",
                    timeout=self._timeout,
                    exec_dir=workspace,
                )
                
                responses.append(FileUploadResponse(
                    path=path,
                    error=None,
                ))
            except Exception as e:
                responses.append(FileUploadResponse(
                    path=path,
                    error=str(e),
                ))
        
        return responses

    def health_check(self) -> bool:
        """Check if the sandbox is healthy and responding.
        
        Returns:
            True if sandbox is healthy, False otherwise
        """
        try:
            self.sync_client.sandbox.get_context()
            return True
        except Exception:
            return False

    # =========================================================================
    # Shell Session Management API
    # =========================================================================
    # 
    # Shell sessions are PROCESS STATE (like tmux panes):
    # - They maintain running processes and their output
    # - You can run async commands, view output, send input
    # - Sessions are ephemeral (lost on container restart)
    # - Different from workspaces which are FILE ORGANIZATION
    #
    # For true package isolation between projects, use Python venv
    # or multiple sandbox containers.
    # =========================================================================

    def create_shell_session(
        self,
        session_id: str | None = None,
        working_dir: str | None = None,
    ) -> dict:
        """Create a new persistent shell session.
        
        Shell sessions maintain process state (running commands, environment).
        Use for interactive processes that need stdin/stdout interaction.
        
        Args:
            session_id: Optional ID (auto-generated if not provided)
            working_dir: Initial working directory (defaults to workspace)
            
        Returns:
            dict with session_id and status
        """
        try:
            exec_dir = working_dir or self.current_workspace
            result = self.sync_client.shell.create_session(
                id=session_id,
                exec_dir=exec_dir,
            )
            
            if hasattr(result, 'data') and result.data:
                return {
                    "success": True,
                    "session_id": getattr(result.data, 'session_id', session_id),
                    "status": getattr(result.data, 'status', 'created'),
                }
            elif hasattr(result, 'success') and result.success:
                return {"success": True, "session_id": session_id or "auto"}
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_in_session(
        self,
        command: str,
        session_id: str | None = None,
        async_mode: bool = False,
        timeout: float = 60.0,
    ) -> dict:
        """Execute command in a shell session (new or existing).
        
        Args:
            command: Shell command to run
            session_id: Use existing session, or auto-create new one
            async_mode: If True, return immediately (use view_session to see output)
            timeout: Max wait time for sync mode
            
        Returns:
            dict with output, exit_code, session_id, is_running
        """
        try:
            result = self.sync_client.shell.exec_command(
                command=command,
                id=session_id,
                exec_dir=self.current_workspace if not session_id else None,
                async_mode=async_mode,
                timeout=timeout,
            )
            
            if hasattr(result, 'data') and result.data:
                data = result.data
                return {
                    "success": True,
                    "output": getattr(data, 'output', ''),
                    "exit_code": getattr(data, 'exit_code', 0),
                    "session_id": getattr(data, 'session_id', session_id),
                    "is_running": getattr(data, 'status', '') == 'running',
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def view_session(self, session_id: str) -> dict:
        """View output of a running shell session.
        
        Use after executing with async_mode=True to see progress.
        
        Args:
            session_id: ID of the session to view
            
        Returns:
            dict with output and is_running status
        """
        try:
            result = self.sync_client.shell.view(id=session_id)
            
            if hasattr(result, 'data') and result.data:
                data = result.data
                return {
                    "success": True,
                    "output": getattr(data, 'output', ''),
                    "is_running": getattr(data, 'status', '') == 'running',
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_process(self, session_id: str, timeout: int = 60) -> dict:
        """Wait for a process in a session to complete.
        
        Args:
            session_id: ID of the session
            timeout: Max seconds to wait
            
        Returns:
            dict with output, exit_code, and completed status
        """
        try:
            result = self.sync_client.shell.wait_for_process(
                id=session_id,
                seconds=timeout,
            )
            
            if hasattr(result, 'data') and result.data:
                data = result.data
                return {
                    "success": True,
                    "output": getattr(data, 'output', ''),
                    "exit_code": getattr(data, 'exit_code', 0),
                    "completed": getattr(data, 'status', '') != 'running',
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_input(
        self,
        session_id: str,
        text: str,
        press_enter: bool = True,
    ) -> dict:
        """Send input to an interactive process (like a REPL or prompt).
        
        Args:
            session_id: ID of the session
            text: Input text to send
            press_enter: Whether to press Enter after input
            
        Returns:
            dict with success status
        """
        try:
            result = self.sync_client.shell.write_to_process(
                id=session_id,
                input=text,
                press_enter=press_enter,
            )
            
            if hasattr(result, 'success') and result.success:
                return {"success": True, "message": "Input sent"}
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def kill_process(self, session_id: str) -> dict:
        """Kill the running process in a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            dict with success status
        """
        try:
            result = self.sync_client.shell.kill_process(id=session_id)
            
            if hasattr(result, 'success'):
                return {"success": result.success, "message": getattr(result, 'message', 'Process killed')}
            return {"success": True, "message": "Kill command sent"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_shell_sessions(self) -> list[dict]:
        """List all active shell sessions.
        
        Returns:
            List of session info dicts with session_id and status
        """
        try:
            result = self.sync_client.shell.list_sessions()
            
            if hasattr(result, 'data') and result.data:
                sessions = getattr(result.data, 'sessions', [])
                return [
                    {
                        "session_id": getattr(s, 'id', getattr(s, 'session_id', '')),
                        "status": getattr(s, 'status', 'unknown'),
                    }
                    for s in sessions
                ]
            return []
        except Exception:
            return []

    def cleanup_sessions(self, session_id: str | None = None) -> dict:
        """Clean up shell session(s).
        
        Args:
            session_id: Specific session to clean up. If None, cleans ALL sessions.
            
        Returns:
            dict with success status
        """
        try:
            if session_id:
                result = self.sync_client.shell.cleanup_session(session_id)
            else:
                result = self.sync_client.shell.cleanup_all_sessions()
            
            if hasattr(result, 'success'):
                return {"success": result.success, "message": getattr(result, 'message', 'Cleaned up')}
            return {"success": True, "message": "Cleanup command sent"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Browser API Methods
    # =========================================================================

    def get_browser_info(self) -> dict:
        """Get information about the sandbox browser.
        
        Returns:
            Dictionary with browser info:
            - cdp_url: Chrome DevTools Protocol URL for Playwright/Puppeteer
            - vnc_url: VNC URL for visual browser access
            - viewport: {width, height} of the browser viewport
            - user_agent: Browser user agent string
        """
        try:
            result = self.sync_client.browser.get_info()
            if result.success and result.data:
                return {
                    "cdp_url": result.data.cdp_url,
                    "vnc_url": result.data.vnc_url,
                    "viewport": {
                        "width": result.data.viewport.width,
                        "height": result.data.viewport.height,
                    },
                    "user_agent": result.data.user_agent,
                }
            return {"error": "Failed to get browser info"}
        except Exception as e:
            return {"error": str(e)}

    def get_vnc_url(self) -> str:
        """Get the VNC URL for accessing the sandbox browser visually.
        
        This URL opens a browser-in-browser view showing the sandbox desktop.
        Useful for viewing web apps running inside the sandbox.
        
        Returns:
            Full VNC URL with autoconnect, e.g. 
            'http://localhost:8090/vnc/index.html?autoconnect=true'
        """
        return f"{self._base_url}/vnc/index.html?autoconnect=true"

    def take_screenshot(self) -> bytes | None:
        """Take a screenshot of the current sandbox display.
        
        This captures the sandbox screen, including any browsers or
        applications running inside it.
        
        Returns:
            PNG image bytes, or None if failed
        """
        try:
            result = self.sync_client.browser.screenshot()
            if result:
                # The result may be a generator/iterator, consume it
                if hasattr(result, '__iter__') and not isinstance(result, (bytes, str)):
                    return b''.join(chunk for chunk in result)
                return result
            return None
        except Exception:
            return None

    def execute_browser_action(self, action: dict) -> dict:
        """Execute a CUA-style browser action.
        
        Supports OpenAI/Anthropic computer-use patterns:
        - click: {"type": "click", "x": 100, "y": 200, "button": "left"}
        - double_click: {"type": "double_click", "x": 100, "y": 200}
        - type: {"type": "type", "text": "hello world"}
        - keypress: {"type": "keypress", "keys": ["Enter"]} or {"type": "keypress", "key": "Enter"}
        - scroll: {"type": "scroll", "x": 100, "y": 200, "scroll_x": 0, "scroll_y": -300}
        - move: {"type": "move", "x": 100, "y": 200}
        - drag: {"type": "drag", "x": 100, "y": 200}
        - wait: {"type": "wait", "duration": 2.0}
        
        Based on browser-use-cua example in agent_infra_examples.
        
        Args:
            action: Action dictionary with 'type' and action-specific parameters
            
        Returns:
            dict with success status and action description
        """
        from agent_sandbox.browser.types.action import (
            Action_Click,
            Action_DoubleClick,
            Action_DragTo,
            Action_MoveTo,
            Action_Press,
            Action_Scroll,
            Action_Typing,
            Action_Wait,
            Button,
        )
        
        action_type = action.get("type", "").lower()
        
        try:
            request = None
            action_desc = ""
            
            if action_type == "click":
                button_map = {"left": Button.LEFT, "right": Button.RIGHT, "middle": Button.MIDDLE}
                request = Action_Click(
                    action_type="CLICK",
                    x=float(action["x"]),
                    y=float(action["y"]),
                    button=button_map.get(action.get("button", "left"), Button.LEFT),
                    num_clicks=action.get("num_clicks", 1),
                )
                action_desc = f"Clicked at ({action['x']}, {action['y']})"
                
            elif action_type == "double_click":
                request = Action_DoubleClick(
                    action_type="DOUBLE_CLICK",
                    x=float(action["x"]),
                    y=float(action["y"]),
                )
                action_desc = f"Double-clicked at ({action['x']}, {action['y']})"
                
            elif action_type in ("type", "typing"):
                request = Action_Typing(
                    action_type="TYPING",
                    text=action["text"],
                    use_clipboard=action.get("use_clipboard", False),
                )
                action_desc = f"Typed: {action['text'][:50]}..."
                
            elif action_type in ("keypress", "press"):
                key = action.get("key") or (action.get("keys", [""])[0] if action.get("keys") else "")
                key_map = {
                    "enter": "Return",
                    "return": "Return",
                    "space": "space",
                    "tab": "Tab",
                    "escape": "Escape",
                    "backspace": "BackSpace",
                    "delete": "Delete",
                    "up": "Up",
                    "down": "Down",
                    "left": "Left",
                    "right": "Right",
                }
                mapped_key = key_map.get(key.lower(), key) if key else "Return"
                request = Action_Press(
                    action_type="PRESS",
                    key=mapped_key,
                )
                action_desc = f"Pressed key: {mapped_key}"
                
            elif action_type == "scroll":
                request = Action_Scroll(
                    action_type="SCROLL",
                    dx=int(action.get("scroll_x", 0)),
                    dy=int(action.get("scroll_y", 0)),
                )
                action_desc = f"Scrolled by ({action.get('scroll_x', 0)}, {action.get('scroll_y', 0)})"
                
            elif action_type == "move":
                request = Action_MoveTo(
                    action_type="MOVE_TO",
                    x=float(action["x"]),
                    y=float(action["y"]),
                )
                action_desc = f"Moved to ({action['x']}, {action['y']})"
                
            elif action_type == "drag":
                request = Action_DragTo(
                    action_type="DRAG_TO",
                    x=float(action["x"]),
                    y=float(action["y"]),
                )
                action_desc = f"Dragged to ({action['x']}, {action['y']})"
                
            elif action_type == "wait":
                request = Action_Wait(
                    action_type="WAIT",
                    duration=float(action.get("duration", 2.0)),
                )
                action_desc = f"Waited {action.get('duration', 2.0)}s"
                
            else:
                return {"success": False, "error": f"Unknown action type: {action_type}"}
            
            # Execute the action
            result = self.sync_client.browser.execute_action(request=request)
            
            if hasattr(result, 'success') and result.success:
                return {"success": True, "action": action_type, "description": action_desc}
            return {"success": True, "action": action_type, "description": action_desc}
            
        except KeyError as e:
            return {"success": False, "error": f"Missing required parameter: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_browser_cdp_url(self) -> str:
        """Get Chrome DevTools Protocol URL for Playwright/Puppeteer integration.
        
        Use this to connect external browser automation tools to the sandbox browser.
        
        Example:
            cdp_url = backend.get_browser_cdp_url()
            # Then use with Playwright:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            
        Returns:
            CDP URL string, or empty string if failed
        """
        try:
            result = self.sync_client.browser.get_info()
            if result.success and result.data:
                return result.data.cdp_url
            return ""
        except Exception:
            return ""

    # =========================================================================
    # Jupyter Execution API Methods
    # =========================================================================

    def execute_python(
        self, 
        code: str, 
        session_id: str | None = None,
        timeout: int = 30,
        kernel_name: str = "python3",
    ) -> dict:
        """Execute Python code using Jupyter kernel.
        
        This provides better Python execution than shell commands:
        - Session persistence (variables survive across calls)
        - Rich outputs (images, dataframes, etc.)
        - Better error handling
        
        Args:
            code: Python code to execute
            session_id: Optional session ID to maintain state across calls
            timeout: Execution timeout in seconds (max 300)
            kernel_name: Kernel to use (python3, python3.11, python3.12)
            
        Returns:
            Dictionary with:
            - success: bool
            - status: 'ok', 'error', or 'timeout'
            - session_id: ID for this session (use to maintain state)
            - outputs: List of execution outputs
            - error: Error message if failed
        """
        try:
            # Prepend os.chdir to ensure Python runs in session workspace
            if self._current_session:
                workspace = self.current_workspace
                code = f"import os; os.chdir({workspace!r})\n{code}"
            
            result = self.sync_client.jupyter.execute_code(
                code=code,
                session_id=session_id,
                timeout=timeout,
                kernel_name=kernel_name,
            )
            
            if result.success and result.data:
                outputs = []
                for output in result.data.outputs:
                    out = {"type": output.output_type}
                    if output.text:
                        out["text"] = output.text
                    if output.data:
                        out["data"] = output.data
                    if output.ename:
                        out["error_name"] = output.ename
                        out["error_value"] = output.evalue
                        out["traceback"] = output.traceback
                    outputs.append(out)
                
                return {
                    "success": True,
                    "status": result.data.status,
                    "session_id": result.data.session_id,
                    "outputs": outputs,
                    "execution_count": result.data.execution_count,
                }
            return {
                "success": False,
                "error": result.message or "Unknown error",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def create_jupyter_session(
        self,
        session_id: str | None = None,
        kernel_name: str = "python3",
    ) -> dict:
        """Create a new Jupyter session.
        
        Sessions allow maintaining Python state across multiple
        execute_python calls.
        
        Args:
            session_id: Optional ID (auto-generated if not provided)
            kernel_name: Kernel to use
            
        Returns:
            Dictionary with session_id and kernel_name
        """
        try:
            result = self.sync_client.jupyter.create_session(
                session_id=session_id,
                kernel_name=kernel_name,
            )
            if result.success and result.data:
                return {
                    "success": True,
                    "session_id": result.data.session_id,
                    "kernel_name": result.data.kernel_name,
                }
            return {"success": False, "error": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_jupyter_info(self) -> dict:
        """Get information about available Jupyter kernels.
        
        Returns:
            Dictionary with available kernels, active sessions, etc.
        """
        try:
            result = self.sync_client.jupyter.get_info()
            if result.success and result.data:
                return {
                    "success": True,
                    "default_kernel": result.data.default_kernel,
                    "available_kernels": result.data.available_kernels,
                    "active_sessions": result.data.active_sessions,
                }
            return {"success": False, "error": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Node.js Execution API Methods
    # =========================================================================

    def execute_javascript(
        self,
        code: str,
        timeout: int = 30,
    ) -> dict:
        """Execute JavaScript code using Node.js.
        
        Each request creates a fresh execution environment.
        
        Args:
            code: JavaScript code to execute
            timeout: Execution timeout in seconds (max 300)
            
        Returns:
            Dictionary with:
            - success: bool
            - status: 'ok', 'error', or 'timeout'
            - stdout: Standard output
            - stderr: Standard error
            - exit_code: Process exit code
        """
        try:
            result = self.sync_client.nodejs.execute_code(
                code=code,
                timeout=timeout,
            )
            
            if result.success and result.data:
                return {
                    "success": True,
                    "status": result.data.status,
                    "stdout": result.data.stdout,
                    "stderr": result.data.stderr,
                    "exit_code": result.data.exit_code,
                }
            return {
                "success": False,
                "error": result.message or "Unknown error",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_nodejs_info(self) -> dict:
        """Get Node.js runtime information.
        
        Returns:
            Dictionary with node_version, npm_version, etc.
        """
        try:
            result = self.sync_client.nodejs.get_info()
            if result.success and result.data:
                return {
                    "success": True,
                    "node_version": result.data.node_version,
                    "npm_version": result.data.npm_version,
                }
            return {"success": False, "error": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Unified Code Execution API
    # =========================================================================

    def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
    ) -> dict:
        """Execute code in specified language.
        
        Unified interface that dispatches to Python (Jupyter) or
        JavaScript (Node.js) executors.
        
        Args:
            code: Code to execute
            language: 'python' or 'javascript'
            timeout: Execution timeout in seconds
            
        Returns:
            Execution result dictionary
        """
        try:
            result = self.sync_client.code.execute_code(
                code=code,
                language=language,
                timeout=timeout,
            )
            
            if result.success and result.data:
                return {
                    "success": True,
                    "language": result.data.language,
                    "status": result.data.status,
                    "stdout": result.data.stdout,
                    "stderr": result.data.stderr,
                    "exit_code": result.data.exit_code,
                }
            return {
                "success": False,
                "error": result.message or "Unknown error",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # =========================================================================
    # MCP Integration API
    # =========================================================================
    #
    # The sandbox exposes ALL tools via MCP at {base_url}/mcp/
    # You can use langchain_mcp_adapters.MultiServerMCPClient to get all tools:
    #
    #     mcp_client = MultiServerMCPClient({
    #         "sandbox": {"url": f"{base_url}/mcp/", "transport": "streamable_http"}
    #     })
    #     tools = await mcp_client.get_tools()
    #
    # =========================================================================

    def list_mcp_servers(self) -> list[str]:
        """List available MCP servers in the sandbox.
        
        MCP servers provide additional tools like browser automation,
        file conversion, etc.
        
        Returns:
            List of MCP server names
        """
        try:
            result = self.sync_client.mcp.servers()
            if result.success and result.data:
                return result.data
            return []
        except Exception:
            return []

    def list_mcp_tools(self, server_name: str = "sandbox") -> list[dict]:
        """List tools available from an MCP server.
        
        Args:
            server_name: Name of the MCP server (default: "sandbox")
            
        Returns:
            List of tool definitions with name, description, and input_schema
        """
        try:
            result = self.sync_client.mcp.list_mcp_tools(server_name)
            if hasattr(result, 'data') and result.data:
                tools = getattr(result.data, 'tools', [])
                return [
                    {
                        "name": getattr(t, 'name', ''),
                        "description": getattr(t, 'description', ''),
                        "input_schema": getattr(t, 'input_schema', {}),
                    }
                    for t in tools
                ]
            # Fallback to curl if SDK method doesn't work
            shell_result = self.execute(f"curl -s {self._base_url}/v1/mcp/{server_name}/tools")
            if shell_result.exit_code == 0 and shell_result.output:
                import json
                data = json.loads(shell_result.output)
                if data.get("success") and data.get("data"):
                    return data["data"].get("tools", [])
            return []
        except Exception:
            return []

    def execute_mcp_tool(
        self,
        tool_name: str,
        arguments: dict,
        server_name: str = "sandbox",
    ) -> dict:
        """Execute an MCP tool directly.
        
        The sandbox exposes all its functionality via MCP tools.
        This method allows direct tool execution.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments as a dictionary
            server_name: MCP server name (default: "sandbox")
            
        Returns:
            dict with success status and tool result
        """
        try:
            result = self.sync_client.mcp.execute_mcp_tool(
                server_name=server_name,
                tool_name=tool_name,
                request=arguments,
            )
            if hasattr(result, 'data') and result.data:
                content = getattr(result.data, 'content', [])
                return {
                    "success": True,
                    "result": content,
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_mcp_tools(self):
        """Get all sandbox tools via MCP adapter (async).
        
        This is the recommended way to get sandbox tools for LangGraph agents.
        Uses langchain_mcp_adapters for proper tool format.
        
        Example:
            tools = await backend.get_mcp_tools()
            agent = create_deep_agent(tools=tools, ...)
            
        Returns:
            List of LangChain-compatible tools
        """
        from langchain_mcp_adapters.client import MultiServerMCPClient
        
        mcp_client = MultiServerMCPClient({
            "sandbox": {
                "url": f"{self._base_url}/mcp/",
                "transport": "streamable_http"
            },
        })
        return await mcp_client.get_tools()

    def get_mcp_endpoint(self) -> str:
        """Get the MCP endpoint URL for external tool adapters.
        
        Returns:
            MCP endpoint URL (e.g., 'http://localhost:8090/mcp/')
        """
        return f"{self._base_url}/mcp/"

    # =========================================================================
    # File Operations API (SDK-based, more robust than shell commands)
    # =========================================================================

    def read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> dict:
        """Read file content using SDK.
        
        More robust than shell `cat`:
        - Handles binary files (returns base64 for non-text)
        - Supports line range selection
        - Proper encoding handling
        
        Args:
            path: File path (relative to workspace or absolute)
            start_line: Optional starting line (1-indexed)
            end_line: Optional ending line (1-indexed)
            
        Returns:
            dict with content, lines, encoding, or error
        """
        resolved_path = self._resolve_workspace_path(path)
        try:
            result = self.sync_client.file.read_file(
                file=resolved_path,
                start_line=start_line,
                end_line=end_line,
            )
            if hasattr(result, 'data') and result.data:
                return {
                    "success": True,
                    "content": getattr(result.data, 'content', ''),
                    "lines": getattr(result.data, 'lines', 0),
                    "encoding": getattr(result.data, 'encoding', 'utf-8'),
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
    ) -> dict:
        """Write file content using SDK.
        
        More robust than shell `printf`:
        - Handles special characters safely
        - Supports binary via base64 encoding
        - Auto-creates parent directories
        
        Args:
            path: File path (relative to workspace or absolute)
            content: File content ("utf-8" text or "base64" encoded binary)
            encoding: Content encoding ("utf-8" or "base64")
            create_dirs: Whether to create parent directories
            
        Returns:
            dict with bytes_written and path
        """
        resolved_path = self._resolve_workspace_path(path)
        
        # Create parent directories if needed
        if create_dirs:
            parent = "/".join(resolved_path.rsplit("/", 1)[:-1])
            if parent:
                self.sync_client.shell.exec_command(f"mkdir -p {parent}")
        
        try:
            result = self.sync_client.file.write_file(
                file=resolved_path,
                content=content,
                encoding=encoding,
            )
            if hasattr(result, 'data') and result.data:
                return {
                    "success": True,
                    "bytes_written": getattr(result.data, 'bytes_written', len(content)),
                    "path": resolved_path,
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def edit_file(
        self,
        path: str,
        old_str: str,
        new_str: str,
    ) -> dict:
        """Replace text in a file (safer than full rewrite).
        
        Args:
            path: File path
            old_str: Text to find and replace
            new_str: Replacement text
            
        Returns:
            dict with success and replacement count
        """
        resolved_path = self._resolve_workspace_path(path)
        try:
            result = self.sync_client.file.replace_in_file(
                file=resolved_path,
                old_str=old_str,
                new_str=new_str,
            )
            if hasattr(result, 'data') and result.data:
                return {
                    "success": True,
                    "replacements": getattr(result.data, 'replacements', 0),
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_files(
        self,
        query: str,
        path: str | None = None,
        in_content: bool = False,
    ) -> dict:
        """Search for files or within file content.
        
        Consolidates find_files() and search_in_file().
        
        Args:
            query: Glob pattern (if in_content=False) or regex (if in_content=True)
            path: Directory or file to search (defaults to workspace)
            in_content: If True, search within file content; else search by name
            
        Returns:
            dict with files or matches
        """
        search_path = path or self.current_workspace
        resolved_path = self._resolve_workspace_path(search_path)
        
        try:
            if in_content:
                # Search within file content
                result = self.sync_client.file.search_in_file(
                    file=resolved_path,
                    regex=query,
                )
                if hasattr(result, 'data') and result.data:
                    matches = getattr(result.data, 'matches', [])
                    return {
                        "success": True,
                        "matches": [
                            {
                                "line": getattr(m, 'line_number', 0),
                                "content": getattr(m, 'line_content', ''),
                            }
                            for m in matches
                        ],
                    }
            else:
                # Search by file name
                result = self.sync_client.file.find_files(
                    path=resolved_path,
                    glob=query,
                )
                if hasattr(result, 'data') and result.data:
                    return {
                        "success": True,
                        "files": getattr(result.data, 'files', []),
                    }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_directory(
        self,
        path: str | None = None,
        recursive: bool = False,
        include_hidden: bool = False,
    ) -> dict:
        """List directory contents with file info.
        
        Args:
            path: Directory path (defaults to workspace)
            recursive: Whether to list recursively
            include_hidden: Whether to include hidden files
            
        Returns:
            dict with files list and total count
        """
        list_path = path or self.current_workspace
        resolved_path = self._resolve_workspace_path(list_path)
        
        try:
            result = self.sync_client.file.list_path(path=resolved_path)
            if hasattr(result, 'data') and result.data:
                files = getattr(result.data, 'files', [])
                file_list = []
                for f in files:
                    name = getattr(f, 'name', '')
                    if not include_hidden and name.startswith('.'):
                        continue
                    file_list.append({
                        "name": name,
                        "path": getattr(f, 'path', ''),
                        "is_directory": getattr(f, 'is_directory', False),
                        "size": getattr(f, 'size', 0),
                        "extension": getattr(f, 'extension', ''),
                    })
                return {
                    "success": True,
                    "files": file_list,
                    "total": len(file_list),
                }
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_to_host(
        self,
        sandbox_path: str,
        local_path: str,
    ) -> dict:
        """Download a file from sandbox to the host computer.
        
        This solves the "how do I get files to my computer" problem.
        
        Args:
            sandbox_path: Path in the sandbox
            local_path: Path on host computer to save to
            
        Returns:
            dict with bytes_downloaded and local_path
        """
        resolved_path = self._resolve_workspace_path(sandbox_path)
        
        try:
            # Use SDK's streaming download
            content = b""
            download_result = self.sync_client.file.download_file(path=resolved_path)
            if hasattr(download_result, '__iter__'):
                for chunk in download_result:
                    content += chunk
            else:
                content = download_result
            
            # Write to local filesystem
            import os as local_os
            local_os.makedirs(local_os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(content if isinstance(content, bytes) else content.encode())
            
            return {
                "success": True,
                "bytes_downloaded": len(content),
                "local_path": local_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Jupyter Session Management (Additional Methods)
    # =========================================================================

    def list_jupyter_sessions(self) -> list[dict]:
        """List all active Jupyter sessions."""
        try:
            result = self.sync_client.jupyter.list_sessions()
            if hasattr(result, 'data') and result.data:
                sessions = getattr(result.data, 'sessions', [])
                return [
                    {
                        "session_id": getattr(s, 'session_id', ''),
                        "kernel_name": getattr(s, 'kernel_name', ''),
                    }
                    for s in sessions
                ]
            return []
        except Exception:
            return []

    def delete_jupyter_session(self, session_id: str) -> dict:
        """Delete a specific Jupyter session."""
        try:
            result = self.sync_client.jupyter.delete_session(session_id)
            if hasattr(result, 'success'):
                return {"success": result.success, "message": getattr(result, 'message', 'Deleted')}
            return {"success": True, "message": "Delete command sent"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Skills API (Sandbox Storage - Separate from local file skills)
    # =========================================================================
    #
    # Note: This is the SANDBOX skills storage API, which is separate from
    # the local file-based skills system in deepagents_cli/skills/.
    # DeepAgents CLI uses local skills because it works with multiple sandboxes.
    # =========================================================================

    def register_sandbox_skill(
        self,
        name: str,
        content: str | bytes,
    ) -> dict:
        """Register a skill in the sandbox's skill storage."""
        try:
            import io
            file_obj = io.BytesIO(content.encode() if isinstance(content, str) else content)
            result = self.sync_client.skills.register_skills(
                file=file_obj,
                name=name,
            )
            if hasattr(result, 'data') and result.data:
                return {"success": True, "name": getattr(result.data, 'name', name)}
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_sandbox_skills(self) -> list[dict]:
        """List skills stored in the sandbox."""
        try:
            result = self.sync_client.skills.list_metadata()
            if hasattr(result, 'data') and result.data:
                skills = getattr(result.data, 'skills', [])
                return [
                    {
                        "name": getattr(s, 'name', ''),
                        "description": getattr(s, 'description', ''),
                    }
                    for s in skills
                ]
            return []
        except Exception:
            return []

    def get_sandbox_skill(self, name: str) -> dict:
        """Get content of a skill from sandbox storage."""
        try:
            result = self.sync_client.skills.get_content(name)
            if hasattr(result, 'data') and result.data:
                return {"success": True, "content": getattr(result.data, 'content', '')}
            return {"success": False, "error": getattr(result, 'message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Utility Methods  
    # =========================================================================

    def convert_to_markdown(self, uri: str) -> str:
        """Convert a URL or file to markdown.
        
        Uses the sandbox's markitdown utility to convert web pages
        or documents to markdown format.
        
        Args:
            uri: URL or file path to convert
            
        Returns:
            Markdown content
        """
        try:
            result = self.sync_client.util.convert_to_markdown(uri=uri)
            if result.success and result.data:
                return result.data
            return f"Error: {result.message}"
        except Exception as e:
            return f"Error: {e}"

    def get_terminal_url(self) -> str:
        """Get the WebSocket terminal URL.
        
        Returns:
            Terminal URL for WebSocket connection
        """
        try:
            result = self.sync_client.shell.get_terminal_url()
            if result.success and result.data:
                return result.data
            return f"{self._base_url}/terminal"
        except Exception:
            return f"{self._base_url}/terminal"

    def get_code_server_url(self, folder: str | None = None) -> str:
        """Get the VS Code Server URL for accessing the sandbox IDE.
        
        Args:
            folder: Optional folder to open (defaults to home dir)
            
        Returns:
            VS Code Server URL that can be opened in browser
        """
        path = folder or self._get_home_dir()
        return f"{self._base_url}/code-server/?folder={path}"

    # =========================================================================
    # Environment Isolation Helpers
    # =========================================================================
    #
    # Shell sessions = PROCESS isolation (ephemeral)
    # Workspaces = FILE isolation (persisted directories)
    # Virtual environments = PACKAGE isolation (persisted)
    #
    # For true package isolation between projects, use these venv helpers.
    # =========================================================================

    def create_venv(
        self,
        name: str = "venv",
        path: str | None = None,
    ) -> dict:
        """Create a Python virtual environment for isolated packages.
        
        Use this when you need different Python package versions
        between projects. Each venv has its own pip installations.
        
        Args:
            name: Name of the virtual environment folder
            path: Where to create it (defaults to workspace)
            
        Returns:
            dict with venv_path and activation instructions
        """
        base_path = path or self.current_workspace
        venv_path = f"{base_path}/{name}"
        
        result = self.execute(f"python3 -m venv {venv_path}")
        if result.exit_code != 0:
            return {"success": False, "error": result.output}
        
        return {
            "success": True,
            "venv_path": venv_path,
            "activate_command": f"source {venv_path}/bin/activate",
            "pip_path": f"{venv_path}/bin/pip",
            "python_path": f"{venv_path}/bin/python",
            "message": f"Virtual environment created. Use 'source {venv_path}/bin/activate' before pip install.",
        }

    def run_in_venv(
        self,
        command: str,
        venv_name: str = "venv",
        venv_path: str | None = None,
    ) -> dict:
        """Run a command within a virtual environment.
        
        Automatically activates the venv before running the command.
        
        Args:
            command: Command to run (e.g., "pip install numpy")
            venv_name: Name of the venv folder
            venv_path: Base path containing the venv (defaults to workspace)
            
        Returns:
            ExecuteResponse-like dict with output and exit_code
        """
        base_path = venv_path or self.current_workspace
        activate = f"source {base_path}/{venv_name}/bin/activate"
        
        result = self.execute(f"{activate} && {command}")
        return {
            "success": result.exit_code == 0,
            "output": result.output,
            "exit_code": result.exit_code,
        }

    def get_sandbox_info(self) -> dict:
        """Get comprehensive sandbox environment information.
        
        Returns:
            dict with all sandbox URLs and capabilities
        """
        home_dir = self._get_home_dir()
        return {
            "base_url": self._base_url,
            "home_dir": home_dir,
            "current_workspace": self.current_workspace,
            "urls": {
                "vnc": self.get_vnc_url(),
                "code_server": self.get_code_server_url(),
                "terminal": self.get_terminal_url(),
                "mcp_endpoint": self.get_mcp_endpoint(),
            },
            "preview_urls": {
                "info": "Access web apps running in sandbox via these patterns:",
                "frontend": f"{self._base_url}/absproxy/{{port}}/ (for React, Next.js, Vite)",
                "backend": f"{self._base_url}/proxy/{{port}}/ (for FastAPI, Express)",
                "note": "These only work when a service is actually running on that port!",
            },
        }
