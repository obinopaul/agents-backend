"""Beamer template processor.

PDF presentation slides using LaTeX Beamer class for
academic-style presentations with sections and bibliography.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_beamer_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the Beamer template."""
    return f"""
Document directory `{document_dir}` created successfully. This is a Beamer presentation template for PDF slides.

## File Structure
```
{document_dir}/
├── main.tex          # Main presentation file (compile this)
├── header.tex        # Beamer settings and theme configuration
├── reference.bib     # Bibliography entries
└── Figures/          # Directory for images and diagrams
```

## Key Files

### main.tex (Main File)
The presentation document with slides:
```latex
\\input{{header.tex}}
\\begin{{document}}
\\maketitle
\\begin{{frame}}{{Outline}}
  \\tableofcontents
\\end{{frame}}
\\section{{Introduction}}
\\begin{{frame}}{{Slide Title}}
  Slide content here...
\\end{{frame}}
\\end{{document}}
```

### header.tex (Theme Settings)
Beamer theme and style configuration:
- Theme selection (Madrid, Berlin, Singapore, etc.)
- Color scheme
- Font settings
- Custom commands

### reference.bib (Bibliography)
BibTeX entries for citations in slides.

## Editing Workflow

1. **Set presentation metadata** in header.tex:
   ```latex
   \\title{{Your Presentation Title}}
   \\subtitle{{Optional Subtitle}}
   \\author{{Your Name}}
   \\institute{{University/Organization}}
   \\date{{\\today}}
   ```

2. **Create slides** in main.tex:
   ```latex
   \\section{{Main Section}}
   
   \\begin{{frame}}{{Slide Title}}
     \\begin{{itemize}}
       \\item First point
       \\item Second point
       \\item Third point
     \\end{{itemize}}
   \\end{{frame}}
   
   \\begin{{frame}}{{Slide with Figure}}
     \\begin{{center}}
       \\includegraphics[width=0.7\\textwidth]{{Figures/diagram.png}}
     \\end{{center}}
   \\end{{frame}}
   ```

3. **Add math slides**:
   ```latex
   \\begin{{frame}}{{Mathematical Results}}
     The main theorem states:
     \\begin{{theorem}}
       For all $x \\in \\mathbb{{R}}$, we have $f(x) \\geq 0$.
     \\end{{theorem}}
   \\end{{frame}}
   ```

4. **Add columns for side-by-side content**:
   ```latex
   \\begin{{frame}}{{Two Columns}}
     \\begin{{columns}}
       \\begin{{column}}{{0.5\\textwidth}}
         Left side content
       \\end{{column}}
       \\begin{{column}}{{0.5\\textwidth}}
         Right side content
       \\end{{column}}
     \\end{{columns}}
   \\end{{frame}}
   ```

5. **Add blocks for emphasis**:
   ```latex
   \\begin{{block}}{{Block Title}}
     Important content here
   \\end{{block}}
   
   \\begin{{alertblock}}{{Warning}}
     Alert content
   \\end{{alertblock}}
   
   \\begin{{exampleblock}}{{Example}}
     Example content
   \\end{{exampleblock}}
   ```

6. **Add animations** (appear one by one):
   ```latex
   \\begin{{itemize}}
     \\item<1-> First (appears on click 1)
     \\item<2-> Second (appears on click 2)
     \\item<3-> Third (appears on click 3)
   \\end{{itemize}}
   ```

## Compilation
Compile with: `document_compile(document_name="{document_dir.split('/')[-1]}")`

## Tips
- Keep slides concise - aim for 6-8 lines per slide
- Use figures and diagrams when possible
- Available themes: Madrid, Berlin, Singapore, Copenhagen, Boadilla
- Change theme: `\\usetheme{{ThemeName}}` in header.tex
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("Beamer")
class BeamerProcessor(DocumentProcessor):
    """Processor for Beamer presentation template."""
    
    template_name = "Beamer"
    main_file = "main.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_beamer_template_rule(self.document_dir)
