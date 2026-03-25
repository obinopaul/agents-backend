"""Excalidraw element distribution tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_distribute_elements"
DISPLAY_NAME = "Distribute Excalidraw elements"

DESCRIPTION = """Distribute elements evenly on the Excalidraw canvas.

## Required Parameters
- **element_ids**: Array of element IDs to distribute (minimum 3)
- **direction**: Distribution direction (horizontal or vertical)

## Example Usage
Distribute elements horizontally with equal spacing:
```json
{
    "element_ids": ["abc123", "def456", "ghi789"],
    "direction": "horizontal"
}
```

## Notes
- At least 3 elements are required for distribution
- Elements are distributed based on their current positions
- The first and last elements stay in place, others are spaced evenly between them
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "element_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "description": "Array of element IDs to distribute. Minimum 3 elements required.",
        },
        "direction": {
            "type": "string",
            "enum": ["horizontal", "vertical"],
            "description": "Distribution direction.",
        },
    },
    "required": ["element_ids", "direction"],
}


class ExcalidrawDistributeTool(BaseTool):
    """Tool for distributing elements on the Excalidraw canvas."""
    
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
        """Execute element distribution on the canvas."""
        element_ids = tool_input.get("element_ids", [])
        direction = tool_input.get("direction")
        
        # Validate inputs
        if not element_ids or len(element_ids) < 3:
            return ToolResult(
                llm_content="Error: At least 3 element IDs are required for distribution.",
                user_display_content="Insufficient elements for distribution",
                is_error=True,
            )
        
        if direction not in ["horizontal", "vertical"]:
            return ToolResult(
                llm_content=f"Error: Invalid direction '{direction}'. Must be 'horizontal' or 'vertical'.",
                user_display_content="Invalid direction",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.EXCALIDRAW_URL}/api/elements/distribute",
                    json={"elementIds": element_ids, "direction": direction}
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to distribute elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to distribute elements",
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
                llm_content=f"Error distributing elements: {str(e)}",
                user_display_content="Failed to distribute elements",
                is_error=True,
            )
        
        distribute_summary = {
            "type": "excalidraw_elements_distributed",
            "direction": direction,
            "element_count": len(element_ids),
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully distributed {len(element_ids)} elements {direction}ly.\n\n"
                f"The elements are now evenly spaced on the canvas."
            ),
            user_display_content=[distribute_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, element_ids: list[str], direction: str):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"element_ids": element_ids, "direction": direction})
