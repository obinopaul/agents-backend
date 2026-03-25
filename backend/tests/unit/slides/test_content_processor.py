
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from backend.src.services.slides.content_processor import SlideContentProcessor

class TestSlideContentProcessor(unittest.IsolatedAsyncioTestCase):
    """Test SlideContentProcessor logic."""

    def setUp(self):
        self.mock_storage = AsyncMock()
        self.mock_download = AsyncMock()
        self.processor = SlideContentProcessor(
            storage=self.mock_storage,
            sandbox_download_func=self.mock_download
        )

    def test_find_local_references(self):
        """Test finding various local file references."""
        html = """
        <html>
            <img src="/workspace/images/pic.png">
            <link href="/workspace/css/style.css">
            <div style="background: url('/workspace/bg.jpg')"></div>
            <img src="https://external.com/img.jpg"> <!-- Should skip -->
            <a href="./relative/doc.pdf">Link</a>
        </html>
        """
        refs = self.processor._find_local_references(html)
        expected = {
            "/workspace/images/pic.png",
            "/workspace/css/style.css",
            "/workspace/bg.jpg",
            "./relative/doc.pdf"
        }
        self.assertEqual(set(refs), expected)

    async def test_process_html_content_replacements(self):
        """Test replacing local paths with permanent URLs."""
        html = '<img src="/workspace/img.png">'
        
        # Setup mocks
        self.mock_download.return_value = b"image_data"
        self.mock_storage.exists.return_value = False
        self.mock_storage.get_url.return_value = "https://storage.com/permanent.png"
        
        processed = await self.processor.process_html_content(
            html, "sandbox-1", "thread-1"
        )
        
        self.assertIn('src="https://storage.com/permanent.png"', processed)
        self.mock_storage.upload.assert_called_once()

    async def test_process_html_content_cache_hit(self):
        """Test that subsequent calls use cache."""
        html = '<img src="/workspace/img.png">'
        
        # Pre-populate cache
        cache_key = "sandbox-1:/workspace/img.png"
        self.processor._url_cache[cache_key] = "https://cached.com/img.png"
        
        processed = await self.processor.process_html_content(
            html, "sandbox-1", "thread-1"
        )
        
        self.assertIn('src="https://cached.com/img.png"', processed)
        self.mock_download.assert_not_called()

    async def test_resolve_sandbox_path(self):
        """Test path resolution logic."""
        # Absolute path
        p1 = self.processor._resolve_sandbox_path("/workspace/file.txt")
        self.assertEqual(p1, "/workspace/file.txt")
        
        # Relative path with slide context
        p2 = self.processor._resolve_sandbox_path(
            "images/pic.png", 
            slide_filepath="/workspace/pres/slides.html"
        )
        self.assertEqual(p2, "/workspace/pres/images/pic.png")
        
        # Relative path without slide context (default to workspace)
        p3 = self.processor._resolve_sandbox_path("file.txt")
        self.assertEqual(p3, "/workspace/file.txt")

    async def test_deduplication_via_hash(self):
        """Test that identical content uses same storage path/url."""
        html = '...'
        content = b"same_content"
        self.mock_download.return_value = content
        
        # First file
        self.mock_storage.exists.return_value = True
        self.mock_storage.get_url.return_value = "https://storage.com/hash123"
        
        url1 = await self.processor._get_or_upload_file(
            "/workspace/file1.png", "sb1", "t1"
        )
        
        # Second file (same content)
        url2 = await self.processor._get_or_upload_file(
            "/workspace/file2.png", "sb1", "t1"
        )
        
        self.assertEqual(url1, url2)
