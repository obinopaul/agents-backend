
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from backend.src.services.slides.slide_subscriber import (
    SlideEventSubscriber, 
    ToolResultExtractor,
    SLIDE_WRITE_TOOL,
    SLIDE_EDIT_TOOL,
    SLIDE_APPLY_PATCH_TOOL
)

class TestToolResultExtractor(unittest.TestCase):
    """Test the ToolResultExtractor class."""

    def test_extract_from_tuple(self):
        """Test extraction from LangChain tuple format (content_str, artifact)."""
        # (content_str, artifact_dict)
        mock_result = (
            "Slide created",
            {
                "display_content": {
                    "content": "<html><body>Slide 1</body></html>",
                    "filepath": "/path/to/slide.html"
                }
            }
        )
        result = ToolResultExtractor.extract_user_display_content(mock_result)
        self.assertIsNotNone(result)
        self.assertEqual(result["content"], "<html><body>Slide 1</body></html>")

    def test_extract_from_tuple_nested_list(self):
        """Test extraction from tuple with list in display_content (ApplyPatch)."""
        mock_result = (
            "Patch applied",
            {
                "display_content": [
                    {"new_content": "slide1", "filepath": "path1"},
                    {"new_content": "slide2", "filepath": "path2"}
                ]
            }
        )
        result = ToolResultExtractor.extract_user_display_content(mock_result)
        self.assertIn("_batch_results", result)
        self.assertEqual(len(result["_batch_results"]), 2)

    def test_extract_from_dict_direct(self):
        """Test extraction from direct dict."""
        mock_result = {"content": "<html>slide</html>"}
        result = ToolResultExtractor.extract_user_display_content(mock_result)
        self.assertEqual(result["content"], "<html>slide</html>")

    def test_extract_from_mcp_structured(self):
        """Test extraction from MCP structured_content."""
        mock_result = {
            "structured_content": {
                "user_display_content": {
                    "content": "<html>mcp</html>"
                }
            }
        }
        result = ToolResultExtractor.extract_user_display_content(mock_result)
        self.assertEqual(result["content"], "<html>mcp</html>")

    def test_extract_from_list(self):
        """Test extraction from direct list."""
        mock_result = [{"content": "slide1"}, {"content": "slide2"}]
        result = ToolResultExtractor.extract_user_display_content(mock_result)
        self.assertIn("_batch_results", result)


class TestSlideEventSubscriber(unittest.IsolatedAsyncioTestCase):
    """Test SlideEventSubscriber logic."""

    async def asyncSetUp(self):
        self.db_session = AsyncMock()
        self.subscriber = SlideEventSubscriber()
        
        # Patch SlideService
        self.patcher = patch("backend.src.services.slides.slide_subscriber.SlideService")
        self.mock_service = self.patcher.start()
        self.mock_service.save_slide_to_db = AsyncMock(return_value=1)

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_on_tool_complete_write(self):
        """Test on_tool_complete with SlideWriteTool."""
        tool_input = {
            "presentation_name": "TestPres",
            "slide_number": 1,
            "title": "My Title"
        }
        tool_result = (
            "Done",
            {"display_content": {"content": "<html>content</html>"}}
        )

        success = await self.subscriber.on_tool_complete(
            db_session=self.db_session,
            tool_name=SLIDE_WRITE_TOOL,
            tool_input=tool_input,
            tool_result=tool_result,
            thread_id="thread-1"
        )

        self.assertTrue(success)
        self.mock_service.save_slide_to_db.assert_called_once()
        call_args = self.mock_service.save_slide_to_db.call_args[1]
        self.assertEqual(call_args["presentation_name"], "TestPres")
        self.assertEqual(call_args["slide_content"], "<html>content</html>")

    async def test_on_tool_complete_fallback_input(self):
        """Test fallback to tool_input content if result is empty string."""
        tool_input = {
            "presentation_name": "FallbackPres",
            "slide_number": 2,
            "content": "<html>fallback</html>"
        }
        tool_result = "Just a string message"

        success = await self.subscriber.on_tool_complete(
            db_session=self.db_session,
            tool_name=SLIDE_WRITE_TOOL,
            tool_input=tool_input,
            tool_result=tool_result,
            thread_id="thread-1"
        )

        self.assertTrue(success)
        call_args = self.mock_service.save_slide_to_db.call_args[1]
        self.assertEqual(call_args["slide_content"], "<html>fallback</html>")

    async def test_apply_patch_flow(self):
        """Test SlideApplyPatchTool batch processing."""
        tool_result = (
            "Patched",
            {
                "display_content": [
                    {
                        "new_content": "slide1", 
                        "filepath": "/workspace/presentations/Deck/slide_1.html"
                    },
                    {
                        "new_content": "slide2", 
                        "filepath": "/workspace/presentations/Deck/slide_2.html"
                    }
                ]
            }
        )
        
        success = await self.subscriber.on_tool_complete(
            db_session=self.db_session,
            tool_name=SLIDE_APPLY_PATCH_TOOL,
            tool_input={},
            tool_result=tool_result,
            thread_id="thread-1"
        )
        
        self.assertTrue(success)
        self.assertEqual(self.mock_service.save_slide_to_db.call_count, 2)

    async def test_content_processing_integration(self):
        """Test that content processing is called if sandbox context is provided."""
        tool_input = {"presentation_name": "P", "slide_number": 1}
        tool_result = {"user_display_content": {"content": "<html>img</html>"}}
        
        # Mock processor
        mock_processor = AsyncMock()
        mock_processor.process_html_content.return_value = "<html>processed</html>"
        
        with patch("backend.src.services.slides.content_processor.SlideContentProcessor", return_value=mock_processor):
            # We need to access the singleton or fresh instance
            # Since subscriber is created in setUp, we can patch the lazy import inside methods
            # But the code does 'from ... import SlideContentProcessor' inside _process_content
            # proper patching is tricky for local imports.
            
            # Alternative: Assign a mock processor directly if the class allows injection
            self.subscriber._content_processor = mock_processor
            
            await self.subscriber.on_tool_complete(
                db_session=self.db_session,
                tool_name=SLIDE_WRITE_TOOL,
                tool_input=tool_input,
                tool_result=tool_result,
                thread_id="thread-1",
                sandbox_id="sandbox-1",
                sandbox_download_func=AsyncMock()
            )
            
            mock_processor.process_html_content.assert_called_once()
            call_args = self.mock_service.save_slide_to_db.call_args[1]
            self.assertEqual(call_args["slide_content"], "<html>processed</html>")
