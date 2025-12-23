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
        
        # Add session-specific context
        session_context = f"""

## Current Session: {session_name}

**Workspace Directory Structure:**
```
{workspace_path}/
├── .deepagents/agent/agent.md  # Your configuration (this file)
├── memories/                    # Persistent notes for this session
└── [your project files]         # Your code and project files
```

**IMPORTANT**: 
- Your workspace is at: `{workspace_path}`
- Agent config is at: `{workspace_path}/.deepagents/agent/agent.md`
- Store memories in: `{workspace_path}/memories/`
- All file operations should use paths within this workspace
- Do NOT look for agent.md or memories outside this workspace
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
                # Resolve relative paths against session workspace
                if workspace and not path.startswith('/'):
                    resolved_path = f"{workspace}/{path}"
                else:
                    resolved_path = path
                
                # Read file content using shell command in workspace context
                result = self.sync_client.shell.exec_command(
                    command=f"cat {resolved_path}",
                    timeout=self._timeout,
                    exec_dir=workspace,  # Ensure we're in workspace context
                )
                
                content = ""
                if hasattr(result, 'data') and hasattr(result.data, 'output'):
                    content = result.data.output
                elif hasattr(result, 'output'):
                    content = result.output
                else:
                    content = str(result)
                
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
                # Resolve relative paths against session workspace
                if workspace and not path.startswith('/'):
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

    def list_mcp_tools(self, server_name: str) -> list[dict]:
        """List tools available from an MCP server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List of tool definitions
        """
        try:
            # Access endpoint via shell since SDK may not have this
            result = self.execute(f"curl -s {self._base_url}/v1/mcp/{server_name}/tools")
            if result.exit_code == 0 and result.output:
                import json
                data = json.loads(result.output)
                if data.get("success") and data.get("data"):
                    return data["data"].get("tools", [])
            return []
        except Exception:
            return []

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
