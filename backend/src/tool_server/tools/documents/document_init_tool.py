"""Document template initialization tool for creating LaTeX documents from templates."""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager
from backend.src.tool_server.tools.documents.template_processor import (
    DocumentProcessorRegistry,
)


NAME = "document_template_init"
DISPLAY_NAME = "Initialize LaTeX document from template"

DESCRIPTION = """Initializes a new LaTeX document from pre-designed professional templates.

## Overview
This tool scaffolds a complete LaTeX document project from academic-quality templates.
Each template includes properly structured files, headers, and styling ready for customization.

## Available Templates (7 options)

### Academic Writing
- **Note** - Academic lecture notes with sections, table of contents, bibliography, and appendix.
  Best for course notes, study materials, and technical documentation.
  Files: master.tex, header.tex, appendix.tex, reference.bib

- **Report** - Clean academic report/assignment template with professional formatting.
  Suitable for homework, lab reports, project reports, and short papers.
  Files: main.tex, header.tex

### Professional Documents
- **CV** - Full academic CV with comprehensive sections for education, experience,
  publications, teaching, awards, and service. Multi-file modular structure.
  Files: cv.tex, header.tex, 1_education.tex, 2_experience.tex, 3_publication.tex, etc.

- **CV_2** - Alternative CV style with different formatting and layout options.
  Similar modular structure with different visual styling.

- **Letter** - Formal letter template with professional letterhead styling.
  Includes custom class file for institutional formatting.
  Files: letter.tex, UIUCletter.cls

### Presentations & Posters
- **Beamer** - Presentation slides using LaTeX Beamer class.
  Academic-style PDF slides with sections, figures, and bibliography support.
  Files: main.tex, header.tex, reference.bib, Figures/

- **Poster** - Academic poster template for conferences and research presentations.
  Large format with customizable sections and Gemini color theme.
  Files: poster.tex, header.tex, beamerthemegemini.sty, reference.bib

## Usage
1. Choose a template that matches your document's purpose
2. Provide a document name (will be used as directory name)
3. The template will be copied to `documents/<your_name>/`
4. Edit the .tex files using file editing tools
5. Compile using the document_compile tool

## Post-Initialization
After initialization:
1. Edit the main .tex file to add your content
2. Modify header.tex for custom packages or styling
3. Add bibliography entries to reference.bib
4. Use document_compile to build PDF and check for errors
"""

# Detailed template information including main file and description
TEMPLATE_INFO = {
    "Note": {
        "description": "Academic lecture notes with sections, table of contents, bibliography, and appendix. Best for course notes and study materials.",
        "main_file": "master.tex",
        "files": ["master.tex", "header.tex", "appendix.tex", "reference.bib"],
        "output": "master.pdf",
    },
    "Report": {
        "description": "Clean academic report/assignment template. Suitable for homework, lab reports, and short papers.",
        "main_file": "main.tex",
        "files": ["main.tex", "header.tex"],
        "output": "main.pdf",
    },
    "CV": {
        "description": "Full academic CV with sections for education, experience, publications, teaching, awards, and service.",
        "main_file": "cv.tex",
        "files": ["cv.tex", "resume.tex", "header.tex", "1_education.tex", "2_experience.tex", 
                  "3_publication.tex", "4_teaching.tex", "5_award.tex", "6_service.tex"],
        "output": "cv.pdf",
    },
    "CV_2": {
        "description": "Alternative CV style with different formatting and layout options.",
        "main_file": "cv.tex",
        "files": [],  # Will be auto-detected on copy
        "output": "cv.pdf",
    },
    "Letter": {
        "description": "Formal letter template with professional letterhead styling.",
        "main_file": "letter.tex",
        "files": ["letter.tex", "UIUCletter.cls"],
        "output": "letter.pdf",
    },
    "Beamer": {
        "description": "Presentation slides using LaTeX Beamer class. Academic-style PDF slides.",
        "main_file": "main.tex",
        "files": ["main.tex", "header.tex", "reference.bib"],
        "output": "main.pdf",
    },
    "Poster": {
        "description": "Academic poster template for conferences. Large format with customizable sections.",
        "main_file": "poster.tex",
        "files": ["poster.tex", "header.tex", "beamerthemegemini.sty", 
                  "beamercolorthemegemini.sty", "reference.bib"],
        "output": "poster.pdf",
    },
}

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_name": {
            "type": "string",
            "description": "Name for your document (lowercase, no spaces, use hyphens if needed). Example: `thesis-draft`, `conference-paper`, `my-cv`",
        },
        "template": {
            "type": "string",
            "description": "Template to use for the document",
            "enum": list(TEMPLATE_INFO.keys()),
        },
    },
    "required": ["document_name", "template"],
}


