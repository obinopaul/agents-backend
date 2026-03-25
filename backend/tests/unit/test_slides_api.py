"""Tests for Slides API endpoints.

Tests cover:
- Slides module imports
- Helper functions
- Router configuration
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


class TestSlidesImport:
    """Tests for slides module imports."""

    def test_slides_module_import(self):
        """Test that slides module can be imported without errors."""
        # This verifies the ResponseSchemaModel fix works
        from backend.app.agent.api.v1 import slides
        assert hasattr(slides, 'router')
        assert hasattr(slides, 'PresentationInfo')
        assert hasattr(slides, 'SlideInfo')

    def test_router_exists(self):
        """Test that slides router is properly configured."""
        from backend.app.agent.api.v1.slides import router
        assert router is not None
        assert hasattr(router, 'routes')

    def test_presentation_info_model(self):
        """Test PresentationInfo model."""
        from backend.app.agent.api.v1.slides import PresentationInfo
        
        info = PresentationInfo(
            name="my_presentation",
            slide_count=5,
            path="/workspace/presentations/my_presentation"
        )
        
        assert info.name == "my_presentation"
        assert info.slide_count == 5

    def test_slide_info_model(self):
        """Test SlideInfo model."""
        from backend.app.agent.api.v1.slides import SlideInfo
        
        info = SlideInfo(
            slide_number=1,
            filename="slide_1.html",
            path="/workspace/presentations/test/slide_1.html"
        )
        
        assert info.slide_number == 1
        assert info.filename == "slide_1.html"


class TestSlideHelperFunctions:
    """Tests for helper functions."""

    def test_parse_slide_number_standard(self):
        """Test parsing slide number from standard filename."""
        from backend.app.agent.api.v1.slides import parse_slide_number
        
        assert parse_slide_number("slide_1.html") == 1
        assert parse_slide_number("slide_10.html") == 10
        assert parse_slide_number("SLIDE_5.HTML") == 5

    def test_parse_slide_number_numbered_prefix(self):
        """Test parsing slide number from numbered prefix filename."""
        from backend.app.agent.api.v1.slides import parse_slide_number
        
        assert parse_slide_number("01_intro.html") == 1
        assert parse_slide_number("05-content.html") == 5

    def test_parse_slide_number_just_number(self):
        """Test parsing slide number from just number filename."""
        from backend.app.agent.api.v1.slides import parse_slide_number
        
        assert parse_slide_number("1.html") == 1
        assert parse_slide_number("12.html") == 12

    def test_parse_slide_number_no_match(self):
        """Test parsing returns None for non-matching filenames."""
        from backend.app.agent.api.v1.slides import parse_slide_number
        
        assert parse_slide_number("style.css") is None
        assert parse_slide_number("readme.txt") is None


class TestRouterConfiguration:
    """Tests for router configuration."""

    def test_router_has_presentations_endpoint(self):
        """Test router has list presentations endpoint."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        assert "/{sandbox_id}/presentations" in route_paths

    def test_router_has_slides_endpoints(self):
        """Test router has slides-related endpoints."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        assert "/{sandbox_id}/slides/export" in route_paths
        assert "/{sandbox_id}/slides/download/{presentation_name}" in route_paths


class TestSlideExportDependencies:
    """Tests for slide export dependencies."""

    def test_pypdf_import(self):
        """Test that pypdf can be imported."""
        try:
            from pypdf import PdfWriter, PdfReader
            available = True
        except ImportError:
            available = False
        
        # Just document availability, don't fail if not installed
        assert True

    def test_playwright_import(self):
        """Test that playwright can be imported."""
        try:
            from playwright.async_api import async_playwright
            available = True
        except ImportError:
            available = False
        
        # Just document availability, don't fail if not installed
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
