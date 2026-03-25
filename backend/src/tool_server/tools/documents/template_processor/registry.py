"""Registry for document template processors.

Provides decorator-based registration and factory pattern for creating
processors based on template name.
"""

from typing import Dict, Type

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)


class DocumentProcessorRegistry:
    """Registry-based factory for document processors with decorator support."""

    _registry: Dict[str, Type[DocumentProcessor]] = {}

    @classmethod
    def register(cls, template_name: str):
        """Decorator to register a processor class.
        
        Usage:
            @DocumentProcessorRegistry.register("Report")
            class ReportProcessor(DocumentProcessor):
                ...
        """

        def decorator(processor_class: Type[DocumentProcessor]):
            cls._registry[template_name] = processor_class
            return processor_class

        return decorator

    @classmethod
    def get(cls, template_name: str, document_dir: str) -> DocumentProcessor:
        """Get a processor instance for the given template.
        
        Args:
            template_name: Name of the template (e.g., 'Report', 'CV')
            document_dir: Path to the document directory
            
        Returns:
            DocumentProcessor instance for the template
            
        Raises:
            ValueError: If template_name is not registered
        """
        processor_class = cls._registry.get(template_name)

        if processor_class is None:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Unknown template '{template_name}'. Available: {available}"
            )

        return processor_class(document_dir)

    @classmethod
    def list_templates(cls) -> list[str]:
        """List all registered template names."""
        return sorted(cls._registry.keys())
    
    @classmethod
    def has_template(cls, template_name: str) -> bool:
        """Check if a template is registered."""
        return template_name in cls._registry
