# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
File Processing Service Module.

This module provides comprehensive file handling capabilities:
- File parsing and text extraction (PDF, Word, Excel, PowerPoint)
- Image compression and optimization
- Storage backends (local filesystem, S3-compatible)
- Staged file management for chat attachments

Components:
- fast_parse: Text extraction from various document formats
- storage: Pluggable storage backends
- image_utils: Image compression and resizing
"""

from backend.src.services.file_processing.fast_parse import (
    FastParse,
    ParseResult,
    ParseError,
    FileType,
    FastParseConfig,
    parse,
    parse_file,
    sanitize_filename,
    sanitize_filename_for_path,
    format_file_size,
    get_mime_type as detect_mime_type,
    is_supported_file,
)

from backend.src.services.file_processing.storage import (
    FileStorageBackend,
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

__all__ = [
    # Fast Parse exports
    "FastParse",
    "ParseResult",
    "ParseError",
    "FileType",
    "FastParseConfig",
    "parse",
    "parse_file",
    "sanitize_filename",
    "sanitize_filename_for_path",
    "format_file_size",
    "detect_mime_type",
    "is_supported_file",
    # Storage exports
    "FileStorageBackend",
    "LocalFileStorage",
    "get_storage_backend",
    "reset_storage_backend",
    # Image utils exports
    "compress_image",
    "is_image_mime",
    "get_image_dimensions",
    "create_thumbnail",
]

