# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Unit tests for the file processing system.

Tests cover:
- FastParse module (parsing various file types)
- Storage backends (local and S3)
- Image utilities (compression, thumbnails)
"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the file processing modules
from backend.src.services.file_processing import (
    parse,
    ParseResult,
    FileType,
    FastParseConfig,
    sanitize_filename_for_path,
    format_file_size,
    detect_mime_type,
    is_supported_file,
)
from backend.src.services.file_processing.storage import (
    LocalFileStorage,
    get_storage_backend,
    reset_storage_backend,
)
from backend.src.services.file_processing.image_utils import (
    compress_image,
    is_image_mime,
    get_image_dimensions,
    create_thumbnail,
)
from backend.src.services.file_processing.fast_parse.exceptions import (
    FileSizeExceededError,
    UnsupportedFormatError,
)


# =============================================================================
# FastParse Tests
# =============================================================================

class TestFastParse:
    """Tests for the FastParse module."""

    def test_parse_text_file(self):
        """Test parsing a simple text file."""
        content = b"Hello, World!\nThis is a test file."
        result = parse(content, "test.txt", "text/plain")
        
        assert result.success is True
        assert result.file_type == FileType.TEXT
        assert "Hello, World!" in result.content
        assert result.error is None

    def test_parse_json_file(self):
        """Test parsing a JSON file."""
        content = b'{"name": "test", "value": 123}'
        result = parse(content, "data.json", "application/json")
        
        assert result.success is True
        assert result.file_type == FileType.TEXT
        assert '"name": "test"' in result.content

    def test_parse_python_file(self):
        """Test parsing a Python source file."""
        content = b'def hello():\n    print("Hello!")\n'
        result = parse(content, "script.py", "text/x-python")
        
        assert result.success is True
        assert result.file_type == FileType.TEXT
        assert "def hello():" in result.content

    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        result = parse(b"", "empty.txt", "text/plain")
        
        assert result.success is True
        assert result.content == ""

    def test_parse_binary_file(self):
        """Test parsing a binary file."""
        content = b"\x00\x01\x02\x03\xff\xfe\xfd"
        result = parse(content, "binary.bin", "application/octet-stream")
        
        assert result.success is True
        assert result.file_type == FileType.BINARY

    def test_parse_image_file_metadata(self):
        """Test parsing an image file returns metadata."""
        # Create a minimal valid PNG
        png_header = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D,  # Chunk length
            0x49, 0x48, 0x44, 0x52,  # IHDR
            0x00, 0x00, 0x00, 0x01,  # Width: 1
            0x00, 0x00, 0x00, 0x01,  # Height: 1
            0x08, 0x02,              # Bit depth, color type
            0x00, 0x00, 0x00,        # Compression, filter, interlace
            0x90, 0x77, 0x53, 0xDE,  # CRC
        ])
        
        result = parse(png_header, "image.png", "image/png")
        
        assert result.file_type == FileType.IMAGE
        # May succeed or fail depending on full PNG support
        # Just check it doesn't crash

    def test_parse_unknown_extension(self):
        """Test parsing a file with unknown extension."""
        content = b"Some content"
        result = parse(content, "file.xyz123", "application/octet-stream")
        
        assert result.success is True
        # Should fall back to binary or unknown type


class TestFastParseConfig:
    """Tests for FastParse configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FastParseConfig()
        
        assert config.max_file_size_bytes > 0
        assert config.max_pdf_pages > 0
        assert config.max_excel_rows > 0
        assert config.max_text_chars > 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = FastParseConfig(
            max_file_size_bytes=1024,
            max_pdf_pages=10,
        )
        
        assert config.max_file_size_bytes == 1024
        assert config.max_pdf_pages == 10


class TestFastParseUtils:
    """Tests for FastParse utility functions."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Remove path separators
        assert "/" not in sanitize_filename_for_path("path/to/file.txt")
        assert "\\" not in sanitize_filename_for_path("path\\to\\file.txt")
        
        # Handle special characters
        result = sanitize_filename_for_path("file<>:name.txt")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_format_file_size(self):
        """Test file size formatting."""
        assert "B" in format_file_size(100)
        assert "KB" in format_file_size(1024)
        assert "MB" in format_file_size(1024 * 1024)
        assert "GB" in format_file_size(1024 * 1024 * 1024)

    def test_detect_mime_type(self):
        """Test MIME type detection."""
        assert detect_mime_type("file.txt") == "text/plain"
        assert detect_mime_type("file.json") == "application/json"
        assert detect_mime_type("file.pdf") == "application/pdf"
        assert detect_mime_type("file.png") == "image/png"

    def test_is_supported_file(self):
        """Test supported file check."""
        assert is_supported_file("document.pdf") is True
        assert is_supported_file("image.png") is True
        assert is_supported_file("script.py") is True


# =============================================================================
# Storage Backend Tests
# =============================================================================

