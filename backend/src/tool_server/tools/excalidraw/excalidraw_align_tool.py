"""Excalidraw element alignment tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_align_elements"
DISPLAY_NAME = "Align Excalidraw elements"

DESCRIPTION = """Align multiple elements on the Excalidraw canvas.

## Required Parameters
- **element_ids**: Array of element IDs to align
- **alignment**: The alignment type

## Alignment Options
- **left**: Align left edges
- **right**: Align right edges
- **center**: Align horizontal centers
- **top**: Align top edges
- **bottom**: Align bottom edges
- **middle**: Align vertical centers

## Example Usage
Align elements to the left:
```json
{
    "element_ids": ["abc123", "def456", "ghi789"],
    "alignment": "left"
}
```

Center elements vertically:
```json
{
    "element_ids": ["abc123", "def456"],
    "alignment": "middle"
}
```
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "element_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "description": "Array of element IDs to align.",
        },
        "alignment": {
            "type": "string",
            "enum": ["left", "right", "center", "top", "bottom", "middle"],
            "description": "The alignment type.",
        },
    },
    "required": ["element_ids", "alignment"],
}


class ExcalidrawAlignTool(BaseTool):
    """Tool for aligning elements on the Excalidraw canvas."""
    
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
        """Execute element alignment on the canvas."""
        element_ids = tool_input.get("element_ids", [])
        alignment = tool_input.get("alignment")
        
        # Validate inputs
        if not element_ids or len(element_ids) < 2:
            return ToolResult(
                llm_content="Error: At least 2 element IDs are required for alignment.",
                user_display_content="Insufficient elements for alignment",
                is_error=True,
            )
        
        valid_alignments = ["left", "right", "center", "top", "bottom", "middle"]
        if alignment not in valid_alignments:
            return ToolResult(
                llm_content=f"Error: Invalid alignment '{alignment}'. Must be one of: {', '.join(valid_alignments)}",
                user_display_content="Invalid alignment type",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.EXCALIDRAW_URL}/api/elements/align",
                    json={"elementIds": element_ids, "alignment": alignment}
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to align elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to align elements",
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
                llm_content=f"Error aligning elements: {str(e)}",
                user_display_content="Failed to align elements",
                is_error=True,
            )
        
        align_summary = {
            "type": "excalidraw_elements_aligned",
            "alignment": alignment,
            "element_count": len(element_ids),
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully aligned {len(element_ids)} elements to '{alignment}'.\n\n"
                f"The elements have been repositioned on the canvas."
            ),
            user_display_content=[align_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, element_ids: list[str], alignment: str):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"element_ids": element_ids, "alignment": alignment})