def get_latex_root() -> Path:
    """Get the LaTeX templates root directory.
    
    In E2B sandbox: /app/agents_backend/.latex
    In local development: Project root /.latex
    """
    # E2B sandbox path
    sandbox_path = Path("/app/agents_backend/.latex")
    if sandbox_path.exists():
        return sandbox_path
    
    # Alternative sandbox path
    alt_sandbox_path = Path("/app/.latex")
    if alt_sandbox_path.exists():
        return alt_sandbox_path
    
    # Local development - find via PYTHONPATH
    pythonpath = os.getenv("PYTHONPATH", "")
    for path in pythonpath.split(os.pathsep):
        if not path:
            continue
        p = Path(path)
        if p.exists():
            # Check current path
            latex_path = p / ".latex"
            if latex_path.exists():
                return latex_path
            # Check parent directories
            parent = p.parent
            while parent != parent.parent:
                latex_path = parent / ".latex"
                if latex_path.exists():
                    return latex_path
                parent = parent.parent
    
    # Last resort: try common development paths
    common_paths = [
        Path.cwd() / ".latex",
        Path.cwd().parent / ".latex",
    ]
    for p in common_paths:
        if p.exists():
            return p
    
    raise Exception(
        "Failed to find .latex directory. "
        "Expected at /app/agents_backend/.latex/ in sandbox or in project root locally."
    )


def detect_main_file(template_dir: Path) -> Optional[str]:
    """Auto-detect the main .tex file in a template directory.
    
    Priority:
    1. main.tex
    2. master.tex
    3. Any file matching template name (e.g., cv.tex, poster.tex)
    4. First .tex file found
    """
    tex_files = list(template_dir.glob("*.tex"))
    
    if not tex_files:
        return None
    
    # Check priority order
    priority_names = ["main.tex", "master.tex"]
    for name in priority_names:
        if (template_dir / name).exists():
            return name
    
    # Check for template-named files
    template_name = template_dir.name.lower()
    for tex_file in tex_files:
        if tex_file.stem.lower() == template_name:
            return tex_file.name
    
    # Fallback: first tex file that's not a header/section
    for tex_file in tex_files:
        if not tex_file.name.startswith(('header', 'appendix', '1_', '2_', '3_', '4_', '5_', '6_')):
            return tex_file.name
    
    return tex_files[0].name if tex_files else None


