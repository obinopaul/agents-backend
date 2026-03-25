"""Unit tests for Documents tools and template processors.

Tests for:
- DocumentProcessorRegistry
- Individual template processors
- document_template_init tool
- document_compile tool
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Import template processors
from backend.src.tool_server.tools.documents.template_processor import (
    DocumentProcessorRegistry,
    DocumentProcessor,
)


class TestDocumentProcessorRegistry:
    """Tests for the DocumentProcessorRegistry."""
    
    def test_list_templates_returns_all_seven(self):
        """Verify all 7 templates are registered."""
        templates = DocumentProcessorRegistry.list_templates()
        expected = ["Beamer", "CV", "CV_2", "Letter", "Note", "Poster", "Report"]
        assert sorted(templates) == expected
    
    def test_has_template_returns_true_for_valid(self):
        """Verify has_template returns True for valid templates."""
        assert DocumentProcessorRegistry.has_template("Report")
        assert DocumentProcessorRegistry.has_template("CV")
        assert DocumentProcessorRegistry.has_template("Beamer")
    
    def test_has_template_returns_false_for_invalid(self):
        """Verify has_template returns False for invalid templates."""
        assert not DocumentProcessorRegistry.has_template("InvalidTemplate")
        assert not DocumentProcessorRegistry.has_template("thesis")
    
    def test_get_returns_processor_instance(self):
        """Verify get() returns a valid processor instance."""
        processor = DocumentProcessorRegistry.get("Report", "/workspace/documents/test")
        assert isinstance(processor, DocumentProcessor)
        assert processor.template_name == "Report"
        assert processor.main_file == "main.tex"
    
    def test_get_raises_for_unknown_template(self):
        """Verify get() raises ValueError for unknown template."""
        with pytest.raises(ValueError) as excinfo:
            DocumentProcessorRegistry.get("UnknownTemplate", "/workspace/documents/test")
        assert "Unknown template" in str(excinfo.value)


class TestTemplateProcessors:
    """Tests for individual template processors."""
    
    @pytest.fixture
    def temp_document_dir(self):
        """Create a temporary document directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.parametrize("template_name,expected_main_file", [
        ("Note", "master.tex"),
        ("Report", "main.tex"),
        ("CV", "cv.tex"),
        ("CV_2", "cv.tex"),
        ("Letter", "letter.tex"),
        ("Beamer", "main.tex"),
        ("Poster", "poster.tex"),
    ])
    def test_processor_main_file(self, template_name, expected_main_file):
        """Verify each processor has correct main file."""
        processor = DocumentProcessorRegistry.get(template_name, "/workspace/documents/test")
        assert processor.main_file == expected_main_file
    
    @pytest.mark.parametrize("template_name", [
        "Note", "Report", "CV", "CV_2", "Letter", "Beamer", "Poster"
    ])
    def test_processor_returns_template_rule(self, template_name, temp_document_dir):
        """Verify each processor returns non-empty template rules."""
        processor = DocumentProcessorRegistry.get(template_name, temp_document_dir)
        rule = processor.get_template_rule()
        
        assert rule is not None
        assert len(rule) > 100  # Rules should be substantial
        assert temp_document_dir in rule  # Should include document dir
        assert "document_compile" in rule  # Should mention compilation
    
    def test_report_processor_has_correct_content(self, temp_document_dir):
        """Verify Report processor has expected content in rules."""
        processor = DocumentProcessorRegistry.get("Report", temp_document_dir)
        rule = processor.get_template_rule()
        
        assert "main.tex" in rule
        assert "header.tex" in rule
        assert "section" in rule.lower()
        assert "figure" in rule.lower() or "table" in rule.lower()
    
    def test_cv_processor_has_modular_sections(self, temp_document_dir):
        """Verify CV processor mentions modular structure."""
        processor = DocumentProcessorRegistry.get("CV", temp_document_dir)
        rule = processor.get_template_rule()
        
        assert "education" in rule.lower()
        assert "experience" in rule.lower()
        assert "cv.tex" in rule
    
    def test_beamer_processor_has_slides_info(self, temp_document_dir):
        """Verify Beamer processor mentions slide-specific features."""
        processor = DocumentProcessorRegistry.get("Beamer", temp_document_dir)
        rule = processor.get_template_rule()
        
        assert "frame" in rule.lower() or "slide" in rule.lower()
        assert "presentation" in rule.lower()
    
    def test_processor_get_file_structure_for_empty_dir(self, temp_document_dir):
        """Verify get_file_structure works for empty directory."""
        processor = DocumentProcessorRegistry.get("Report", temp_document_dir)
        structure = processor.get_file_structure()
        
        assert Path(temp_document_dir).name in structure
    
    def test_processor_get_file_structure_for_nonexistent_dir(self):
        """Verify get_file_structure handles nonexistent directory."""
        processor = DocumentProcessorRegistry.get("Report", "/nonexistent/path/test")
        structure = processor.get_file_structure()
        
        assert "not yet created" in structure


