"""Tests for SlideService and Pydantic models.

Tests the database service layer focusing on model validation and imports.
Complex async tests that require actual database connections are in integration tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestSlideModels:
    """Tests for Pydantic models."""

    def test_slide_content_info_model(self):
        """Test SlideContentInfo model creation."""
        from backend.src.services.slides.models import SlideContentInfo
        
        info = SlideContentInfo(
            id=1,
            thread_id="thread-123",
            presentation_name="Test",
            slide_number=1,
            slide_title="Title",
            slide_content="<html></html>",
            metadata={},
            created_time=datetime.now(),
        )
        
        assert info.id == 1
        assert info.thread_id == "thread-123"
        assert info.presentation_name == "Test"

    def test_presentation_info_model(self):
        """Test PresentationInfo model creation."""
        from backend.src.services.slides.models import PresentationInfo
        
        info = PresentationInfo(
            name="My Presentation",
            slide_count=5,
        )
        
        assert info.name == "My Presentation"
        assert info.slide_count == 5
        assert info.slides == []

    def test_presentation_list_response_model(self):
        """Test PresentationListResponse model."""
        from backend.src.services.slides.models import PresentationListResponse
        
        response = PresentationListResponse(
            thread_id="test-thread",
            presentations=[],
            total=0,
        )
        
        assert response.thread_id == "test-thread"
        assert response.total == 0

    def test_slide_write_request_validation(self):
        """Test SlideWriteRequest validates slide_number >= 1."""
        from backend.src.services.slides.models import SlideWriteRequest
        from pydantic import ValidationError
        
        # Valid request
        valid = SlideWriteRequest(
            presentation_name="Test",
            slide_number=1,
            content="<html></html>",
        )
        assert valid.slide_number == 1
        
        # Invalid slide number should fail
        with pytest.raises(ValidationError):
            SlideWriteRequest(
                presentation_name="Test",
                slide_number=0,
                content="<html></html>",
            )

    def test_slide_write_response_model(self):
        """Test SlideWriteResponse model."""
        from backend.src.services.slides.models import SlideWriteResponse
        
        # Success response
        success = SlideWriteResponse(
            success=True,
            presentation_name="Test",
            slide_number=1,
            slide_id=42,
        )
        assert success.success is True
        assert success.slide_id == 42
        
        # Error response
        error = SlideWriteResponse(
            success=False,
            presentation_name="Test",
            slide_number=1,
            error="Something went wrong",
            error_code="WRITE_FAILED",
        )
        assert error.success is False
        assert error.error_code == "WRITE_FAILED"


class TestSlideServiceImports:
    """Tests for service imports."""

    def test_slide_service_import(self):
        """Test SlideService can be imported."""
        from backend.src.services.slides.service import SlideService
        assert SlideService is not None

    def test_slide_service_has_required_methods(self):
        """Test SlideService has all required methods."""
        from backend.src.services.slides.service import SlideService
        
        assert hasattr(SlideService, 'save_slide_to_db')
        assert hasattr(SlideService, 'get_thread_presentations')
        assert hasattr(SlideService, 'get_slide_content')
        assert hasattr(SlideService, 'get_all_slides_for_presentation')
        assert hasattr(SlideService, 'execute_slide_write')

    def test_slide_service_methods_are_static(self):
        """Test SlideService methods are static."""
        from backend.src.services.slides.service import SlideService
        
        # Static methods can be called on the class directly
        assert callable(SlideService.save_slide_to_db)
        assert callable(SlideService.get_thread_presentations)


class TestSlideServiceConversion:
    """Tests for model conversion helper."""

    def test_to_slide_content_info_conversion(self):
        """Test _to_slide_content_info converts DB model to Pydantic."""
        from backend.src.services.slides.service import SlideService
        
        # Create mock DB model
        mock_slide = MagicMock()
        mock_slide.id = 1
        mock_slide.thread_id = "test-thread"
        mock_slide.presentation_name = "Test Pres"
        mock_slide.slide_number = 1
        mock_slide.slide_title = "Title"
        mock_slide.slide_content = "<html>Content</html>"
        mock_slide.slide_metadata = {"tool_name": "SlideWrite"}
        mock_slide.created_time = datetime.now()
        mock_slide.updated_time = None
        
        result = SlideService._to_slide_content_info(mock_slide)
        
        assert result.id == 1
        assert result.thread_id == "test-thread"
        assert result.presentation_name == "Test Pres"
        assert result.slide_number == 1


class TestSlideContentModel:
    """Tests for SlideContent SQLAlchemy model."""

    def test_slide_content_model_import(self):
        """Test SlideContent model can be imported."""
        from backend.app.agent.model.slide_content import SlideContent
        assert SlideContent is not None

    def test_slide_content_model_table_name(self):
        """Test SlideContent has correct table name."""
        from backend.app.agent.model.slide_content import SlideContent
        assert SlideContent.__tablename__ == "slide_content"

    def test_slide_content_model_columns(self):
        """Test SlideContent has required columns."""
        from backend.app.agent.model.slide_content import SlideContent
        
        columns = SlideContent.__table__.columns.keys()
        
        assert "id" in columns
        assert "thread_id" in columns
        assert "presentation_name" in columns
        assert "slide_number" in columns
        assert "slide_title" in columns
        assert "slide_content" in columns
        assert "slide_metadata" in columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
