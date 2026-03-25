"""Excalidraw element locking tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_lock_elements"
DISPLAY_NAME = "Lock Excalidraw elements"

DESCRIPTION = """Lock elements on the Excalidraw canvas to prevent modification.

## Required Parameters
- **element_ids**: Array of element IDs to lock

## Example Usage
Lock specific elements:
```json
{
    "element_ids": ["abc123", "def456"]
}
```

## Notes
- Locked elements cannot be moved, resized, or edited in the browser
- Locked elements can still be deleted or modified via API
- Use `excalidraw_unlock_elements` to unlock elements
- Useful for preserving background or reference elements
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "element_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Array of element IDs to lock.",
        },
    },
    "required": ["element_ids"],
}


class ExcalidrawLockTool(BaseTool):
    """Tool for locking elements on the Excalidraw canvas."""
    
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
        """Execute element locking on the canvas."""
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
                    json={"elementIds": element_ids, "locked": True}
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to lock elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to lock elements",
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
                llm_content=f"Error locking elements: {str(e)}",
                user_display_content="Failed to lock elements",
                is_error=True,
            )
        
        lock_summary = {
            "type": "excalidraw_elements_locked",
            "element_count": len(element_ids),
            "element_ids": element_ids,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully locked {len(element_ids)} element(s).\n\n"
                f"Locked elements: {', '.join(element_ids)}\n\n"
                f"These elements cannot be moved or edited in the browser. "
                f"Use `excalidraw_unlock_elements` to unlock them."
            ),
            user_display_content=[lock_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, element_ids: list[str]):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"element_ids": element_ids})
