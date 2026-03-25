"""
Slide content processor for replacing local file paths with permanent storage URLs.

This module processes HTML slide content to find local file references (images,
stylesheets, etc.) and uploads them to permanent storage, replacing the local
paths with permanent URLs.

This ensures slides remain viewable after sandbox cleanup or when accessed
from the frontend without sandbox context.

Features:
- Finds src, href, and CSS url() references
- Downloads files from sandbox
- Uploads to S3/Supabase storage with content-based deduplication
- Caches URLs within a processing session
- Handles relative and absolute paths

Usage:
    from backend.src.services.slides.content_processor import SlideContentProcessor
    
    processor = SlideContentProcessor(sandbox_download_func=sandbox.download_file)
    processed_html = await processor.process_html_content(
        html=slide_html,
        sandbox_id="sandbox-123",
        thread_id="thread-456",
    )

Adapted from external_slide_system/slides/content_processor.py with project-specific integrations.
"""

import hashlib
import logging
import mimetypes
import posixpath
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple
from urllib.parse import unquote

logger = logging.getLogger(__name__)


# Compiled regex patterns for finding file references in HTML
# These patterns are designed to match various HTML and CSS file reference formats
FILE_REFERENCE_PATTERNS: List[Tuple[str, Pattern]] = [
    # src="..." and src='...' - matches images, scripts, iframes, video, audio
    ("src_double", re.compile(r'src="([^"]+)"', re.IGNORECASE)),
    ("src_single", re.compile(r"src='([^']+)'", re.IGNORECASE)),
    
    # href="..." and href='...' - matches stylesheets, links
    ("href_double", re.compile(r'href="([^"]+)"', re.IGNORECASE)),
    ("href_single", re.compile(r"href='([^']+)'", re.IGNORECASE)),
    
    # CSS url("...") and url('...') and url(...)
    ("url_double", re.compile(r'url\("([^"]+)"\)', re.IGNORECASE)),
    ("url_single", re.compile(r"url\('([^']+)'\)", re.IGNORECASE)),
    ("url_bare", re.compile(r'url\(([^"\')][^)]*)\)', re.IGNORECASE)),
    
    # Background attribute (legacy HTML)
    ("background", re.compile(r'background="([^"]+)"', re.IGNORECASE)),
    
    # poster attribute for video elements
    ("poster", re.compile(r'poster="([^"]+)"', re.IGNORECASE)),
]

# Prefixes that indicate the path is already external and shouldn't be processed
EXTERNAL_URL_PREFIXES = frozenset([
    "http://",
    "https://",
    "data:",
    "//",  # Protocol-relative URL
    "mailto:",
    "tel:",
    "javascript:",
    "blob:",
    "#",  # Fragment link
])

# Prefixes that indicate a local sandbox path
LOCAL_PATH_PREFIXES = frozenset([
    "/workspace/",
    "/home/",
    "workspace/",
    "./",
    "../",
])


