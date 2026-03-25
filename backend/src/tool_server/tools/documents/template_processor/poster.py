"""Poster template processor.

Academic poster template for conferences using Beamer's
poster mode with Gemini theme styling.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_poster_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the Poster template."""
    return f"""
Document directory `{document_dir}` created successfully. This is an academic poster template using Beamer/Gemini theme.

## File Structure
```
{document_dir}/
├── poster.tex                  # Main poster file (compile this)
├── header.tex                  # Settings and imports
├── beamerthemegemini.sty       # Gemini theme (do not modify)
├── beamercolorthemegemini.sty  # Color scheme (do not modify)
├── reference.bib               # Bibliography entries
└── Figures/                    # Directory for images and plots
```

## Key Files

### poster.tex (Main File)
The poster document with blocks arranged in columns:
```latex
\\input{{header.tex}}
\\begin{{document}}
\\begin{{frame}}[t]
\\begin{{columns}}[t]
  \\begin{{column}}{{0.32\\textwidth}}
    % Left column blocks
  \\end{{column}}
  \\begin{{column}}{{0.32\\textwidth}}
    % Middle column blocks
  \\end{{column}}
  \\begin{{column}}{{0.32\\textwidth}}
    % Right column blocks
  \\end{{column}}
\\end{{columns}}
\\end{{frame}}
\\end{{document}}
```

### beamerthemegemini.sty (Theme)
Gemini poster theme - do not modify unless you understand Beamer themes.

## Editing Workflow

1. **Set poster metadata** in poster.tex:
   ```latex
   \\title{{Your Poster Title}}
   \\author{{Author One \\inst{{1}} \\and Author Two \\inst{{2}}}}
   \\institute{{\\inst{{1}} University One \\samelineand \\inst{{2}} University Two}}
   ```

2. **Create content blocks**:
   ```latex
   \\begin{{block}}{{Introduction}}
     Your introduction text here. Keep it concise for posters.
     \\begin{{itemize}}
       \\item Key point one
       \\item Key point two
     \\end{{itemize}}
   \\end{{block}}
   
   \\begin{{block}}{{Methods}}
     Description of your methodology...
   \\end{{block}}
   ```

3. **Add figures**:
   ```latex
   \\begin{{block}}{{Results}}
     \\begin{{figure}}
       \\centering
       \\includegraphics[width=0.9\\textwidth]{{Figures/results.png}}
       \\caption{{Main experimental results}}
     \\end{{figure}}
   \\end{{block}}
   ```

4. **Add equations**:
   ```latex
   \\begin{{block}}{{Mathematical Model}}
     Our model is defined as:
     \\begin{{equation}}
       L(\\theta) = \\sum_{{i=1}}^N \\log p(x_i | \\theta)
     \\end{{equation}}
   \\end{{block}}
   ```

5. **Add highlighted/alert blocks**:
   ```latex
   \\begin{{alertblock}}{{Key Finding}}
     Our main contribution is...
   \\end{{alertblock}}
   
   \\begin{{exampleblock}}{{Example Application}}
     This can be applied to...
   \\end{{exampleblock}}
   ```

6. **Add tables**:
   ```latex
   \\begin{{block}}{{Comparison}}
     \\begin{{table}}
       \\centering
       \\begin{{tabular}}{{lcc}}
         \\toprule
         Method & Accuracy & Speed \\\\
         \\midrule
         Baseline & 0.85 & 100ms \\\\
         Ours & \\textbf{{0.92}} & 80ms \\\\
         \\bottomrule
       \\end{{tabular}}
     \\end{{table}}
   \\end{{block}}
   ```

7. **Add references block**:
   ```latex
   \\begin{{block}}{{References}}
     \\small
     \\bibliographystyle{{unsrt}}
     \\bibliography{{reference}}
   \\end{{block}}
   ```

## Poster Layout Tips
- Typical layout: 3 columns for portrait, 4 columns for landscape
- Column width: `0.32\\textwidth` for 3 columns (with gaps)
- Balance content across columns
- Use minimal text, let figures speak
- Include QR code to paper/website

## Compilation
Compile with: `document_compile(document_name="{document_dir.split('/')[-1]}")`

## Tips
- Standard sizes: A0 (841mm x 1189mm), A1 (594mm x 841mm)
- Set size in header.tex: `\\geometry{{paperwidth=..., paperheight=...}}`
- Use high-resolution figures (300+ DPI)
- Color scheme customization in beamercolorthemegemini.sty
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("Poster")
class PosterProcessor(DocumentProcessor):
    """Processor for academic poster template."""
    
    template_name = "Poster"
    main_file = "poster.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_poster_template_rule(self.document_dir)
