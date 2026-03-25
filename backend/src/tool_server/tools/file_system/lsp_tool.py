"""Language Server Protocol (LSP) tool for code intelligence features.

This tool provides semantic code understanding capabilities through LSP,
including go-to-definition, find references, hover information, and document
symbols.
"""

import asyncio
import json
import logging
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from backend.src.tool_server.core.workspace import WorkspaceManager, FileSystemValidationError
from backend.src.tool_server.tools.base import BaseTool, ToolResult


# Configure logging
logger = logging.getLogger(__name__)


# Constants
COMMAND_TIMEOUT = 60  # LSP operations can be slow for large codebases
MAX_RESULTS = 100

# Name
NAME = "Lsp"
DISPLAY_NAME = "Language Server Protocol"

# Supported LSP operations (only those available in multilspy)
LSP_OPERATIONS = [
    "goToDefinition",
    "findReferences", 
    "hover",
    "documentSymbol",
    "workspaceSymbol",
]

# Tool description
DESCRIPTION = """Interact with Language Server Protocol (LSP) servers to get code intelligence features.

This tool provides semantic understanding of code - it knows what symbols mean, where they're defined, 
and how they're used. This is more powerful than text search (Grep) or pattern matching (ASTGrep) 
because it understands the actual meaning of code.

Supported operations:
- goToDefinition: Find where a symbol (function, class, variable) is defined
- findReferences: Find all references to a symbol across the codebase
- hover: Get hover information (documentation, type info) for a symbol
- documentSymbol: Get all symbols (functions, classes, variables) in a document
- workspaceSymbol: Search for symbols across the entire workspace

All operations require:
- filePath: The file to operate on (absolute or relative to workspace)
- line: The line number (1-based, as shown in editors)
- character: The character offset (1-based, as shown in editors)

Supported languages: Python, Java, JavaScript, TypeScript, Rust, C#, Go, Dart, Ruby

IMPORTANT: This tool requires a Linux environment (sandbox). It will not work on Windows
due to asyncio subprocess transport limitations.

Note: LSP servers are automatically managed. The first operation on a new language may take a few 
seconds while the language server starts up.

Use cases:
- "Where is this function defined?" -> goToDefinition
- "What code uses this variable?" -> findReferences  
- "What does this function return?" -> hover
- "What functions are in this file?" -> documentSymbol
- "Find all classes named User" -> workspaceSymbol
"""

# Input schema
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": LSP_OPERATIONS,
            "description": "The LSP operation to perform"
        },
        "filePath": {
            "type": "string",
            "description": "The absolute or relative path to the file"
        },
        "line": {
            "type": "integer",
            "minimum": 1,
            "description": "The line number (1-based, as shown in editors)"
        },
        "character": {
            "type": "integer",
            "minimum": 1,
            "description": "The character offset (1-based, as shown in editors)"
        },
        "query": {
            "type": "string",
            "description": "Optional query string for workspaceSymbol operation. If omitted, returns all symbols."
        },
        "timeout": {
            "type": "integer",
            "minimum": 5,
            "maximum": 300,
            "default": 60,
            "description": "Operation timeout in seconds (default: 60)"
        },
        "forceRestart": {
            "type": "boolean",
            "default": False,
            "description": "Force restart the language server before this operation"
        }
    },
    "required": ["operation", "filePath", "line", "character"]
}

# Language to file extension mapping
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    '.py': 'python',
    '.pyw': 'python',
    '.pyi': 'python',
    '.java': 'java',
    '.js': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mts': 'typescript',
    '.cts': 'typescript',
    '.rs': 'rust',
    '.cs': 'csharp',
    '.go': 'go',
    '.dart': 'dart',
    '.rb': 'ruby',
    '.erb': 'ruby',
}


class LspToolError(Exception):
    """Custom exception for LSP tool errors."""
    pass


def _detect_language(file_path: Path) -> Optional[str]:
    """Detect programming language from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language string (e.g., 'python', 'java') or None if unsupported
    """
    extension = file_path.suffix.lower()
    return LANGUAGE_EXTENSIONS.get(extension)


