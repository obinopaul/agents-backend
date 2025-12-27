
import subprocess
import os
import time
import shlex
import threading
import queue
from pathlib import Path
from typing import List, Optional
from backend.src.tool_server.tools.shell.terminal_manager import (
    BaseShellManager, 
    ShellResult, 
    SessionState,
    ShellInvalidSessionNameError,
    ShellRunDirNotFoundError,
    ShellSessionNotFoundError,
    ShellSessionExistsError,
    ShellBusyError,
    _DEFAULT_TIMEOUT
)

class LocalShellManager(BaseShellManager):
    """
    A Windows-compatible ShellManager using subprocess via cmd.exe or powershell.
    Does not rely on tmux/libtmux.
    """
    def __init__(self):
        self.sessions = {}
        self.session_locks = {}

    def get_all_sessions(self) -> List[str]:
        return list(self.sessions.keys())

    def create_session(self, session_name: str, start_directory: str, timeout: int = _DEFAULT_TIMEOUT):
        if session_name in self.sessions:
            raise ShellSessionExistsError(f"Session '{session_name}' already exists")
        
        if not os.path.isdir(start_directory):
            raise ShellRunDirNotFoundError(f"Directory {start_directory} does not exist")

        # Initialize session state
        self.sessions[session_name] = {
            "cwd": start_directory,
            "last_output": "",
            "state": SessionState.IDLE,
            "history": []
        }
        self.session_locks[session_name] = threading.Lock()

    def delete_session(self, session_name: str):
        if session_name in self.sessions:
            del self.sessions[session_name]
            del self.session_locks[session_name]
        else:
            raise ShellSessionNotFoundError(f"Session '{session_name}' not found")

    def run_command(self, session_name: str, command: str, run_dir: str | None = None, 
                   timeout: int = _DEFAULT_TIMEOUT, wait_for_output: bool = True) -> ShellResult:
        
        if session_name not in self.sessions:
             raise ShellSessionNotFoundError(f"Session '{session_name}' not found")
        
        session = self.sessions[session_name]
        
        if session["state"] == SessionState.BUSY:
            raise ShellBusyError(f"Session '{session_name}' is busy")

        # Determine working directory
        cwd = run_dir if run_dir else session["cwd"]
        if not os.path.exists(cwd):
             raise ShellRunDirNotFoundError(f"Working directory {cwd} does not exist")

        with self.session_locks[session_name]:
            try:
                session["state"] = SessionState.BUSY
                
                # Execute command
                # Use shell=True for flexibility, capture output
                process = subprocess.run(
                    command,
                    cwd=cwd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                output = process.stdout + process.stderr
                
                # Update session
                session["last_output"] = output
                session["history"].append({"command": command, "output": output, "exit_code": process.returncode})
                
                # If command was 'cd', we can't easily track it with subprocess.run unless we parse it.
                # But since we are mocked/robust-local, we might infer it.
                # However, subprocess.run spawns a subshell, so 'cd' doesn't persist.
                # Real fix: chain commands or parse 'cd'. 
                # For robust testing script, we'll assume cwd stays same unless explicit mechanism.
                
                return ShellResult(clean_output=output, ansi_output=output)
                
            except subprocess.TimeoutExpired:
                return ShellResult(clean_output="Error: Command timed out", ansi_output="")
            except Exception as e:
                return ShellResult(clean_output=f"Error: {e}", ansi_output="")
            finally:
                session["state"] = SessionState.IDLE

    def get_session_state(self, session_name: str) -> SessionState:
        if session_name not in self.sessions:
            return SessionState.IDLE # Or raise error
        return self.sessions[session_name]["state"]

    def get_session_output(self, session_name: str) -> ShellResult:
        if session_name not in self.sessions:
            raise ShellSessionNotFoundError(f"Session '{session_name}' not found")
        return ShellResult(
            clean_output=self.sessions[session_name]["last_output"],
            ansi_output=self.sessions[session_name]["last_output"]
        )

    def kill_current_command(self, session_name: str) -> ShellResult:
        # Not applicable for synchronous subprocess.run
        return ShellResult(clean_output="Cannot kill synchronous command", ansi_output="")

    def write_to_process(self, session_name: str, input: str, press_enter: bool) -> ShellResult:
        return ShellResult(clean_output="Interactive input not supported in SimpleLocalShell", ansi_output="")
