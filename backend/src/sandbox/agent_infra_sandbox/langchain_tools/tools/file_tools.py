"""File system operation tools for AIO Sandbox."""

import base64
from typing import List, Optional, Literal, Any

import structlog
from langchain_core.tools import tool, BaseTool

from backend.src.sandbox.agent_infra_sandbox.langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_file_tools(client: SandboxClient) -> List[BaseTool]:
    """Create all file system tools bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        List of file operation tools
    """
    
    @tool
    async def file_read(
        file: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        sudo: bool = False,
    ) -> str:
        """Read content from a file in the sandbox.
        
        Use this to read file contents. Supports reading specific line ranges.
        
        Args:
            file: Absolute file path in the sandbox (e.g., /home/gem/file.txt)
            start_line: Optional start line number (0-based)
            end_line: Optional end line number (not inclusive)
            sudo: Whether to use sudo privileges
            
        Returns:
            File content with line numbers, or error message
        """
        try:
            logger.info("Reading file", file=file, start_line=start_line, end_line=end_line)
            
            result = await client.async_client.file.read_file(
                file=file,
                start_line=start_line,
                end_line=end_line,
                sudo=sudo,
            )
            
            if result.data.content is None:
                return f"ERROR: File '{file}' not found or empty"
                
            return result.data.content
            
        except Exception as e:
            error_msg = f"Failed to read file: {e!s}"
            logger.error(error_msg, file=file, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def file_write(
        file: str,
        content: str,
        encoding: Literal["utf-8", "base64"] = "utf-8",
        append: bool = False,
        sudo: bool = False,
    ) -> str:
        """Write content to a file in the sandbox.
        
        Creates the file if it doesn't exist. For binary files, set encoding to 'base64'.
        
        Args:
            file: Absolute file path in the sandbox
            content: Content to write (text or base64 encoded for binary)
            encoding: 'utf-8' for text files, 'base64' for binary files
            append: If True, append to file instead of overwriting
            sudo: Whether to use sudo privileges
            
        Returns:
            Success message with bytes written, or error message
        """
        try:
            logger.info("Writing file", file=file, encoding=encoding, append=append)
            
            result = await client.async_client.file.write_file(
                file=file,
                content=content,
                encoding=encoding,
                append=append,
                sudo=sudo,
            )
            
            return f"Successfully wrote {result.data.bytes_written} bytes to {file}"
            
        except Exception as e:
            error_msg = f"Failed to write file: {e!s}"
            logger.error(error_msg, file=file, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def file_edit(
        file: str,
        old_str: str,
        new_str: str,
        replace_all: bool = False,
        sudo: bool = False,
    ) -> str:
        """Replace content in an existing file.
        
        Finds and replaces occurrences of old_str with new_str in the file.
        
        Args:
            file: Absolute file path in the sandbox
            old_str: The exact string to find and replace
            new_str: The string to replace with
            replace_all: If True, replace all occurrences; otherwise just the first
            sudo: Whether to use sudo privileges
            
        Returns:
            Success message with replacement count, or error message
        """
        try:
            logger.info("Editing file", file=file, replace_all=replace_all)
            
            result = await client.async_client.file.replace_in_file(
                file=file,
                old_str=old_str,
                new_str=new_str,
                sudo=sudo,
            )
            
            if result.data.success:
                return f"Successfully replaced content in {file} ({result.data.replaced_count} replacement(s))"
            else:
                return f"ERROR: {result.data.error or 'String not found in file'}"
                
        except Exception as e:
            error_msg = f"Failed to edit file: {e!s}"
            logger.error(error_msg, file=file, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def file_list(
        path: str,
        recursive: bool = False,
        show_hidden: bool = False,
        max_depth: Optional[int] = None,
        sort_by: Optional[Literal["name", "size", "modified", "type"]] = "name",
    ) -> str:
        """List contents of a directory in the sandbox.
        
        Args:
            path: Absolute directory path to list
            recursive: Whether to list recursively  
            show_hidden: Whether to show hidden files (starting with .)
            max_depth: Maximum depth for recursive listing
            sort_by: Sort results by: name, size, modified, or type
            
        Returns:
            Formatted directory listing, or error message
        """
        try:
            logger.info("Listing path", path=path, recursive=recursive)
            
            result = await client.async_client.file.list_path(
                path=path,
                recursive=recursive,
                show_hidden=show_hidden,
                max_depth=max_depth,
                sort_by=sort_by,
            )
            
            if not result.data.files:
                return f"Directory '{path}' is empty or does not exist"
            
            output = f"Contents of {path} ({result.data.total_count} items):\n"
            for f in result.data.files:
                type_indicator = "/" if f.is_directory else ""
                size_str = f" ({f.size} bytes)" if f.size and not f.is_directory else ""
                output += f"  {f.name}{type_indicator}{size_str}\n"
                
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to list path: {e!s}"
            logger.error(error_msg, path=path, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def file_find(
        path: str,
        glob: str,
    ) -> str:
        """Find files matching a glob pattern.
        
        Args:
            path: Directory path to search in
            glob: Glob pattern to match (e.g., '*.py', '**/*.txt')
            
        Returns:
            List of matching file paths, or error message
        """
        try:
            logger.info("Finding files", path=path, glob=glob)
            
            result = await client.async_client.file.find_files(
                path=path,
                glob=glob,
            )
            
            if not result.data.files:
                return f"No files matching '{glob}' found in {path}"
            
            output = f"Found {len(result.data.files)} file(s) matching '{glob}':\n"
            for f in result.data.files:
                output += f"  {f}\n"
                
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to find files: {e!s}"
            logger.error(error_msg, path=path, glob=glob, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def file_search(
        file: str,
        regex: str,
        sudo: bool = False,
    ) -> str:
        """Search for content in a file using regex.
        
        Args:
            file: Absolute file path to search in
            regex: Regular expression pattern to search for
            sudo: Whether to use sudo privileges
            
        Returns:
            Matching lines with line numbers, or error message
        """
        try:
            logger.info("Searching in file", file=file, regex=regex)
            
            result = await client.async_client.file.search_in_file(
                file=file,
                regex=regex,
                sudo=sudo,
            )
            
            if not result.data.matches:
                return f"No matches for pattern '{regex}' in {file}"
            
            output = f"Found {len(result.data.matches)} match(es) in {file}:\n"
            for match in result.data.matches:
                output += f"  Line {match.line_number}: {match.content}\n"
                
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to search file: {e!s}"
            logger.error(error_msg, file=file, regex=regex, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def file_download(
        path: str,
    ) -> str:
        """Download a file from the sandbox.
        
        Returns the file content as base64-encoded string for binary files
        or as text for text files.
        
        Args:
            path: Absolute file path to download
            
        Returns:
            File content (base64 for binary, text otherwise), or error
        """
        try:
            logger.info("Downloading file", path=path)
            
            # Collect all bytes from the streaming response
            content_bytes = b""
            async for chunk in client.async_client.file.download_file(path=path):
                content_bytes += chunk
            
            # Try to decode as text, fall back to base64
            try:
                return content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return f"[BASE64]{base64.b64encode(content_bytes).decode('ascii')}"
                
        except Exception as e:
            error_msg = f"Failed to download file: {e!s}"
            logger.error(error_msg, path=path, error=str(e))
            return f"ERROR: {error_msg}"
    
    return [
        file_read,
        file_write,
        file_edit,
        file_list,
        file_find,
        file_search,
        file_download,
    ]
