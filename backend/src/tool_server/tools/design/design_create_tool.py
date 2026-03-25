"""Design diagram creation tool for generating new diagrams from XML."""

from typing import Any
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "design_create_diagram"
DISPLAY_NAME = "Create a new draw.io diagram"

DESCRIPTION = """Create a NEW diagram from mxGraphModel XML.

## Overview
This tool creates a complete diagram from scratch using draw.io's mxGraphModel XML format.
The diagram will immediately appear in the browser viewer.

## When to Use
- Creating a new diagram from scratch
- Replacing the current diagram with a completely different one
- Major structural changes that require regenerating the diagram

## When to Use `design_edit_diagram` Instead
- Small modifications to existing diagram
- Adding/removing individual elements
- Changing labels, colors, or positions

## XML FORMAT

You MUST provide the `xml` argument containing the mxGraphModel structure.
The root cells (id="0" and id="1") are required and will be added automatically if missing.

```xml
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    <!-- Your shapes and connectors start from id="2" -->
    <mxCell id="2" value="Shape" style="rounded=1;" vertex="1" parent="1">
      <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
    </mxCell>
  </root>
</mxGraphModel>
```

## Layout Guidelines
- Keep all elements within x=0-800, y=0-600 (single page viewport)
- Start from margins (x=40, y=40), keep elements grouped closely
- Use unique IDs starting from "2" (0 and 1 are reserved)
- Set parent="1" for top-level shapes
- Space shapes 150-200px apart for clear edge routing

## Edge Routing Rules
- Never let multiple edges share the same path - use different exitY/entryY values
- For bidirectional connections (A↔B), use OPPOSITE sides
- Always specify exitX, exitY, entryX, entryY explicitly in edge style
- Route edges AROUND obstacles using waypoints

## Common Styles
- Shapes: `rounded=1;fillColor=#hex;strokeColor=#hex`
- Edges: `endArrow=classic;edgeStyle=orthogonalEdgeStyle;curved=1`
- Text: `fontSize=14;fontStyle=1 (bold);align=center`

## Cloud Architecture Icons
For AWS/GCP/Azure diagrams, the AI models have been trained on these icon sets.
Specify in your prompt: "Use AWS icons" or "Use GCP icons" etc.
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {
            "type": "string",
            "description": "The session ID from design_init. Required.",
        },
        "xml": {
            "type": "string",
            "description": "The complete mxGraphModel XML for the diagram. REQUIRED.",
        },
    },
    "required": ["session_id", "xml"],
}


class DesignCreateTool(BaseTool):
    """Tool for creating new diagrams from XML."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False
    
    # Design MCP Server configuration
    DESIGN_MCP_PORT = 6002
    DESIGN_MCP_URL = f"http://localhost:{DESIGN_MCP_PORT}"
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the diagram creation."""
        session_id = tool_input.get("session_id", "")
        xml = tool_input.get("xml", "")
        
        # Validate inputs
        if not session_id:
            return ToolResult(
                llm_content="Error: session_id is required. Call design_init first to get a session ID.",
                user_display_content="Missing session_id",
                is_error=True,
            )
        
        if not xml:
            return ToolResult(
                llm_content="Error: xml is required. Provide the mxGraphModel XML content.",
                user_display_content="Missing XML content",
                is_error=True,
            )
        
        # Ensure XML has proper mxfile wrapper if needed
        wrapped_xml = self._wrap_with_mxfile(xml)
        
        try:
            # Send XML to Design MCP Server via HTTP API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.DESIGN_MCP_URL}/api/state",
                    json={
                        "sessionId": session_id,
                        "xml": wrapped_xml,
                    }
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        llm_content=f"Failed to create diagram: HTTP {response.status_code}",
                        user_display_content="Failed to create diagram",
                        is_error=True,
                    )
                
                result = response.json()
                version = result.get("version", 1)
        
        except httpx.ConnectError:
            return ToolResult(
                llm_content=(
                    "Failed to connect to Design MCP Server on port 6002. "
                    "The server may not be running."
                ),
                user_display_content="Design MCP Server not available",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                llm_content=f"Error creating diagram: {str(e)}",
                user_display_content="Failed to create diagram",
                is_error=True,
            )
        
        # Build response
        viewer_url = f"{self.DESIGN_MCP_URL}/?mcp={session_id}"
        
        return ToolResult(
            llm_content=(
                f"Diagram created successfully!\n\n"
                f"Session ID: {session_id}\n"
                f"Version: {version}\n"
                f"XML length: {len(wrapped_xml)} characters\n\n"
                f"The diagram is now visible at: {viewer_url}\n\n"
                f"Next steps:\n"
                f"- Use `design_edit_diagram` to make modifications\n"
                f"- Use `design_get_diagram` to retrieve current state\n"
                f"- Use `design_export_diagram` to save to a .drawio file"
            ),
            user_display_content={
                "type": "design_create_result",
                "session_id": session_id,
                "version": version,
                "xml_length": len(wrapped_xml),
            },
            is_error=False,
        )
    
    def _wrap_with_mxfile(self, xml: str) -> str:
        """Wrap XML content with the full mxfile structure if needed.
        
        Ensures root cells (id="0" and id="1") are present.
        """
        ROOT_CELLS = '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        
        if not xml or not xml.strip():
            return f'<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root>{ROOT_CELLS}</root></mxGraphModel></diagram></mxfile>'
        
        # Already has full structure
        if "<mxfile" in xml:
            return xml
        
        # Has mxGraphModel but not mxfile
        if "<mxGraphModel" in xml:
            return f'<mxfile><diagram name="Page-1" id="page-1">{xml}</diagram></mxfile>'
        
        # Has <root> wrapper - extract inner content
        content = xml
        if "<root>" in xml:
            content = xml.replace("<root>", "").replace("</root>", "").strip()
        
        # Remove any existing root cells from content (LLM shouldn't include them)
        import re
        content = re.sub(r'<mxCell[^>]*\bid=["\']0["\'][^>]*(?:/>|></mxCell>)', '', content)
        content = re.sub(r'<mxCell[^>]*\bid=["\']1["\'][^>]*(?:/>|></mxCell>)', '', content)
        content = content.strip()
        
        return f'<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root>{ROOT_CELLS}{content}</root></mxGraphModel></diagram></mxfile>'
    
    async def execute_mcp_wrapper(
        self,
        session_id: str,
        xml: str,
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "session_id": session_id,
                "xml": xml,
            }
        )
