# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
User Message Subscriber - Production-grade attachment processing.

This module intercepts message_user tool results and processes file attachments
by downloading them from the sandbox and uploading to persistent storage (S3/local).

Architecture:
    Agent Tool (message_user) -> Sandbox path attachments
                              -> UserMessageSubscriber.on_tool_complete()
                              -> Download from sandbox
                              -> Upload to storage (S3/local)
                              -> Return public URLs

Usage:
    from backend.src.services.user_message import user_message_subscriber
    
    # In agent.py on_tool_end handler:
    if tool_name == "message_user":
        enhanced = await user_message_subscriber.on_tool_complete(
            tool_name=tool_name,
            tool_result=tool_output,
            thread_id=thread_id,
            sandbox_download_func=sandbox_download,
        )
        if enhanced:
            tool_output = enhanced
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================

class FileCategory(str, Enum):
    """File type categories for frontend display."""
    CODE = "code"
    DOCUMENTS = "documents"
    SPREADSHEET = "xlsx"
    ARCHIVE = "archive"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DATA = "data"
    OTHER = "other"


class AttachmentDict(TypedDict, total=False):
    """Type definition for processed attachment."""
    name: str
    file_type: str
    url: str
    size: int
    mime_type: str
    original_path: str
    error: Optional[str]


@dataclass
class ProcessedAttachment:
    """Represents a processed attachment with metadata."""
    name: str
    file_type: FileCategory
    url: str
    size: int = 0
    mime_type: str = "application/octet-stream"
    original_path: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> AttachmentDict:
        """Convert to dictionary for JSON serialization."""
        result: AttachmentDict = {
            "name": self.name,
            "file_type": self.file_type.value,
            "url": self.url,
        }
        if self.size > 0:
            result["size"] = self.size
        if self.mime_type != "application/octet-stream":
            result["mime_type"] = self.mime_type
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class AttachmentProcessingResult:
    """Result of processing all attachments."""
    attachments: List[ProcessedAttachment] = field(default_factory=list)
    success_count: int = 0
    error_count: int = 0
    total_bytes: int = 0


# =============================================================================
# File Type Classification
# =============================================================================

