"""Document template processors package.

This package provides template-specific processors that generate
deployment rules and usage guidance for AI agents working with
LaTeX document templates.

Available Templates:
- Note: Academic lecture notes with sections, TOC, bibliography
- Report: Clean academic report/assignment template
- CV: Full academic CV with modular sections
- CV_2: Alternative CV style with Awesome-CV class
- Letter: Formal letter with letterhead
- Beamer: PDF presentation slides
- Poster: Academic conference poster

Usage:
    from backend.src.tool_server.tools.documents.template_processor import (
        DocumentProcessorRegistry,
    )
    
    processor = DocumentProcessorRegistry.get("Report", "/workspace/documents/my-paper")
    rules = processor.get_template_rule()
"""

from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)
from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)

# Import all processors to register them
from backend.src.tool_server.tools.documents.template_processor import note
from backend.src.tool_server.tools.documents.template_processor import report
from backend.src.tool_server.tools.documents.template_processor import cv
from backend.src.tool_server.tools.documents.template_processor import cv_2
from backend.src.tool_server.tools.documents.template_processor import letter
from backend.src.tool_server.tools.documents.template_processor import beamer
from backend.src.tool_server.tools.documents.template_processor import poster

__all__ = [
    "DocumentProcessorRegistry",
    "DocumentProcessor",
]
