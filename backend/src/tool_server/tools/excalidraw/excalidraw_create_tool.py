"""Excalidraw element creation tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_create_element"
DISPLAY_NAME = "Create an Excalidraw element"

DESCRIPTION = """Create a new element on the Excalidraw canvas.

## Supported Element Types
- **rectangle**: A rectangle shape
- **ellipse**: An ellipse/circle shape
- **diamond**: A diamond shape
- **line**: A straight line
- **arrow**: An arrow with arrowhead
- **text**: Text label
- **freedraw**: Freehand drawing (requires points array)

## Required Parameters
- **type**: The element type (rectangle, ellipse, diamond, line, arrow, text, freedraw)
- **x**: X coordinate position
- **y**: Y coordinate position

## Optional Parameters
- **width**: Element width (default: 100)
- **height**: Element height (default: 100)
- **backgroundColor**: Fill color (e.g., "#ff0000", "transparent")
- **strokeColor**: Border/stroke color (e.g., "#000000")
- **strokeWidth**: Border width (1-5)
- **roughness**: Hand-drawn roughness (0=none, 1=low, 2=high)
- **opacity**: Opacity 0-100 (default: 100)
- **text**: Text content (required for text elements)
- **fontSize**: Font size in pixels (default: 20)
- **fontFamily**: Font family (1=Hand-drawn, 2=Normal, 3=Code)

## Example Usage
Create a blue rectangle at position (100, 100):
```json
{
    "type": "rectangle",
    "x": 100,
    "y": 100,
    "width": 200,
    "height": 100,
    "backgroundColor": "#a5d8ff",
    "strokeColor": "#1971c2"
}
```

Create a text label:
```json
{
    "type": "text",
    "x": 150,
    "y": 120,
    "text": "Hello World",
    "fontSize": 24
}
```
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["rectangle", "ellipse", "diamond", "line", "arrow", "text", "freedraw"],
            "description": "The type of element to create.",
        },
        "x": {
            "type": "number",
            "description": "X coordinate position on the canvas.",
        },
        "y": {
            "type": "number",
            "description": "Y coordinate position on the canvas.",
        },
        "width": {
            "type": "number",
            "description": "Width of the element. Default: 100.",
        },
        "height": {
            "type": "number",
            "description": "Height of the element. Default: 100.",
        },
        "backgroundColor": {
            "type": "string",
            "description": "Fill color (hex or 'transparent'). Default: transparent.",
        },
        "strokeColor": {
            "type": "string",
            "description": "Stroke/border color (hex). Default: #1e1e1e.",
        },
        "strokeWidth": {
            "type": "number",
            "description": "Stroke width (1-5). Default: 1.",
        },
        "roughness": {
            "type": "number",
            "description": "Hand-drawn roughness (0=none, 1=low, 2=high). Default: 1.",
        },
        "opacity": {
            "type": "number",
            "description": "Opacity 0-100. Default: 100.",
        },
        "text": {
            "type": "string",
            "description": "Text content (required for text elements).",
        },
        "fontSize": {
            "type": "number",
            "description": "Font size in pixels. Default: 20.",
        },
        "fontFamily": {
            "type": "number",
            "description": "Font family: 1=Hand-drawn, 2=Normal, 3=Code. Default: 1.",
        },
    },
    "required": ["type", "x", "y"],
}


class ExcalidrawCreateTool(BaseTool):
    """Tool for creating elements on the Excalidraw canvas."""
    
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
        """Execute element creation on the canvas."""
        element_type = tool_input.get("type")
        x = tool_input.get("x")
        y = tool_input.get("y")
        
        # Validate required fields
        if not element_type:
            return ToolResult(
                llm_content="Error: 'type' is required. Must be one of: rectangle, ellipse, diamond, line, arrow, text, freedraw",
                user_display_content="Missing element type",
                is_error=True,
            )
        
        if x is None or y is None:
            return ToolResult(
                llm_content="Error: 'x' and 'y' coordinates are required.",
                user_display_content="Missing coordinates",
                is_error=True,
            )
        
        # Validate text for text elements
        if element_type == "text" and not tool_input.get("text"):
            return ToolResult(
                llm_content="Error: 'text' is required for text elements.",
                user_display_content="Missing text content",
                is_error=True,
            )
        
        # Build element data
        element_data = {
            "type": element_type,
            "x": float(x),
            "y": float(y),
        }
        
        # Add optional properties
        optional_fields = [
            "width", "height", "backgroundColor", "strokeColor",
            "strokeWidth", "roughness", "opacity", "text", "fontSize", "fontFamily"
        ]
        for field in optional_fields:
            if field in tool_input and tool_input[field] is not None:
                element_data[field] = tool_input[field]
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.EXCALIDRAW_URL}/api/elements",
                    json=element_data
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to create element: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to create element",
                        is_error=True,
                    )
                
                result = response.json()
                created_element = result.get("element", {})
                element_id = created_element.get("id", "unknown")
        
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
                llm_content=f"Error creating element: {str(e)}",
                user_display_content="Failed to create element",
                is_error=True,
            )
        
        # Build response
        element_summary = {
            "type": "excalidraw_element_created",
            "element_id": element_id,
            "element_type": element_type,
            "position": {"x": x, "y": y},
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully created {element_type} element.\n\n"
                f"Element ID: {element_id}\n"
                f"Type: {element_type}\n"
                f"Position: ({x}, {y})\n\n"
                f"The element is now visible on the canvas. "
                f"Use `excalidraw_update_element` with ID '{element_id}' to modify it."
            ),
            user_display_content=[element_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(
        self,
        type: str,
        x: float,
        y: float,
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
        tool_input = {"type": type, "x": x, "y": y}
        
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
