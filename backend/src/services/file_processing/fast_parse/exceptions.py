# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
FastParse Exceptions - Custom exception classes for file parsing errors.

Adapted from SUNA project's fast_parse/exceptions.py.
"""

from typing import Any, Dict, Optional


class FastParseError(Exception):
    """
    Base exception for all FastParse errors.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code
        details: Additional context about the error
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "PARSE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class FileSizeExceededError(FastParseError):
    """Raised when file exceeds maximum size limit."""
    
    def __init__(
        self,
        file_size: int,
        max_size: int,
        filename: Optional[str] = None,
    ):
        self.file_size = file_size
        self.max_size = max_size
        self.filename = filename
        
        message = (
            f"File size ({file_size:,} bytes) exceeds maximum limit "
            f"({max_size:,} bytes)"
        )
        if filename:
            message = f"{filename}: {message}"
        
        super().__init__(
            message=message,
            error_code="FILE_SIZE_EXCEEDED",
            details={
                "file_size": file_size,
                "max_size": max_size,
                "filename": filename,
            },
        )


class UnsupportedFormatError(FastParseError):
    """Raised when file format is not supported."""
    
    def __init__(
        self,
        format_type: str,
        filename: Optional[str] = None,
        supported_formats: Optional[list] = None,
    ):
        self.format_type = format_type
        self.filename = filename
        self.supported_formats = supported_formats or []
        
        message = f"Unsupported file format: {format_type}"
        if filename:
            message = f"{filename}: {message}"
        
        super().__init__(
            message=message,
            error_code="UNSUPPORTED_FORMAT",
            details={
                "format_type": format_type,
                "filename": filename,
                "supported_formats": self.supported_formats,
            },
        )


class CorruptedFileError(FastParseError):
    """Raised when file is corrupted or invalid."""
    
    def __init__(
        self,
        filename: Optional[str] = None,
        format_type: Optional[str] = None,
        original_error: Optional[str] = None,
    ):
        self.filename = filename
        self.format_type = format_type
        self.original_error = original_error
        
        message = "File is corrupted or invalid"
        if format_type:
            message = f"Invalid or corrupted {format_type.upper()} file"
        if filename:
            message = f"{filename}: {message}"
        if original_error:
            message = f"{message}: {original_error}"
        
        super().__init__(
            message=message,
            error_code="CORRUPTED_FILE",
            details={
                "filename": filename,
                "format_type": format_type,
                "original_error": original_error,
            },
        )


class EncodingError(FastParseError):
    """Raised when file encoding cannot be detected or decoded."""
    
    def __init__(
        self,
        filename: Optional[str] = None,
        detected_encoding: Optional[str] = None,
        original_error: Optional[str] = None,
    ):
        self.filename = filename
        self.detected_encoding = detected_encoding
        self.original_error = original_error
        
        message = "Failed to decode file content"
        if detected_encoding:
            message = f"{message} (detected encoding: {detected_encoding})"
        if filename:
            message = f"{filename}: {message}"
        
        super().__init__(
            message=message,
            error_code="ENCODING_ERROR",
            details={
                "filename": filename,
                "detected_encoding": detected_encoding,
                "original_error": original_error,
            },
        )


class DependencyMissingError(FastParseError):
    """Raised when a required library is not installed."""
    
    def __init__(
        self,
        dependency: str,
        format_type: Optional[str] = None,
        install_command: Optional[str] = None,
    ):
        self.dependency = dependency
        self.format_type = format_type
        self.install_command = install_command
        
        message = f"Required dependency not installed: {dependency}"
        if format_type:
            message = f"{message} (needed for {format_type} parsing)"
        if install_command:
            message = f"{message}. Install with: {install_command}"
        
        super().__init__(
            message=message,
            error_code="MISSING_DEPENDENCY",
            details={
                "dependency": dependency,
                "format_type": format_type,
                "install_command": install_command,
            },
        )


class SecurityWarningError(FastParseError):
    """Raised when potentially dangerous content is detected."""
    
    def __init__(
        self,
        patterns_found: list,
        filename: Optional[str] = None,
    ):
        self.patterns_found = patterns_found
        self.filename = filename
        
        patterns_str = ", ".join(patterns_found[:3])
        if len(patterns_found) > 3:
            patterns_str += f" (and {len(patterns_found) - 3} more)"
        
        message = f"Potentially dangerous content detected: {patterns_str}"
        if filename:
            message = f"{filename}: {message}"
        
        super().__init__(
            message=message,
            error_code="SECURITY_WARNING",
            details={
                "patterns_found": patterns_found,
                "filename": filename,
            },
        )


class ImageAnalysisError(FastParseError):
    """Raised when image analysis fails."""
    
    def __init__(
        self,
        filename: Optional[str] = None,
        original_error: Optional[str] = None,
    ):
        self.filename = filename
        self.original_error = original_error
        
        message = "Failed to analyze image"
        if filename:
            message = f"{filename}: {message}"
        if original_error:
            message = f"{message}: {original_error}"
        
        super().__init__(
            message=message,
            error_code="IMAGE_ANALYSIS_ERROR",
            details={
                "filename": filename,
                "original_error": original_error,
            },
        )


class TruncationWarning(FastParseError):
    """Warning raised when content was truncated."""
    
    def __init__(
        self,
        original_size: int,
        truncated_size: int,
        truncation_type: str = "characters",
        filename: Optional[str] = None,
    ):
        self.original_size = original_size
        self.truncated_size = truncated_size
        self.truncation_type = truncation_type
        self.filename = filename
        
        message = (
            f"Content truncated from {original_size:,} to {truncated_size:,} "
            f"{truncation_type}"
        )
        if filename:
            message = f"{filename}: {message}"
        
        super().__init__(
            message=message,
            error_code="CONTENT_TRUNCATED",
            details={
                "original_size": original_size,
                "truncated_size": truncated_size,
                "truncation_type": truncation_type,
                "filename": filename,
            },
        )


def classify_exception(exc: Exception) -> FastParseError:
    """
    Convert a generic exception to a FastParseError.
    
    Args:
        exc: The exception to classify
        
    Returns:
        An appropriate FastParseError subclass
    """
    error_str = str(exc).lower()
    
    # Check for common patterns
    if "not installed" in error_str or "no module named" in error_str:
        return DependencyMissingError(
            dependency=str(exc),
            original_error=str(exc),
        )
    
    if "corrupt" in error_str or "invalid" in error_str:
        return CorruptedFileError(original_error=str(exc))
    
    if "encoding" in error_str or "decode" in error_str or "codec" in error_str:
        return EncodingError(original_error=str(exc))
    
    # Default to base error
    return FastParseError(
        message=f"Parsing failed: {str(exc)}",
        error_code="PARSE_ERROR",
        details={"original_error": str(exc)},
    )
