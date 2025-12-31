# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
FastParse Utilities - Helper functions for file parsing.

Adapted from SUNA project's fast_parse/utils.py.
"""

import mimetypes
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional, Set

from backend.src.services.file_processing.fast_parse.config import DEFAULT_CONFIG


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe storage.
    
    Removes or replaces characters that could cause issues:
    - Path separators (/, \\)
    - Null bytes
    - Control characters
    - Leading/trailing whitespace and dots
    
    Args:
        filename: Original filename
        max_length: Maximum length of the result
        
    Returns:
        Sanitized filename safe for storage
    """
    if not filename:
        return "unnamed_file"
    
    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)
    
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Remove null bytes and control characters
    filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip().strip(".")
    
    # Replace multiple underscores/spaces with single underscore
    filename = re.sub(r"[_\s]+", "_", filename)
    
    # Truncate if too long, preserving extension
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_len = max_length - len(ext)
        if max_name_len > 0:
            filename = name[:max_name_len] + ext
        else:
            filename = filename[:max_length]
    
    return filename or "unnamed_file"


def sanitize_filename_for_path(filename: str) -> str:
    """
    Sanitize filename for use in a storage path.
    
    More aggressive sanitization that only allows alphanumeric,
    underscore, hyphen, and dot characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Path-safe filename
    """
    if not filename:
        return "unnamed_file"
    
    # Get name and extension
    name, ext = os.path.splitext(filename)
    
    # Keep only safe characters
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    safe_ext = re.sub(r"[^a-zA-Z0-9]", "", ext.lstrip("."))
    
    # Remove multiple underscores
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")
    
    # Ensure we have something
    if not safe_name:
        safe_name = "file"
    
    # Combine
    if safe_ext:
        return f"{safe_name}.{safe_ext}"
    return safe_name


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string (e.g., "2.5 MB")
    """
    if size_bytes < 0:
        return "Unknown"
    
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            if unit == "B":
                return f"{size_bytes} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    
    return f"{size_bytes:.1f} PB"


def get_file_extension(filename: str) -> str:
    """
    Get lowercase file extension from filename.
    
    Args:
        filename: The filename
        
    Returns:
        Lowercase extension including dot (e.g., ".pdf")
    """
    return Path(filename).suffix.lower()


def get_mime_type(filename: str, default: str = "application/octet-stream") -> str:
    """
    Guess MIME type from filename.
    
    Args:
        filename: The filename
        default: Default MIME type if unknown
        
    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or default


