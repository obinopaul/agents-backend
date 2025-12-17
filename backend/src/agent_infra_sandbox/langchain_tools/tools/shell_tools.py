"""Shell/terminal operation tools for AIO Sandbox."""

from typing import List, Optional

import structlog
from langchain_core.tools import tool, BaseTool

from langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_shell_tools(client: SandboxClient) -> List[BaseTool]:
    """Create all shell/terminal tools bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        List of shell operation tools
    """
    
    @tool
    async def shell_exec(
        command: str,
        exec_dir: Optional[str] = None,
        timeout: Optional[float] = None,
        session_id: Optional[str] = None,
        async_mode: bool = False,
    ) -> str:
        """Execute a shell command in the sandbox.
        
        Use this to run any terminal command. For long-running commands,
        use async_mode=True and then shell_wait to get the result.
        
        Args:
            command: Shell command to execute (e.g., 'ls -la', 'python script.py')
            exec_dir: Working directory for the command (absolute path)
            timeout: Maximum time in seconds to wait for completion
            session_id: Optional session ID to reuse a shell session
            async_mode: If True, return immediately without waiting for completion
            
        Returns:
            Command output and exit code, or error message
        """
        try:
            logger.info("Executing shell command", command=command, exec_dir=exec_dir)
            
            result = await client.async_client.shell.exec_command(
                command=command,
                exec_dir=exec_dir,
                timeout=timeout,
                id=session_id,
                async_mode=async_mode,
            )
            
            data = result.data
            output = data.output or ""
            
            if async_mode:
                return f"Command started in session '{data.id}'. Use shell_wait to get results."
            
            status = "SUCCESS" if data.exit_code == 0 else f"FAILED (exit code: {data.exit_code})"
            return f"[{status}]\n{output}"
            
        except Exception as e:
            error_msg = f"Failed to execute command: {e!s}"
            logger.error(error_msg, command=command, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def shell_view(
        session_id: str,
    ) -> str:
        """View the output of a shell session.
        
        Use this to check the current output of a running or completed command.
        
        Args:
            session_id: The session ID returned from shell_exec
            
        Returns:
            Session output, or error message
        """
        try:
            logger.info("Viewing shell session", session_id=session_id)
            
            result = await client.async_client.shell.view(id=session_id)
            
            return result.data.output or "(no output yet)"
            
        except Exception as e:
            error_msg = f"Failed to view session: {e!s}"
            logger.error(error_msg, session_id=session_id, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def shell_write(
        session_id: str,
        input: str,
        press_enter: bool = True,
    ) -> str:
        """Write input to a running process in a shell session.
        
        Use this to interact with processes that require input (like prompts).
        
        Args:
            session_id: The session ID of the running process
            input: The text to send to the process
            press_enter: Whether to press Enter after the input
            
        Returns:
            Confirmation message, or error
        """
        try:
            logger.info("Writing to shell session", session_id=session_id)
            
            await client.async_client.shell.write_to_process(
                id=session_id,
                input=input,
                press_enter=press_enter,
            )
            
            return f"Sent input to session '{session_id}'"
            
        except Exception as e:
            error_msg = f"Failed to write to session: {e!s}"
            logger.error(error_msg, session_id=session_id, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def shell_wait(
        session_id: str,
        seconds: Optional[int] = 30,
    ) -> str:
        """Wait for a process in a shell session to complete.
        
        Use this after starting a command with async_mode=True.
        
        Args:
            session_id: The session ID to wait for
            seconds: Maximum seconds to wait (default: 30)
            
        Returns:
            Final output and exit status, or timeout message
        """
        try:
            logger.info("Waiting for shell session", session_id=session_id, seconds=seconds)
            
            result = await client.async_client.shell.wait_for_process(
                id=session_id,
                seconds=seconds,
            )
            
            data = result.data
            if data.status == "running":
                return f"Process still running after {seconds}s. Current output:\n{data.output or '(no output)'}"
            
            status = "SUCCESS" if data.exit_code == 0 else f"FAILED (exit code: {data.exit_code})"
            return f"[{status}]\n{data.output or '(no output)'}"
            
        except Exception as e:
            error_msg = f"Failed to wait for session: {e!s}"
            logger.error(error_msg, session_id=session_id, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def shell_kill(
        session_id: str,
    ) -> str:
        """Kill a running process in a shell session.
        
        Use this to terminate a long-running or stuck process.
        
        Args:
            session_id: The session ID of the process to kill
            
        Returns:
            Confirmation message, or error
        """
        try:
            logger.info("Killing shell process", session_id=session_id)
            
            await client.async_client.shell.kill_process(id=session_id)
            
            return f"Process in session '{session_id}' terminated"
            
        except Exception as e:
            error_msg = f"Failed to kill process: {e!s}"
            logger.error(error_msg, session_id=session_id, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def shell_sessions() -> str:
        """List all active shell sessions.
        
        Returns:
            List of active session IDs and their status
        """
        try:
            logger.info("Listing shell sessions")
            
            result = await client.async_client.shell.list_sessions()
            
            sessions = result.data.sessions
            if not sessions:
                return "No active shell sessions"
            
            output = f"Active shell sessions ({len(sessions)}):\n"
            for s in sessions:
                output += f"  - {s.id}: {s.status}\n"
                
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to list sessions: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    return [
        shell_exec,
        shell_view,
        shell_write,
        shell_wait,
        shell_kill,
        shell_sessions,
    ]
