"""Note template processor.

Academic lecture notes template with sections, table of contents,
bibliography, and appendix support.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_note_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the Note template."""
    return f"""
Document directory `{document_dir}` created successfully. This is an academic lecture notes template.

## File Structure
```
{document_dir}/
├── master.tex        # Main file (compile this)
├── header.tex        # Preamble: packages, macros, custom commands
├── appendix.tex      # Appendix content (included via \\input)
├── reference.bib     # Bibliography entries
├── Lectures/         # Directory for lecture section files
└── Figures/          # Directory for images and diagrams
```

## Key Files

### master.tex (Main File)
The main document file that includes all other files. Contains:
- `\\input{{header.tex}}` - loads packages and settings
- Document body with `\\section{{}}` commands
- `\\input{{appendix.tex}}` - loads appendix
- `\\bibliography{{reference}}` - loads bibliography

### header.tex (Preamble)
Contains all LaTeX packages and custom macros. Key features:
- Math packages: amsmath, amsthm, amssymb
- Theorem environments: theorem, lemma, corollary, definition, example, remark
- Custom formatting and styling
- Bibliography setup

### appendix.tex
Additional content that goes at the end of the document.
Use `\\appendix` command before including this file.

### reference.bib (Bibliography)
BibTeX entries for citations. Use `\\cite{{key}}` in the main text.

## Editing Workflow

1. **Add content** to `master.tex`:
   ```latex
   \\section{{Introduction}}
   Your introduction text here...
   
   \\section{{Main Content}}
   \\subsection{{Topic 1}}
   Details with math: $E = mc^2$
   
   \\cite{{einstein1905}} % cite a reference
   ```

2. **Add new packages** to `header.tex`:
   ```latex
   \\usepackage{{tikz}}  % for diagrams
   ```

3. **Add citations** to `reference.bib`:
   ```bibtex
   @article{{einstein1905,
     author = {{Einstein, Albert}},
     title = {{On the Electrodynamics of Moving Bodies}},
     journal = {{Annalen der Physik}},
     year = {{1905}}
   }}
   ```

4. **Add figures** to `Figures/` directory, then include:
   ```latex
   \\includegraphics[width=0.8\\textwidth]{{Figures/diagram.png}}
   ```

## Compilation
Compile with: `document_compile(document_name="{document_dir.split('/')[-1]}")`

The tool automatically runs:
1. pdflatex master.tex
2. bibtex master (if .bib file exists)
3. pdflatex master.tex (2 more times for references)

## Tips
- Use theorem environments: `\\begin{{theorem}}...\\end{{theorem}}`
- Math mode: inline `$...$`, display `\\[...\\]`
- Cross-references: `\\label{{sec:intro}}` and `\\ref{{sec:intro}}`
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("Note")
class NoteProcessor(DocumentProcessor):
    """Processor for academic lecture notes template."""
    
    template_name = "Note"
    main_file = "master.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_note_template_rule(self.document_dir)