# Comprehensive file extension to category mapping (industry standard)
FILE_EXTENSION_MAP: Dict[str, FileCategory] = {
    # Code files
    ".py": FileCategory.CODE,
    ".js": FileCategory.CODE,
    ".ts": FileCategory.CODE,
    ".tsx": FileCategory.CODE,
    ".jsx": FileCategory.CODE,
    ".java": FileCategory.CODE,
    ".c": FileCategory.CODE,
    ".cpp": FileCategory.CODE,
    ".cc": FileCategory.CODE,
    ".h": FileCategory.CODE,
    ".hpp": FileCategory.CODE,
    ".cs": FileCategory.CODE,
    ".go": FileCategory.CODE,
    ".rs": FileCategory.CODE,
    ".rb": FileCategory.CODE,
    ".php": FileCategory.CODE,
    ".swift": FileCategory.CODE,
    ".kt": FileCategory.CODE,
    ".scala": FileCategory.CODE,
    ".r": FileCategory.CODE,
    ".R": FileCategory.CODE,
    ".sql": FileCategory.CODE,
    ".sh": FileCategory.CODE,
    ".bash": FileCategory.CODE,
    ".ps1": FileCategory.CODE,
    ".bat": FileCategory.CODE,
    ".cmd": FileCategory.CODE,
    ".html": FileCategory.CODE,
    ".htm": FileCategory.CODE,
    ".css": FileCategory.CODE,
    ".scss": FileCategory.CODE,
    ".sass": FileCategory.CODE,
    ".less": FileCategory.CODE,
    ".vue": FileCategory.CODE,
    ".svelte": FileCategory.CODE,
    ".yaml": FileCategory.CODE,
    ".yml": FileCategory.CODE,
    ".toml": FileCategory.CODE,
    ".ini": FileCategory.CODE,
    ".cfg": FileCategory.CODE,
    ".conf": FileCategory.CODE,
    ".json": FileCategory.CODE,
    ".xml": FileCategory.CODE,
    ".dockerfile": FileCategory.CODE,
    ".makefile": FileCategory.CODE,
    ".cmake": FileCategory.CODE,
    ".gradle": FileCategory.CODE,
    ".ipynb": FileCategory.CODE,
    
    # Documents
    ".pdf": FileCategory.DOCUMENTS,
    ".doc": FileCategory.DOCUMENTS,
    ".docx": FileCategory.DOCUMENTS,
    ".odt": FileCategory.DOCUMENTS,
    ".rtf": FileCategory.DOCUMENTS,
    ".txt": FileCategory.DOCUMENTS,
    ".md": FileCategory.DOCUMENTS,
    ".markdown": FileCategory.DOCUMENTS,
    ".rst": FileCategory.DOCUMENTS,
    ".tex": FileCategory.DOCUMENTS,
    ".latex": FileCategory.DOCUMENTS,
    ".ppt": FileCategory.DOCUMENTS,
    ".pptx": FileCategory.DOCUMENTS,
    ".odp": FileCategory.DOCUMENTS,
    ".key": FileCategory.DOCUMENTS,
    
    # Spreadsheets
    ".xls": FileCategory.SPREADSHEET,
    ".xlsx": FileCategory.SPREADSHEET,
    ".xlsm": FileCategory.SPREADSHEET,
    ".xlsb": FileCategory.SPREADSHEET,
    ".ods": FileCategory.SPREADSHEET,
    ".csv": FileCategory.SPREADSHEET,
    ".tsv": FileCategory.SPREADSHEET,
    
    # Archives
    ".zip": FileCategory.ARCHIVE,
    ".tar": FileCategory.ARCHIVE,
    ".gz": FileCategory.ARCHIVE,
    ".tgz": FileCategory.ARCHIVE,
    ".bz2": FileCategory.ARCHIVE,
    ".xz": FileCategory.ARCHIVE,
    ".7z": FileCategory.ARCHIVE,
    ".rar": FileCategory.ARCHIVE,
    ".jar": FileCategory.ARCHIVE,
    ".war": FileCategory.ARCHIVE,
    ".ear": FileCategory.ARCHIVE,
    
    # Images
    ".jpg": FileCategory.IMAGE,
    ".jpeg": FileCategory.IMAGE,
    ".png": FileCategory.IMAGE,
    ".gif": FileCategory.IMAGE,
    ".bmp": FileCategory.IMAGE,
    ".webp": FileCategory.IMAGE,
    ".svg": FileCategory.IMAGE,
    ".ico": FileCategory.IMAGE,
    ".tiff": FileCategory.IMAGE,
    ".tif": FileCategory.IMAGE,
    ".psd": FileCategory.IMAGE,
    ".ai": FileCategory.IMAGE,
    ".eps": FileCategory.IMAGE,
    
    # Video
    ".mp4": FileCategory.VIDEO,
    ".avi": FileCategory.VIDEO,
    ".mov": FileCategory.VIDEO,
    ".wmv": FileCategory.VIDEO,
    ".flv": FileCategory.VIDEO,
    ".webm": FileCategory.VIDEO,
    ".mkv": FileCategory.VIDEO,
    ".m4v": FileCategory.VIDEO,
    
    # Audio
    ".mp3": FileCategory.AUDIO,
    ".wav": FileCategory.AUDIO,
    ".flac": FileCategory.AUDIO,
    ".aac": FileCategory.AUDIO,
    ".ogg": FileCategory.AUDIO,
    ".wma": FileCategory.AUDIO,
    ".m4a": FileCategory.AUDIO,
    
    # Data files
    ".parquet": FileCategory.DATA,
    ".feather": FileCategory.DATA,
    ".arrow": FileCategory.DATA,
    ".avro": FileCategory.DATA,
    ".npy": FileCategory.DATA,
    ".npz": FileCategory.DATA,
    ".h5": FileCategory.DATA,
    ".hdf5": FileCategory.DATA,
    ".pkl": FileCategory.DATA,
    ".pickle": FileCategory.DATA,
    ".joblib": FileCategory.DATA,
    ".db": FileCategory.DATA,
    ".sqlite": FileCategory.DATA,
    ".sqlite3": FileCategory.DATA,
}


def get_file_category(filename: str) -> FileCategory:
    """
    Determine file category from filename extension.
    
    Args:
        filename: Name of the file
        
    Returns:
        FileCategory enum value
    """
    if not filename:
        return FileCategory.OTHER
    
    # Handle special filenames (no extension)
    basename = os.path.basename(filename).lower()
    if basename in ("dockerfile", "makefile", "vagrantfile", "jenkinsfile"):
        return FileCategory.CODE
    
    # Get extension
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    return FILE_EXTENSION_MAP.get(ext, FileCategory.OTHER)


