"""Document compilation tool for compiling LaTeX documents to PDF."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, List
from dataclasses import dataclass

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "document_compile"
DISPLAY_NAME = "Compile LaTeX document to PDF"

DESCRIPTION = """Compiles a LaTeX document to PDF and returns compilation results.

## Overview
This tool compiles LaTeX documents using pdflatex and returns:
- Success or failure status
- Path to the generated PDF (if successful)
- Compilation logs with line numbers
- Parsed error and warning messages

## Usage
After creating and editing LaTeX files, use this tool to compile them to PDF.

## Parameters
- **document_name**: Name of the document directory (e.g., 'my-thesis')
- **main_file**: (Optional) The main .tex file to compile. If not provided, auto-detects
  using metadata.json or common naming conventions (main.tex, master.tex, etc.)

## Examples
```
# Compile using auto-detected main file
document_compile(document_name="my-thesis")

# Compile specific file
document_compile(document_name="my-thesis", main_file="chapter1.tex")
```

## Error Handling
If compilation fails, the tool returns:
- Full log output for debugging
- Parsed errors with line numbers
- Suggestions for common fixes

## Compilation Steps
1. Locate the document directory
2. Identify or validate the main .tex file
3. Run pdflatex (with bibtex if .bib files exist)
4. Parse logs for errors and warnings
5. Return results with PDF path if successful
"""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_name": {
            "type": "string",
            "description": "Name of the document directory to compile (e.g., 'my-thesis', 'conference-paper')",
        },
        "main_file": {
            "type": "string",
            "description": "The main .tex file to compile. If not provided, auto-detects from metadata or naming conventions.",
        },
    },
    "required": ["document_name"],
}


@dataclass
class CompilationError:
    """Represents a LaTeX compilation error or warning."""
    line: int
    message: str
    error_type: str  # 'error', 'warning', 'badbox'
    file: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "message": self.message,
            "type": self.error_type,
            "file": self.file,
        }


@dataclass
class CompilationResult:
    """Result of LaTeX compilation."""
    success: bool
    pdf_path: Optional[str] = None
    log: str = ""
    errors: List[CompilationError] = None
    warnings: List[CompilationError] = None
    run_count: int = 0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


def parse_latex_log(log_content: str, main_file: str) -> tuple[List[CompilationError], List[CompilationError]]:
    """Parse pdflatex log file to extract errors and warnings.
    
    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []
    
    lines = log_content.split('\n')
    current_file = main_file
    
    # Pattern for errors: starts with "!" 
    error_pattern = re.compile(r'^! (.+)$')
    # Pattern for line number: "l.123"
    line_pattern = re.compile(r'^l\.(\d+)')
    # Pattern for warnings
    warning_pattern = re.compile(r'LaTeX Warning: (.+)')
    # Pattern for package warnings
    package_warning_pattern = re.compile(r'Package (\w+) Warning: (.+)')
    # Pattern for overfull/underfull boxes
    box_pattern = re.compile(r'(Overfull|Underfull) \\[hv]box .+ at lines? (\d+)(?:--(\d+))?')
    # Pattern for file changes
    file_pattern = re.compile(r'\(([^()]+\.tex)')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Track current file
        file_match = file_pattern.search(line)
        if file_match:
            current_file = file_match.group(1)
        
        # Check for errors
        error_match = error_pattern.match(line)
        if error_match:
            error_message = error_match.group(1)
            line_num = 0
            
            # Look for line number in next few lines
            for j in range(i + 1, min(i + 5, len(lines))):
                line_match = line_pattern.match(lines[j])
                if line_match:
                    line_num = int(line_match.group(1))
                    break
            
            errors.append(CompilationError(
                line=line_num,
                message=error_message.strip(),
                error_type="error",
                file=current_file,
            ))
        
        # Check for warnings
        warning_match = warning_pattern.search(line)
        if warning_match:
            warnings.append(CompilationError(
                line=0,
                message=warning_match.group(1).strip(),
                error_type="warning",
                file=current_file,
            ))
        
        # Check for package warnings
        pkg_warning_match = package_warning_pattern.search(line)
        if pkg_warning_match:
            warnings.append(CompilationError(
                line=0,
                message=f"[{pkg_warning_match.group(1)}] {pkg_warning_match.group(2).strip()}",
                error_type="warning",
                file=current_file,
            ))
        
        # Check for box warnings
        box_match = box_pattern.search(line)
        if box_match:
            line_num = int(box_match.group(2))
            warnings.append(CompilationError(
                line=line_num,
                message=line.strip(),
                error_type="badbox",
                file=current_file,
            ))
        
        i += 1
    
    return errors, warnings