class TestDocumentInitToolIntegration:
    """Integration tests for document_template_init tool with processors."""
    
    @pytest.fixture
    def mock_workspace_manager(self, tmp_path):
        """Create a mock workspace manager."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        
        manager = MagicMock()
        manager.get_workspace_path.return_value = str(workspace_path)
        return manager
    
    @pytest.fixture
    def sample_latex_root(self, tmp_path):
        """Create a sample .latex directory with templates."""
        latex_root = tmp_path / ".latex"
        latex_root.mkdir()
        
        # Create a minimal Report template
        report_dir = latex_root / "Report"
        report_dir.mkdir()
        (report_dir / "main.tex").write_text(r"\documentclass{article}\begin{document}Hello\end{document}")
        (report_dir / "header.tex").write_text(r"% Header file")
        
        return latex_root


class TestDocumentCompileToolBasics:
    """Basic tests for document_compile tool."""
    
    def test_main_file_detection_priority(self):
        """Test the priority order for main file detection."""
        from backend.src.tool_server.tools.documents.document_compile_tool import detect_main_file
        
        with tempfile.TemporaryDirectory() as temp_dir:
            doc_dir = Path(temp_dir)
            
            # Create multiple .tex files
            (doc_dir / "main.tex").write_text(r"\documentclass{article}")
            (doc_dir / "other.tex").write_text(r"% not main")
            
            # main.tex should be detected first
            detected = detect_main_file(doc_dir)
            assert detected == "main.tex"
    
    def test_main_file_detection_master(self):
        """Test detection of master.tex as main file."""
        from backend.src.tool_server.tools.documents.document_compile_tool import detect_main_file
        
        with tempfile.TemporaryDirectory() as temp_dir:
            doc_dir = Path(temp_dir)
            
            # Only master.tex exists
            (doc_dir / "master.tex").write_text(r"\documentclass{article}")
            (doc_dir / "header.tex").write_text(r"% header")
            
            detected = detect_main_file(doc_dir)
            assert detected == "master.tex"
    
    def test_main_file_detection_with_documentclass(self):
        """Test detection by searching for \\documentclass."""
        from backend.src.tool_server.tools.documents.document_compile_tool import detect_main_file
        
        with tempfile.TemporaryDirectory() as temp_dir:
            doc_dir = Path(temp_dir)
            
            # No standard names, but one has \documentclass
            (doc_dir / "header.tex").write_text(r"% packages")
            (doc_dir / "thesis_document.tex").write_text(r"\documentclass{report}")
            
            detected = detect_main_file(doc_dir)
            assert detected == "thesis_document.tex"


class TestLatexLogParsing:
    """Tests for LaTeX log parsing."""
    
    def test_parse_error_from_log(self):
        """Test parsing of LaTeX errors from log content."""
        from backend.src.tool_server.tools.documents.document_compile_tool import parse_latex_log
        
        log_content = """
This is pdfTeX
! Undefined control sequence.
l.42 \\badcommand

? 
"""
        errors, warnings = parse_latex_log(log_content, "main.tex")
        
        assert len(errors) >= 1
        assert any("Undefined control sequence" in e.message for e in errors)
    
    def test_parse_warning_from_log(self):
        """Test parsing of LaTeX warnings from log content."""
        from backend.src.tool_server.tools.documents.document_compile_tool import parse_latex_log
        
        log_content = """
LaTeX Warning: Reference `fig:missing' on page 1 undefined.
"""
        errors, warnings = parse_latex_log(log_content, "main.tex")
        
        assert len(warnings) >= 1
        assert any("Reference" in w.message for w in warnings)
    
    def test_parse_overfull_box_warning(self):
        """Test parsing of overfull box warnings."""
        from backend.src.tool_server.tools.documents.document_compile_tool import parse_latex_log
        
        log_content = """
Overfull \\hbox (15.0pt too wide) at lines 10--12
"""
        errors, warnings = parse_latex_log(log_content, "main.tex")
        
        assert len(warnings) >= 1
        assert any(w.error_type == "badbox" for w in warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
