"""Letter template processor.

Formal letter template with professional letterhead styling
using custom UIUCletter document class.
"""

from backend.src.tool_server.tools.documents.template_processor.base_processor import (
    DocumentProcessor,
)
from backend.src.tool_server.tools.documents.template_processor.registry import (
    DocumentProcessorRegistry,
)


def get_letter_template_rule(document_dir: str) -> str:
    """Generate deployment rules for the Letter template."""
    return f"""
Document directory `{document_dir}` created successfully. This is a formal letter template with professional letterhead.

## File Structure
```
{document_dir}/
├── letter.tex        # Main letter file (compile this)
├── UIUCletter.cls    # Custom document class (do not modify)
└── Figures/          # Directory for letterhead logo/images
```

## Key Files

### letter.tex (Main File)
The letter document using custom letterhead formatting:
```latex
\\documentclass{{UIUCletter}}
\\begin{{document}}
% Recipient information
\\begin{{letter}}{{Recipient Name \\\\ Company \\\\ Address}}
\\opening{{Dear Dr. Name,}}
% Letter body
Your letter content here...
\\closing{{Sincerely,}}
\\end{{letter}}
\\end{{document}}
```

### UIUCletter.cls (Document Class)
Custom class providing letterhead styling. Do not modify this file
unless you need to change institutional branding.

## Editing Workflow

1. **Set sender information** (in preamble of letter.tex):
   ```latex
   \\name{{Your Full Name}}
   \\signature{{Your Name}}
   \\position{{Your Title}}
   \\department{{Department Name}}
   \\address{{123 Main Street \\\\ City, State 12345}}
   \\telephone{{(123) 456-7890}}
   \\email{{your.email@university.edu}}
   ```

2. **Set recipient and date**:
   ```latex
   \\begin{{letter}}{{
     Dr. Jane Smith \\\\
     Head of Department \\\\
     University of Example \\\\
     456 Academic Ave \\\\
     City, State 67890
   }}
   \\date{{\\today}}  % or specific date
   ```

3. **Write letter content**:
   ```latex
   \\opening{{Dear Dr. Smith,}}
   
   I am writing to express my interest in the position of...
   
   In my current role, I have developed expertise in...
   
   I would welcome the opportunity to discuss...
   
   \\closing{{Sincerely,}}
   ```

4. **Add enclosures** (optional):
   ```latex
   \\encl{{Curriculum Vitae \\\\ List of Publications}}
   ```

5. **Add CC** (optional):
   ```latex
   \\cc{{Dr. Other Person \\\\ Department Head}}
   ```

## Compilation
Compile with: `document_compile(document_name="{document_dir.split('/')[-1]}")`

## Tips
- Keep the letter professional and concise
- Use proper salutation (Dear Dr./Mr./Ms./Prof.)
- Sign off appropriately (Sincerely, Best regards, Respectfully)
- Common enclosures: CV, transcripts, reference letters
- To view in LaTeX Editor: use `register_deployment(port=9001)` for public URL
"""


@DocumentProcessorRegistry.register("Letter")
class LetterProcessor(DocumentProcessor):
    """Processor for formal letter template."""
    
    template_name = "Letter"
    main_file = "letter.tex"
    
    def __init__(self, document_dir: str) -> None:
        super().__init__(document_dir)
    
    def get_template_rule(self) -> str:
        return get_letter_template_rule(self.document_dir)
