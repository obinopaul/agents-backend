"""Unit tests for design tools.

These tests verify the design tools work correctly by mocking the HTTP
communication with the Design MCP Server.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

# Mock httpx before importing tools
pytest.importorskip("httpx")

from backend.src.tool_server.tools.design.design_init_tool import DesignInitTool
from backend.src.tool_server.tools.design.design_create_tool import DesignCreateTool
from backend.src.tool_server.tools.design.design_get_tool import DesignGetTool
from backend.src.tool_server.tools.design.design_edit_tool import DesignEditTool
from backend.src.tool_server.tools.design.design_export_tool import DesignExportTool


@pytest.fixture
def workspace_manager():
    """Create a mock workspace manager."""
    manager = MagicMock()
    manager.get_workspace_path.return_value = "/workspace"
    return manager


class TestDesignInitTool:
    """Tests for DesignInitTool."""
    
    @pytest.mark.asyncio
    async def test_init_success(self, workspace_manager):
        """Test successful session initialization."""
        tool = DesignInitTool(workspace_manager)
        
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": 1}
        
        # Patch httpx where it's imported in the tool module
        with patch("backend.src.tool_server.tools.design.design_init_tool.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await tool.execute({"diagram_name": "test_diagram"})
        
        assert not result.is_error
        assert "session id" in result.llm_content.lower()
        assert "viewer url" in result.llm_content.lower()
    
    @pytest.mark.asyncio
    async def test_init_connection_error(self, workspace_manager):
        """Test handling of connection error."""
        import httpx
        tool = DesignInitTool(workspace_manager)
        
        with patch("backend.src.tool_server.tools.design.design_init_tool.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await tool.execute({})
        
        assert result.is_error
        assert "connect" in result.llm_content.lower()


class TestDesignCreateTool:
    """Tests for DesignCreateTool."""
    
    @pytest.mark.asyncio
    async def test_create_success(self, workspace_manager):
        """Test successful diagram creation."""
        tool = DesignCreateTool(workspace_manager)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": 1}
        
        with patch("backend.src.tool_server.tools.design.design_create_tool.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await tool.execute({
                "session_id": "mcp-test123",
                "xml": '<mxCell id="2" value="Test" vertex="1" parent="1"/>'
            })
        
        assert not result.is_error
        assert "created" in result.llm_content.lower()
    
    @pytest.mark.asyncio
    async def test_create_missing_session(self, workspace_manager):
        """Test error when session_id is missing."""
        tool = DesignCreateTool(workspace_manager)
        
        result = await tool.execute({
            "xml": '<mxCell id="2" value="Test" vertex="1" parent="1"/>'
        })
        
        assert result.is_error
        assert "session_id" in result.llm_content.lower()
    
    @pytest.mark.asyncio
    async def test_create_missing_xml(self, workspace_manager):
        """Test error when xml is missing."""
        tool = DesignCreateTool(workspace_manager)
        
        result = await tool.execute({
            "session_id": "mcp-test123"
        })
        
        assert result.is_error
        assert "xml" in result.llm_content.lower()


class TestDesignGetTool:
    """Tests for DesignGetTool."""
    
    @pytest.mark.asyncio
    async def test_get_success(self, workspace_manager):
        """Test successful diagram retrieval."""
        tool = DesignGetTool(workspace_manager)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "xml": '<mxfile><diagram><mxGraphModel><root><mxCell id="0"/></root></mxGraphModel></diagram></mxfile>',
            "version": 1
        }
        
        with patch("backend.src.tool_server.tools.design.design_get_tool.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await tool.execute({"session_id": "mcp-test123"})
        
        assert not result.is_error
        assert "mxfile" in result.llm_content.lower()


class TestDesignEditTool:
    """Tests for DesignEditTool."""
    
    @pytest.mark.asyncio
    async def test_add_operation(self, workspace_manager):
        """Test add operation."""
        tool = DesignEditTool(workspace_manager)
        
        current_xml = '<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>'
        
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"xml": current_xml, "version": 1}
        
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"version": 2}
        
        with patch("backend.src.tool_server.tools.design.design_edit_tool.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_get_response
            mock_instance.post.return_value = mock_post_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await tool.execute({
                "session_id": "mcp-test123",
                "operations": [
                    {
                        "operation": "add",
                        "cell_id": "box1",
                        "new_xml": '<mxCell id="box1" value="Test" style="rounded=1;" vertex="1" parent="1"><mxGeometry x="100" y="100" width="120" height="60" as="geometry"/></mxCell>'
                    }
                ]
            })
        
        assert not result.is_error
        assert "edited" in result.llm_content.lower() or "version" in result.llm_content.lower()
    
    def test_xml_operations_add(self, workspace_manager):
        """Test _apply_operations add logic."""
        tool = DesignEditTool(workspace_manager)
        
        xml = '<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>'
        operations = [
            {
                "operation": "add",
                "cell_id": "new-cell",
                "new_xml": '<mxCell id="new-cell" value="New" vertex="1" parent="1"/>'
            }
        ]
        
        result_xml, errors = tool._apply_operations(xml, operations)
        
        assert "new-cell" in result_xml
        assert len(errors) == 0
    
    def test_xml_operations_delete(self, workspace_manager):
        """Test _apply_operations delete logic."""
        tool = DesignEditTool(workspace_manager)
        
        xml = '<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="to-delete" value="Delete me" vertex="1" parent="1"/></root></mxGraphModel></diagram></mxfile>'
        operations = [
            {
                "operation": "delete",
                "cell_id": "to-delete"
            }
        ]
        
        result_xml, errors = tool._apply_operations(xml, operations)
        
        assert "to-delete" not in result_xml
        assert len(errors) == 0
    
    def test_cannot_delete_root_cells(self, workspace_manager):
        """Test that root cells (0, 1) cannot be deleted."""
        tool = DesignEditTool(workspace_manager)
        
        xml = '<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>'
        operations = [
            {"operation": "delete", "cell_id": "0"},
            {"operation": "delete", "cell_id": "1"}
        ]
        
        result_xml, errors = tool._apply_operations(xml, operations)
        
        # Root cells should still exist
        assert 'id="0"' in result_xml
        assert 'id="1"' in result_xml
        # Should have 2 errors for attempting to delete root cells
        assert len(errors) == 2


class TestDesignExportTool:
    """Tests for DesignExportTool."""
    
    @pytest.mark.asyncio
    async def test_export_success(self, workspace_manager, tmp_path):
        """Test successful diagram export."""
        workspace_manager.get_workspace_path.return_value = str(tmp_path)
        tool = DesignExportTool(workspace_manager)
        
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "xml": '<mxfile><diagram><mxGraphModel><root></root></mxGraphModel></diagram></mxfile>',
            "version": 1
        }
        
        with patch("backend.src.tool_server.tools.design.design_export_tool.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_get_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await tool.execute({
                "session_id": "mcp-test123",
                "file_path": "test-diagram"
            })
        
        assert not result.is_error
        assert "exported" in result.llm_content.lower()
        
        # Verify file was created
        expected_path = tmp_path / "diagrams" / "test-diagram.drawio"
        assert expected_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
