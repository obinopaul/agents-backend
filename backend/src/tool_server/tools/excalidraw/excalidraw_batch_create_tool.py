"""Excalidraw batch element creation tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_batch_create"
DISPLAY_NAME = "Batch create Excalidraw elements"

DESCRIPTION = """Create multiple elements on the Excalidraw canvas in a single operation.

## Parameters
- **elements**: Array of element objects, each with the same properties as `excalidraw_create_element`

## Limits
- Maximum 50 elements per batch operation

## Example Usage
Create a flowchart with multiple shapes:
```json
{
    "elements": [
        {"type": "rectangle", "x": 100, "y": 100, "width": 150, "height": 80, "backgroundColor": "#a5d8ff"},
        {"type": "rectangle", "x": 100, "y": 250, "width": 150, "height": 80, "backgroundColor": "#b2f2bb"},
        {"type": "arrow", "x": 175, "y": 180, "width": 0, "height": 70}
    ]
}
```

## Use Cases
- Create complex diagrams efficiently
- Generate flowcharts, org charts, or network diagrams
- Reduce API calls for multiple elements
- Maintain consistency across related elements
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["rectangle", "ellipse", "diamond", "line", "arrow", "text", "freedraw"],
                    },
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "backgroundColor": {"type": "string"},
                    "strokeColor": {"type": "string"},
                    "strokeWidth": {"type": "number"},
                    "roughness": {"type": "number"},
                    "opacity": {"type": "number"},
                    "text": {"type": "string"},
                    "fontSize": {"type": "number"},
                    "fontFamily": {"type": "number"},
                },
                "required": ["type", "x", "y"],
            },
            "description": "Array of elements to create. Each element requires type, x, y.",
        },
    },
    "required": ["elements"],
}


class ExcalidrawBatchCreateTool(BaseTool):
    """Tool for batch creating elements on the Excalidraw canvas."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False
    
    # Excalidraw Canvas Server configuration
    EXCALIDRAW_PORT = 6003
    EXCALIDRAW_URL = f"http://localhost:{EXCALIDRAW_PORT}"
    MAX_BATCH_SIZE = 50
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute batch element creation on the canvas."""
        elements = tool_input.get("elements", [])
        
        # Validate elements
        if not elements:
            return ToolResult(
                llm_content="Error: 'elements' array is required and cannot be empty.",
                user_display_content="Missing elements",
                is_error=True,
            )
        
        if len(elements) > self.MAX_BATCH_SIZE:
            return ToolResult(
                llm_content=f"Error: Batch size exceeds maximum limit of {self.MAX_BATCH_SIZE}. Got {len(elements)} elements.",
                user_display_content="Batch size exceeded",
                is_error=True,
            )
        
        # Validate each element has required fields
        for i, elem in enumerate(elements):
            if not elem.get("type"):
                return ToolResult(
                    llm_content=f"Error: Element at index {i} is missing 'type'.",
                    user_display_content=f"Invalid element at index {i}",
                    is_error=True,
                )
            if elem.get("x") is None or elem.get("y") is None:
                return ToolResult(
                    llm_content=f"Error: Element at index {i} is missing 'x' or 'y' coordinates.",
                    user_display_content=f"Invalid element at index {i}",
                    is_error=True,
                )
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.EXCALIDRAW_URL}/api/elements/batch",
                    json={"elements": elements}
                )
                
                if response.status_code not in (200, 201):
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to batch create elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to create elements",
                        is_error=True,
                    )
                
                result = response.json()
                created_elements = result.get("elements", [])
                count = result.get("count", len(created_elements))
        
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
                llm_content=f"Error creating elements: {str(e)}",
                user_display_content="Failed to create elements",
                is_error=True,
            )
        
        # Build element ID list for response
        created_ids = [elem.get("id", "unknown") for elem in created_elements]
        created_summary = {
            "type": "excalidraw_batch_created",
            "count": count,
            "element_ids": created_ids,
        }
        
        return ToolResult(
            llm_content=(
                f"Successfully created {count} elements.\n\n"
                f"Element IDs: {', '.join(created_ids)}\n\n"
                f"All elements are now visible on the canvas."
            ),
            user_display_content=[created_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, elements: list[dict]):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"elements": elements})
