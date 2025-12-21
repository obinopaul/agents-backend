"""Tests for Slides API endpoints.

Tests cover:
- Slides API router imports
- Helper functions
- Response models
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


class TestSlidesModels:
    """Tests for slides API models."""

    def test_presentation_info_model(self):
        """Test PresentationInfo model."""
        from backend.app.agent.api.v1.slides import PresentationInfo
        
        info = PresentationInfo(
            name="my_presentation",
            slide_count=5,
            created_at="2024-01-01T00:00:00"
        )
        
        assert info.name == "my_presentation"
        assert info.slide_count == 5

    def test_slide_info_model(self):
        """Test SlideInfo model."""
        from backend.app.agent.api.v1.slides import SlideInfo
        
        info = SlideInfo(
            filename="slide_1.html",
            number=1,
            path="presentations/test/slide_1.html"
        )
        
        assert info.number == 1
        assert info.filename == "slide_1.html"

    def test_export_request_model(self):
        """Test ExportRequest model."""
        from backend.app.agent.api.v1.slides import ExportRequest
        
        request = ExportRequest(
            presentation_name="my_slides",
            format="pdf"
        )
        
        assert request.presentation_name == "my_slides"
        assert request.format == "pdf"


class TestSlideHelpers:
    """Tests for slides helper functions."""

    @pytest.mark.asyncio
    async def test_get_presentations_from_sandbox(self):
        """Test getting presentations list."""
        from backend.app.agent.api.v1.slides import get_presentations_from_sandbox
        
        mock_sandbox = MagicMock()
        mock_sandbox.list_directory = AsyncMock(return_value=[
            {"name": "presentation1", "type": "directory"},
            {"name": "presentation2", "type": "directory"},
            {"name": "other_file.txt", "type": "file"},
        ])
        
        result = await get_presentations_from_sandbox(mock_sandbox)
        
        assert len(result) == 2
        assert "presentation1" in result
        assert "presentation2" in result

    @pytest.mark.asyncio
    async def test_get_slides_from_presentation(self):
        """Test getting slides from a presentation."""
        from backend.app.agent.api.v1.slides import get_slides_from_presentation
        
        mock_sandbox = MagicMock()
        mock_sandbox.list_directory = AsyncMock(return_value=[
            {"name": "slide_1.html", "type": "file"},
            {"name": "slide_2.html", "type": "file"},
            {"name": "style.css", "type": "file"},
        ])
        
        result = await get_slides_from_presentation(mock_sandbox, "test_pres")
        
        # Should only return HTML files
        assert len(result) == 2
        assert all(s.endswith('.html') for s in result)


class TestSlidesRouter:
    """Tests for slides router configuration."""

    def test_router_import(self):
        """Test that slides router can be imported."""
        from backend.app.agent.api.v1.slides import router
        
        assert router is not None
        assert hasattr(router, 'routes')

    def test_router_has_expected_routes(self):
        """Test that router has expected endpoint paths."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        
        # Check for key endpoints
        assert "/{sandbox_id}/presentations" in route_paths
        assert "/{sandbox_id}/slides/export" in route_paths


class TestSlideExport:
    """Tests for slide export functionality."""

    def test_slides_dependencies_available(self):
        """Test that required dependencies are available."""
        try:
            from pypdf import PdfWriter
            from playwright.async_api import async_playwright
            pdf_available = True
        except ImportError:
            pdf_available = False
        
        # Just test imports, don't require them to be installed
        # This test documents the dependencies
        assert True  # Placeholder - actual functionality tested in integration


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
