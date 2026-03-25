"""Excalidraw element unlocking tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_unlock_elements"
DISPLAY_NAME = "Unlock Excalidraw elements"

DESCRIPTION = """Unlock previously locked elements on the Excalidraw canvas.

## Required Parameters
- **element_ids**: Array of element IDs to unlock

## Example Usage
Unlock specific elements:
```json
{
    "element_ids": ["abc123", "def456"]
}
```

## Notes
- After unlocking, elements can be moved, resized, and edited in the browser
- Use with elements that were previously locked using `excalidraw_lock_elements`
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "element_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Array of element IDs to unlock.",
        },
    },
    "required": ["element_ids"],
}


class ExcalidrawUnlockTool(BaseTool):
    """Tool for unlocking elements on the Excalidraw canvas."""
    
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
        """Execute element unlocking on the canvas."""
        element_ids = tool_input.get("element_ids", [])
        
        # Validate element IDs
        if not element_ids:
            return ToolResult(
                llm_content="Error: At least 1 element ID is required.",
                user_display_content="Missing element IDs",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.EXCALIDRAW_URL}/api/elements/lock",
                    json={"elementIds": element_ids, "locked": False}
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to unlock elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to unlock elements",
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
                llm_content=f"Error unlocking elements: {str(e)}",
                user_display_content="Failed to unlock elements",
                is_error=True,
            )
        
        unlock_summary = {
            "type": "excalidraw_elements_unlocked",
            "element_count": len(element_ids),
            "element_ids": element_ids,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully unlocked {len(element_ids)} element(s).\n\n"
                f"Unlocked elements: {', '.join(element_ids)}\n\n"
                f"These elements can now be moved and edited in the browser."
            ),
            user_display_content=[unlock_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, element_ids: list[str]):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"element_ids": element_ids})
