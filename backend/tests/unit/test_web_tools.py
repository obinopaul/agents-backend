"""
Unit tests for Web tools.

Tests WebSearchTool, WebVisitTool, ImageSearchTool, and other web-related tools.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWebSearchTool:
    """Test WebSearchTool."""

    @pytest.fixture
    def mock_credential(self):
        """Create mock credentials."""
        return {
            "user_api_key": "test_key",
            "session_id": "test_session",
            "serper_api_key": "test_serper_key"
        }

    @pytest.mark.asyncio
    async def test_web_search_success(self, mock_credential):
        """Test successful web search."""
        from backend.src.tool_server.tools.web.web_search import WebSearchTool
        
        tool = WebSearchTool(mock_credential)
        
        mock_response = {
            "organic": [
                {"title": "Result 1", "link": "https://example.com", "snippet": "Description 1"},
                {"title": "Result 2", "link": "https://example2.com", "snippet": "Description 2"}
            ]
        }
        
        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await tool.execute({
                "query": "test search query"
            })
        
        assert result is not None
        assert result.is_error is False or result.is_error is None

    @pytest.mark.asyncio
    async def test_web_search_empty_query(self, mock_credential):
        """Test web search with empty query."""
        from backend.src.tool_server.tools.web.web_search import WebSearchTool
        
        tool = WebSearchTool(mock_credential)
        
        result = await tool.execute({
            "query": ""
        })
        
        # Should handle empty query gracefully
        assert result is not None

    def test_web_search_tool_properties(self, mock_credential):
        """Test WebSearchTool has correct properties."""
        from backend.src.tool_server.tools.web.web_search import WebSearchTool
        
        tool = WebSearchTool(mock_credential)
        
        assert tool.name is not None
        assert tool.description is not None
        assert tool.input_schema is not None
        assert "query" in str(tool.input_schema)


class TestWebVisitTool:
    """Test WebVisitTool."""

    @pytest.fixture
    def mock_credential(self):
        """Create mock credentials."""
        return {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_web_visit_success(self, mock_credential):
        """Test successful web visit."""
        from backend.src.tool_server.tools.web.web_visit import WebVisitTool
        
        tool = WebVisitTool(mock_credential)
        
        mock_response = {
            "title": "Test Page",
            "content": "Page content here"
        }
        
        with patch.object(tool, '_visit', new_callable=AsyncMock) as mock_visit:
            mock_visit.return_value = mock_response
            
            result = await tool.execute({
                "url": "https://example.com"
            })
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_web_visit_invalid_url(self, mock_credential):
        """Test web visit with invalid URL."""
        from backend.src.tool_server.tools.web.web_visit import WebVisitTool
        
        tool = WebVisitTool(mock_credential)
        
        with patch.object(tool, '_visit', new_callable=AsyncMock) as mock_visit:
            mock_visit.side_effect = Exception("Invalid URL")
            
            result = await tool.execute({
                "url": "not-a-valid-url"
            })
        
        # Should handle error gracefully
        assert result is not None

    def test_web_visit_tool_properties(self, mock_credential):
        """Test WebVisitTool has correct properties."""
        from backend.src.tool_server.tools.web.web_visit import WebVisitTool
        
        tool = WebVisitTool(mock_credential)
        
        assert tool.name is not None
        assert tool.description is not None
        assert tool.input_schema is not None


class TestWebVisitCompressTool:
    """Test WebVisitCompressTool."""

    @pytest.fixture
    def mock_credential(self):
        """Create mock credentials."""
        return {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_web_visit_compress_success(self, mock_credential):
        """Test successful web visit with compression."""
        from backend.src.tool_server.tools.web.web_visit_compress import WebVisitCompressTool
        
        tool = WebVisitCompressTool(mock_credential)
        
        with patch.object(tool, '_visit_and_compress', new_callable=AsyncMock) as mock_visit:
            mock_visit.return_value = "Compressed content"
            
            result = await tool.execute({
                "url": "https://example.com",
                "query": "What is this page about?"
            })
        
        assert result is not None


class TestImageSearchTool:
    """Test ImageSearchTool."""

    @pytest.fixture
    def mock_credential(self):
        """Create mock credentials."""
        return {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_image_search_success(self, mock_credential):
        """Test successful image search."""
        from backend.src.tool_server.tools.web.image_search import ImageSearchTool
        
        tool = ImageSearchTool(mock_credential)
        
        mock_response = {
            "images": [
                {"url": "https://example.com/image1.jpg", "title": "Image 1"},
                {"url": "https://example.com/image2.jpg", "title": "Image 2"}
            ]
        }
        
        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await tool.execute({
                "query": "cute cats"
            })
        
        assert result is not None

    def test_image_search_tool_properties(self, mock_credential):
        """Test ImageSearchTool has correct properties."""
        from backend.src.tool_server.tools.web.image_search import ImageSearchTool
        
        tool = ImageSearchTool(mock_credential)
        
        assert tool.name is not None
        assert tool.description is not None
        assert tool.input_schema is not None


class TestReadRemoteImageTool:
    """Test ReadRemoteImageTool."""

    @pytest.mark.asyncio
    async def test_read_remote_image_success(self):
        """Test successful remote image read."""
        from backend.src.tool_server.tools.web.read_remote_image import ReadRemoteImageTool
        
        tool = ReadRemoteImageTool()
        
        # Mock HTTP response with image data
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_response.headers = {"content-type": "image/png"}
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock()
            
            result = await tool.execute({
                "url": "https://example.com/image.png"
            })
        
        assert result is not None

    def test_read_remote_image_properties(self):
        """Test ReadRemoteImageTool has correct properties."""
        from backend.src.tool_server.tools.web.read_remote_image import ReadRemoteImageTool
        
        tool = ReadRemoteImageTool()
        
        assert tool.name is not None
        assert tool.description is not None
        assert tool.read_only is True


class TestWebBatchSearchTool:
    """Test WebBatchSearchTool."""

    @pytest.fixture
    def mock_credential(self):
        """Create mock credentials."""
        return {
            "user_api_key": "test_key",
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_web_batch_search_success(self, mock_credential):
        """Test successful batch search."""
        from backend.src.tool_server.tools.web.web_batch_search import WebBatchSearchTool
        
        tool = WebBatchSearchTool(mock_credential)
        
        mock_results = [
            {"query": "query1", "results": [{"title": "Result 1"}]},
            {"query": "query2", "results": [{"title": "Result 2"}]}
        ]
        
        with patch.object(tool, '_batch_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            
            result = await tool.execute({
                "queries": ["query1", "query2"]
            })
        
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
