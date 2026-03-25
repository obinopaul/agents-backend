"""Excalidraw session initialization tool."""

import uuid
from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "excalidraw_init"
DISPLAY_NAME = "Initialize an Excalidraw whiteboard session"

DESCRIPTION = """Initialize a new Excalidraw whiteboard session for creating diagrams and drawings.

## Overview
This tool creates a new Excalidraw session and returns the viewer URL where the whiteboard
can be viewed and edited in real-time.

## What This Creates
- A unique session ID for tracking the canvas
- A blank Excalidraw canvas ready for drawing
- A real-time browser viewer URL

## Usage
1. Call this tool to start a new Excalidraw session
2. Use the returned viewer URL to see the whiteboard in a browser
3. Use `excalidraw_create_element` to add shapes, text, arrows, etc.
4. The browser updates automatically as you make changes

## Excalidraw vs Design (Draw.io)
- **Excalidraw**: Hand-drawn style, freeform, great for sketches and brainstorming
- **Design (Draw.io)**: Professional diagrams, structured, great for flowcharts and architecture

## Session Persistence
Sessions persist as long as the sandbox is running. Canvas states can be synced
between the AI and browser viewer in real-time via WebSocket.

## Supported Element Types
- rectangle, ellipse, diamond (shapes)
- line, arrow (connectors)
- text (labels)
- freedraw (freehand drawing)
- image (embedded images)
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_name": {
            "type": "string",
            "description": "Optional name for the canvas. If not provided, a unique name will be generated.",
        },
    },
    "required": [],
}


class ExcalidrawInitTool(BaseTool):
    """Tool for initializing Excalidraw sessions."""
    
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
        """Execute the Excalidraw session initialization."""
        canvas_name = tool_input.get("canvas_name", "")
        
        # Generate session ID
        session_id = f"excalidraw-{uuid.uuid4().hex[:12]}"
        
        # Generate canvas name if not provided
        if not canvas_name:
            canvas_name = f"canvas_{uuid.uuid4().hex[:8]}"
        
        try:
            # Check health of Excalidraw server
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.EXCALIDRAW_URL}/health")
                
                if response.status_code != 200:
                    return ToolResult(
                        llm_content=f"Excalidraw server health check failed: HTTP {response.status_code}",
                        user_display_content="Excalidraw server not healthy",
                        is_error=True,
                    )
                
                health_data = response.json()
                element_count = health_data.get("elements_count", 0)
                websocket_clients = health_data.get("websocket_clients", 0)
        
        except httpx.ConnectError:
            return ToolResult(
                llm_content=(
                    "Failed to connect to Excalidraw Canvas Server on port 6003. "
                    "The server may not be running. Check /tmp/excalidraw.log for details."
                ),
                user_display_content="Excalidraw server not available",
                is_error=True,
            )
        except httpx.TimeoutException:
            return ToolResult(
                llm_content="Excalidraw server connection timed out after 5 seconds.",
                user_display_content="Excalidraw server timeout",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                llm_content=f"Error initializing Excalidraw session: {str(e)}",
                user_display_content="Failed to initialize Excalidraw session",
                is_error=True,
            )
        
        # Build viewer URL
        viewer_url = f"{self.EXCALIDRAW_URL}/"
        
        # Build response metadata
        session_metadata = {
            "type": "excalidraw_session_metadata",
            "session_id": session_id,
            "canvas_name": canvas_name,
            "viewer_url": viewer_url,
            "current_element_count": element_count,
            "websocket_clients": websocket_clients,
        }
        
        # Build guidance for next steps
        next_steps = (
            "Next steps:\n"
            "1. Use `excalidraw_create_element` to add shapes, text, arrows, or lines\n"
            "2. Use `excalidraw_query_elements` to see what's on the canvas\n"
            "3. Use `excalidraw_update_element` to modify existing elements\n"
            "4. Use `excalidraw_delete_element` to remove elements\n"
            "5. Use `excalidraw_batch_create` for multiple elements at once\n"
            "6. Use `excalidraw_group_elements` to group related elements\n"
            "7. Use `excalidraw_align_elements` or `excalidraw_distribute_elements` for layout\n\n"
            "The user can view the canvas at the viewer URL in real-time.\n"
            "Any changes made via these tools will be immediately visible in the browser."
        )
        
        return ToolResult(
            llm_content=(
                f"Successfully initialized Excalidraw session '{canvas_name}'.\n\n"
                f"Session ID: {session_id}\n"
                f"Viewer URL: {viewer_url}\n"
                f"Current elements on canvas: {element_count}\n"
                f"WebSocket clients connected: {websocket_clients}\n\n"
                f"{next_steps}"
            ),
            user_display_content=[session_metadata],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(self, canvas_name: str = ""):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(tool_input={"canvas_name": canvas_name})