def _format_location(location: Dict[str, Any], workspace_root: Path) -> Dict[str, Any]:
    """Format an LSP location result for display.
    
    Args:
        location: LSP location dictionary
        workspace_root: The workspace root path
        
    Returns:
        Formatted location dictionary
    """
    result = {}
    
    # Handle URI
    if 'uri' in location:
        uri = location['uri']
        if uri.startswith('file://'):
            # Convert file URI to path
            file_path = uri[7:]  # Remove 'file://'
            if file_path.startswith('/') and len(file_path) > 2 and file_path[2] == ':':
                # Windows path like /C:/...
                file_path = file_path[1:]
            try:
                rel_path = Path(file_path).relative_to(workspace_root)
                result['file'] = str(rel_path)
            except ValueError:
                result['file'] = file_path
        else:
            result['file'] = uri
    
    # Handle range
    if 'range' in location:
        range_info = location['range']
        start = range_info.get('start', {})
        end = range_info.get('end', {})
        result['range'] = {
            'start': {
                'line': start.get('line', 0) + 1,  # Convert to 1-based
                'character': start.get('character', 0) + 1
            },
            'end': {
                'line': end.get('line', 0) + 1,
                'character': end.get('character', 0) + 1
            }
        }
    
    return result


def _format_symbol(symbol: Dict[str, Any], workspace_root: Path) -> Dict[str, Any]:
    """Format an LSP symbol for display.
    
    Args:
        symbol: LSP symbol dictionary
        workspace_root: The workspace root path
        
    Returns:
        Formatted symbol dictionary
    """
    # Symbol kind mapping (LSP spec)
    SYMBOL_KINDS = {
        1: 'File', 2: 'Module', 3: 'Namespace', 4: 'Package',
        5: 'Class', 6: 'Method', 7: 'Property', 8: 'Field',
        9: 'Constructor', 10: 'Enum', 11: 'Interface', 12: 'Function',
        13: 'Variable', 14: 'Constant', 15: 'String', 16: 'Number',
        17: 'Boolean', 18: 'Array', 19: 'Object', 20: 'Key',
        21: 'Null', 22: 'EnumMember', 23: 'Struct', 24: 'Event',
        25: 'Operator', 26: 'TypeParameter'
    }
    
    result = {
        'name': symbol.get('name', 'unknown'),
        'kind': SYMBOL_KINDS.get(symbol.get('kind', 0), 'Unknown'),
    }
    
    # Add detail if present
    if 'detail' in symbol:
        result['detail'] = symbol['detail']
    
    # Handle location
    if 'location' in symbol:
        result['location'] = _format_location(symbol['location'], workspace_root)
    elif 'range' in symbol:
        # DocumentSymbol format
        range_info = symbol['range']
        start = range_info.get('start', {})
        result['location'] = {
            'line': start.get('line', 0) + 1,
            'character': start.get('character', 0) + 1
        }
    
    # Handle children (for DocumentSymbol hierarchy)
    if 'children' in symbol and symbol['children']:
        result['children'] = [
            _format_symbol(child, workspace_root) 
            for child in symbol['children']
        ]
    
    return result


def _format_hover(hover_result: Any) -> str:
    """Format hover result for display.
    
    Args:
        hover_result: LSP hover result (can be string, dict, or list)
        
    Returns:
        Formatted hover string
    """
    if not hover_result:
        return "No hover information available"
    
    # Handle string directly
    if isinstance(hover_result, str):
        return hover_result
    
    # Handle dict with contents
    if isinstance(hover_result, dict):
        contents = hover_result.get('contents', hover_result)
        
        # Handle MarkupContent
        if isinstance(contents, dict):
            if 'value' in contents:
                return contents['value']
            elif 'language' in contents and 'value' in contents:
                return f"```{contents['language']}\n{contents['value']}\n```"
        
        # Handle string
        if isinstance(contents, str):
            return contents
        
        # Handle MarkedString array
        if isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if 'value' in item:
                        if 'language' in item:
                            parts.append(f"```{item['language']}\n{item['value']}\n```")
                        else:
                            parts.append(item['value'])
            return '\n\n'.join(parts) if parts else str(hover_result)
    
    # Handle list directly
    if isinstance(hover_result, list):
        parts = []
        for item in hover_result:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and 'value' in item:
                parts.append(item['value'])
        return '\n\n'.join(parts) if parts else str(hover_result)
    
    return str(hover_result)


