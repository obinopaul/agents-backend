"""Design diagram edit tool for modifying diagrams using ID-based operations."""

import xml.etree.ElementTree as ET
from typing import Any, List, Dict
import httpx

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "design_edit_diagram"
DISPLAY_NAME = "Edit diagram by ID-based operations"

DESCRIPTION = """Edit the current diagram by ID-based operations (update/add/delete cells).

## IMPORTANT
You MUST call `design_get_diagram` BEFORE this tool to:
1. See current cell IDs and structure
2. Ensure you have the latest state including user's manual edits

Skipping `design_get_diagram` may cause user's changes to be LOST.

## Operations

### add - Add a new cell
```json
{
    "operation": "add",
    "cell_id": "shape-1",
    "new_xml": "<mxCell id=\"shape-1\" value=\"Hello\" style=\"rounded=0;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"100\" y=\"100\" width=\"120\" height=\"60\" as=\"geometry\"/></mxCell>"
}
```

### update - Replace an existing cell
```json
{
    "operation": "update",
    "cell_id": "3",
    "new_xml": "<mxCell id=\"3\" value=\"New Label\" style=\"rounded=1;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"100\" y=\"100\" width=\"120\" height=\"60\" as=\"geometry\"/></mxCell>"
}
```

### delete - Remove a cell by ID
```json
{
    "operation": "delete",
    "cell_id": "rect-1"
}
```

## Rules
- For add/update, `new_xml` must be a complete mxCell element including mxGeometry
- The `id` attribute in `new_xml` must match `cell_id`
- Root cells (id="0" and id="1") cannot be deleted
- Deleting a cell cascades to its children and connected edges

## Example - Multiple Operations
```json
{
    "operations": [
        {"operation": "add", "cell_id": "box1", "new_xml": "<mxCell id=\"box1\" value=\"Box 1\" .../>"},
        {"operation": "update", "cell_id": "3", "new_xml": "<mxCell id=\"3\" value=\"Updated\" .../>"},
        {"operation": "delete", "cell_id": "old-shape"}
    ]
}
```
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {
            "type": "string",
            "description": "The session ID from design_init. Required.",
        },
        "operations": {
            "type": "array",
            "description": "Array of operations to apply (add/update/delete)",
            "items": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "update", "delete"],
                        "description": "Operation type",
                    },
                    "cell_id": {
                        "type": "string",
                        "description": "The id of the mxCell to operate on",
                    },
                    "new_xml": {
                        "type": "string",
                        "description": "Complete mxCell XML (required for add/update)",
                    },
                },
                "required": ["operation", "cell_id"],
            },
        },
    },
    "required": ["session_id", "operations"],
}


class DesignEditTool(BaseTool):
    """Tool for editing diagrams by ID-based operations."""
    
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
        """Execute the diagram edit operations."""
        session_id = tool_input.get("session_id", "")
        operations = tool_input.get("operations", [])
        
        # Validate inputs
        if not session_id:
            return ToolResult(
                llm_content="Error: session_id is required. Call design_init first to get a session ID.",
                user_display_content="Missing session_id",
                is_error=True,
            )
        
        if not operations:
            return ToolResult(
                llm_content="Error: operations array is required and must not be empty.",
                user_display_content="No operations provided",
                is_error=True,
            )
        
        try:
            # Get current XML from Design MCP Server
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.DESIGN_MCP_URL}/api/state",
                    params={"sessionId": session_id}
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        llm_content=f"Failed to get current diagram: HTTP {response.status_code}",
                        user_display_content="Failed to get current diagram",
                        is_error=True,
                    )
                
                result = response.json()
                current_xml = result.get("xml", "")
        
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
                llm_content=f"Error getting current diagram: {str(e)}",
                user_display_content="Failed to get current diagram",
                is_error=True,
            )
        
        if not current_xml:
            return ToolResult(
                llm_content=(
                    "Error: No diagram to edit. Please create a diagram first with design_create_diagram."
                ),
                user_display_content="No diagram to edit",
                is_error=True,
            )
        
        # Apply operations to XML
        new_xml, errors = self._apply_operations(current_xml, operations)
        
        if new_xml == current_xml and errors:
            # All operations failed
            error_text = "\n".join([f"- {e['type']} {e['cell_id']}: {e['message']}" for e in errors])
            return ToolResult(
                llm_content=f"All operations failed:\n{error_text}",
                user_display_content="All operations failed",
                is_error=True,
            )
        
        try:
            # Push updated XML to Design MCP Server
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.DESIGN_MCP_URL}/api/state",
                    json={
                        "sessionId": session_id,
                        "xml": new_xml,
                    }
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        llm_content=f"Failed to save edited diagram: HTTP {response.status_code}",
                        user_display_content="Failed to save diagram",
                        is_error=True,
                    )
                
                result = response.json()
                version = result.get("version", 1)
        
        except Exception as e:
            return ToolResult(
                llm_content=f"Error saving diagram: {str(e)}",
                user_display_content="Failed to save diagram",
                is_error=True,
            )
        
        # Build response
        success_msg = f"Diagram edited successfully!\n\nApplied {len(operations)} operation(s).\nVersion: {version}"
        
        if errors:
            error_text = "\n".join([f"- {e['type']} {e['cell_id']}: {e['message']}" for e in errors])
            success_msg += f"\n\nWarnings:\n{error_text}"
        
        return ToolResult(
            llm_content=success_msg,
            user_display_content={
                "type": "design_edit_result",
                "session_id": session_id,
                "version": version,
                "operations_count": len(operations),
                "errors": errors,
            },
            is_error=False,
        )
    
    def _apply_operations(self, xml_content: str, operations: List[Dict]) -> tuple:
        """Apply diagram operations using Python's xml.etree.ElementTree.
        
        Returns (result_xml, errors_list)
        """
        errors = []
        
        try:
            # Parse the XML - handle mxfile wrapper
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return xml_content, [{"type": "parse", "cell_id": "", "message": f"XML parse error: {e}"}]
        
        # Find the mxGraphModel root element
        # Structure: mxfile > diagram > mxGraphModel > root
        graph_root = root.find(".//root")
        if graph_root is None:
            return xml_content, [{"type": "parse", "cell_id": "", "message": "Could not find <root> element in XML"}]
        
        # Build cell ID map
        cell_map = {}
        for cell in graph_root.findall("mxCell"):
            cell_id = cell.get("id")
            if cell_id:
                cell_map[cell_id] = cell
        
        # Process each operation
        for op in operations:
            op_type = op.get("operation")
            cell_id = op.get("cell_id")
            new_xml = op.get("new_xml", "")
            
            if op_type == "add":
                if cell_id in cell_map:
                    errors.append({
                        "type": "add",
                        "cell_id": cell_id,
                        "message": f"Cell with id=\"{cell_id}\" already exists"
                    })
                    continue
                
                if not new_xml:
                    errors.append({
                        "type": "add",
                        "cell_id": cell_id,
                        "message": "new_xml is required for add operation"
                    })
                    continue
                
                try:
                    # Parse the new cell
                    new_cell = ET.fromstring(new_xml)
                    if new_cell.tag != "mxCell":
                        errors.append({
                            "type": "add",
                            "cell_id": cell_id,
                            "message": "new_xml must be an mxCell element"
                        })
                        continue
                    
                    # Validate ID matches
                    new_id = new_cell.get("id")
                    if new_id != cell_id:
                        errors.append({
                            "type": "add",
                            "cell_id": cell_id,
                            "message": f"ID mismatch: cell_id is \"{cell_id}\" but new_xml has id=\"{new_id}\""
                        })
                        continue
                    
                    # Add to graph root
                    graph_root.append(new_cell)
                    cell_map[cell_id] = new_cell
                    
                except ET.ParseError as e:
                    errors.append({
                        "type": "add",
                        "cell_id": cell_id,
                        "message": f"Invalid XML: {e}"
                    })
            
            elif op_type == "update":
                if cell_id not in cell_map:
                    errors.append({
                        "type": "update",
                        "cell_id": cell_id,
                        "message": f"Cell with id=\"{cell_id}\" not found"
                    })
                    continue
                
                if not new_xml:
                    errors.append({
                        "type": "update",
                        "cell_id": cell_id,
                        "message": "new_xml is required for update operation"
                    })
                    continue
                
                try:
                    new_cell = ET.fromstring(new_xml)
                    if new_cell.tag != "mxCell":
                        errors.append({
                            "type": "update",
                            "cell_id": cell_id,
                            "message": "new_xml must be an mxCell element"
                        })
                        continue
                    
                    new_id = new_cell.get("id")
                    if new_id != cell_id:
                        errors.append({
                            "type": "update",
                            "cell_id": cell_id,
                            "message": f"ID mismatch: cell_id is \"{cell_id}\" but new_xml has id=\"{new_id}\""
                        })
                        continue
                    
                    # Find and replace the existing cell
                    old_cell = cell_map[cell_id]
                    index = list(graph_root).index(old_cell)
                    graph_root.remove(old_cell)
                    graph_root.insert(index, new_cell)
                    cell_map[cell_id] = new_cell
                    
                except ET.ParseError as e:
                    errors.append({
                        "type": "update",
                        "cell_id": cell_id,
                        "message": f"Invalid XML: {e}"
                    })
            
            elif op_type == "delete":
                # Protect root cells
                if cell_id in ("0", "1"):
                    errors.append({
                        "type": "delete",
                        "cell_id": cell_id,
                        "message": f"Cannot delete root cell \"{cell_id}\""
                    })
                    continue
                
                if cell_id not in cell_map:
                    # Cell might have been cascade-deleted, skip silently
                    continue
                
                # Cascade delete: collect all cells to delete
                cells_to_delete = set()
                self._collect_descendants(graph_root, cell_id, cells_to_delete, cell_map)
                
                # Also collect edges referencing deleted cells
                for cid in list(cells_to_delete):
                    for cell in graph_root.findall("mxCell"):
                        if cell.get("source") == cid or cell.get("target") == cid:
                            edge_id = cell.get("id")
                            if edge_id and edge_id not in ("0", "1"):
                                self._collect_descendants(graph_root, edge_id, cells_to_delete, cell_map)
                
                # Delete all collected cells
                for cid in cells_to_delete:
                    if cid in cell_map:
                        cell = cell_map[cid]
                        graph_root.remove(cell)
                        del cell_map[cid]
        
        # Serialize back to string
        result = ET.tostring(root, encoding="unicode")
        return result, errors
    
    def _collect_descendants(self, graph_root, cell_id: str, cells_to_delete: set, cell_map: dict):
        """Recursively collect cell and all its descendants."""
        if cell_id in cells_to_delete:
            return
        cells_to_delete.add(cell_id)
        
        # Find children (cells where parent == cell_id)
        for cell in graph_root.findall("mxCell"):
            if cell.get("parent") == cell_id:
                child_id = cell.get("id")
                if child_id and child_id not in ("0", "1"):
                    self._collect_descendants(graph_root, child_id, cells_to_delete, cell_map)
    
    async def execute_mcp_wrapper(
        self,
        session_id: str,
        operations: List[Dict],
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "session_id": session_id,
                "operations": operations,
            }
        )
