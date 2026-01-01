"""Tests for Slides API endpoints.

Tests the new /db/ database-backed endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime


class TestDBPresentationsEndpoint:
    """Tests for GET /slides/db/presentations endpoint."""

    def test_list_db_presentations_route_exists(self):
        """Test that the /db/presentations route exists."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        assert "/db/presentations" in route_paths

    @pytest.mark.asyncio
    async def test_list_db_presentations_handler(self):
        """Test list_db_presentations function returns correct format."""
        from backend.app.agent.api.v1.slides import list_db_presentations
        
        # Create mock db session
        mock_db = AsyncMock()
        
        # Mock SlideService response
        with patch('backend.app.agent.api.v1.slides.SlideService') as mock_service:
            mock_service.get_thread_presentations = AsyncMock(return_value=MagicMock(
                thread_id="test-123",
                presentations=[],
                total=0,
            ))
            
            # Call the handler
            result = await list_db_presentations(
                thread_id="test-123",
                db=mock_db,
            )
            
            assert result is not None


class TestDBSlideEndpoint:
    """Tests for GET /slides/db/slide endpoint."""

    def test_get_db_slide_route_exists(self):
        """Test that the /db/slide route exists."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        assert "/db/slide" in route_paths

    @pytest.mark.asyncio
    async def test_get_db_slide_not_found(self):
        """Test 404 response when slide not found."""
        from backend.app.agent.api.v1.slides import get_db_slide
        from fastapi import HTTPException
        
        mock_db = AsyncMock()
        
        with patch('backend.app.agent.api.v1.slides.SlideService') as mock_service:
            mock_service.get_slide_content = AsyncMock(return_value=None)
            
            with pytest.raises(HTTPException) as exc_info:
                await get_db_slide(
                    thread_id="test-123",
                    presentation_name="NonExistent",
                    slide_number=1,
                    db=mock_db,
                )
            
            assert exc_info.value.status_code == 404


class TestWriteDBSlideEndpoint:
    """Tests for POST /slides/db/slide endpoint."""

    def test_write_db_slide_route_exists(self):
        """Test that POST /db/slide route exists."""
        from backend.app.agent.api.v1.slides import router
        
        # Check for POST method on /db/slide
        found = False
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/db/slide":
                if hasattr(route, 'methods') and 'POST' in route.methods:
                    found = True
                    break
        
        assert found, "POST /db/slide route not found"

    @pytest.mark.asyncio
    async def test_write_db_slide_handler(self):
        """Test write_db_slide returns success response."""
        from backend.app.agent.api.v1.slides import write_db_slide
        from backend.src.services.slides.models import SlideWriteRequest, SlideWriteResponse
        
        mock_db = AsyncMock()
        request = SlideWriteRequest(
            presentation_name="Test",
            slide_number=1,
            content="<html></html>",
        )
        
        with patch('backend.app.agent.api.v1.slides.SlideService') as mock_service:
            mock_service.execute_slide_write = AsyncMock(return_value=SlideWriteResponse(
                success=True,
                presentation_name="Test",
                slide_number=1,
                slide_id=1,
            ))
            
            result = await write_db_slide(
                request=request,
                thread_id="test-123",
                db=mock_db,
            )
            
            assert result is not None


class TestDownloadDBSlidesEndpoint:
    """Tests for GET /slides/db/download endpoint."""

    def test_download_db_slides_route_exists(self):
        """Test that /db/download route exists."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        assert "/db/download" in route_paths


class TestImports:
    """Tests for required imports in slides module."""

    def test_slide_service_import(self):
        """Test SlideService can be imported."""
        from backend.src.services.slides import SlideService
        assert SlideService is not None

    def test_pydantic_models_import(self):
        """Test Pydantic models can be imported."""
        from backend.src.services.slides import (
            SlideContentInfo,
            PresentationInfo,
            PresentationListResponse,
            SlideWriteRequest,
            SlideWriteResponse,
        )
        
        assert SlideContentInfo is not None
        assert PresentationInfo is not None

    def test_current_session_import(self):
        """Test CurrentSession can be imported."""
        from backend.database.db import CurrentSession
        assert CurrentSession is not None


class TestNewEndpointsInRouter:
    """Tests to verify all new DB endpoints are registered."""

    def test_all_db_endpoints_registered(self):
        """Test all four new /db/ endpoints are in router."""
        from backend.app.agent.api.v1.slides import router
        
        route_paths = [r.path for r in router.routes]
        
        assert "/db/presentations" in route_paths, "Missing /db/presentations"
        assert "/db/slide" in route_paths, "Missing /db/slide"
        assert "/db/download" in route_paths, "Missing /db/download"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
