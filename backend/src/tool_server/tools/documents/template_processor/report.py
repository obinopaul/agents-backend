"""Report template processor.

Clean academic report/assignment template for homework, lab reports,
and short papers.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_report_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the Report template."""
    return f"""
Document directory `{document_dir}` created successfully. This is a clean academic report template.

## File Structure
```
{document_dir}/
├── main.tex          # Main file (compile this)
└── header.tex        # Preamble: packages and settings
```

## Key Files

### main.tex (Main File)
The main document file containing:
- `\\input{{header.tex}}` - loads packages and settings
- Title, author, date configuration
- Document body with sections

### header.tex (Preamble)
Contains LaTeX packages and custom settings:
- Document class configuration (article)
- Page margins and formatting
- Math and graphics packages
- Custom commands

## Editing Workflow

1. **Set document metadata** at the top of `main.tex`:
   ```latex
   \\title{{Your Report Title}}
   \\author{{Your Name}}
   \\date{{\\today}}
   ```

2. **Add sections and content**:
   ```latex
   \\section{{Introduction}}
   This report covers...
   
   \\section{{Methods}}
   We used the following approach...
   
   \\section{{Results}}
   The results show that...
   
   \\section{{Conclusion}}
   In conclusion...
   ```

3. **Add math equations**:
   ```latex
   The equation is:
   \\begin{{equation}}
       f(x) = ax^2 + bx + c
   \\end{{equation}}
   ```

4. **Add figures**:
   ```latex
   \\begin{{figure}}[h]
       \\centering
       \\includegraphics[width=0.8\\textwidth]{{image.png}}
       \\caption{{Description of the figure}}
       \\label{{fig:example}}
   \\end{{figure}}
   ```

5. **Add tables**:
   ```latex
   \\begin{{table}}[h]
       \\centering
       \\begin{{tabular}}{{|c|c|c|}}
           \\hline
           Column 1 & Column 2 & Column 3 \\\\
           \\hline
           Data 1 & Data 2 & Data 3 \\\\
           \\hline
       \\end{{tabular}}
       \\caption{{Table description}}
   \\end{{table}}
   ```

## Compilation
Compile with: `document_compile(document_name="{document_dir.split('/')[-1]}")`

## Tips
- Use `\\maketitle` after `\\begin{{document}}` to generate title
- Lists: `\\begin{{itemize}}` or `\\begin{{enumerate}}`
- Code blocks: Use `verbatim` environment or `listings` package
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("Report")
class ReportProcessor(DocumentProcessor):
    """Processor for academic report template."""
    
    template_name = "Report"
    main_file = "main.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_report_template_rule(self.document_dir)