class LspTool(BaseTool):
    """Tool for Language Server Protocol code intelligence operations.
    
    This tool provides semantic code understanding through LSP, enabling
    operations like go-to-definition, find-references, hover, and document
    symbol analysis.
    
    Language servers are managed by LspServerManager with:
    - Server pooling by (language, workspace) key for reuse
    - Idle timeout (5 min) for automatic cleanup
    - Health checking with automatic recovery
    """
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = True

    def __init__(self, workspace_manager: WorkspaceManager):
        """Initialize the LSP tool.
        
        Args:
            workspace_manager: Workspace manager for file path validation
        """
        self.workspace_manager = workspace_manager
        # Use the singleton server manager for lifecycle management
        from backend.src.tool_server.tools.file_system.lsp_manager import get_lsp_manager
        self._manager = get_lsp_manager()
    
    async def _execute_lsp_operation(
        self,
        operation: str,
        file_path: Path,
        line: int,
        character: int,
        workspace_root: Path,
        language: str,
        query: Optional[str] = None,
        timeout: int = COMMAND_TIMEOUT,
        force_restart: bool = False
    ) -> Any:
        """Execute an LSP operation using the managed server pool.
        
        Args:
            operation: The LSP operation to perform
            file_path: Absolute path to the target file
            line: 1-based line number
            character: 1-based character offset
            workspace_root: The workspace root directory
            language: The programming language
            query: Optional query for workspaceSymbol
            timeout: Operation timeout in seconds
            force_restart: Force restart the server before operation
            
        Returns:
            Results from the LSP operation
        """
        from backend.src.tool_server.tools.file_system.lsp_manager import LspManagerError
        
        workspace_str = str(workspace_root)
        lsp = None
        
        try:
            # Get server from pool (reuses existing or creates new)
            lsp = await self._manager.get_server(
                language=language,
                workspace=workspace_str,
                force_restart=force_restart
            )
            
            # Convert to relative path for multilspy
            try:
                relative_path = str(file_path.relative_to(workspace_root))
            except ValueError:
                # File is outside workspace, use absolute path
                relative_path = str(file_path)
            
            # Convert to 0-based indices (LSP uses 0-based)
            lsp_line = line - 1
            lsp_character = character - 1
            
            # Execute operation with timeout
            async with asyncio.timeout(timeout):
                if operation == "goToDefinition":
                    result = await lsp.request_definition(relative_path, lsp_line, lsp_character)
                elif operation == "findReferences":
                    result = await lsp.request_references(relative_path, lsp_line, lsp_character)
                elif operation == "hover":
                    result = await lsp.request_hover(relative_path, lsp_line, lsp_character)
                elif operation == "documentSymbol":
                    result = await lsp.request_document_symbols(relative_path)
                elif operation == "workspaceSymbol":
                    # workspaceSymbol uses a query string
                    result = await lsp.request_workspace_symbol(query or "")
                else:
                    raise LspToolError(f"Unknown operation: {operation}")
                
                return result if result else []
                
        except LspManagerError as e:
            raise LspToolError(str(e))
        except LspToolError:
            raise
        except asyncio.TimeoutError:
            raise LspToolError(f"LSP operation timed out after {timeout} seconds")
        except Exception as e:
            logger.exception(f"LSP operation failed: {e}")
            raise LspToolError(f"LSP operation failed: {e}")
        finally:
            # Always release server back to pool (starts idle timeout)
            if lsp:
                try:
                    await self._manager.release_server(language, workspace_str)
                except Exception as e:
                    logger.warning(f"Failed to release server: {e}")

    def _format_results(
        self,
        operation: str,
        results: Any,
        file_path: Path,
        line: int,
        character: int,
        workspace_root: Path
    ) -> str:
        """Format LSP results for display.
        
        Args:
            operation: The LSP operation performed
            results: Raw results from LSP
            file_path: The target file path
            line: The target line number
            character: The target character offset
            workspace_root: The workspace root directory
            
        Returns:
            Formatted string for display
        """
        if not results:
            return f"No results found for {operation} at {file_path.name}:{line}:{character}"
        
        # Get relative path for display
        try:
            rel_path = file_path.relative_to(workspace_root)
        except ValueError:
            rel_path = file_path
        
        header = f"{operation} at {rel_path}:{line}:{character}"
        
        if operation == "hover":
            # Hover returns a single result
            formatted = _format_hover(results)
            return f"{header}\n---\n{formatted}"
        
        elif operation in ("goToDefinition", "findReferences"):
            # These return locations
            if isinstance(results, dict):
                results = [results]
            
            if not isinstance(results, list):
                return f"{header}\n---\n{str(results)}"
            
            locations = [_format_location(loc, workspace_root) for loc in results[:MAX_RESULTS] if isinstance(loc, dict)]
            
            output_lines = [f"{header}", f"Found {len(locations)} result(s):", "---"]
            for loc in locations:
                file_info = loc.get('file', 'unknown')
                if 'range' in loc:
                    start = loc['range']['start']
                    output_lines.append(f"  {file_info}:{start['line']}:{start['character']}")
                else:
                    output_lines.append(f"  {file_info}")
            
            if len(results) > MAX_RESULTS:
                output_lines.append(f"... and {len(results) - MAX_RESULTS} more results")
            
            return '\n'.join(output_lines)
        
        elif operation in ("documentSymbol", "workspaceSymbol"):
            # These return symbols
            if isinstance(results, dict):
                results = [results]
            
            if not isinstance(results, list):
                return f"{header}\n---\n{str(results)}"
            
            symbols = [_format_symbol(sym, workspace_root) for sym in results[:MAX_RESULTS] if isinstance(sym, dict)]
            
            output_lines = [f"{header}", f"Found {len(symbols)} symbol(s):", "---"]
            
            def format_symbol_tree(symbol: Dict[str, Any], indent: int = 0) -> List[str]:
                prefix = "  " * indent
                lines = []
                
                loc_info = ""
                if 'location' in symbol:
                    loc = symbol['location']
                    if 'line' in loc:
                        loc_info = f" at line {loc['line']}"
                    elif 'file' in loc:
                        file_info = loc['file']
                        range_info = loc.get('range', {}).get('start', {})
                        if range_info:
                            loc_info = f" at {file_info}:{range_info.get('line', '?')}"
                        else:
                            loc_info = f" in {file_info}"
                
                detail = f" - {symbol['detail']}" if 'detail' in symbol else ""
                lines.append(f"{prefix}{symbol['kind']} {symbol['name']}{detail}{loc_info}")
                
                if 'children' in symbol:
                    for child in symbol['children']:
                        lines.extend(format_symbol_tree(child, indent + 1))
                
                return lines
            
            for symbol in symbols:
                output_lines.extend(format_symbol_tree(symbol))
            
            if len(results) > MAX_RESULTS:
                output_lines.append(f"... and {len(results) - MAX_RESULTS} more symbols")
            
            return '\n'.join(output_lines)
        
        else:
            # Fallback: JSON dump
            try:
                return f"{header}\n---\n{json.dumps(results, indent=2, default=str)}"
            except Exception:
                return f"{header}\n---\n{str(results)}"

    async def execute(
        self,
        tool_input: Dict[str, Any],
    ) -> ToolResult:
        """Execute an LSP operation.
        
        Args:
            tool_input: Dictionary containing operation, filePath, line, character
            
        Returns:
            ToolResult with the operation results or error
        """
        # Check platform - LSP tool requires Linux due to asyncio subprocess limitations
        if platform.system() == "Windows":
            return ToolResult(
                llm_content="ERROR: The LSP tool is not supported on Windows due to asyncio subprocess "
                           "transport limitations. This tool is designed to run in a Linux sandbox environment "
                           "(E2B or Daytona). Please use the ASTGrep or Grep tools as alternatives for "
                           "code search on Windows.",
                is_error=True
            )
        
        operation = tool_input.get("operation")
        file_path_str = tool_input.get("filePath")
        line = tool_input.get("line")
        character = tool_input.get("character")
        query = tool_input.get("query")
        timeout = tool_input.get("timeout", COMMAND_TIMEOUT)
        force_restart = tool_input.get("forceRestart", False)
        
        # Validate required parameters
        if not operation:
            return ToolResult(
                llm_content="ERROR: operation is required",
                is_error=True
            )
        
        if operation not in LSP_OPERATIONS:
            return ToolResult(
                llm_content=f"ERROR: Invalid operation '{operation}'. Valid operations: {', '.join(LSP_OPERATIONS)}",
                is_error=True
            )
        
        if not file_path_str:
            return ToolResult(
                llm_content="ERROR: filePath is required",
                is_error=True
            )
        
        if line is None or line < 1:
            return ToolResult(
                llm_content="ERROR: line must be a positive integer (1-based)",
                is_error=True
            )
        
        if character is None or character < 1:
            return ToolResult(
                llm_content="ERROR: character must be a positive integer (1-based)",
                is_error=True
            )
        
        try:
            # Resolve file path
            workspace_root = self.workspace_manager.get_workspace_path()
            
            if Path(file_path_str).is_absolute():
                file_path = Path(file_path_str).resolve()
            else:
                file_path = (workspace_root / file_path_str).resolve()
            
            # Validate file exists
            if not file_path.exists():
                return ToolResult(
                    llm_content=f"ERROR: File not found: {file_path}",
                    is_error=True
                )
            
            if not file_path.is_file():
                return ToolResult(
                    llm_content=f"ERROR: Path is not a file: {file_path}",
                    is_error=True
                )
            
            # Detect language
            language = _detect_language(file_path)
            if not language:
                return ToolResult(
                    llm_content=f"ERROR: No LSP server available for file type: {file_path.suffix}\n"
                               f"Supported extensions: {', '.join(sorted(LANGUAGE_EXTENSIONS.keys()))}",
                    is_error=True
                )
            
            # Execute LSP operation
            results = await self._execute_lsp_operation(
                operation=operation,
                file_path=file_path,
                line=line,
                character=character,
                workspace_root=workspace_root,
                language=language,
                query=query,
                timeout=timeout,
                force_restart=force_restart
            )
            
            # Format results
            formatted_output = self._format_results(
                operation=operation,
                results=results,
                file_path=file_path,
                line=line,
                character=character,
                workspace_root=workspace_root
            )
            
            result_count = len(results) if isinstance(results, list) else 1
            
            return ToolResult(
                llm_content=formatted_output,
                user_display_content={
                    "operation": operation,
                    "file": str(file_path),
                    "line": line,
                    "character": character,
                    "language": language,
                    "result_count": result_count
                },
                is_error=False
            )
            
        except FileSystemValidationError as e:
            return ToolResult(
                llm_content=f"ERROR: File validation failed: {e}",
                is_error=True
            )
        except LspToolError as e:
            return ToolResult(
                llm_content=f"ERROR: {e}",
                is_error=True
            )
        except Exception as e:
            logger.exception(f"Unexpected error in LSP tool: {e}")
            return ToolResult(
                llm_content=f"ERROR: Unexpected error: {e}",
                is_error=True
            )

    async def execute_mcp_wrapper(
        self,
        operation: str,
        filePath: str,
        line: int,
        character: int,
        query: Optional[str] = None,
        timeout: Optional[int] = None,
        forceRestart: bool = False,
    ):
        """MCP wrapper for the execute method.
        
        Args:
            operation: The LSP operation to perform
            filePath: Path to the file
            line: 1-based line number
            character: 1-based character offset
            query: Optional query for workspaceSymbol
            timeout: Optional operation timeout in seconds (default: 60)
            forceRestart: Force restart the language server before operation
            
        Returns:
            FastMCP-formatted result
        """
        tool_input = {
            "operation": operation,
            "filePath": filePath,
            "line": line,
            "character": character,
            "query": query,
            "forceRestart": forceRestart,
        }
        if timeout is not None:
            tool_input["timeout"] = timeout
        return await self._mcp_wrapper(tool_input=tool_input)
