"""CV_2 template processor.

Alternative CV style using Awesome-CV class with modern formatting
and support for CV, resume, and cover letter.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_cv2_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the CV_2 template."""
    return f"""
Document directory `{document_dir}` created successfully. This is an Awesome-CV style template with modern formatting.

## File Structure
```
{document_dir}/
├── cv.tex            # Full CV document (compile this)
├── resume.tex        # Short resume version
├── coverletter.tex   # Cover letter template
├── awesome-cv.cls    # Awesome-CV document class
├── profile.png       # Profile photo (optional)
├── cv/               # CV section files
│   └── ...           # Individual CV sections
└── resume/           # Resume section files
    └── ...           # Individual resume sections
```

## Key Files

### cv.tex (Full CV)
Uses Awesome-CV class for modern, professional formatting:
```latex
\\documentclass[11pt,a4paper,sans]{{awesome-cv}}
\\begin{{document}}
\\makecvheader
% Section includes
\\input{{cv/education.tex}}
\\input{{cv/experience.tex}}
...
\\end{{document}}
```

### resume.tex (Short Version)
Condensed one-page resume with selected sections.

### coverletter.tex (Cover Letter)
Professional cover letter with matching style.

### awesome-cv.cls (Document Class)
Custom class file - do not modify unless you understand LaTeX class files.

## Editing Workflow

1. **Update personal info** at the top of `cv.tex`:
   ```latex
   \\name{{First}}{{Last}}
   \\position{{Job Title{{\\enskip\\cdotp\\enskip}}Specialization}}
   \\address{{City, Country}}
   \\mobile{{(+1) 123-456-7890}}
   \\email{{your@email.com}}
   \\github{{github-username}}
   \\linkedin{{linkedin-username}}
   ```

2. **Add profile photo** (optional):
   - Replace `profile.png` with your photo
   - Uncomment `\\photo[circle,noedge,left]{{profile}}` in header

3. **Edit CV sections** in `cv/` directory:
   
   **Education**:
   ```latex
   \\cvsection{{Education}}
   \\begin{{cventries}}
     \\cventry
       {{Ph.D. in Computer Science}} % Degree
       {{University Name}} % Institution
       {{City, Country}} % Location
       {{2020 -- Present}} % Date
       {{
         \\begin{{cvitems}}
           \\item {{Research focus: Machine Learning}}
           \\item {{Advisor: Prof. Name}}
         \\end{{cvitems}}
       }}
   \\end{{cventries}}
   ```

   **Experience**:
   ```latex
   \\cventry
     {{Software Engineer}} % Position
     {{Company Name}} % Employer
     {{City, Country}} % Location
     {{Jan. 2020 -- Present}} % Date
     {{
       \\begin{{cvitems}}
         \\item {{Built scalable microservices...}}
         \\item {{Led team of 5 engineers...}}
       \\end{{cvitems}}
     }}
   ```

4. **Edit cover letter** in `coverletter.tex`:
   ```latex
   \\recipient{{Hiring Manager}}{{Company Name \\\\ Address}}
   \\letterdate{{\\today}}
   \\lettertitle{{Application for Software Engineer Position}}
   \\letteropening{{Dear Hiring Manager,}}
   \\letterclosing{{Sincerely,}}
   ```

## Compilation
- CV: `document_compile(document_name="{document_dir.split('/')[-1]}", main_file="cv.tex")`
- Resume: `document_compile(document_name="{document_dir.split('/')[-1]}", main_file="resume.tex")`
- Cover Letter: `document_compile(document_name="{document_dir.split('/')[-1]}", main_file="coverletter.tex")`

## Tips
- Use accent colors: `\\colorlet{{awesome}}{{awesome-emerald}}` in preamble
- Available colors: awesome-emerald, awesome-skyblue, awesome-red, awesome-pink, etc.
- Photo is optional - remove `\\photo` line if not needed
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("CV_2")
class CV2Processor(DocumentProcessor):
    """Processor for Awesome-CV style template."""
    
    template_name = "CV_2"
    main_file = "cv.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_cv2_template_rule(self.document_dir)