class TestLocalFileStorage:
    """Tests for LocalFileStorage backend."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_path=tmpdir)
            yield storage

    @pytest.mark.asyncio
    async def test_upload_file(self, temp_storage):
        """Test uploading a file."""
        content = b"Test file content"
        
        path = await temp_storage.upload(
            user_id="123",
            file_id="abc-def",
            content=content,
            filename="test.txt",
            mime_type="text/plain",
        )
        
        assert path is not None
        assert "123" in path
        assert "abc-def" in path

    @pytest.mark.asyncio
    async def test_download_file(self, temp_storage):
        """Test downloading a file."""
        content = b"Download test content"
        
        path = await temp_storage.upload(
            user_id="123",
            file_id="download-test",
            content=content,
            filename="download.txt",
            mime_type="text/plain",
        )
        
        downloaded = await temp_storage.download(path)
        assert downloaded == content

    @pytest.mark.asyncio
    async def test_delete_file(self, temp_storage):
        """Test deleting a file."""
        content = b"Delete test content"
        
        path = await temp_storage.upload(
            user_id="123",
            file_id="delete-test",
            content=content,
            filename="delete.txt",
            mime_type="text/plain",
        )
        
        # File exists
        assert await temp_storage.exists(path) is True
        
        # Delete
        result = await temp_storage.delete(path)
        assert result is True
        
        # File no longer exists
        assert await temp_storage.exists(path) is False

    @pytest.mark.asyncio
    async def test_download_nonexistent(self, temp_storage):
        """Test downloading a file that doesn't exist."""
        result = await temp_storage.download("nonexistent/path/file.txt")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self, temp_storage):
        """Test file existence check."""
        assert await temp_storage.exists("nonexistent") is False
        
        path = await temp_storage.upload(
            user_id="123",
            file_id="exists-test",
            content=b"content",
            filename="exists.txt",
            mime_type="text/plain",
        )
        
        assert await temp_storage.exists(path) is True


class TestStorageBackendFactory:
    """Tests for storage backend factory function."""

    def test_get_local_backend(self):
        """Test getting local storage backend."""
        reset_storage_backend()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = get_storage_backend(
                backend_type="local",
                base_path=tmpdir,
            )
            
            assert isinstance(storage, LocalFileStorage)
        
        reset_storage_backend()

    def test_invalid_backend_type(self):
        """Test invalid backend type raises error."""
        reset_storage_backend()
        
        with pytest.raises(ValueError):
            get_storage_backend(backend_type="invalid")
        
        reset_storage_backend()


# =============================================================================
# Image Utils Tests
# =============================================================================

class TestImageUtils:
    """Tests for image processing utilities."""

    def test_is_image_mime(self):
        """Test image MIME type detection."""
        assert is_image_mime("image/jpeg") is True
        assert is_image_mime("image/png") is True
        assert is_image_mime("image/gif") is True
        assert is_image_mime("image/webp") is True
        assert is_image_mime("image/svg+xml") is False  # SVG excluded
        assert is_image_mime("text/plain") is False
        assert is_image_mime("application/pdf") is False

    def test_compress_image_jpeg(self):
        """Test JPEG compression."""
        try:
            from PIL import Image
            
            # Create a test image
            img = Image.new("RGB", (100, 100), color="red")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            original_bytes = buffer.getvalue()
            
            compressed, mime = compress_image(original_bytes, "image/jpeg")
            
            assert mime == "image/jpeg"
            assert len(compressed) > 0
        except ImportError:
            pytest.skip("Pillow not installed")

    def test_compress_image_resize(self):
        """Test image resizing."""
        try:
            from PIL import Image
            
            # Create a large image
            img = Image.new("RGB", (4000, 4000), color="blue")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            original_bytes = buffer.getvalue()
            
            compressed, mime = compress_image(
                original_bytes,
                "image/jpeg",
                max_width=1000,
                max_height=1000,
            )
            
            # Verify resized
            resized = Image.open(io.BytesIO(compressed))
            assert resized.width <= 1000
            assert resized.height <= 1000
        except ImportError:
            pytest.skip("Pillow not installed")

    def test_get_image_dimensions(self):
        """Test getting image dimensions."""
        try:
            from PIL import Image
            
            img = Image.new("RGB", (200, 150), color="green")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            
            dimensions = get_image_dimensions(buffer.getvalue())
            
            assert dimensions == (200, 150)
        except ImportError:
            pytest.skip("Pillow not installed")

    def test_create_thumbnail(self):
        """Test thumbnail creation."""
        try:
            from PIL import Image
            
            img = Image.new("RGB", (500, 500), color="yellow")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            
            thumb_bytes, mime = create_thumbnail(
                buffer.getvalue(),
                size=(100, 100),
            )
            
            thumb = Image.open(io.BytesIO(thumb_bytes))
            assert thumb.width <= 100
            assert thumb.height <= 100
        except ImportError:
            pytest.skip("Pillow not installed")


# =============================================================================
# Integration Tests
# =============================================================================

class TestFileProcessingIntegration:
    """Integration tests for the file processing system."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for integration tests."""
        reset_storage_backend()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = get_storage_backend(
                backend_type="local",
                base_path=tmpdir,
            )
            yield storage
        reset_storage_backend()

    @pytest.mark.asyncio
    async def test_upload_parse_download_flow(self, temp_storage):
        """Test complete upload, parse, download flow."""
        # Create a text file
        content = b"This is a test document.\nIt has multiple lines."
        
        # Parse the content
        result = parse(content, "document.txt", "text/plain")
        assert result.success is True
        assert "test document" in result.content
        
        # Upload to storage
        path = await temp_storage.upload(
            user_id="user123",
            file_id="file456",
            content=content,
            filename="document.txt",
            mime_type="text/plain",
        )
        
        # Download and verify
        downloaded = await temp_storage.download(path)
        assert downloaded == content

    def test_parse_multiple_file_types(self):
        """Test parsing various file types."""
        test_cases = [
            (b"Plain text content", "file.txt", "text/plain", FileType.TEXT),
            (b'{"key": "value"}', "data.json", "application/json", FileType.TEXT),
            (b"# Markdown\n\nContent", "readme.md", "text/markdown", FileType.TEXT),
            (b"<html><body>Hello</body></html>", "page.html", "text/html", FileType.TEXT),
        ]
        
        for content, filename, mime, expected_type in test_cases:
            result = parse(content, filename, mime)
            assert result.success is True, f"Failed for {filename}"
            assert result.file_type == expected_type, f"Wrong type for {filename}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
