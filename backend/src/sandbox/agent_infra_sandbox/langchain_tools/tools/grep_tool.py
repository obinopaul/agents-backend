"""Grep tool for content searching with ripgrep in AIO Sandbox."""

import re
from typing import Optional, Literal

import structlog
from langchain_core.tools import tool, BaseTool

from backend.src.sandbox.agent_infra_sandbox.langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_grep_tool(client: SandboxClient) -> BaseTool:
    """Create the grep content search tool bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        The grep tool
    """
    
    @tool
    async def grep(
        pattern: str,
        path: Optional[str] = None,
        output_mode: Literal["files_with_matches", "content", "count"] = "content",
        glob: Optional[str] = None,
        file_type: Optional[str] = None,
        case_insensitive: bool = False,
        show_line_numbers: bool = True,
        context_before: Optional[int] = None,
        context_after: Optional[int] = None,
        context: Optional[int] = None,
        max_results: Optional[int] = 50,
    ) -> str:
        """Search file contents using ripgrep regex patterns.
        
        Use for: Content search in files across the sandbox.
        NOT for: Simple file reading (use file_read instead).
        
        Args:
            pattern: Regex pattern to search for
            path: Directory or file to search (default: home directory)
            output_mode: Output format:
                - 'files_with_matches': Only show file paths with matches
                - 'content': Show matching lines with context
                - 'count': Show match count per file
            glob: File filter pattern (e.g., '*.py', '*.txt')
            file_type: File type filter (e.g., 'py', 'js', 'md')
            case_insensitive: Ignore case when matching
            show_line_numbers: Include line numbers in output
            context_before: Lines to show before each match
            context_after: Lines to show after each match
            context: Lines of context before AND after (overrides context_before/after)
            max_results: Maximum number of results to return
            
        Returns:
            Search results or error message
        """
        try:
            # Validate regex pattern
            try:
                re.compile(pattern)
            except re.error as e:
                error_msg = f"Invalid regex pattern: {e}"
                logger.error(error_msg, pattern=pattern)
                return f"ERROR: {error_msg}"
            
            # Get home directory if path not specified
            if path is None:
                path = await client.get_home_dir()
            
            logger.info(
                "Grepping content",
                pattern=pattern,
                path=path,
                output_mode=output_mode,
                glob=glob,
            )
            
            # Build the ripgrep command
            rg_cmd = ["rg"]
            
            # Output mode
            if output_mode == "files_with_matches":
                rg_cmd.append("-l")  # Only print filenames
            elif output_mode == "count":
                rg_cmd.append("-c")  # Count matches per file
            
            # Options
            if case_insensitive:
                rg_cmd.append("-i")
            if show_line_numbers and output_mode == "content":
                rg_cmd.append("-n")
            if glob:
                rg_cmd.extend(["-g", glob])
            if file_type:
                rg_cmd.extend(["-t", file_type])
            
            # Context
            if context is not None:
                rg_cmd.extend(["-C", str(context)])
            else:
                if context_before is not None:
                    rg_cmd.extend(["-B", str(context_before)])
                if context_after is not None:
                    rg_cmd.extend(["-A", str(context_after)])
            
            # Max results
            if max_results:
                rg_cmd.extend(["-m", str(max_results)])
            
            # Pattern and path
            rg_cmd.extend(["--", pattern, path])
            
            # Execute the command
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in rg_cmd)
            result = await client.async_client.shell.exec_command(command=cmd_str)
            
            output = result.data.output or ""
            exit_code = result.data.exit_code
            
            # ripgrep returns 1 if no matches found (not an error)
            if exit_code == 1 and not output.strip():
                return f"No matches found for pattern '{pattern}' in '{path}'"
            
            if exit_code not in (0, 1):
                return f"ERROR: Search failed with exit code {exit_code}. Output:\n{output}"
            
            if not output.strip():
                return f"No matches found for pattern '{pattern}' in '{path}'"
            
            # Format output based on mode
            if output_mode == "files_with_matches":
                files = [f for f in output.strip().split("\n") if f]
                result_str = f"Found matches in {len(files)} file(s):\n"
                for f in files[:max_results] if max_results else files:
                    result_str += f"  {f}\n"
            elif output_mode == "count":
                result_str = f"Match counts for pattern '{pattern}':\n"
                for line in output.strip().split("\n"):
                    if ":" in line:
                        result_str += f"  {line}\n"
            else:  # content
                # Limit output length
                lines = output.strip().split("\n")
                if max_results and len(lines) > max_results * 2:
                    lines = lines[:max_results * 2]
                    result_str = f"Matches for pattern '{pattern}' (truncated):\n\n"
                else:
                    result_str = f"Matches for pattern '{pattern}':\n\n"
                result_str += "\n".join(lines)
            
            logger.info(
                "Grep completed successfully",
                pattern=pattern,
                path=path,
                output_mode=output_mode,
            )
            
            return result_str.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to grep content: {e!s}"
            logger.error(
                error_msg,
                pattern=pattern,
                path=path,
                error=str(e),
            )
            return f"ERROR: {error_msg}"
    
    return grep