class SlideContentProcessor:
    """
    Processes slide HTML content to replace local file paths with permanent URLs.
    
    This class handles:
    - Finding all file references in HTML/CSS
    - Downloading files from the sandbox
    - Uploading to permanent storage (S3/Supabase)
    - Content-based deduplication via hashing
    - URL caching for session-level efficiency
    
    Thread Safety:
        The processor maintains internal state (cache) and should be used
        per-thread or per-session. Create a new instance for each session.
    """

    def __init__(
        self,
        storage: Any = None,
        sandbox_download_func: Optional[Callable] = None,
    ):
        """
        Initialize the content processor.
        
        Args:
            storage: Optional storage backend (default: from config)
            sandbox_download_func: Async function to download files from sandbox
                                   Signature: async (sandbox_id: str, path: str) -> bytes
        """
        self._storage = storage
        self._sandbox_download_func = sandbox_download_func
        
        # Session-level cache: {local_path -> permanent_url}
        self._url_cache: Dict[str, str] = {}
        
        # Content hash cache: {content_hash -> permanent_url}
        self._hash_cache: Dict[str, str] = {}

    @property
    def storage(self):
        """Lazy load storage backend."""
        if self._storage is None:
            from backend.src.services.file_processing.storage import get_storage_backend
            self._storage = get_storage_backend()
        return self._storage

    async def process_html_content(
        self,
        html: str,
        sandbox_id: str,
        thread_id: str,
        slide_filepath: Optional[str] = None,
    ) -> str:
        """
        Process HTML content to replace local file paths with permanent URLs.
        
        Args:
            html: The HTML slide content
            sandbox_id: ID of the sandbox containing the files
            thread_id: Thread ID for organizing storage paths
            slide_filepath: Optional path to slide file for resolving relative paths
            
        Returns:
            HTML content with local paths replaced by permanent URLs
        """
        if not self._sandbox_download_func:
            logger.warning("No sandbox_download_func provided, skipping content processing")
            return html
        
        if not html:
            return html
        
        logger.info(f"Processing slide content for thread {thread_id}")
        
        # Find all local file references
        references = self._find_local_references(html)
        
        if not references:
            logger.debug("No local file references found in HTML")
            return html
        
        logger.info(f"Found {len(references)} local file references to process")
        
        # Process each reference
        replacements_made = 0
        
        for local_path in references:
            try:
                permanent_url = await self._get_or_upload_file(
                    local_path=local_path,
                    sandbox_id=sandbox_id,
                    thread_id=thread_id,
                    slide_filepath=slide_filepath,
                )
                
                if permanent_url and permanent_url != local_path:
                    # Replace all occurrences of this path
                    html = html.replace(local_path, permanent_url)
                    replacements_made += 1
                    logger.debug(f"Replaced: {local_path} -> {permanent_url}")
                    
            except Exception as e:
                logger.warning(f"Failed to process {local_path}: {e}")
                # Keep original path on failure - slide will still display
        
        if replacements_made > 0:
            logger.info(f"Made {replacements_made} URL replacements in slide content")
        
        return html

    def _find_local_references(self, html: str) -> List[str]:
        """
        Find all local file references in HTML content.
        
        This scans the HTML for:
        - src and href attributes
        - CSS url() functions
        - background attributes
        - poster attributes
        
        Args:
            html: HTML content to scan
            
        Returns:
            List of unique local file paths found
        """
        references = set()
        
        for pattern_name, pattern in FILE_REFERENCE_PATTERNS:
            for match in pattern.finditer(html):
                path = match.group(1).strip()
                
                # Skip empty paths
                if not path:
                    continue
                
                # Decode URL encoding
                path = unquote(path)
                
                # Skip external URLs
                if self._is_external_url(path):
                    continue
                
                # Skip if it doesn't look like a file path
                if not self._is_local_path(path):
                    continue
                
                references.add(path)
        
        return list(references)

    def _is_external_url(self, path: str) -> bool:
        """Check if path is already an external URL or special scheme."""
        path_lower = path.lower()
        for prefix in EXTERNAL_URL_PREFIXES:
            if path_lower.startswith(prefix):
                return True
        return False

    def _is_local_path(self, path: str) -> bool:
        """Check if path looks like a local file path that we should process."""
        # Any path starting with our known local prefixes
        for prefix in LOCAL_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
        
        # Relative paths that look like files (have extension or are in known dirs)
        if "/" in path or path.count(".") >= 1:
            # Check for common file extensions
            common_extensions = {
                ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
                ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
                ".mp4", ".webm", ".ogg", ".mp3", ".wav",
                ".pdf", ".json", ".xml",
            }
            for ext in common_extensions:
                if path.lower().endswith(ext):
                    return True
        
        return False

    async def _get_or_upload_file(
        self,
        local_path: str,
        sandbox_id: str,
        thread_id: str,
        slide_filepath: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get file from cache or upload to storage.
        
        This method:
        1. Checks URL cache for previously processed paths
        2. Resolves the path to sandbox absolute path
        3. Downloads from sandbox
        4. Generates content hash for deduplication
        5. Checks hash cache for identical content
        6. Uploads to storage if needed
        7. Returns permanent URL
        
        Args:
            local_path: The local path from HTML
            sandbox_id: Sandbox containing the file
            thread_id: Thread ID for storage organization
            slide_filepath: Optional slide path for resolving relative paths
            
        Returns:
            Permanent URL or None if not found/failed
        """
        # Check URL cache first (path-based, fastest)
        cache_key = f"{sandbox_id}:{local_path}"
        if cache_key in self._url_cache:
            return self._url_cache[cache_key]
        
        # Resolve to sandbox path
        resolved_path = self._resolve_sandbox_path(local_path, slide_filepath)
        if not resolved_path:
            logger.debug(f"Could not resolve path: {local_path}")
            return None
        
        # Download from sandbox
        try:
            file_content = await self._download_from_sandbox(sandbox_id, resolved_path)
            if not file_content:
                logger.warning(f"File not found in sandbox: {resolved_path}")
                return None
        except Exception as e:
            logger.warning(f"Failed to download {resolved_path} from sandbox: {e}")
            return None
        
        # Generate content hash for deduplication
        content_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check hash cache (content-based deduplication)
        if content_hash in self._hash_cache:
            url = self._hash_cache[content_hash]
            self._url_cache[cache_key] = url
            logger.debug(f"Found cached URL for content hash: {content_hash[:12]}")
            return url
        
        # Generate storage path
        filename = Path(resolved_path).name
        storage_path = self._generate_storage_path(content_hash, filename, thread_id)
        
        # Check if already exists in storage
        try:
            if await self.storage.exists(storage_path):
                url = await self.storage.get_url(storage_path, expires_in=86400 * 7)  # 7 days
                if url:
                    self._hash_cache[content_hash] = url
                    self._url_cache[cache_key] = url
                    logger.debug(f"File already in storage: {storage_path}")
                    return url
        except Exception as e:
            logger.debug(f"Storage exists check failed: {e}")
        
        # Upload to storage
        try:
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            
            await self.storage.upload(
                user_id=f"slides_{thread_id[:8]}",  # Organize by thread
                file_id=content_hash[:16],
                content=file_content,
                filename=filename,
                mime_type=mime_type,
            )
            
            # Get permanent URL
            url = await self.storage.get_url(storage_path, expires_in=86400 * 7)
            
            if url:
                self._hash_cache[content_hash] = url
                self._url_cache[cache_key] = url
                logger.info(f"Uploaded {filename} to storage, URL: {url[:60]}...")
                return url
            else:
                logger.warning(f"Upload succeeded but failed to get URL for {storage_path}")
                
        except Exception as e:
            logger.error(f"Failed to upload {filename} to storage: {e}")
        
        return None

    async def _download_from_sandbox(self, sandbox_id: str, path: str) -> Optional[bytes]:
        """
        Download a file from the sandbox.
        
        Args:
            sandbox_id: Sandbox ID (may not be needed depending on download func)
            path: Path within sandbox
            
        Returns:
            File content as bytes or None if not found
        """
        if not self._sandbox_download_func:
            return None
        
        try:
            # The download function signature varies by implementation
            # Try different call patterns
            import inspect
            sig = inspect.signature(self._sandbox_download_func)
            params = list(sig.parameters.keys())
            
            # If function takes sandbox_id as first arg
            if len(params) >= 2 and 'sandbox_id' in params[0].lower():
                result = await self._sandbox_download_func(sandbox_id, path)
            # If function takes path only (sandbox already bound)
            elif len(params) == 1:
                result = await self._sandbox_download_func(path)
            # Fallback: try with path and format
            else:
                result = await self._sandbox_download_func(path, format="bytes")
            
            # Handle different return types
            if isinstance(result, bytes):
                return result
            elif isinstance(result, str):
                return result.encode("utf-8")
            elif result is not None:
                return bytes(result)
            
            return None
            
        except Exception as e:
            logger.debug(f"Sandbox download failed for {path}: {e}")
            return None

    def _resolve_sandbox_path(
        self,
        path: str,
        slide_filepath: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve a file path to an absolute sandbox path.
        
        Args:
            path: Path from HTML (relative or absolute)
            slide_filepath: Optional slide file path for relative resolution
            
        Returns:
            Resolved absolute sandbox path or None if invalid
        """
        try:
            # Decode URL encoding
            path = unquote(path)
            
            # Already absolute
            if path.startswith("/"):
                return posixpath.normpath(path)
            
            # Relative path - resolve against slide directory
            if slide_filepath:
                slide_dir = posixpath.dirname(slide_filepath)
                resolved = posixpath.join(slide_dir, path)
                return posixpath.normpath(resolved)
            
            # Default: assume relative to /workspace
            resolved = posixpath.join("/workspace", path)
            return posixpath.normpath(resolved)
            
        except Exception as e:
            logger.debug(f"Path resolution failed for {path}: {e}")
            return None

    def _generate_storage_path(
        self,
        content_hash: str,
        filename: str,
        thread_id: str,
    ) -> str:
        """
        Generate a storage path for the file.
        
        Uses content hash for deduplication and thread_id for organization.
        
        Args:
            content_hash: SHA-256 hash of file content
            filename: Original filename (for extension)
            thread_id: Thread ID for path organization
            
        Returns:
            Storage path string
        """
        # Get file extension
        extension = Path(filename).suffix or ""
        
        # Use first 16 chars of hash (sufficient for uniqueness)
        hash_prefix = content_hash[:16]
        
        # Create organized storage path
        # Format: slides/assets/{thread_prefix}/{hash_prefix}{extension}
        thread_prefix = thread_id[:8] if thread_id else "default"
        
        return f"slides/assets/{thread_prefix}/{hash_prefix}{extension}"

    def clear_cache(self) -> None:
        """
        Clear all caches.
        
        Call this between processing different presentations or sessions
        to free memory.
        """
        self._url_cache.clear()
        self._hash_cache.clear()
        logger.debug("Content processor caches cleared")


# Convenience function for one-off processing
async def process_slide_content(
    html: str,
    sandbox_id: str,
    thread_id: str,
    sandbox_download_func: Callable,
    storage: Any = None,
) -> str:
    """
    Process slide HTML content to replace local paths with permanent URLs.
    
    This is a convenience function that creates a processor and processes
    the content in one call. For processing multiple slides, create a
    SlideContentProcessor instance and reuse it for cache efficiency.
    
    Args:
        html: HTML slide content
        sandbox_id: Sandbox containing referenced files
        thread_id: Thread ID for storage organization
        sandbox_download_func: Async function to download sandbox files
        storage: Optional storage backend
        
    Returns:
        Processed HTML with permanent URLs
    """
    processor = SlideContentProcessor(
        storage=storage,
        sandbox_download_func=sandbox_download_func,
    )
    
    return await processor.process_html_content(
        html=html,
        sandbox_id=sandbox_id,
        thread_id=thread_id,
    )
