"""Excalidraw element query tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_query_elements"
DISPLAY_NAME = "Query Excalidraw elements"

DESCRIPTION = """Query elements on the Excalidraw canvas with optional filters.

## Optional Filters
- **type**: Filter by element type (rectangle, ellipse, diamond, line, arrow, text, freedraw)

## Returns
A list of all elements matching the filters, including:
- Element ID (for use with update/delete)
- Element type
- Position (x, y)
- Dimensions (width, height)
- Style properties (colors, stroke, opacity)

## Example Usage
Get all elements:
```json
{}
```

Get only rectangles:
```json
{
    "type": "rectangle"
}
```

## Use Cases
- Get element IDs for update/delete operations
- Review current canvas state
- Find specific elements by type
- Check element count before/after operations
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["rectangle", "ellipse", "diamond", "line", "arrow", "text", "freedraw"],
            "description": "Optional: Filter by element type.",
        },
    },
    "required": [],
}


class ExcalidrawQueryTool(BaseTool):
    """Tool for querying elements on the Excalidraw canvas."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = True
    
    # Excalidraw Canvas Server configuration
    EXCALIDRAW_PORT = 6003
    EXCALIDRAW_URL = f"http://localhost:{EXCALIDRAW_PORT}"
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute element query on the canvas."""
        type_filter = tool_input.get("type")
        
        try:
            # Build query URL
            url = f"{self.EXCALIDRAW_URL}/api/elements"
            if type_filter:
                url = f"{self.EXCALIDRAW_URL}/api/elements/search?type={type_filter}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to query elements: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to query elements",
                        is_error=True,
                    )
                
                result = response.json()
                elements = result.get("elements", [])
                count = result.get("count", len(elements))
        
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
                llm_content=f"Error querying elements: {str(e)}",
                user_display_content="Failed to query elements",
                is_error=True,
            )
        
        # Format elements for response
        if not elements:
            filter_msg = f" of type '{type_filter}'" if type_filter else ""
            return ToolResult(
                llm_content=f"No elements{filter_msg} found on the canvas.",
                user_display_content={"type": "excalidraw_query_result", "count": 0, "elements": []},
                is_error=False,
            )
        
        # Build compact element summaries for LLM
        element_summaries = []
        for elem in elements:
            summary = {
                "id": elem.get("id"),
                "type": elem.get("type"),
                "x": elem.get("x"),
                "y": elem.get("y"),
            }
            if elem.get("width"):
                summary["width"] = elem.get("width")
            if elem.get("height"):
                summary["height"] = elem.get("height")
            if elem.get("text"):
                summary["text"] = elem.get("text")[:50]  # Truncate long text
            element_summaries.append(summary)
        
        # Build formatted LLM response
        elements_text = "\n".join([
            f"  - ID: {e['id']}, Type: {e['type']}, Position: ({e['x']}, {e['y']})"
            + (f", Text: \"{e.get('text', '')}\"" if e.get('text') else "")
            for e in element_summaries
        ])
        
        filter_msg = f" of type '{type_filter}'" if type_filter else ""
        
        query_result = {
            "type": "excalidraw_query_result",
            "count": count,
            "filter": type_filter,
            "elements": element_summaries,
        }
        
        return ToolResult(
            llm_content=(
                f"Found {count} element(s){filter_msg} on the canvas:\n\n"
                f"{elements_text}\n\n"
                f"Use element IDs with `excalidraw_update_element` or `excalidraw_delete_element` to modify."
            ),
            user_display_content=[query_result],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, type: str = None):
        """MCP wrapper for the tool."""
        tool_input = {}
        if type is not None:
            tool_input["type"] = type
        return await self._mcp_wrapper(tool_input=tool_input)
