"""Excalidraw element update tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_update_element"
DISPLAY_NAME = "Update an Excalidraw element"

DESCRIPTION = """Update an existing element on the Excalidraw canvas by its ID.

## Required Parameters
- **id**: The element ID to update (returned from create or query operations)

## Updatable Properties
- **x**, **y**: New position coordinates
- **width**, **height**: New dimensions
- **backgroundColor**: New fill color (hex or 'transparent')
- **strokeColor**: New stroke/border color
- **strokeWidth**: New stroke width (1-5)
- **roughness**: New roughness level (0-2)
- **opacity**: New opacity (0-100)
- **text**: New text content (for text elements)
- **fontSize**: New font size
- **fontFamily**: New font family

## Example Usage
Move an element to a new position:
```json
{
    "id": "abc123",
    "x": 200,
    "y": 300
}
```

Change element color:
```json
{
    "id": "abc123",
    "backgroundColor": "#ffc9c9",
    "strokeColor": "#c92a2a"
}
```

## Notes
- Only provide the properties you want to change
- The element ID is required and must exist on the canvas
- Use `excalidraw_query_elements` to find element IDs
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "The ID of the element to update.",
        },
        "x": {
            "type": "number",
            "description": "New X coordinate position.",
        },
        "y": {
            "type": "number",
            "description": "New Y coordinate position.",
        },
        "width": {
            "type": "number",
            "description": "New width.",
        },
        "height": {
            "type": "number",
            "description": "New height.",
        },
        "backgroundColor": {
            "type": "string",
            "description": "New fill color.",
        },
        "strokeColor": {
            "type": "string",
            "description": "New stroke color.",
        },
        "strokeWidth": {
            "type": "number",
            "description": "New stroke width.",
        },
        "roughness": {
            "type": "number",
            "description": "New roughness level.",
        },
        "opacity": {
            "type": "number",
            "description": "New opacity (0-100).",
        },
        "text": {
            "type": "string",
            "description": "New text content (for text elements).",
        },
        "fontSize": {
            "type": "number",
            "description": "New font size.",
        },
        "fontFamily": {
            "type": "number",
            "description": "New font family.",
        },
    },
    "required": ["id"],
}


class ExcalidrawUpdateTool(BaseTool):
    """Tool for updating elements on the Excalidraw canvas."""
    
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
        """Execute element update on the canvas."""
        element_id = tool_input.get("id")
        
        # Validate required fields
        if not element_id:
            return ToolResult(
                llm_content="Error: 'id' is required. Use `excalidraw_query_elements` to find element IDs.",
                user_display_content="Missing element ID",
                is_error=True,
            )
        
        # Build update data (exclude 'id' from the payload body)
        update_data = {}
        updatable_fields = [
            "x", "y", "width", "height", "backgroundColor", "strokeColor",
            "strokeWidth", "roughness", "opacity", "text", "fontSize", "fontFamily"
        ]
        
        for field in updatable_fields:
            if field in tool_input and tool_input[field] is not None:
                update_data[field] = tool_input[field]
        
        if not update_data:
            return ToolResult(
                llm_content="Error: No properties to update. Provide at least one property to change.",
                user_display_content="No update properties provided",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(
                    f"{self.EXCALIDRAW_URL}/api/elements/{element_id}",
                    json=update_data
                )
                
                if response.status_code == 404:
                    return ToolResult(
                        llm_content=f"Error: Element with ID '{element_id}' not found on the canvas.",
                        user_display_content="Element not found",
                        is_error=True,
                    )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to update element: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to update element",
                        is_error=True,
                    )
                
                result = response.json()
                updated_element = result.get("element", {})
        
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
                llm_content=f"Error updating element: {str(e)}",
                user_display_content="Failed to update element",
                is_error=True,
            )
        
        # Build response
        updated_fields_list = list(update_data.keys())
        update_summary = {
            "type": "excalidraw_element_updated",
            "element_id": element_id,
            "updated_fields": updated_fields_list,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully updated element '{element_id}'.\n\n"
                f"Updated fields: {', '.join(updated_fields_list)}\n\n"
                f"The changes are now visible on the canvas."
            ),
            user_display_content=[update_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(
        self,
        id: str,
        x: float = None,
        y: float = None,
        width: float = None,
        height: float = None,
        backgroundColor: str = None,
        strokeColor: str = None,
        strokeWidth: float = None,
        roughness: float = None,
        opacity: float = None,
        text: str = None,
        fontSize: float = None,
        fontFamily: int = None,
    ):
        """MCP wrapper for the tool."""
        tool_input = {"id": id}
        
        if x is not None:
            tool_input["x"] = x
        if y is not None:
            tool_input["y"] = y
        if width is not None:
            tool_input["width"] = width
        if height is not None:
            tool_input["height"] = height
        if backgroundColor is not None:
            tool_input["backgroundColor"] = backgroundColor
        if strokeColor is not None:
            tool_input["strokeColor"] = strokeColor
        if strokeWidth is not None:
            tool_input["strokeWidth"] = strokeWidth
        if roughness is not None:
            tool_input["roughness"] = roughness
        if opacity is not None:
            tool_input["opacity"] = opacity
        if text is not None:
            tool_input["text"] = text
        if fontSize is not None:
            tool_input["fontSize"] = fontSize
        if fontFamily is not None:
            tool_input["fontFamily"] = fontFamily
        
        return await self._mcp_wrapper(tool_input=tool_input)
