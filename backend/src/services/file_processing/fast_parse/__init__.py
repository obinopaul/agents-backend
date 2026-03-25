# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
FastParse Module - Comprehensive file parsing and text extraction.

Adapted from SUNA project's fast_parse module.
Supports: PDF, Word (docx, doc, rtf, odt), Excel (xlsx, xls, csv, ods),
PowerPoint (pptx, ppt, odp), text files, and images.

Usage:
    from backend.src.services.file_processing.fast_parse import parse, FileType
    
    result = parse(file_bytes, "document.pdf", "application/pdf")
    if result.success:
        print(result.content)  # Extracted text
        print(result.metadata)  # File metadata
"""

from backend.src.services.file_processing.fast_parse.parser import (
    FastParse,
    ParseResult,
    ParseError,
    FileType,
    parse,
    parse_file,
    get_parser,
)

from backend.src.services.file_processing.fast_parse.config import (
    FastParseConfig,
    DEFAULT_CONFIG,
)

from backend.src.services.file_processing.fast_parse.utils import (
    sanitize_filename,
    sanitize_filename_for_path,
    format_file_size,
    get_file_extension,
    get_mime_type,
    strip_script_tags,
    normalize_whitespace,
    truncate_content,
    extract_preview,
    is_supported_file,
    get_supported_extensions,
)

from backend.src.services.file_processing.fast_parse.exceptions import (
    FastParseError,
    FileSizeExceededError,
    UnsupportedFormatError,
    CorruptedFileError,
    EncodingError,
    DependencyMissingError,
    SecurityWarningError,
)

__all__ = [
    # Core parser
    "FastParse",
    "ParseResult",
    "ParseError",
    "FileType",
    "parse",
    "parse_file",
    "get_parser",
    # Config
    "FastParseConfig",
    "DEFAULT_CONFIG",
    # Utils
    "sanitize_filename",
    "sanitize_filename_for_path",
    "format_file_size",
    "get_file_extension",
    "get_mime_type",
    "strip_script_tags",
    "normalize_whitespace",
    "truncate_content",
    "extract_preview",
    "is_supported_file",
    "get_supported_extensions",
    # Exceptions
    "FastParseError",
    "FileSizeExceededError",
    "UnsupportedFormatError",
    "CorruptedFileError",
    "EncodingError",
    "DependencyMissingError",
    "SecurityWarningError",
]