def run_pdflatex(
    document_dir: Path,
    main_file: str,
    run_bibtex: bool = False,
) -> CompilationResult:
    """Run pdflatex compilation.
    
    Args:
        document_dir: Path to the document directory
        main_file: Name of the main .tex file
        run_bibtex: Whether to run bibtex for bibliography
        
    Returns:
        CompilationResult with success status, logs, and errors
    """
    main_path = document_dir / main_file
    if not main_path.exists():
        return CompilationResult(
            success=False,
            log=f"Main file not found: {main_file}",
            errors=[CompilationError(
                line=0,
                message=f"Main file not found: {main_file}",
                error_type="error",
            )],
        )
    
    # Base name without extension
    base_name = main_file.rsplit('.', 1)[0]
    log_file = document_dir / f"{base_name}.log"
    pdf_file = document_dir / f"{base_name}.pdf"
    
    # pdflatex command with options
    pdflatex_cmd = [
        "pdflatex",
        "-interaction=nonstopmode",  # Don't stop on errors
        "-file-line-error",          # Better error reporting
        "-halt-on-error",            # Stop on first error (but still produce log)
        main_file,
    ]
    
    all_logs = []
    run_count = 0
    
    try:
        # First run
        run_count += 1
        result = subprocess.run(
            pdflatex_cmd,
            cwd=str(document_dir),
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )
        all_logs.append(f"=== pdflatex run {run_count} ===\n{result.stdout}\n{result.stderr}")
        
        # Run bibtex if needed
        if run_bibtex:
            bib_files = list(document_dir.glob("*.bib"))
            if bib_files:
                bibtex_cmd = ["bibtex", base_name]
                bib_result = subprocess.run(
                    bibtex_cmd,
                    cwd=str(document_dir),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                all_logs.append(f"=== bibtex ===\n{bib_result.stdout}\n{bib_result.stderr}")
                
                # Need two more pdflatex runs for bibliography
                for _ in range(2):
                    run_count += 1
                    result = subprocess.run(
                        pdflatex_cmd,
                        cwd=str(document_dir),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    all_logs.append(f"=== pdflatex run {run_count} ===\n{result.stdout}")
        
        # Check if PDF was created
        pdf_created = pdf_file.exists()
        
        # Read log file for detailed parsing
        log_content = ""
        if log_file.exists():
            try:
                log_content = log_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                log_content = result.stdout + result.stderr
        
        # Parse errors and warnings
        errors, warnings = parse_latex_log(log_content, main_file)
        
        # Determine success: PDF created and no fatal errors
        success = pdf_created and len(errors) == 0
        
        return CompilationResult(
            success=success,
            pdf_path=str(pdf_file) if pdf_created else None,
            log="\n".join(all_logs),
            errors=errors,
            warnings=warnings,
            run_count=run_count,
        )
        
    except subprocess.TimeoutExpired:
        return CompilationResult(
            success=False,
            log="Compilation timed out after 120 seconds",
            errors=[CompilationError(
                line=0,
                message="Compilation timed out. Check for infinite loops or very large documents.",
                error_type="error",
            )],
        )
    except FileNotFoundError:
        return CompilationResult(
            success=False,
            log="pdflatex not found. LaTeX is not installed in this environment.",
            errors=[CompilationError(
                line=0,
                message="pdflatex not found. Use LaTeX.Online API or install texlive.",
                error_type="error",
            )],
        )
    except Exception as e:
        return CompilationResult(
            success=False,
            log=f"Compilation failed with exception: {str(e)}",
            errors=[CompilationError(
                line=0,
                message=str(e),
                error_type="error",
            )],
        )


def detect_main_file(document_dir: Path, metadata: Optional[dict] = None) -> Optional[str]:
    """Detect the main .tex file to compile.
    
    Priority:
    1. Value from metadata.json
    2. main.tex
    3. master.tex  
    4. File matching directory name (e.g., thesis/thesis.tex)
    5. Any .tex file that contains \\documentclass
    """
    # Check metadata first
    if metadata and metadata.get("main_file"):
        main_from_meta = metadata["main_file"]
        if (document_dir / main_from_meta).exists():
            return main_from_meta
    
    # Check common names
    common_names = ["main.tex", "master.tex"]
    for name in common_names:
        if (document_dir / name).exists():
            return name
    
    # Check for directory-named file
    dir_name = document_dir.name
    for ext in [".tex", "_main.tex"]:
        candidate = f"{dir_name}{ext}"
        if (document_dir / candidate).exists():
            return candidate
    
    # Find .tex files with \documentclass
    tex_files = list(document_dir.glob("*.tex"))
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8", errors="replace")
            if r"\documentclass" in content:
                return tex_file.name
        except Exception:
            continue
    
    # Last resort: first .tex file that's not header/appendix
    for tex_file in tex_files:
        name = tex_file.name.lower()
        if not any(exclude in name for exclude in ['header', 'appendix', 'preamble']):
            return tex_file.name
    
    return tex_files[0].name if tex_files else None


class DocumentCompileTool(BaseTool):
    """Tool for compiling LaTeX documents to PDF."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = True  # Compiling doesn't modify source files
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
        self.documents_dir = "documents"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize document name for filesystem."""
        sanitized = name.replace(" ", "_").replace("-", "_")
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
        return sanitized.lower()
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the document compilation."""
        document_name = tool_input["document_name"]
        main_file = tool_input.get("main_file")
        
        # Get paths
        workspace_path = Path(self.workspace_manager.get_workspace_path())
        safe_name = self._sanitize_name(document_name)
        document_dir = workspace_path / self.documents_dir / safe_name
        
        # Check if document exists
        if not document_dir.exists():
            return ToolResult(
                llm_content=(
                    f"Document '{safe_name}' not found at {document_dir}. "
                    "Use document_template_init to create a new document first."
                ),
                user_display_content=f"Document '{safe_name}' not found",
                is_error=True,
            )
        
        # Load metadata if available
        metadata = None
        metadata_file = document_dir / "metadata.json"
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        # Determine main file
        if not main_file:
            main_file = detect_main_file(document_dir, metadata)
        
        if not main_file:
            tex_files = [f.name for f in document_dir.glob("*.tex")]
            return ToolResult(
                llm_content=(
                    f"Could not determine main file to compile. "
                    f"Available .tex files: {tex_files}. "
                    "Please specify main_file parameter."
                ),
                user_display_content="Could not determine main file",
                is_error=True,
            )
        
        # Check if main file exists
        main_path = document_dir / main_file
        if not main_path.exists():
            return ToolResult(
                llm_content=f"Main file '{main_file}' not found in {document_dir}",
                user_display_content=f"Main file '{main_file}' not found",
                is_error=True,
            )
        
        # Check for bibliography files
        has_bib = len(list(document_dir.glob("*.bib"))) > 0
        
        # Run compilation
        result = run_pdflatex(document_dir, main_file, run_bibtex=has_bib)
        
        # Update metadata with compilation result
        if metadata:
            metadata["compilation"] = {
                "last_compiled": datetime.now().isoformat(),
                "status": "success" if result.success else "error",
                "output_file": result.pdf_path,
                "main_file": main_file,
            }
            try:
                metadata_file.write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception:
                pass
        
        # Build response
        if result.success:
            # Successful compilation
            error_summary = ""
            if result.warnings:
                warning_count = len([w for w in result.warnings if w.error_type == "warning"])
                badbox_count = len([w for w in result.warnings if w.error_type == "badbox"])
                if warning_count:
                    error_summary += f"{warning_count} warnings. "
                if badbox_count:
                    error_summary += f"{badbox_count} box warnings. "
            
            compilation_metadata = {
                "type": "latex_compilation_result",
                "document_name": safe_name,
                "main_file": main_file,
                "success": True,
                "pdf_path": result.pdf_path,
                "run_count": result.run_count,
                "warning_count": len(result.warnings),
            }
            
            response = (
                f"✓ Compilation successful!\n\n"
                f"Document: {safe_name}\n"
                f"Main file: {main_file}\n"
                f"Output: {result.pdf_path}\n"
                f"Runs: {result.run_count}\n"
            )
            
            if error_summary:
                response += f"\n{error_summary}\n"
            
            if result.warnings:
                response += "\nWarnings:\n"
                for w in result.warnings[:5]:  # Limit to first 5
                    line_info = f"line {w.line}" if w.line else ""
                    response += f"  • {w.message} {line_info}\n"
                if len(result.warnings) > 5:
                    response += f"  ... and {len(result.warnings) - 5} more warnings\n"
            
            return ToolResult(
                llm_content=response,
                user_display_content=[compilation_metadata],
                is_error=False,
            )
        else:
            # Failed compilation
            compilation_metadata = {
                "type": "latex_compilation_result",
                "document_name": safe_name,
                "main_file": main_file,
                "success": False,
                "error_count": len(result.errors),
            }
            
            response = (
                f"✗ Compilation failed\n\n"
                f"Document: {safe_name}\n"
                f"Main file: {main_file}\n"
                f"Errors: {len(result.errors)}\n\n"
            )
            
            if result.errors:
                response += "Errors:\n"
                for error in result.errors:
                    line_info = f"line {error.line}" if error.line else ""
                    file_info = f"[{error.file}]" if error.file else ""
                    response += f"  • {error.message} {line_info} {file_info}\n"
            
            # Add truncated log for context
            if result.log:
                log_lines = result.log.split('\n')
                if len(log_lines) > 30:
                    relevant_log = '\n'.join(log_lines[-30:])
                    response += f"\n--- Last 30 lines of log ---\n{relevant_log}\n"
                else:
                    response += f"\n--- Compilation log ---\n{result.log}\n"
            
            return ToolResult(
                llm_content=response,
                user_display_content=[compilation_metadata],
                is_error=True,
            )
    
    async def execute_mcp_wrapper(
        self,
        document_name: str,
        main_file: str = None,
    ):
        """MCP wrapper for the tool."""
        tool_input = {"document_name": document_name}
        if main_file:
            tool_input["main_file"] = main_file
        return await self._mcp_wrapper(tool_input=tool_input)
