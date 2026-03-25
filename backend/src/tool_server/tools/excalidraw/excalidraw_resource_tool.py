"""Excalidraw resource retrieval tool."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_get_resource"
DISPLAY_NAME = "Get Excalidraw resource"

DESCRIPTION = """Get canvas resources from the Excalidraw server.

## Required Parameters
- **resource**: The resource type to retrieve

## Resource Types
- **scene**: Get the complete scene data (all elements + app state)
- **elements**: Get all elements on the canvas
- **library**: Get the element library (saved templates)
- **theme**: Get current theme settings

## Example Usage
Get the complete scene:
```json
{
    "resource": "scene"
}
```

Get all elements:
```json
{
    "resource": "elements"
}
```

## Use Cases
- Export canvas state for backup
- Get scene data for external processing
- Retrieve library items
- Check current theme settings
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "resource": {
            "type": "string",
            "enum": ["scene", "elements", "library", "theme"],
            "description": "The resource type to retrieve.",
        },
    },
    "required": ["resource"],
}


class ExcalidrawResourceTool(BaseTool):
    """Tool for retrieving resources from the Excalidraw canvas."""
    
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
        """Execute resource retrieval from the canvas."""
        resource = tool_input.get("resource")
        
        # Validate resource type
        valid_resources = ["scene", "elements", "library", "theme"]
        if resource not in valid_resources:
            return ToolResult(
                llm_content=f"Error: Invalid resource '{resource}'. Must be one of: {', '.join(valid_resources)}",
                user_display_content="Invalid resource type",
                is_error=True,
            )
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Map resource to API endpoint
                endpoint_map = {
                    "scene": "/api/scene",
                    "elements": "/api/elements",
                    "library": "/api/library",
                    "theme": "/api/theme",
                }
                endpoint = endpoint_map.get(resource, f"/api/{resource}")
                
                response = await client.get(f"{self.EXCALIDRAW_URL}{endpoint}")
                
                if response.status_code == 404:
                    return ToolResult(
                        llm_content=f"Resource '{resource}' not found or not supported by the server.",
                        user_display_content="Resource not found",
                        is_error=True,
                    )
                
                if response.status_code != 200:
                    error_text = response.text
                    return ToolResult(
                        llm_content=f"Failed to get resource: HTTP {response.status_code} - {error_text}",
                        user_display_content="Failed to get resource",
                        is_error=True,
                    )
                
                data = response.json()
        
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
                llm_content=f"Error getting resource: {str(e)}",
                user_display_content="Failed to get resource",
                is_error=True,
            )
        
        # Format response based on resource type
        if resource == "elements":
            elements = data.get("elements", [])
            count = data.get("count", len(elements))
            resource_summary = {
                "type": "excalidraw_resource",
                "resource_type": resource,
                "element_count": count,
            }
            llm_text = f"Retrieved {count} elements from the canvas."
        elif resource == "scene":
            elements = data.get("elements", [])
            app_state = data.get("appState", {})
            resource_summary = {
                "type": "excalidraw_resource",
                "resource_type": resource,
                "element_count": len(elements),
                "has_app_state": bool(app_state),
            }
            llm_text = f"Retrieved scene with {len(elements)} elements and app state."
        else:
            resource_summary = {
                "type": "excalidraw_resource",
                "resource_type": resource,
                "data": data,
            }
            llm_text = f"Retrieved {resource} resource successfully."
        
        return ToolResult(
            llm_content=llm_text,
            user_display_content=[resource_summary],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, resource: str):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"resource": resource})
