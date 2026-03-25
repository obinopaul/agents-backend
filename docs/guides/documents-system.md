# Documents System Guide

> A comprehensive guide to using the Documents system for creating LaTeX documents with AI assistance.

---

## Overview

The Documents system enables AI agents to create professional LaTeX documents from templates. Unlike the Slides system (HTML-based presentations), Documents uses LaTeX for academic papers, CVs, reports, and formal correspondence.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Templates** | Pre-designed LaTeX document structures (7 available) |
| **Documents** | User-created documents stored in `/workspace/documents/` |
| **Compilation** | Converting LaTeX to PDF via pdflatex |
| **LaTeX Editor** | Web-based Monaco editor on port 9001 |

---

## Quick Start

### 1. Initialize a Document

The agent uses `document_template_init` to create a new document:

```json
{
  "tool": "document_template_init",
  "input": {
    "document_name": "my-thesis",
    "template": "Report"
  }
}
```

This creates:
```
/workspace/documents/my_thesis/
├── main.tex          # Main document file
├── header.tex        # Preamble and packages  
└── metadata.json     # Document metadata
```

### 2. Edit Files

The agent uses standard file tools to edit LaTeX content:

```json
{
  "tool": "FileEdit",
  "input": {
    "file_path": "/workspace/documents/my_thesis/main.tex",
    "content": "\\section{Introduction}\nThis is my thesis..."
  }
}
```

### 3. Compile to PDF

```json
{
  "tool": "document_compile",
  "input": {
    "document_name": "my-thesis"
  }
}
```

### 4. View in Editor

The LaTeX Editor is available at port 9001 and shows all documents in `/workspace/documents/`.

---

## Templates

### Academic Writing

#### Note
Academic lecture notes with sections, table of contents, and bibliography.

**Best for:** Course notes, study materials, technical documentation

**Main file:** `master.tex`

**Structure:**
```
Note/
├── master.tex        # Main file
├── header.tex        # Packages and macros
├── appendix.tex      # Appendix content
├── reference.bib     # Bibliography
└── Lectures/         # Lecture sections
```

---

#### Report
Clean academic report template for assignments and papers.

**Best for:** Homework, lab reports, short papers

**Main file:** `main.tex`

**Structure:**
```
Report/
├── main.tex          # Main file
└── header.tex        # Packages
```

---

### Professional Documents

#### CV
Full academic CV with comprehensive sections.

**Best for:** Academic job applications, grant proposals

**Main file:** `cv.tex`

**Structure:**
```
CV/
├── cv.tex            # Main CV file
├── resume.tex        # Shorter resume version
├── header.tex        # Styling
├── 1_education.tex   # Education section
├── 2_experience.tex  # Experience section
├── 3_publication.tex # Publications
├── 4_teaching.tex    # Teaching
├── 5_award.tex       # Awards
└── 6_service.tex     # Service
```

---

#### CV_2
Alternative CV style with different formatting.

**Main file:** `cv.tex`

---

#### Letter
Formal letter with professional letterhead.

**Best for:** Official correspondence, cover letters

**Main file:** `letter.tex`

**Structure:**
```
Letter/
├── letter.tex        # Main file
├── UIUCletter.cls    # Custom class file
└── Figures/          # Letterhead images
```

---

### Presentations & Posters

#### Beamer
PDF presentation slides using LaTeX Beamer class.

**Best for:** Academic presentations, conference talks

**Main file:** `main.tex`

**Structure:**
```
Beamer/
├── main.tex          # Main file
├── header.tex        # Beamer settings
├── reference.bib     # Bibliography
└── Figures/          # Images
```

---

#### Poster
Academic poster for conferences.

**Best for:** Research posters, conference presentations

**Main file:** `poster.tex`

**Structure:**
```
Poster/
├── poster.tex              # Main file
├── header.tex              # Settings
├── beamerthemegemini.sty   # Theme file
├── beamercolorthemegemini.sty
├── reference.bib           # Bibliography
└── Figures/                # Images
```

