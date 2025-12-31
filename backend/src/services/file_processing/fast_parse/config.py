# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
FastParse Configuration - Configurable limits and file type mappings.

Adapted from SUNA project's fast_parse/config.py.
"""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class FastParseConfig:
    """
    Configuration for the FastParse file parser.
    
    Attributes:
        max_file_size_bytes: Maximum file size to process (default: 100MB)
        max_pdf_pages: Maximum PDF pages to extract (default: 500)
        max_excel_rows: Maximum Excel rows to process (default: 100,000)
        max_excel_sheets: Maximum Excel sheets to process (default: 50)
        max_text_chars: Maximum characters for text files (default: 10M)
        chunk_size: Read chunk size for streaming (default: 64KB)
        enable_script_detection: Detect potentially dangerous patterns (default: True)
        enable_image_analysis: Extract image metadata (default: True)
        image_analysis_timeout: Timeout for image analysis in seconds (default: 30)
    """
    
    # Size limits
    max_file_size_bytes: int = 100 * 1024 * 1024  # 100MB
    max_pdf_pages: int = 500
    max_excel_rows: int = 100_000
    max_excel_sheets: int = 50
    max_text_chars: int = 10_000_000  # 10M characters
    chunk_size: int = 65536  # 64KB
    
    # Security settings
    enable_script_detection: bool = True
    enable_image_analysis: bool = True
    image_analysis_timeout: float = 30.0
    
    # Dangerous patterns to detect in content
    dangerous_patterns: Set[str] = field(default_factory=lambda: {
        "<script",
        "javascript:",
        "vbscript:",
        "data:text/html",
        "eval(",
        "exec(",
        "__import__",
        "os.system",
        "subprocess",
        "shell=True",
    })
    
    # Text file extensions (code, config, documentation)
    text_extensions: Set[str] = field(default_factory=lambda: {
        # Plain text
        ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
        # Config formats
        ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        # Web
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        # Python
        ".py", ".pyw", ".pyi", ".pyx",
        # JavaScript/TypeScript
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        # JVM languages
        ".java", ".kt", ".kts", ".scala", ".groovy",
        # C-family
        ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx",
        # .NET
        ".cs", ".fs", ".fsx",
        # Systems languages
        ".go", ".rs", ".swift", ".m", ".mm",
        # Scripting
        ".rb", ".rake", ".gemspec",
        ".php", ".phtml",
        ".pl", ".pm", ".pod",
        ".lua", ".r", ".R", ".jl",
        # Shell
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".psm1", ".bat", ".cmd",
        # Query/schema
        ".sql", ".graphql", ".gql",
        # Frontend frameworks
        ".vue", ".svelte", ".astro",
        # Build/config
        ".dockerfile", ".docker",
        ".makefile", ".cmake",
        ".env", ".envrc", ".gitignore", ".gitattributes",
        ".editorconfig", ".prettierrc", ".eslintrc",
    })
    
    # Binary file extensions (archives, executables)
    binary_extensions: Set[str] = field(default_factory=lambda: {
        ".exe", ".dll", ".so", ".dylib", ".bin",
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
        ".iso", ".dmg",
    })
    
    # Image file extensions
    image_extensions: Set[str] = field(default_factory=lambda: {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
        ".tiff", ".tif", ".ico", ".svg", ".heic", ".heif",
        ".raw", ".cr2", ".nef", ".arw", ".dng",
    })
    
    # PDF extensions
    pdf_extensions: Set[str] = field(default_factory=lambda: {".pdf"})
    
    # Word document extensions
    word_extensions: Set[str] = field(default_factory=lambda: {
        ".docx", ".doc", ".odt", ".rtf",
    })
    
    # Excel/spreadsheet extensions
    excel_extensions: Set[str] = field(default_factory=lambda: {
        ".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv",
    })
    
    # Presentation extensions
    presentation_extensions: Set[str] = field(default_factory=lambda: {
        ".pptx", ".ppt", ".odp",
    })
    
    # Audio extensions
    audio_extensions: Set[str] = field(default_factory=lambda: {
        ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma",
    })
    
    # Video extensions
    video_extensions: Set[str] = field(default_factory=lambda: {
        ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv",
    })


# Default configuration instance
DEFAULT_CONFIG = FastParseConfig()
