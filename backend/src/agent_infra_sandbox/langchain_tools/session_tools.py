"""Session-scoped LangChain tools with automatic workspace isolation.

These tools are automatically scoped to a SandboxSession's workspace,
ensuring all operations happen within the isolated workspace directory.
"""

from typing import List, Optional, Literal, Dict, Any
import base64
import re

import structlog
from langchain_core.tools import tool, BaseTool

logger = structlog.get_logger(__name__)


def create_session_tools(session: "SandboxSession") -> List[BaseTool]:
    """Create all tools scoped to the given session's workspace.
    
    All file paths are automatically resolved relative to the workspace.
    All shell commands execute in the workspace directory.
    All code execution uses the session's dedicated Jupyter/shell sessions.
    
    Args:
        session: The SandboxSession to bind tools to
        
    Returns:
        List of workspace-scoped LangChain tools
    """
    from langchain_tools.session import SandboxSession
    
    # =========================================================================
    # FILE TOOLS - All paths relative to workspace
    # =========================================================================
    
    @tool
    async def file_read(
        file: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Read content from a file in the workspace.
        
        Args:
            file: File path (relative to workspace, e.g., 'src/app.py')
            start_line: Optional start line number (0-based)
            end_line: Optional end line number (not inclusive)
            
        Returns:
            File content, or error message
        """
        try:
            abs_path = session.resolve_path(file)
            logger.info("Reading file", file=abs_path)
            
            result = await session.client.file.read_file(
                file=abs_path,
                start_line=start_line,
                end_line=end_line,
            )
            
            return result.data.content or f"ERROR: File '{file}' is empty or not found"
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Failed to read file", file=file, error=str(e))
            return f"ERROR: Failed to read file: {e}"
    
    @tool
    async def file_write(
        file: str,
        content: str,
        encoding: Literal["utf-8", "base64"] = "utf-8",
        append: bool = False,
    ) -> str:
        """Write content to a file in the workspace.
        
        Creates the file and any parent directories if they don't exist.
        
        Args:
            file: File path (relative to workspace, e.g., 'src/app.py')
            content: Content to write
            encoding: 'utf-8' for text, 'base64' for binary
            append: If True, append instead of overwrite
            
        Returns:
            Success message, or error
        """
        try:
            abs_path = session.resolve_path(file)
            logger.info("Writing file", file=abs_path)
            
            # Ensure parent directory exists
            import os.path
            parent_dir = os.path.dirname(abs_path)
            if parent_dir and parent_dir != session.workspace_path:
                await session.client.shell.exec_command(
                    command=f"mkdir -p {parent_dir}",
                    id=session.shell_session_id,
                )
            
            result = await session.client.file.write_file(
                file=abs_path,
                content=content,
                encoding=encoding,
                append=append,
            )
            
            return f"Successfully wrote {result.data.bytes_written} bytes to {file}"
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Failed to write file", file=file, error=str(e))
            return f"ERROR: Failed to write file: {e}"
    
    @tool
    async def file_edit(
        file: str,
        old_str: str,
        new_str: str,
    ) -> str:
        """Replace content in an existing file.
        
        Args:
            file: File path (relative to workspace)
            old_str: Exact string to find and replace
            new_str: Replacement string
            
        Returns:
            Success message, or error
        """
        try:
            abs_path = session.resolve_path(file)
            logger.info("Editing file", file=abs_path)
            
            result = await session.client.file.replace_in_file(
                file=abs_path,
                old_str=old_str,
                new_str=new_str,
            )
            
            if result.data.success:
                return f"Successfully edited {file}"
            return f"ERROR: {result.data.error or 'String not found'}"
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Failed to edit file", file=file, error=str(e))
            return f"ERROR: Failed to edit file: {e}"
    
    @tool
    async def file_list(
        path: str = ".",
        recursive: bool = False,
        show_hidden: bool = False,
    ) -> str:
        """List contents of a directory in the workspace.
        
        Args:
            path: Directory path (relative to workspace, default: workspace root)
            recursive: Whether to list recursively
            show_hidden: Whether to show hidden files
            
        Returns:
            Directory listing, or error
        """
        try:
            abs_path = session.resolve_path(path)
            logger.info("Listing path", path=abs_path)
            
            result = await session.client.file.list_path(
                path=abs_path,
                recursive=recursive,
                show_hidden=show_hidden,
            )
            
            if not result.data.files:
                return f"Directory '{path}' is empty"
            
            output = f"Contents of {path} ({result.data.total_count} items):\n"
            for f in result.data.files:
                type_ind = "/" if f.is_directory else ""
                size = f" ({f.size}B)" if f.size and not f.is_directory else ""
                output += f"  {f.name}{type_ind}{size}\n"
            
            return output.rstrip()
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Failed to list path", path=path, error=str(e))
            return f"ERROR: Failed to list directory: {e}"
    
    @tool
    async def file_find(
        glob: str,
        path: str = ".",
    ) -> str:
        """Find files matching a glob pattern in the workspace.
        
        Args:
            glob: Glob pattern (e.g., '*.py', '**/*.txt')
            path: Directory to search (relative to workspace)
            
        Returns:
            List of matching files, or error
        """
        try:
            abs_path = session.resolve_path(path)
            logger.info("Finding files", path=abs_path, glob=glob)
            
            result = await session.client.file.find_files(
                path=abs_path,
                glob=glob,
            )
            
            if not result.data.files:
                return f"No files matching '{glob}'"
            
            # Make paths relative to workspace for cleaner output
            files = []
            for f in result.data.files:
                rel_path = f.replace(session.workspace_path + "/", "")
                files.append(rel_path)
            
            output = f"Found {len(files)} file(s) matching '{glob}':\n"
            for f in files:
                output += f"  {f}\n"
            
            return output.rstrip()
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Failed to find files", glob=glob, error=str(e))
            return f"ERROR: Failed to find files: {e}"
    
    @tool
    async def file_search(
        file: str,
        regex: str,
    ) -> str:
        """Search for content in a file using regex.
        
        Args:
            file: File path (relative to workspace)
            regex: Regular expression pattern
            
        Returns:
            Matching lines with line numbers, or error
        """
        try:
            abs_path = session.resolve_path(file)
            logger.info("Searching in file", file=abs_path, regex=regex)
            
            result = await session.client.file.search_in_file(
                file=abs_path,
                regex=regex,
            )
            
            if not result.data.matches:
                return f"No matches for '{regex}' in {file}"
            
            output = f"Found {len(result.data.matches)} match(es):\n"
            for m in result.data.matches:
                output += f"  L{m.line_number}: {m.content}\n"
            
            return output.rstrip()
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Failed to search file", file=file, error=str(e))
            return f"ERROR: Failed to search file: {e}"
    
    # =========================================================================
    # SHELL TOOLS - All commands run in workspace directory
    # =========================================================================
    
    @tool
    async def shell_exec(
        command: str,
        timeout: Optional[float] = None,
        background: bool = False,
    ) -> str:
        """Execute a shell command in the workspace.
        
        Commands run in the workspace directory automatically.
        
        Args:
            command: Shell command to execute
            timeout: Maximum seconds to wait (default: no limit)
            background: If True, run in background and return immediately
            
        Returns:
            Command output, or error
        """
        try:
            logger.info("Executing command", command=command)
            
            result = await session.client.shell.exec_command(
                command=command,
                id=session.shell_session_id,
                exec_dir=session.workspace_path,
                timeout=timeout,
                async_mode=background,
            )
            
            data = result.data
            
            if background:
                return f"Command started in background (session: {session.shell_session_id})"
            
            status = "SUCCESS" if data.exit_code == 0 else f"FAILED (exit {data.exit_code})"
            output = data.output or "(no output)"
            
            return f"[{status}]\n{output}"
            
        except Exception as e:
            logger.error("Command failed", command=command, error=str(e))
            return f"ERROR: Command failed: {e}"
    
    @tool
    async def shell_view() -> str:
        """View the current output of the shell session.
        
        Returns:
            Current shell session output
        """
        try:
            result = await session.client.shell.view(id=session.shell_session_id)
            return result.data.output or "(no output)"
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def shell_write(
        input: str,
        press_enter: bool = True,
    ) -> str:
        """Write input to a running process in the shell.
        
        Args:
            input: Text to send to the process
            press_enter: Whether to press Enter after input
            
        Returns:
            Confirmation message
        """
        try:
            await session.client.shell.write_to_process(
                id=session.shell_session_id,
                input=input,
                press_enter=press_enter,
            )
            return "Input sent"
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def shell_wait(
        seconds: int = 30,
    ) -> str:
        """Wait for a background process to complete.
        
        Args:
            seconds: Maximum seconds to wait
            
        Returns:
            Process output and status
        """
        try:
            result = await session.client.shell.wait_for_process(
                id=session.shell_session_id,
                seconds=seconds,
            )
            
            data = result.data
            if data.status == "running":
                return f"Still running after {seconds}s. Output:\n{data.output or '(none)'}"
            
            status = "SUCCESS" if data.exit_code == 0 else f"FAILED (exit {data.exit_code})"
            return f"[{status}]\n{data.output or '(no output)'}"
            
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def shell_kill() -> str:
        """Kill any running process in the shell session.
        
        Returns:
            Confirmation message
        """
        try:
            await session.client.shell.kill_process(id=session.shell_session_id)
            return "Process terminated"
        except Exception as e:
            return f"ERROR: {e}"
    
    # =========================================================================
    # CODE EXECUTION TOOLS - Use dedicated sessions
    # =========================================================================
    
    @tool
    async def python_execute(
        code: str,
        timeout: int = 30,
    ) -> str:
        """Execute Python code in the workspace's Jupyter kernel.
        
        Variables persist across calls within this session.
        Working directory is automatically set to workspace.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            
        Returns:
            Execution output, or error
        """
        try:
            logger.info("Executing Python code")
            
            result = await session.client.jupyter.execute_code(
                code=code,
                timeout=timeout,
                session_id=session.jupyter_session_id,
            )
            
            data = result.data
            outputs = []
            
            for output in data.outputs or []:
                if hasattr(output, 'text') and output.text:
                    outputs.append(output.text)
                elif hasattr(output, 'data') and output.data:
                    if 'text/plain' in output.data:
                        outputs.append(output.data['text/plain'])
            
            if data.error:
                return f"ERROR: {data.error.get('ename')}: {data.error.get('evalue')}"
            
            return "\n".join(outputs) if outputs else "(no output)"
            
        except Exception as e:
            logger.error("Python execution failed", error=str(e))
            return f"ERROR: {e}"
    
    @tool
    async def javascript_execute(
        code: str,
        timeout: int = 30,
    ) -> str:
        """Execute JavaScript code using Node.js.
        
        Each execution creates a fresh environment.
        
        Args:
            code: JavaScript code to execute
            timeout: Execution timeout in seconds
            
        Returns:
            Execution output, or error
        """
        try:
            logger.info("Executing JavaScript code")
            
            # Run from workspace directory
            result = await session.client.shell.exec_command(
                command=f"cd {session.workspace_path} && node -e {repr(code)}",
                timeout=timeout,
            )
            
            data = result.data
            if data.exit_code != 0:
                return f"ERROR: {data.output}"
            
            return data.output or "(no output)"
            
        except Exception as e:
            logger.error("JavaScript execution failed", error=str(e))
            return f"ERROR: {e}"
    
    # =========================================================================
    # BROWSER TOOLS
    # =========================================================================
    
    @tool
    async def browser_info() -> str:
        """Get browser information including CDP URL for automation.
        
        Returns:
            Browser info with CDP URL and viewport size
        """
        try:
            result = await session.client.browser.get_info()
            data = result.data
            
            return (
                f"Browser Information:\n"
                f"  CDP URL: {data.cdp_url}\n"
                f"  Viewport: {data.viewport.width}x{data.viewport.height}"
            )
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def browser_screenshot() -> str:
        """Capture a screenshot of the browser.
        
        Returns:
            Base64-encoded PNG image
        """
        try:
            image_bytes = b""
            async for chunk in session.client.browser.screenshot():
                image_bytes += chunk
            
            b64 = base64.b64encode(image_bytes).decode('ascii')
            return f"[SCREENSHOT]\ndata:image/png;base64,{b64}"
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def browser_action(
        action_type: Literal[
            "click", "double_click", "right_click",
            "move_to", "scroll", "typing", "press",
            "hotkey", "wait"
        ],
        x: Optional[float] = None,
        y: Optional[float] = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
        keys: Optional[List[str]] = None,
        delta_x: Optional[float] = None,
        delta_y: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> str:
        """Execute a browser action.
        
        Args:
            action_type: Type of action
            x, y: Coordinates for click/move actions
            text: Text for 'typing' action
            key: Key for 'press' action
            keys: Keys for 'hotkey' action
            delta_x, delta_y: Scroll amounts
            duration: Wait duration
            
        Returns:
            Success confirmation, or error
        """
        try:
            from agent_sandbox.browser import (
                Action_Click, Action_DoubleClick, Action_RightClick,
                Action_MoveTo, Action_Scroll, Action_Typing,
                Action_Press, Action_Hotkey, Action_Wait,
            )
            
            action_map = {
                "click": lambda: Action_Click(x=x, y=y),
                "double_click": lambda: Action_DoubleClick(x=x, y=y),
                "right_click": lambda: Action_RightClick(x=x, y=y),
                "move_to": lambda: Action_MoveTo(x=x, y=y),
                "scroll": lambda: Action_Scroll(delta_x=delta_x or 0, delta_y=delta_y or 0),
                "typing": lambda: Action_Typing(text=text),
                "press": lambda: Action_Press(key=key),
                "hotkey": lambda: Action_Hotkey(keys=keys),
                "wait": lambda: Action_Wait(duration=duration or 1.0),
            }
            
            action = action_map[action_type]()
            await session.client.browser.execute_action(request=action)
            
            return f"Action '{action_type}' executed"
        except Exception as e:
            return f"ERROR: {e}"
    
    # =========================================================================
    # MCP TOOLS
    # =========================================================================
    
    @tool
    async def mcp_list_servers() -> str:
        """List available MCP servers.
        
        Returns:
            List of MCP server names
        """
        try:
            result = await session.client.mcp.list_mcp_servers()
            servers = result.data or []
            
            if not servers:
                return "No MCP servers configured"
            
            return f"MCP Servers ({len(servers)}):\n" + "\n".join(f"  - {s}" for s in servers)
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def mcp_list_tools(server_name: str) -> str:
        """List tools available on an MCP server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List of tools with descriptions
        """
        try:
            result = await session.client.mcp.list_mcp_tools(server_name)
            tools = result.data.tools or []
            
            if not tools:
                return f"No tools on server '{server_name}'"
            
            output = f"Tools on '{server_name}':\n"
            for t in tools:
                output += f"  📌 {t.name}: {t.description or '(no description)'}\n"
            
            return output.rstrip()
        except Exception as e:
            return f"ERROR: {e}"
    
    @tool
    async def mcp_execute(
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute an MCP tool.
        
        Args:
            server_name: MCP server name
            tool_name: Tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            result = await session.client.mcp.execute_mcp_tool(
                server_name=server_name,
                tool_name=tool_name,
                request=arguments or {},
            )
            
            outputs = []
            for content in result.data.content or []:
                if hasattr(content, 'text'):
                    outputs.append(content.text)
            
            return "\n".join(outputs) if outputs else "(no output)"
        except Exception as e:
            return f"ERROR: {e}"
    
    # =========================================================================
    # GREP/GLOB SEARCH TOOLS
    # =========================================================================
    
    @tool
    async def grep(
        pattern: str,
        path: str = ".",
        file_glob: Optional[str] = None,
        case_insensitive: bool = False,
        context: Optional[int] = None,
    ) -> str:
        """Search file contents using regex in the workspace.
        
        Use for: Content search within files.
        NOT for: Finding files by name (use glob instead).
        
        Args:
            pattern: Regex pattern to search for
            path: Directory to search (relative to workspace)
            file_glob: File filter (e.g., '*.py')
            case_insensitive: Ignore case
            context: Lines of context around matches
            
        Returns:
            Search results, or error
        """
        try:
            # Validate regex
            try:
                re.compile(pattern)
            except re.error as e:
                return f"ERROR: Invalid regex: {e}"
            
            abs_path = session.resolve_path(path)
            
            logger.info("Grepping files", pattern=pattern, path=abs_path)
            
            # Build ripgrep command
            cmd = ["rg", "-n"]
            if case_insensitive:
                cmd.append("-i")
            if file_glob:
                cmd.extend(["-g", file_glob])
            if context:
                cmd.extend(["-C", str(context)])
            cmd.extend(["-m", "50", "--", pattern, abs_path])
            
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
            result = await session.client.shell.exec_command(command=cmd_str)
            
            output = result.data.output or ""
            if not output.strip():
                logger.info("No grep matches", pattern=pattern, path=path)
                return f"No matches for '{pattern}'"
            
            # Make paths relative
            output = output.replace(session.workspace_path + "/", "")
            
            logger.info("Grep completed", pattern=pattern, matches_found=True)
            return f"Matches for '{pattern}':\n{output}"
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Grep failed", pattern=pattern, path=path, error=str(e))
            return f"ERROR: {e}"
    
    @tool
    async def glob(
        pattern: str,
        path: str = ".",
    ) -> str:
        """Find files matching a glob pattern in the workspace.
        
        Use for: Finding files by name pattern.
        NOT for: Content search (use grep instead).
        
        Args:
            pattern: Glob pattern (e.g., "**/*.py", "*.{js,ts}", "src/**/*.txt")
            path: Search directory (relative to workspace, default: workspace root)
            
        Returns:
            Matching file paths, or error
        """
        try:
            abs_path = session.resolve_path(path)
            
            logger.info("Globbing files", pattern=pattern, path=abs_path)
            
            result = await session.client.file.find_files(
                path=abs_path,
                glob=pattern,
            )
            
            if not result.data.files:
                logger.info("No glob matches", pattern=pattern, path=path)
                return f"No files matching pattern '{pattern}' found in '{path}'"
            
            # Make paths relative to workspace for cleaner output
            matches = []
            for f in result.data.files:
                rel_path = f.replace(session.workspace_path + "/", "")
                matches.append(rel_path)
            
            output = f"Found {len(matches)} file(s) matching '{pattern}':\n"
            for match in matches:
                output += f"  {match}\n"
            
            logger.info("Glob completed", pattern=pattern, path=path, matches=len(matches))
            return output.rstrip()
            
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:
            logger.error("Glob failed", pattern=pattern, path=path, error=str(e))
            return f"ERROR: Failed to glob files: {e}"
    
    # =========================================================================
    # SESSION INFO TOOLS
    # =========================================================================
    
    @tool
    async def workspace_info() -> str:
        """Get information about this workspace session.
        
        Returns:
            Session and workspace details
        """
        info = session.get_info()
        return (
            f"Workspace Session:\n"
            f"  Session ID: {info['session_id']}\n"
            f"  Workspace: {info['workspace_path']}\n"
            f"  Created: {info['created_at']}\n"
            f"  Shell Session: {info['shell_session_id']}\n"
            f"  Jupyter Session: {info['jupyter_session_id']}"
        )
    
    @tool
    async def workspace_health() -> str:
        """Check if the sandbox is healthy.
        
        Returns:
            Health status
        """
        healthy = await session.health_check()
        return "✅ Sandbox healthy" if healthy else "❌ Sandbox not responding"
    
    # Collect all tools
    return [
        # File tools
        file_read,
        file_write,
        file_edit,
        file_list,
        file_find,
        file_search,
        # Shell tools
        shell_exec,
        shell_view,
        shell_write,
        shell_wait,
        shell_kill,
        # Code tools
        python_execute,
        javascript_execute,
        # Browser tools
        browser_info,
        browser_screenshot,
        browser_action,
        # MCP tools
        mcp_list_servers,
        mcp_list_tools,
        mcp_execute,
        # Search tools
        grep,
        glob,
        # Session info
        workspace_info,
        workspace_health,
    ]