def strip_script_tags(content: str) -> str:
    """
    Remove script tags and inline JavaScript from content.
    
    Args:
        content: HTML or text content
        
    Returns:
        Content with script elements removed
    """
    # Remove script tags and their content
    content = re.sub(
        r"<script[^>]*>.*?</script>",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    
    # Remove inline event handlers
    content = re.sub(
        r'\s+on\w+\s*=\s*["\'][^"\']*["\']',
        "",
        content,
        flags=re.IGNORECASE,
    )
    
    # Remove javascript: URLs
    content = re.sub(
        r'href\s*=\s*["\']javascript:[^"\']*["\']',
        'href="#"',
        content,
        flags=re.IGNORECASE,
    )
    
    return content


def normalize_whitespace(content: str) -> str:
    """
    Normalize whitespace in content.
    
    - Converts all whitespace to single spaces
    - Preserves paragraph breaks (double newlines)
    - Strips leading/trailing whitespace
    
    Args:
        content: Text content
        
    Returns:
        Content with normalized whitespace
    """
    # Preserve paragraph breaks
    content = re.sub(r"\n\s*\n", "\n\n", content)
    
    # Convert other whitespace sequences to single space
    content = re.sub(r"[^\S\n]+", " ", content)
    
    # Clean up line boundaries
    content = re.sub(r" *\n *", "\n", content)
    
    return content.strip()


def truncate_content(
    content: str,
    max_chars: int,
    suffix: str = "\n\n[Content truncated...]",
) -> tuple[str, bool]:
    """
    Truncate content to a maximum number of characters.
    
    Args:
        content: Text content to truncate
        max_chars: Maximum characters
        suffix: Suffix to append if truncated
        
    Returns:
        Tuple of (truncated_content, was_truncated)
    """
    if len(content) <= max_chars:
        return content, False
    
    # Try to truncate at a word boundary
    truncated = content[: max_chars - len(suffix)]
    
    # Find last space or newline
    last_space = truncated.rfind(" ")
    last_newline = truncated.rfind("\n")
    cut_point = max(last_space, last_newline)
    
    if cut_point > max_chars // 2:  # Only cut at boundary if not too far back
        truncated = truncated[:cut_point]
    
    return truncated.rstrip() + suffix, True


def extract_preview(content: str, max_chars: int = 500) -> str:
    """
    Extract a preview from content.
    
    Args:
        content: Full text content
        max_chars: Maximum characters for preview
        
    Returns:
        Preview text
    """
    if not content:
        return ""
    
    preview, _ = truncate_content(content, max_chars, suffix="...")
    return preview


def is_supported_file(
    filename: str,
    config: Optional["FastParseConfig"] = None,
) -> bool:
    """
    Check if a file is supported for parsing.
    
    Args:
        filename: The filename to check
        config: Optional FastParseConfig for custom extensions
        
    Returns:
        True if the file type is supported
    """
    if config is None:
        config = DEFAULT_CONFIG
    
    ext = get_file_extension(filename)
    
    all_extensions: Set[str] = set()
    all_extensions.update(config.text_extensions)
    all_extensions.update(config.pdf_extensions)
    all_extensions.update(config.word_extensions)
    all_extensions.update(config.excel_extensions)
    all_extensions.update(config.presentation_extensions)
    all_extensions.update(config.image_extensions)
    
    return ext in all_extensions


def get_supported_extensions(
    config: Optional["FastParseConfig"] = None,
) -> Set[str]:
    """
    Get all supported file extensions.
    
    Args:
        config: Optional FastParseConfig
        
    Returns:
        Set of supported extensions
    """
    if config is None:
        config = DEFAULT_CONFIG
    
    all_extensions: Set[str] = set()
    all_extensions.update(config.text_extensions)
    all_extensions.update(config.pdf_extensions)
    all_extensions.update(config.word_extensions)
    all_extensions.update(config.excel_extensions)
    all_extensions.update(config.presentation_extensions)
    all_extensions.update(config.image_extensions)
    
    return all_extensions


def format_parse_result_header(
    filename: str,
    file_size: int,
    metadata: dict,
) -> str:
    """
    Format a header for parsed content.
    
    Args:
        filename: Original filename
        file_size: File size in bytes
        metadata: Parsed metadata dict
        
    Returns:
        Formatted header string
    """
    parts = [f"# {filename}"]
    
    if metadata.get("total_pages"):
        parts.append(f"Pages: {metadata['total_pages']}")
    if metadata.get("sheet_count"):
        parts.append(f"Sheets: {metadata['sheet_count']}")
    if metadata.get("slide_count"):
        parts.append(f"Slides: {metadata['slide_count']}")
    if metadata.get("paragraph_count"):
        parts.append(f"Paragraphs: {metadata['paragraph_count']}")
    
    parts.append(f"Size: {format_file_size(file_size)}")
    parts.append("")  # Empty line before content
    
    return "\n".join(parts)


def result_to_markdown(
    content: str,
    filename: str,
    file_size: int,
    metadata: dict,
) -> str:
    """
    Format parse result as markdown.
    
    Args:
        content: Extracted text content
        filename: Original filename
        file_size: File size
        metadata: Parsed metadata
        
    Returns:
        Markdown-formatted content with header
    """
    header = format_parse_result_header(filename, file_size, metadata)
    return header + content


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text from documents.
    
    Removes common artifacts from PDF/document extraction:
    - Form feed characters
    - Excessive whitespace
    - Non-printable characters
    
    Args:
        text: Raw extracted text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove form feed and other control characters
    text = re.sub(r"[\f\v]", "\n", text)
    
    # Remove non-printable characters except newlines and tabs
    text = re.sub(r"[^\x20-\x7E\n\t\r]", "", text)
    
    # Normalize whitespace
    text = normalize_whitespace(text)
    
    return text
