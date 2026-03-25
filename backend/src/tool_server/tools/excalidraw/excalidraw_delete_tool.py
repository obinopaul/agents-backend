"""Excalidraw element deletion tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_delete_element"
DISPLAY_NAME = "Delete an Excalidraw element"

DESCRIPTION = """Delete an element from the Excalidraw canvas by its ID.

## Required Parameters
- **id**: The element ID to delete

## Example Usage
```json
{
    "id": "abc123"
}
```

## Notes
- The element will be immediately removed from the canvas
- This action cannot be undone through the API (use browser undo)
- Use `excalidraw_query_elements` to find element IDs before deleting
- Deleting a container element may leave orphaned text elements
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "The ID of the element to delete.",
        },
    },
    "required": ["id"],
}


class ExcalidrawDeleteTool(BaseTool):
    """Tool for deleting elements from the Excalidraw canvas."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False
    
    # Excalidraw Canvas Server configuration
    EXCALIDRAW_PORT = 6003
    EXCALIDRAW_URL = f"http://localhost:{EXCALIDRAW_PORT}"
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute element deletion from the canvas."""
        element_id = tool_input.get("id")
        
        # Validate required fields
        if not element_id:
            return ToolResult(
                llm_content="Error: 'id' is required. Use `excalidraw_query_elements` to find element IDs.",
                user_display_content="Missing element ID",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{self.EXCALIDRAW_URL}/api/elements/{element_id}"
                )
                
                if response.status_code == 404:
                    return ToolResult(
                        llm_content=f"Error: Element with ID '{element_id}' not found on the canvas.",
                        user_display_content="Element not found",
                        is_error=True,
                    )
                
                if response.status_code not in (200, 204):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to delete element: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to delete element",
                        is_error=True,
                    )
        
        except httpx.ConnectError:
            return ToolResult(
                llm_content=(
                    "Failed to connect to Excalidraw Canvas Server on port 6003. "
                    "The server may not be running."
                ),
                user_display_content="Excalidraw server not available",
                is_error=True,
            )
        except httpx.TimeoutException:
            return ToolResult(
                llm_content="Request to Excalidraw server timed out.",
                user_display_content="Request timeout",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                llm_content=f"Error deleting element: {str(e)}",
                user_display_content="Failed to delete element",
                is_error=True,
            )
        
        # Build response
        delete_summary = {
            "type": "excalidraw_element_deleted",
            "element_id": element_id,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully deleted element '{element_id}' from the canvas.\n\n"
                f"The element has been removed and the canvas has been updated."
            ),
            user_display_content=[delete_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, id: str):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"id": id})
