"""Tests for SlideEventSubscriber.

Tests the event handler that syncs slide tool results to database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSlideEventSubscriber:
    """Tests for SlideEventSubscriber event handling."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def subscriber(self):
        """Create SlideEventSubscriber instance."""
        from backend.src.services.slides.slide_subscriber import SlideEventSubscriber
        return SlideEventSubscriber()

    @pytest.mark.asyncio
    async def test_on_tool_complete_ignores_non_slide_tools(self, subscriber, mock_db_session):
        """Test that non-slide tools are ignored."""
        result = await subscriber.on_tool_complete(
            db_session=mock_db_session,
            tool_name="FileReadTool",
            tool_input={"path": "/workspace/file.txt"},
            tool_result={"content": "file content"},
            thread_id="test-thread",
        )
        
        # Should return False (not handled)
        assert result is False

    @pytest.mark.asyncio
    @patch('backend.src.services.slides.slide_subscriber.SlideService')
    async def test_on_tool_complete_handles_slide_write(self, mock_service, subscriber, mock_db_session):
        """Test SlideWrite tool results are saved to DB."""
        mock_service.save_slide_to_db = AsyncMock(return_value=1)
        
        result = await subscriber.on_tool_complete(
            db_session=mock_db_session,
            tool_name="SlideWrite",
            tool_input={
                "presentation_name": "Test Presentation",
                "slide_number": 1,
                "title": "Introduction",
            },
            tool_result=[{
                "content": "<html><body>Slide content</body></html>",
            }],
            thread_id="test-thread",
        )
        
        # Should return True (handled)
        assert result is True
        mock_service.save_slide_to_db.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.src.services.slides.slide_subscriber.SlideService')
    async def test_on_tool_complete_handles_slide_edit(self, mock_service, subscriber, mock_db_session):
        """Test SlideEdit tool results are saved to DB."""
        mock_service.save_slide_to_db = AsyncMock(return_value=1)
        
        result = await subscriber.on_tool_complete(
            db_session=mock_db_session,
            tool_name="SlideEdit",
            tool_input={
                "presentation_name": "Test Presentation",
                "slide_number": 1,
            },
            tool_result=[{
                "new_content": "<html><body>Updated content</body></html>",
            }],
            thread_id="test-thread",
        )
        
        # Should return True (handled)
        assert result is True
        mock_service.save_slide_to_db.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.src.services.slides.slide_subscriber.SlideService')
    async def test_on_tool_complete_handles_slide_apply_patch(self, mock_service, subscriber, mock_db_session):
        """Test slide_apply_patch tool results are saved to DB."""
        mock_service.save_slide_to_db = AsyncMock(return_value=1)
        
        result = await subscriber.on_tool_complete(
            db_session=mock_db_session,
            tool_name="slide_apply_patch",
            tool_input={},
            tool_result=[
                {
                    "filepath": "/workspace/presentations/TestPres/slide_1.html",
                    "new_content": "<html>Slide 1</html>",
                },
                {
                    "filepath": "/workspace/presentations/TestPres/slide_2.html",
                    "new_content": "<html>Slide 2</html>",
                },
            ],
            thread_id="test-thread",
        )
        
        # Should return True (handled)
        assert result is True
        # Should have saved 2 slides
        assert mock_service.save_slide_to_db.call_count == 2


class TestSlideToolConstants:
    """Tests for slide tool name constants."""

    def test_slide_tools_list(self):
        """Test SLIDE_TOOLS contains expected tools."""
        from backend.src.services.slides.slide_subscriber import SLIDE_TOOLS
        
        assert "SlideWrite" in SLIDE_TOOLS
        assert "SlideEdit" in SLIDE_TOOLS
        assert "slide_apply_patch" in SLIDE_TOOLS

    def test_slide_tool_constants(self):
        """Test individual tool name constants."""
        from backend.src.services.slides.slide_subscriber import (
            SLIDE_WRITE_TOOL,
            SLIDE_EDIT_TOOL,
            SLIDE_APPLY_PATCH_TOOL,
        )
        
        assert SLIDE_WRITE_TOOL == "SlideWrite"
        assert SLIDE_EDIT_TOOL == "SlideEdit"
        assert SLIDE_APPLY_PATCH_TOOL == "slide_apply_patch"


class TestSingletonInstance:
    """Tests for the singleton slide_subscriber instance."""

    def test_slide_subscriber_singleton_exists(self):
        """Test slide_subscriber singleton is available."""
        from backend.src.services.slides.slide_subscriber import slide_subscriber
        
        assert slide_subscriber is not None

    def test_slide_subscriber_singleton_is_instance(self):
        """Test slide_subscriber is a SlideEventSubscriber instance."""
        from backend.src.services.slides.slide_subscriber import (
            slide_subscriber,
            SlideEventSubscriber,
        )
        
        assert isinstance(slide_subscriber, SlideEventSubscriber)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
