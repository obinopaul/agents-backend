"""Excalidraw element grouping tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_group_elements"
DISPLAY_NAME = "Group Excalidraw elements"

DESCRIPTION = """Group multiple elements together on the Excalidraw canvas.

## Required Parameters
- **element_ids**: Array of element IDs to group together (minimum 2)

## Example Usage
Group three elements:
```json
{
    "element_ids": ["abc123", "def456", "ghi789"]
}
```

## Notes
- At least 2 elements are required for grouping
- Grouped elements move together when dragged
- Use `excalidraw_ungroup_elements` to ungroup
- Use `excalidraw_query_elements` to find element IDs
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "element_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "description": "Array of element IDs to group together. Minimum 2 elements required.",
        },
    },
    "required": ["element_ids"],
}


class ExcalidrawGroupTool(BaseTool):
    """Tool for grouping elements on the Excalidraw canvas."""
    
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
        """Execute element grouping on the canvas."""
        element_ids = tool_input.get("element_ids", [])
        
        # Validate element IDs
        if not element_ids or len(element_ids) < 2:
            return ToolResult(
                llm_content="Error: At least 2 element IDs are required for grouping.",
                user_display_content="Insufficient elements for grouping",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.EXCALIDRAW_URL}/api/elements/group",
                    json={"elementIds": element_ids}
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to group elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to group elements",
                        is_error=True,
                    )
                
                result = response.json()
                group_id = result.get("groupId", "unknown")
        
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
                llm_content=f"Error grouping elements: {str(e)}",
                user_display_content="Failed to group elements",
                is_error=True,
            )
        
        group_summary = {
            "type": "excalidraw_elements_grouped",
            "group_id": group_id,
            "element_count": len(element_ids),
            "element_ids": element_ids,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully grouped {len(element_ids)} elements.\n\n"
                f"Group ID: {group_id}\n"
                f"Element IDs: {', '.join(element_ids)}\n\n"
                f"Use `excalidraw_ungroup_elements` with group ID '{group_id}' to ungroup."
            ),
            user_display_content=[group_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, element_ids: list[str]):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"element_ids": element_ids})