---

## Compilation

### How It Works

1. Agent calls `document_compile`
2. Tool locates the document in `/workspace/documents/`
3. Runs `pdflatex` on the main file
4. If `.bib` files exist, runs `bibtex` + 2 more pdflatex passes
5. Parses log for errors and warnings
6. Returns result with PDF path or error details

### Compilation Process

```
pdflatex main.tex  →  First pass
bibtex main        →  If .bib exists
pdflatex main.tex  →  Second pass
pdflatex main.tex  →  Third pass (resolves references)
```

### Main File Detection

If `main_file` is not specified, the tool auto-detects:

1. `main_file` from `metadata.json`
2. `main.tex` (most common)
3. `master.tex` (Note template)
4. File matching document name (e.g., `cv.tex`, `poster.tex`)
5. First file containing `\documentclass`

---

## LaTeX Editor

### Overview

The LaTeX Editor is a web-based Monaco editor that:
- Shows all documents in `/workspace/documents/`
- Provides syntax highlighting for LaTeX
- Includes AI assistance (Write, Debug, Fix, Improve)
- Shows PDF preview after compilation

### Accessing the Editor

The editor runs on **port 9001** and auto-starts with the sandbox.

```bash
# Expose the port
POST /sandboxes/expose-port
{
  "sandbox_id": "sandbox-123",
  "port": 9001
}

# Response
{
  "url": "https://sandbox-123-9001.e2b.dev"
}
```

### Editor Features

| Feature | Description |
|---------|-------------|
| **File Manager** | Browse documents and files |
| **Monaco Editor** | Full LaTeX syntax highlighting |
| **AI Commands** | Write, Debug, Fix, Improve buttons |
| **PDF Preview** | View compiled PDF |
| **Multi-file** | Support for headers, sections, bibliographies |

---

## Mode Comparison

| Aspect | Dev Mode | Documents Mode |
|--------|----------|----------------|
| **Editor Port** | 9000 (Code-Server) | 9001 (LaTeX Editor) |
| **Workspace** | `/workspace` | `/workspace/documents` |
| **Output** | Web apps | PDF documents |
| **Tools** | FileWrite, npm, etc. | document_template_init, document_compile |

> [!NOTE]
> Both modes share the same sandbox. Services on all ports (6060, 9000, 9001) run simultaneously. The frontend selects which editor to display based on the active mode.

---

## Agent Workflow Example

### Creating a CV

```
User: "Create a CV for John Smith, PhD candidate in Computer Science"

Agent:
1. document_template_init(document_name="john-smith-cv", template="CV")
2. FileEdit: Update cv.tex with personal info
3. FileEdit: Update 1_education.tex with education
4. FileEdit: Update 2_experience.tex with experience
5. document_compile(document_name="john-smith-cv")
6. Return PDF path for download
```

### Creating a Conference Paper

```
User: "Write a paper about machine learning"

Agent:
1. document_template_init(document_name="ml-paper", template="Report")
2. FileEdit: Add sections to main.tex
3. FileEdit: Add bibliography to reference.bib
4. document_compile(document_name="ml-paper")
5. If errors: read log, fix LaTeX issues
6. document_compile again
7. Return PDF
```

---

## Troubleshooting

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Undefined control sequence` | Unknown LaTeX command | Check spelling or add package |
| `Missing $ inserted` | Math outside math mode | Wrap in `$...$` or `\[...\]` |
| `File not found` | Missing include file | Check file path in `\input{}` |
| `Citation undefined` | Missing bibtex entry | Add to `.bib` file and recompile |

### Recompiling

If references are broken:
```json
{
  "tool": "document_compile",
  "input": {
    "document_name": "my-paper"
  }
}
```

The tool automatically runs multiple passes when `.bib` files are present.

---

## Related Documentation

- [Documents API Reference](../api-contracts/documents-system.md)
- [Sandbox Guide](./sandbox-guide.md)
- [File Processing Guide](./file-processing.md)
- [Slides System Guide](./slides-system.md)
