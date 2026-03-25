# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Unit tests for UserMessageSubscriber.

Tests cover:
- Tool name filtering
- Attachment extraction from various formats
- Remote URL passthrough
- Sandbox download and upload flow
- Error handling and graceful degradation
- File type classification
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

# Import the module under test
from backend.src.services.user_message.user_message_subscriber import (
    UserMessageSubscriber,
    ProcessedAttachment,
    AttachmentProcessingResult,
    FileCategory,
    get_file_category,
    get_mime_type,
    is_remote_url,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def subscriber():
    """Create a fresh UserMessageSubscriber instance for each test."""
    sub = UserMessageSubscriber()
    # Reset storage initialization for testing
    sub._storage = None
    sub._storage_initialized = False
    return sub


@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    storage = AsyncMock()
    storage.upload = AsyncMock(return_value="test_user/test_file/hello.py")
    storage.get_url = AsyncMock(return_value="https://example.com/files/hello.py")
    return storage


@pytest.fixture
def mock_sandbox_download():
    """Create a mock sandbox download function."""
    async def download_func(path: str, format: str = "bytes") -> bytes:
        return b"print('Hello, World!')"
    return download_func


@pytest.fixture
def message_user_result():
    """Sample message_user tool result with attachments."""
    return {
        "tool_name": "message",
        "action": {
            "type": "result",
            "text": "Here is the file you requested.",
            "attachments": [
                "/workspace/hello.py",
                "/workspace/report.pdf",
            ]
        }
    }


# =============================================================================
# Test: File Category Classification
# =============================================================================

class TestFileCategory:
    """Tests for file type classification functions."""
    
    def test_get_file_category_python(self):
        """Python files should be classified as CODE."""
        assert get_file_category("hello.py") == FileCategory.CODE
        assert get_file_category("test.PY") == FileCategory.CODE  # Case insensitive
    
    def test_get_file_category_javascript(self):
        """JavaScript files should be classified as CODE."""
        assert get_file_category("app.js") == FileCategory.CODE
        assert get_file_category("component.jsx") == FileCategory.CODE
        assert get_file_category("index.ts") == FileCategory.CODE
        assert get_file_category("App.tsx") == FileCategory.CODE
    
    def test_get_file_category_documents(self):
        """Document files should be classified as DOCUMENTS."""
        assert get_file_category("report.pdf") == FileCategory.DOCUMENTS
        assert get_file_category("document.docx") == FileCategory.DOCUMENTS
        assert get_file_category("notes.txt") == FileCategory.DOCUMENTS
        assert get_file_category("README.md") == FileCategory.DOCUMENTS
    
    def test_get_file_category_spreadsheet(self):
        """Spreadsheet files should be classified as SPREADSHEET."""
        assert get_file_category("data.xlsx") == FileCategory.SPREADSHEET
        assert get_file_category("budget.xls") == FileCategory.SPREADSHEET
        assert get_file_category("export.csv") == FileCategory.SPREADSHEET
    
    def test_get_file_category_archive(self):
        """Archive files should be classified as ARCHIVE."""
        assert get_file_category("backup.zip") == FileCategory.ARCHIVE
        assert get_file_category("files.tar.gz") == FileCategory.ARCHIVE
        assert get_file_category("package.7z") == FileCategory.ARCHIVE
    
    def test_get_file_category_images(self):
        """Image files should be classified as IMAGE."""
        assert get_file_category("photo.jpg") == FileCategory.IMAGE
        assert get_file_category("icon.png") == FileCategory.IMAGE
        assert get_file_category("diagram.svg") == FileCategory.IMAGE
    
    def test_get_file_category_special_files(self):
        """Special files without extensions should be handled."""
        assert get_file_category("Dockerfile") == FileCategory.CODE
        assert get_file_category("Makefile") == FileCategory.CODE
    
    def test_get_file_category_unknown(self):
        """Unknown extensions should return OTHER."""
        assert get_file_category("file.xyz") == FileCategory.OTHER
        assert get_file_category("") == FileCategory.OTHER
    
    def test_get_mime_type(self):
        """Test MIME type detection."""
        assert get_mime_type("file.py") == "text/x-python"
        assert get_mime_type("file.json") == "application/json"
        assert get_mime_type("unknown.xyz") == "application/octet-stream"


# =============================================================================
# Test: URL Detection
# =============================================================================

class TestIsRemoteUrl:
    """Tests for remote URL detection."""
    
    def test_http_url(self):
        """HTTP URLs should be detected as remote."""
        assert is_remote_url("http://example.com/file.txt") is True
    
    def test_https_url(self):
        """HTTPS URLs should be detected as remote."""
        assert is_remote_url("https://example.com/file.txt") is True
    
    def test_s3_url(self):
        """S3 URLs should be detected as remote."""
        assert is_remote_url("s3://bucket/key") is True
    
    def test_gs_url(self):
        """GCS URLs should be detected as remote."""
        assert is_remote_url("gs://bucket/object") is True
    
    def test_local_path(self):
        """Local paths should not be detected as remote."""
        assert is_remote_url("/workspace/file.txt") is False
        assert is_remote_url("./relative/path.txt") is False
    
    def test_empty_path(self):
        """Empty paths should return False."""
        assert is_remote_url("") is False
        assert is_remote_url(None) is False


# =============================================================================
# Test: Tool Filtering
# =============================================================================

class TestToolFiltering:
    """Tests for tool name filtering."""
    
    @pytest.mark.asyncio
    async def test_skip_non_message_user_tool(self, subscriber):
        """Non-message_user tools should return None."""
        result = await subscriber.on_tool_complete(
            tool_name="other_tool",
            tool_result={"some": "data"},
            thread_id="test-thread",
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_skip_slide_tools(self, subscriber):
        """Slide tools should be ignored."""
        for tool_name in ["SlideWrite", "SlideEdit", "slide_apply_patch"]:
            result = await subscriber.on_tool_complete(
                tool_name=tool_name,
                tool_result={"slide": "data"},
                thread_id="test-thread",
            )
            assert result is None
    
    @pytest.mark.asyncio
    async def test_process_message_user_tool(self, subscriber, mock_storage, mock_sandbox_download):
        """message_user tool should be processed."""
        # Patch storage initialization
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        tool_result = {
            "tool_name": "message",
            "action": {
                "type": "result",
                "text": "Done!",
                "attachments": ["https://example.com/existing-file.pdf"]
            }
        }
        
        result = await subscriber.on_tool_complete(
            tool_name="message_user",
            tool_result=tool_result,
            thread_id="test-thread",
            sandbox_download_func=mock_sandbox_download,
        )
        
        # Should return enhanced result with remote URL passed through
        assert result is not None
        assert "action" in result
        assert len(result["action"]["attachments"]) == 1


# =============================================================================
# Test: Attachment Extraction
# =============================================================================

class TestAttachmentExtraction:
    """Tests for extracting attachments from tool results."""
    
    @pytest.mark.asyncio
    async def test_extract_nested_attachments(self, subscriber):
        """Test extraction from nested action.attachments structure."""
        result = subscriber._extract_attachments({
            "tool_name": "message",
            "action": {
                "attachments": ["/path/file1.py", "/path/file2.pdf"]
            }
        })
        assert len(result) == 2
        assert result[0] == "/path/file1.py"
    
    @pytest.mark.asyncio
    async def test_extract_top_level_attachments(self, subscriber):
        """Test extraction from top-level attachments key."""
        result = subscriber._extract_attachments({
            "attachments": ["/path/file.py"]
        })
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_extract_empty_attachments(self, subscriber):
        """Test with no attachments."""
        result = subscriber._extract_attachments({
            "tool_name": "message",
            "action": {"text": "No files"}
        })
        assert result == []


# =============================================================================
# Test: Result Parsing
# =============================================================================

class TestResultParsing:
    """Tests for parsing tool results."""
    
    def test_parse_dict_result(self, subscriber):
        """Dictionary results should pass through."""
        result = subscriber._parse_tool_result({"key": "value"})
        assert result == {"key": "value"}
    
    def test_parse_json_string_result(self, subscriber):
        """JSON strings should be parsed."""
        result = subscriber._parse_tool_result('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_parse_invalid_json(self, subscriber):
        """Invalid JSON should return None."""
        result = subscriber._parse_tool_result("not json")
        assert result is None


# =============================================================================
# Test: Remote URL Passthrough
# =============================================================================

class TestRemoteUrlPassthrough:
    """Tests for handling remote URLs."""
    
    @pytest.mark.asyncio
    async def test_remote_url_not_downloaded(self, subscriber, mock_storage):
        """Remote URLs should not trigger sandbox download."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        mock_download = AsyncMock()
        
        result = await subscriber._process_single_attachment(
            attachment="https://example.com/file.pdf",
            thread_id="test-thread",
            sandbox_download_func=mock_download,
            sandbox_id="test-sandbox",
        )
        
        # Should not call download function
        mock_download.assert_not_called()
        # Should return the URL as-is
        assert result.url == "https://example.com/file.pdf"
        assert result.error is None


# =============================================================================
# Test: Sandbox Download Flow
# =============================================================================

class TestSandboxDownloadFlow:
    """Tests for sandbox file download and upload."""
    
    @pytest.mark.asyncio
    async def test_successful_download_and_upload(self, subscriber, mock_storage):
        """Test successful download from sandbox and upload to storage."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        mock_download = AsyncMock(return_value=b"file content here")
        
        result = await subscriber._process_single_attachment(
            attachment="/workspace/file.py",
            thread_id="test-thread",
            sandbox_download_func=mock_download,
            sandbox_id="test-sandbox",
        )
        
        # Should have called download
        mock_download.assert_called_once()
        # Should have called storage upload
        mock_storage.upload.assert_called_once()
        # Should return URL from storage
        assert result.url == "https://example.com/files/hello.py"
        assert result.error is None
        assert result.file_type == FileCategory.CODE
    
    @pytest.mark.asyncio
    async def test_download_returns_none(self, subscriber, mock_storage):
        """Test handling when sandbox download returns None (file not found)."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        mock_download = AsyncMock(return_value=None)
        
        result = await subscriber._process_single_attachment(
            attachment="/workspace/missing.py",
            thread_id="test-thread",
            sandbox_download_func=mock_download,
            sandbox_id="test-sandbox",
        )
        
        # Should have called download
        mock_download.assert_called_once()
        # Should NOT have called storage (file not found)
        mock_storage.upload.assert_not_called()
        # Should have an error
        assert result.error is not None
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_no_sandbox_download_func(self, subscriber, mock_storage):
        """Test handling when no sandbox download function is provided."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        result = await subscriber._process_single_attachment(
            attachment="/workspace/file.py",
            thread_id="test-thread",
            sandbox_download_func=None,
            sandbox_id="test-sandbox",
        )
        
        # Should have an error about missing function
        assert result.error is not None
        assert "download function" in result.error.lower()


# =============================================================================
# Test: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_download_exception(self, subscriber, mock_storage):
        """Test handling of download exceptions."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        mock_download = AsyncMock(side_effect=Exception("Connection error"))
        
        result = await subscriber._process_single_attachment(
            attachment="/workspace/file.py",
            thread_id="test-thread",
            sandbox_download_func=mock_download,
            sandbox_id="test-sandbox",
        )
        
        # Should have an error
        assert result.error is not None
        assert "failed" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_upload_exception(self, subscriber, mock_storage):
        """Test handling of upload exceptions."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        mock_storage.upload = AsyncMock(side_effect=Exception("Storage error"))
        
        mock_download = AsyncMock(return_value=b"file content")
        
        result = await subscriber._process_single_attachment(
            attachment="/workspace/file.py",
            thread_id="test-thread",
            sandbox_download_func=mock_download,
            sandbox_id="test-sandbox",
        )
        
        # Should have an error
        assert result.error is not None
        assert "upload failed" in result.error.lower()


# =============================================================================
# Test: ProcessedAttachment Data Class
# =============================================================================

class TestProcessedAttachment:
    """Tests for ProcessedAttachment data class."""
    
    def test_to_dict_minimal(self):
        """Test minimal to_dict output."""
        att = ProcessedAttachment(
            name="file.py",
            file_type=FileCategory.CODE,
            url="https://example.com/file.py",
        )
        result = att.to_dict()
        
        assert result["name"] == "file.py"
        assert result["file_type"] == "code"
        assert result["url"] == "https://example.com/file.py"
        assert "size" not in result  # 0 is excluded
        assert "error" not in result  # None is excluded
    
    def test_to_dict_full(self):
        """Test full to_dict output with all fields."""
        att = ProcessedAttachment(
            name="file.py",
            file_type=FileCategory.CODE,
            url="https://example.com/file.py",
            size=1024,
            mime_type="text/x-python",
            error="Some warning",
        )
        result = att.to_dict()
        
        assert result["size"] == 1024
        assert result["mime_type"] == "text/x-python"
        assert result["error"] == "Some warning"


# =============================================================================
# Test: Full Integration Flow
# =============================================================================

class TestFullIntegration:
    """Full integration tests."""
    
    @pytest.mark.asyncio
    async def test_complete_flow(self, subscriber, mock_storage, message_user_result):
        """Test complete flow from tool result to enhanced output."""
        subscriber._storage = mock_storage
        subscriber._storage_initialized = True
        
        mock_download = AsyncMock(return_value=b"# Python code\nprint('hello')")
        
        result = await subscriber.on_tool_complete(
            tool_name="message_user",
            tool_result=message_user_result,
            thread_id="test-thread-123",
            sandbox_download_func=mock_download,
            sandbox_id="sandbox-456",
        )
        
        assert result is not None
        assert "action" in result
        assert "attachments" in result["action"]
        
        # Should have processed both attachments
        attachments = result["action"]["attachments"]
        assert len(attachments) == 2
        
        # Check first attachment (hello.py)
        assert attachments[0]["name"] == "hello.py"
        assert attachments[0]["file_type"] == "code"
        assert "url" in attachments[0]


# =============================================================================
# Main entry point for running tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