class DocumentTemplateInitTool(BaseTool):
    """Tool for initializing LaTeX documents from templates."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
        self.documents_dir = "documents"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize document name for filesystem."""
        # Replace spaces and hyphens with underscores
        sanitized = name.replace(" ", "_").replace("-", "_")
        # Keep only alphanumeric and underscore
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
        # Ensure lowercase
        return sanitized.lower()
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the document template initialization."""
        document_name = tool_input["document_name"]
        template = tool_input["template"]
        
        # Validate template exists
        if template not in TEMPLATE_INFO:
            available = ", ".join(sorted(TEMPLATE_INFO.keys()))
            return ToolResult(
                llm_content=f"Unknown template '{template}'. Available templates: {available}",
                user_display_content=f"Unknown template '{template}'",
                is_error=True,
            )
        
        # Get paths
        workspace_path = Path(self.workspace_manager.get_workspace_path())
        safe_name = self._sanitize_name(document_name)
        document_dir = workspace_path / self.documents_dir / safe_name
        
        # Check if document already exists
        if document_dir.exists():
            return ToolResult(
                llm_content=(
                    f"Document '{safe_name}' already exists at {document_dir}. "
                    "Please choose a different name or delete the existing document first."
                ),
                user_display_content=f"Document '{safe_name}' already exists",
                is_error=True,
            )
        
        # Get template directory
        try:
            latex_root = get_latex_root()
        except Exception as e:
            return ToolResult(
                llm_content=str(e),
                user_display_content="Failed to find templates directory",
                is_error=True,
            )
        
        template_dir = latex_root / template
        if not template_dir.exists():
            return ToolResult(
                llm_content=f"Template directory not found: {template_dir}",
                user_display_content=f"Template '{template}' not found on filesystem",
                is_error=True,
            )
        
        # Create documents directory if it doesn't exist
        documents_root = workspace_path / self.documents_dir
        documents_root.mkdir(parents=True, exist_ok=True)
        
        # Copy template to document directory
        try:
            shutil.copytree(template_dir, document_dir)
        except Exception as e:
            return ToolResult(
                llm_content=f"Failed to copy template: {e}",
                user_display_content="Failed to initialize document",
                is_error=True,
            )
        
        # Remove compiled files (.pdf, .aux, .log, .synctex.gz, etc.) to start fresh
        compiled_extensions = ['.pdf', '.aux', '.log', '.synctex.gz', '.bbl', '.blg', 
                               '.fls', '.fdb_latexmk', '.out', '.toc', '.nav', '.snm']
        for ext in compiled_extensions:
            for file in document_dir.glob(f"*{ext}"):
                try:
                    file.unlink()
                except Exception:
                    pass  # Non-fatal, just cleanup
        
        # Detect main file
        template_info = TEMPLATE_INFO[template]
        main_file = template_info.get("main_file") or detect_main_file(document_dir)
        
        # List all tex files in the document
        tex_files = sorted([f.name for f in document_dir.glob("*.tex")])
        bib_files = sorted([f.name for f in document_dir.glob("*.bib")])
        
        # Create metadata.json for document
        metadata = {
            "document_name": safe_name,
            "template": template,
            "main_file": main_file,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "files": {
                "tex": tex_files,
                "bib": bib_files,
            },
            "compilation": {
                "last_compiled": None,
                "status": "not_compiled",
                "output_file": None,
            }
        }
        
        metadata_file = document_dir / "metadata.json"
        try:
            metadata_file.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception:
            pass  # Non-fatal
        
        # Get template-specific deployment rules from processor
        template_rule = ""
        try:
            processor = DocumentProcessorRegistry.get(template, str(document_dir))
            template_rule = processor.get_template_rule()
        except Exception:
            # Fallback if processor not found - provide basic guidance
            template_rule = (
                f"Edit the main file ({main_file}) to add your content. "
                f"Use document_compile(document_name='{safe_name}') to compile to PDF."
            )
        
        # Build response
        document_metadata = {
            "type": "latex_document_metadata",
            "document_name": safe_name,
            "template": template,
            "template_description": template_info["description"],
            "document_directory": str(document_dir),
            "main_file": main_file,
            "tex_files": tex_files,
            "bib_files": bib_files,
            "template_rule": template_rule,
        }
        
        # Build file structure for display
        file_tree = f"documents/{safe_name}/\n"
        for tex in tex_files:
            marker = " (main)" if tex == main_file else ""
            file_tree += f"├── {tex}{marker}\n"
        for bib in bib_files:
            file_tree += f"├── {bib}\n"
        file_tree += f"└── metadata.json\n"
        
        return ToolResult(
            llm_content=(
                f"Successfully initialized LaTeX document '{safe_name}' from '{template}' template.\n\n"
                f"Location: {document_dir}\n"
                f"Main file: {main_file}\n"
                f"Template: {template}\n\n"
                f"File structure:\n{file_tree}\n\n"
                f"{template_rule}"
            ),
            user_display_content=[document_metadata],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(
        self,
        document_name: str,
        template: str,
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "document_name": document_name,
                "template": template,
            }
        )
