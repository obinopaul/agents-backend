"""Design session initialization tool for creating diagram sessions."""

import uuid
from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "design_init"
DISPLAY_NAME = "Initialize a diagram design session"

DESCRIPTION = """Initialize a new diagram design session for creating draw.io diagrams.

## Overview
This tool creates a new diagram session and returns the viewer URL where the diagram 
can be viewed and edited in real-time using draw.io.

## What This Creates
- A unique session ID for tracking the diagram
- A blank canvas ready for diagram creation
- A real-time browser viewer URL

## Usage
1. Call this tool to start a new diagram session
2. Use the returned viewer URL to see the diagram in a browser
3. Use `design_create_diagram` or `design_edit_diagram` to modify the diagram
4. The browser updates automatically as you make changes

## Session Persistence
Sessions persist as long as the sandbox is running. Diagrams are automatically
saved to the workspace when exported.

## Browser Viewer
The viewer URL opens a page with an embedded draw.io editor. Users can:
- View the AI-generated diagram in real-time
- Make manual edits (which the AI can then see via `design_get_diagram`)
- Pan, zoom, and interact with the diagram
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "diagram_name": {
            "type": "string",
            "description": "Optional name for the diagram (used for file exports). If not provided, a unique name will be generated.",
        },
    },
    "required": [],
}

# Default blank diagram XML
DEFAULT_DIAGRAM_XML = """<mxfile host="app.diagrams.net"><diagram id="blank" name="Page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>"""


class DesignInitTool(BaseTool):
    """Tool for initializing diagram design sessions."""
    
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
        """Execute the design session initialization."""
        diagram_name = tool_input.get("diagram_name", "")
        
        # Generate session ID
        session_id = f"mcp-{uuid.uuid4().hex[:12]}"
        
        # Generate diagram name if not provided
        if not diagram_name:
            diagram_name = f"diagram_{uuid.uuid4().hex[:8]}"
        
        # Sanitize name for filesystem
        safe_name = self._sanitize_name(diagram_name)
        
        try:
            # Initialize session on the Design MCP Server via HTTP API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.DESIGN_MCP_URL}/api/state",
                    json={
                        "sessionId": session_id,
                        "xml": DEFAULT_DIAGRAM_XML,
                    }
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        llm_content=f"Failed to initialize Design MCP session: HTTP {response.status_code}",
                        user_display_content="Failed to initialize diagram session",
                        is_error=True,
                    )
                
                result = response.json()
                version = result.get("version", 1)
        
        except httpx.ConnectError:
            return ToolResult(
                llm_content=(
                    "Failed to connect to Design MCP Server on port 6002. "
                    "The server may not be running. Check /tmp/design-mcp.log for details."
                ),
                user_display_content="Design MCP Server not available",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                llm_content=f"Error initializing diagram session: {str(e)}",
                user_display_content="Failed to initialize diagram session",
                is_error=True,
            )
        
        # Build viewer URL
        viewer_url = f"{self.DESIGN_MCP_URL}/?mcp={session_id}"
        
        # Build response metadata
        session_metadata = {
            "type": "design_session_metadata",
            "session_id": session_id,
            "diagram_name": safe_name,
            "viewer_url": viewer_url,
            "version": version,
        }
        
        # Build guidance for next steps
        next_steps = (
            "Next steps:\n"
            "1. Use `design_create_diagram` to create a new diagram from mxGraphModel XML\n"
            "2. Use `design_edit_diagram` to add/update/delete cells by ID\n"
            "3. Use `design_get_diagram` to retrieve the current diagram XML\n"
            "4. Use `design_export_diagram` to save the diagram to a .drawio file\n\n"
            "The user can view the diagram at the viewer URL in real-time.\n"
            "Any changes made via these tools will be immediately visible in the browser."
        )
        
        return ToolResult(
            llm_content=(
                f"Successfully initialized diagram session '{safe_name}'.\n\n"
                f"Session ID: {session_id}\n"
                f"Viewer URL: {viewer_url}\n"
                f"Version: {version}\n\n"
                f"{next_steps}"
            ),
            user_display_content=[session_metadata],
            is_error=False,
        )
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize diagram name for filesystem."""
        # Replace spaces and hyphens with underscores
        sanitized = name.replace(" ", "_").replace("-", "_")
        # Keep only alphanumeric and underscore
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
        # Ensure lowercase
        return sanitized.lower()
    
    async def execute_mcp_wrapper(
        self,
        diagram_name: str = "",
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "diagram_name": diagram_name,
            }
        )
