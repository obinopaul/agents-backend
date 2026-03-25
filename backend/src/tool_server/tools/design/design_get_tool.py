"""Design diagram get tool for retrieving current diagram XML."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "design_get_diagram"
DISPLAY_NAME = "Get current diagram XML"

DESCRIPTION = """Get the current diagram XML from the active session.

## Overview
This tool retrieves the latest diagram state, including any changes the user
may have made manually in the browser.

## When to Use
- Before using `design_edit_diagram` to see current cell IDs and structure
- To verify what elements exist in the diagram
- To understand the current state before making modifications

## Important
ALWAYS call this before `design_edit_diagram` if you want to:
- Update existing cells (need to know their IDs)
- Delete cells (need to know their IDs)
- Understand what the user has added manually

The returned XML is the authoritative source of truth - it includes both
AI-generated content AND any manual user edits.

## Return Value
Returns the complete mxfile XML with all diagram elements.
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {
            "type": "string",
            "description": "The session ID from design_init. Required.",
        },
    },
    "required": ["session_id"],
}


class DesignGetTool(BaseTool):
    """Tool for retrieving current diagram XML."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = True  # This is a read-only tool
    
    # Design MCP Server configuration
    DESIGN_MCP_PORT = 6002
    DESIGN_MCP_URL = f"http://localhost:{DESIGN_MCP_PORT}"
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the diagram retrieval."""
        session_id = tool_input.get("session_id", "")
        
        # Validate input
        if not session_id:
            return ToolResult(
                llm_content="Error: session_id is required. Call design_init first to get a session ID.",
                user_display_content="Missing session_id",
                is_error=True,
            )
        
        try:
            # Get XML from Design MCP Server via HTTP API
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
                version = result.get("version", 0)
        
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
                llm_content=f"Error retrieving diagram: {str(e)}",
                user_display_content="Failed to retrieve diagram",
                is_error=True,
            )
        
        if not xml:
            return ToolResult(
                llm_content=(
                    f"No diagram exists yet for session {session_id}.\n\n"
                    "Use `design_create_diagram` to create one."
                ),
                user_display_content="No diagram found",
                is_error=False,
            )
        
        # Parse XML to extract useful info
        cell_count = xml.count("<mxCell")
        
        return ToolResult(
            llm_content=(
                f"Current diagram XML (version {version}):\n\n"
                f"```xml\n{xml}\n```\n\n"
                f"Summary:\n"
                f"- Total mxCell elements: {cell_count}\n"
                f"- XML length: {len(xml)} characters\n\n"
                f"You can now use `design_edit_diagram` to modify cells by their ID."
            ),
            user_display_content={
                "type": "design_get_result",
                "session_id": session_id,
                "version": version,
                "cell_count": cell_count,
                "xml_length": len(xml),
            },
            is_error=False,
        )
    
    async def execute_mcp_wrapper(
        self,
        session_id: str,
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "session_id": session_id,
            }
        )