def get_mime_type(filename: str) -> str:
    """
    Get MIME type for a filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def is_remote_url(path: str) -> bool:
    """
    Check if a path is a remote URL (http/https/gs/s3).
    
    Args:
        path: File path or URL
        
    Returns:
        True if path is a remote URL
    """
    if not path:
        return False
    
    parsed = urlparse(path)
    return parsed.scheme in ("http", "https", "gs", "s3", "ftp")


# =============================================================================
# User Message Subscriber
# =============================================================================

class UserMessageSubscriber:
    """
    Production-grade subscriber for processing message_user tool attachments.
    
    This class intercepts message_user tool results and processes file attachments
    by downloading them from the sandbox and uploading to persistent storage.
    
    Features:
        - Downloads files from sandbox using provided download function
        - Uploads to storage backend (S3/local via file_processing.storage)
        - Handles remote URLs by passing them through unchanged
        - Robust error handling with graceful degradation
        - Comprehensive logging for debugging
        - Thread-safe for concurrent processing
    
    Example:
        subscriber = UserMessageSubscriber()
        
        # In agent.py on_tool_end:
        if tool_name == "message_user":
            enhanced = await subscriber.on_tool_complete(
                tool_name=tool_name,
                tool_result=tool_output,
                thread_id=thread_id,
                sandbox_download_func=sandbox.download_file,
            )
    """
    
    # Tool name constant for matching
    TOOL_NAME = "message_user"
    
    # Maximum file size to process (100MB)
    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
    
    # Maximum concurrent downloads
    MAX_CONCURRENT_DOWNLOADS = 5
    
    # Signed URL expiry (7 days for S3)
    SIGNED_URL_EXPIRY_SECONDS = 7 * 24 * 60 * 60
    
    def __init__(self):
        """Initialize the subscriber."""
        self._storage = None
        self._storage_initialized = False
        
    def _get_storage(self):
        """
        Lazy-load the storage backend.
        
        Returns:
            FileStorageBackend instance
        """
        if not self._storage_initialized:
            try:
                from backend.src.services.file_processing.storage import get_storage_backend
                from backend.core.conf import settings
                
                # Get storage with configuration from settings
                if settings.FILE_STORAGE_BACKEND == "s3":
                    self._storage = get_storage_backend(
                        backend_type="s3",
                        bucket=settings.FILE_STORAGE_S3_BUCKET,
                        endpoint_url=settings.FILE_STORAGE_S3_ENDPOINT_URL or None,
                        region=settings.FILE_STORAGE_S3_REGION,
                        access_key=settings.FILE_STORAGE_S3_ACCESS_KEY or None,
                        secret_key=settings.FILE_STORAGE_S3_SECRET_KEY or None,
                        public_url_base=settings.FILE_STORAGE_S3_PUBLIC_URL_BASE or None,
                    )
                else:
                    self._storage = get_storage_backend(
                        backend_type="local",
                        base_path=settings.FILE_STORAGE_LOCAL_PATH,
                        base_url=settings.FILE_STORAGE_LOCAL_BASE_URL or None,
                    )
                    
                logger.info(f"Initialized storage backend: {settings.FILE_STORAGE_BACKEND}")
                
            except Exception as e:
                logger.error(f"Failed to initialize storage backend: {e}")
                self._storage = None
                
            self._storage_initialized = True
            
        return self._storage
    
    async def on_tool_complete(
        self,
        *,
        tool_name: str,
        tool_result: Any,
        thread_id: str,
        sandbox_download_func: Optional[Callable] = None,
        sandbox_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Process message_user tool result and enhance attachments with URLs.
        
        This method:
        1. Checks if tool is message_user
        2. Extracts attachments from tool result
        3. Downloads each attachment from sandbox
        4. Uploads to persistent storage
        5. Replaces paths with public URLs
        
        Args:
            tool_name: Name of the completed tool
            tool_result: Raw tool result (may be dict, str, or other)
            thread_id: Thread/session ID for storage path
            sandbox_download_func: Async function to download files from sandbox
            sandbox_id: Optional sandbox ID for logging
            
        Returns:
            Enhanced tool result with attachment URLs, or None if not applicable
        """
        # 1. Check if this is the message_user tool
        if tool_name != self.TOOL_NAME:
            return None
        
        # 2. Parse tool result
        parsed_result = self._parse_tool_result(tool_result)
        if not parsed_result:
            logger.debug(f"Could not parse message_user tool result: {type(tool_result)}")
            return None
        
        # 3. Extract attachments
        attachments = self._extract_attachments(parsed_result)
        if not attachments:
            logger.debug("No attachments found in message_user result")
            return None
        
        logger.info(
            f"📎 Processing {len(attachments)} attachment(s) for thread {thread_id}"
        )
        
        # 4. Process attachments
        processing_result = await self._process_attachments(
            attachments=attachments,
            thread_id=thread_id,
            sandbox_download_func=sandbox_download_func,
            sandbox_id=sandbox_id,
        )
        
        # 5. Update result with processed attachments
        enhanced_result = self._build_enhanced_result(
            parsed_result=parsed_result,
            processed_attachments=processing_result.attachments,
        )
        
        # Log summary
        logger.info(
            f"✅ Attachment processing complete: "
            f"{processing_result.success_count} succeeded, "
            f"{processing_result.error_count} failed, "
            f"{processing_result.total_bytes:,} bytes total"
        )
        
        return enhanced_result
    
    def _parse_tool_result(self, tool_result: Any) -> Optional[Dict[str, Any]]:
        """
        Parse tool result into a dictionary.
        
        Handles various input formats:
        - Already a dict
        - JSON string
        - Object with __dict__
        
        Args:
            tool_result: Raw tool result
            
        Returns:
            Parsed dictionary or None
        """
        if isinstance(tool_result, dict):
            return tool_result
        
        if isinstance(tool_result, str):
            try:
                return json.loads(tool_result)
            except json.JSONDecodeError:
                return None
        
        # Try to extract from object
        if hasattr(tool_result, "__dict__"):
            return vars(tool_result)
        
        return None
    
    def _extract_attachments(
        self, parsed_result: Dict[str, Any]
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Extract attachments from parsed tool result.
        
        The message_user tool returns structure:
        {
            "tool_name": "message",
            "action": {
                "type": "result",
                "text": "...",
                "attachments": ["/path/to/file", ...]
            }
        }
        
        Args:
            parsed_result: Parsed tool result dictionary
            
        Returns:
            List of attachment paths or attachment objects
        """
        # Try nested structure first (from message_user tool)
        action = parsed_result.get("action", {})
        if isinstance(action, dict):
            attachments = action.get("attachments", [])
            if attachments:
                return attachments
        
        # Try direct attachments key
        attachments = parsed_result.get("attachments", [])
        if attachments:
            return attachments
        
        return []
    
    async def _process_attachments(
        self,
        attachments: List[Union[str, Dict[str, Any]]],
        thread_id: str,
        sandbox_download_func: Optional[Callable],
        sandbox_id: Optional[str],
    ) -> AttachmentProcessingResult:
        """
        Process all attachments concurrently with semaphore.
        
        Args:
            attachments: List of attachment paths or objects
            thread_id: Thread ID for storage path
            sandbox_download_func: Function to download from sandbox
            sandbox_id: Sandbox ID for logging
            
        Returns:
            AttachmentProcessingResult with all processed attachments
        """
        result = AttachmentProcessingResult()
        
        # Create semaphore for concurrent downloads
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DOWNLOADS)
        
        async def process_with_semaphore(attachment):
            async with semaphore:
                return await self._process_single_attachment(
                    attachment=attachment,
                    thread_id=thread_id,
                    sandbox_download_func=sandbox_download_func,
                    sandbox_id=sandbox_id,
                )
        
        # Process all attachments concurrently
        tasks = [process_with_semaphore(att) for att in attachments]
        processed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item in processed:
            if isinstance(item, Exception):
                logger.error(f"Attachment processing failed with exception: {item}")
                result.error_count += 1
            elif isinstance(item, ProcessedAttachment):
                result.attachments.append(item)
                if item.error:
                    result.error_count += 1
                else:
                    result.success_count += 1
                    result.total_bytes += item.size
        
        return result
    
    async def _process_single_attachment(
        self,
        attachment: Union[str, Dict[str, Any]],
        thread_id: str,
        sandbox_download_func: Optional[Callable],
        sandbox_id: Optional[str],
    ) -> ProcessedAttachment:
        """
        Process a single attachment.
        
        Args:
            attachment: Attachment path (str) or object (dict)
            thread_id: Thread ID for storage path
            sandbox_download_func: Function to download from sandbox
            sandbox_id: Sandbox ID
            
        Returns:
            ProcessedAttachment with URL or error
        """
        # Normalize attachment to get path
        if isinstance(attachment, dict):
            file_path = attachment.get("path") or attachment.get("url", "")
            original_name = attachment.get("name", "")
        else:
            file_path = str(attachment)
            original_name = ""
        
        # Get filename from path
        filename = original_name or os.path.basename(file_path) or f"attachment_{uuid.uuid4().hex[:8]}"
        
        # Determine file category and MIME type
        file_category = get_file_category(filename)
        mime_type = get_mime_type(filename)
        
        # Check if already a remote URL
        if is_remote_url(file_path):
            logger.debug(f"Attachment is already a remote URL: {file_path}")
            return ProcessedAttachment(
                name=filename,
                file_type=file_category,
                url=file_path,
                mime_type=mime_type,
                original_path=file_path,
            )
        
        # Must have sandbox download function for local paths
        if not sandbox_download_func:
            logger.warning(f"No sandbox download function provided for: {file_path}")
            return ProcessedAttachment(
                name=filename,
                file_type=file_category,
                url="",
                original_path=file_path,
                error="No sandbox download function available",
            )
        
        # Download from sandbox
        try:
            logger.debug(f"Downloading from sandbox: {file_path}")
            content = await sandbox_download_func(file_path, format="bytes")
            
            if content is None:
                logger.warning(f"File not found in sandbox: {file_path}")
                return ProcessedAttachment(
                    name=filename,
                    file_type=file_category,
                    url="",
                    original_path=file_path,
                    error="File not found in sandbox",
                )
            
            file_size = len(content) if isinstance(content, bytes) else 0
            
            # Check file size
            if file_size > self.MAX_FILE_SIZE_BYTES:
                logger.warning(
                    f"File too large ({file_size:,} bytes): {file_path}"
                )
                return ProcessedAttachment(
                    name=filename,
                    file_type=file_category,
                    url="",
                    size=file_size,
                    original_path=file_path,
                    error=f"File too large: {file_size:,} bytes",
                )
            
            logger.debug(f"Downloaded {file_size:,} bytes from sandbox")
            
        except Exception as e:
            logger.error(f"Failed to download from sandbox: {file_path} - {e}")
            return ProcessedAttachment(
                name=filename,
                file_type=file_category,
                url="",
                original_path=file_path,
                error=f"Download failed: {str(e)}",
            )
        
        # Upload to storage
        try:
            url = await self._upload_to_storage(
                content=content,
                filename=filename,
                thread_id=thread_id,
                mime_type=mime_type,
            )
            
            return ProcessedAttachment(
                name=filename,
                file_type=file_category,
                url=url,
                size=file_size,
                mime_type=mime_type,
                original_path=file_path,
            )
            
        except Exception as e:
            logger.error(f"Failed to upload to storage: {filename} - {e}")
            return ProcessedAttachment(
                name=filename,
                file_type=file_category,
                url="",
                size=file_size,
                mime_type=mime_type,
                original_path=file_path,
                error=f"Upload failed: {str(e)}",
            )
    
    async def _upload_to_storage(
        self,
        content: bytes,
        filename: str,
        thread_id: str,
        mime_type: str,
    ) -> str:
        """
        Upload file content to storage and return URL.
        
        Uses the file_processing.storage backend (S3 or local).
        
        Args:
            content: File bytes
            filename: Original filename
            thread_id: Thread ID for path organization
            mime_type: MIME type for headers
            
        Returns:
            Public URL or signed URL for the uploaded file
        """
        storage = self._get_storage()
        if not storage:
            raise RuntimeError("Storage backend not initialized")
        
        # Generate unique file ID to prevent collisions
        file_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # Use thread_id as user_id for path organization
        # Storage path: {thread_id}/{file_id}/{filename}
        storage_path = await storage.upload(
            user_id=thread_id,
            file_id=file_id,
            content=content,
            filename=filename,
            mime_type=mime_type,
        )
        
        logger.debug(f"Uploaded to storage: {storage_path}")
        
        # Get URL for the uploaded file
        url = await storage.get_url(storage_path, expires_in=self.SIGNED_URL_EXPIRY_SECONDS)
        
        if not url:
            # For local storage without base_url, return storage path
            # The frontend should handle serving this
            logger.warning(f"No URL available for storage path: {storage_path}")
            url = f"/api/v1/files/download/{storage_path}"
        
        return url
    
    def _build_enhanced_result(
        self,
        parsed_result: Dict[str, Any],
        processed_attachments: List[ProcessedAttachment],
    ) -> Dict[str, Any]:
        """
        Build enhanced result with processed attachments.
        
        Maintains the original structure but replaces attachments
        with processed versions containing URLs.
        
        Args:
            parsed_result: Original parsed result
            processed_attachments: List of processed attachments
            
        Returns:
            Enhanced result dictionary
        """
        # Deep copy to avoid modifying original
        import copy
        enhanced = copy.deepcopy(parsed_result)
        
        # Convert processed attachments to dicts
        attachment_dicts = [att.to_dict() for att in processed_attachments]
        
        # Update nested structure (message_user format)
        if "action" in enhanced and isinstance(enhanced["action"], dict):
            enhanced["action"]["attachments"] = attachment_dicts
        else:
            # Fallback: set at top level
            enhanced["attachments"] = attachment_dicts
        
        return enhanced


# =============================================================================
# Singleton Instance
# =============================================================================

# Global singleton for use throughout the application
user_message_subscriber = UserMessageSubscriber()
