"""Design diagram export tool for saving diagrams to files."""

from pathlib import Path
from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "design_export_diagram"
DISPLAY_NAME = "Export diagram to file"

DESCRIPTION = """Export the current diagram to a .drawio file.

## Overview
This tool saves the current diagram to a file in the workspace.
The file can be opened in the desktop draw.io application or
uploaded to diagrams.net.

## File Format
- Output: `.drawio` file (XML format)
- Compatible with: diagrams.net, draw.io desktop, VS Code extension

## Usage
Provide a file path (relative to workspace or absolute).
The `.drawio` extension will be added automatically if not present.

## Examples
- `architecture-diagram` → `/workspace/diagrams/architecture-diagram.drawio`
- `diagrams/flowchart.drawio` → `/workspace/diagrams/flowchart.drawio`
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {
            "type": "string",
            "description": "The session ID from design_init. Required.",
        },
        "file_path": {
            "type": "string",
            "description": "File path to save the diagram (e.g., 'architecture-diagram' or 'diagrams/flowchart.drawio'). The .drawio extension is added automatically if not present.",
        },
    },
    "required": ["session_id", "file_path"],
}


class DesignExportTool(BaseTool):
    """Tool for exporting diagrams to files."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False
    
    # Design MCP Server configuration
    DESIGN_MCP_PORT = 6002
    DESIGN_MCP_URL = f"http://localhost:{DESIGN_MCP_PORT}"
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
        self.diagrams_dir = "diagrams"
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the diagram export."""
        session_id = tool_input.get("session_id", "")
        file_path = tool_input.get("file_path", "")
        
        # Validate inputs
        if not session_id:
            return ToolResult(
                llm_content="Error: session_id is required. Call design_init first to get a session ID.",
                user_display_content="Missing session_id",
                is_error=True,
            )
        
        if not file_path:
            return ToolResult(
                llm_content="Error: file_path is required. Provide a path for the .drawio file.",
                user_display_content="Missing file_path",
                is_error=True,
            )
        
        try:
            # Get current XML from Design MCP Server
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.DESIGN_MCP_URL}/api/state",
                    params={"sessionId": session_id}
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        llm_content=f"Failed to get diagram: HTTP {response.status_code}",
                        user_display_content="Failed to get diagram",
                        is_error=True,
                    )
                
                result = response.json()
                xml = result.get("xml", "")
        
        except httpx.ConnectError:
            return ToolResult(
                llm_content=(
                    "Failed to connect to Design MCP Server on port 6002. "
                    "The server may not be running."
                ),
                user_display_content="Design MCP Server not available",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                llm_content=f"Error getting diagram: {str(e)}",
                user_display_content="Failed to get diagram",
                is_error=True,
            )
        
        if not xml:
            return ToolResult(
                llm_content="Error: No diagram to export. Please create a diagram first with design_create_diagram.",
                user_display_content="No diagram to export",
                is_error=True,
            )
        
        # Resolve file path
        workspace_path = Path(self.workspace_manager.get_workspace_path())
        
        # Add .drawio extension if not present
        if not file_path.endswith(".drawio"):
            file_path = f"{file_path}.drawio"
        
        # If path doesn't include directory, put in diagrams/
        if "/" not in file_path and "\\" not in file_path:
            file_path = f"{self.diagrams_dir}/{file_path}"
        
        full_path = workspace_path / file_path
        
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write the file
            full_path.write_text(xml, encoding="utf-8")
        except Exception as e:
            return ToolResult(
                llm_content=f"Error writing file: {str(e)}",
                user_display_content="Failed to write file",
                is_error=True,
            )
        
        return ToolResult(
            llm_content=(
                f"Diagram exported successfully!\n\n"
                f"File: {full_path}\n"
                f"Size: {len(xml)} characters\n\n"
                f"The file can be opened with:\n"
                f"- diagrams.net (web)\n"
                f"- draw.io desktop application\n"
                f"- VS Code draw.io extension"
            ),
            user_display_content={
                "type": "design_export_result",
                "session_id": session_id,
                "file_path": str(full_path),
                "file_size": len(xml),
            },
            is_error=False,
        )
    
    async def execute_mcp_wrapper(
        self,
        session_id: str,
        file_path: str,
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "session_id": session_id,
                "file_path": file_path,
            }
        )
