"""CV template processor.

Full academic CV with modular sections for education, experience,
publications, teaching, awards, and service.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_cv_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the CV template."""
    return f"""
Document directory `{document_dir}` created successfully. This is a full academic CV template with modular sections.

## File Structure
```
{document_dir}/
├── cv.tex            # Full CV (compile this for complete version)
├── resume.tex        # Shorter resume version
├── header.tex        # Shared preamble and styling
├── 1_education.tex   # Education section
├── 2_experience.tex  # Work/research experience section
├── 3_publication.tex # Publications section
├── 4_teaching.tex    # Teaching experience section
├── 5_award.tex       # Awards and honors section
└── 6_service.tex     # Professional service section
```

## Key Files

### cv.tex (Main CV)
Full academic CV that includes all section files:
```latex
\\input{{header.tex}}
\\begin{{document}}
\\input{{1_education.tex}}
\\input{{2_experience.tex}}
\\input{{3_publication.tex}}
\\input{{4_teaching.tex}}
\\input{{5_award.tex}}
\\input{{6_service.tex}}
\\end{{document}}
```

### resume.tex (Short Version)
Condensed resume for job applications. Includes only selected sections.

### header.tex (Styling)
Custom CV formatting including:
- Personal information (name, contact, links)
- Section heading styles
- Entry formatting macros

## Editing Workflow

1. **Update personal information** in `header.tex`:
   ```latex
   \\name{{Your Name}}
   \\address{{Your City, State}}
   \\email{{your.email@example.com}}
   \\phone{{(123) 456-7890}}
   \\linkedin{{linkedin.com/in/yourprofile}}
   \\github{{github.com/yourusername}}
   ```

2. **Edit individual sections**:

   **1_education.tex**:
   ```latex
   \\cvsection{{Education}}
   \\cventry{{Ph.D. in Computer Science}}{{University Name}}{{Expected 2025}}{{}}
   \\cventry{{B.S. in Mathematics}}{{Another University}}{{2020}}{{GPA: 3.9/4.0}}
   ```

   **2_experience.tex**:
   ```latex
   \\cvsection{{Experience}}
   \\cventry{{Research Assistant}}{{Lab Name, University}}{{2021--Present}}{{
     \\begin{{itemize}}
       \\item Developed machine learning models...
       \\item Published 3 papers in top venues...
     \\end{{itemize}}
   }}
   ```

   **3_publication.tex**:
   ```latex
   \\cvsection{{Publications}}
   \\begin{{enumerate}}
     \\item \\textbf{{Your Name}}, Co-author. "Paper Title." \\textit{{Journal Name}}, 2024.
   \\end{{enumerate}}
   ```

3. **Customize which sections appear**:
   - For full CV: include all sections in `cv.tex`
   - For resume: include only relevant sections in `resume.tex`

## Compilation
- Full CV: `document_compile(document_name="{document_dir.split('/')[-1]}", main_file="cv.tex")`
- Resume: `document_compile(document_name="{document_dir.split('/')[-1]}", main_file="resume.tex")`

## Tips
- Keep descriptions concise and action-oriented
- Use bullet points for responsibilities and achievements
- Order sections by relevance to target position
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("CV")
class CVProcessor(DocumentProcessor):
    """Processor for academic CV template."""
    
    template_name = "CV"
    main_file = "cv.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_cv_template_rule(self.document_dir)
