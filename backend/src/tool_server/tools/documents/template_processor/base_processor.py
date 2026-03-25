"""Base class for document template processors.

Document processors provide template-specific deployment rules and guidance
to help AI agents work effectively with LaTeX document templates.

Unlike dev processors (which install dependencies), document processors
focus on providing context and usage instructions since LaTeX templates
don't require npm/pip installation.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class DocumentProcessor(ABC):
    """Abstract base class for document template processors.
    
    Each processor provides:
    - template_name: The name of the template (e.g., 'Note', 'Report')
    - main_file: The main .tex file to compile
    - get_template_rule(): Detailed usage instructions for the agent
    """
    
    template_name: str
    main_file: str
    
    def __init__(self, document_dir: str) -> None:
        """Initialize processor with document directory path.
        
        Args:
            document_dir: Absolute path to the document directory
        """
        self.document_dir = document_dir
    
    @abstractmethod
    def get_template_rule(self) -> str:
        """Return deployment rules and usage instructions for this template.
        
        Returns detailed guidance including:
        - File structure explanation
        - Which files to edit for what purpose
        - Compilation instructions
        - Common customizations
        """
        raise NotImplementedError("Subclasses must implement get_template_rule()")
    
    def get_main_file(self) -> str:
        """Return the main .tex file for this template."""
        return self.main_file
    
    def get_file_structure(self) -> str:
        """Get the actual file structure from the document directory."""
        doc_path = Path(self.document_dir)
        if not doc_path.exists():
            return f"{self.document_dir}/ (not yet created)"
        
        lines = [f"{doc_path.name}/"]
        files = sorted(doc_path.iterdir())
        for i, f in enumerate(files):
            is_last = i == len(files) - 1
            prefix = "└── " if is_last else "├── "
            suffix = "/" if f.is_dir() else ""
            lines.append(f"{prefix}{f.name}{suffix}")
        
        return "\n".join(lines)
