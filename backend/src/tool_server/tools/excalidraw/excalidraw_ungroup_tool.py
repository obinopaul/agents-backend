"""Excalidraw element ungrouping tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_ungroup_elements"
DISPLAY_NAME = "Ungroup Excalidraw elements"

DESCRIPTION = """Ungroup a previously grouped set of elements on the Excalidraw canvas.

## Required Parameters
- **group_id**: The ID of the group to ungroup (returned from `excalidraw_group_elements`)

## Example Usage
```json
{
    "group_id": "group-abc123"
}
```

## Notes
- The group ID is returned when you call `excalidraw_group_elements`
- After ungrouping, elements become independent again
- Individual elements retain their original IDs
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "group_id": {
            "type": "string",
            "description": "The ID of the group to ungroup.",
        },
    },
    "required": ["group_id"],
}


class ExcalidrawUngroupTool(BaseTool):
    """Tool for ungrouping elements on the Excalidraw canvas."""
    
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
        """Execute element ungrouping on the canvas."""
        group_id = tool_input.get("group_id")
        
        # Validate group ID
        if not group_id:
            return ToolResult(
                llm_content="Error: 'group_id' is required.",
                user_display_content="Missing group ID",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{self.EXCALIDRAW_URL}/api/elements/group/{group_id}"
                )
                
                if response.status_code == 404:
                    return ToolResult(
                        llm_content=f"Error: Group with ID '{group_id}' not found.",
                        user_display_content="Group not found",
                        is_error=True,
                    )
                
                if response.status_code not in (200, 204):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to ungroup elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to ungroup elements",
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
                llm_content=f"Error ungrouping elements: {str(e)}",
                user_display_content="Failed to ungroup elements",
                is_error=True,
            )
        
        ungroup_summary = {
            "type": "excalidraw_elements_ungrouped",
            "group_id": group_id,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully ungrouped elements from group '{group_id}'.\n\n"
                f"The elements are now independent and can be moved/edited separately."
            ),
            user_display_content=[ungroup_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, group_id: str):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"group_id": group_id})
