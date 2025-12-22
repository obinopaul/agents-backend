# Slides API Contracts

> **Base URL:** `http://localhost:8000/api/v1/agent/slides`
>
> All endpoints require `Authorization: Bearer <token>` header.

---

## Overview

The Slides API manages presentation files stored in sandboxes. Presentations are HTML-based slides that can be previewed and exported to PDF.

**Storage Location:** `/workspace/presentations/{presentation_name}/`

**File Structure:**
```
/workspace/presentations/
└── my-presentation/
    ├── slide_1.html
    ├── slide_2.html
    ├── slide_3.html
    └── assets/
        ├── image1.png
        └── styles.css
```

---

## Table of Contents

1. [List Presentations](#1-list-presentations)
2. [List Slides](#2-list-slides)
3. [Get Slide Content](#3-get-slide-content)
4. [Export Presentation](#4-export-presentation)
5. [Thumbnail Generation](#5-thumbnail-generation)

---

## 1. List Presentations

### GET `/presentations`

List all presentations in a sandbox.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | string | ✅ | Sandbox ID |

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "presentations": [
      {
        "name": "ai-research-2024",
        "slide_count": 12,
        "path": "/workspace/presentations/ai-research-2024"
      },
      {
        "name": "quarterly-report",
        "slide_count": 8,
        "path": "/workspace/presentations/quarterly-report"
      }
    ],
    "message": "Presentations retrieved successfully"
  }
}
```

---

## 2. List Slides

### GET `/presentations/{presentation_name}/slides`

List all slides in a presentation.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | string | ✅ | Sandbox ID |

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "presentation_name": "ai-research-2024",
    "slides": [
      {
        "slide_number": 1,
        "filename": "slide_1.html",
        "path": "/workspace/presentations/ai-research-2024/slide_1.html"
      },
      {
        "slide_number": 2,
        "filename": "slide_2.html",
        "path": "/workspace/presentations/ai-research-2024/slide_2.html"
      }
    ],
    "message": "Slides retrieved successfully"
  }
}
```

---

## 3. Get Slide Content

### GET `/presentations/{presentation_name}/slides/{slide_number}`

Get HTML content of a specific slide.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | string | ✅ | Sandbox ID |

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "slide_number": 1,
    "presentation_name": "ai-research-2024",
    "content": "<!DOCTYPE html>\n<html>\n<head>\n  <style>/* slide styles */</style>\n</head>\n<body>\n  <h1>AI Research 2024</h1>\n  <p>Key findings and insights</p>\n</body>\n</html>",
    "message": "Slide content retrieved successfully"
  }
}
```

---

### GET `/presentations/{presentation_name}/slides/{slide_number}/raw`

Get raw HTML file directly (no JSON wrapper).

**Query:** `?sandbox_id=abc123`

**Response:** Raw HTML content with `Content-Type: text/html`

---

## 4. Export Presentation

### POST `/export`

Export presentation to PDF.

**Request:**
```json
{
  "sandbox_id": "sandbox-abc123",
  "presentation_name": "ai-research-2024",
  "format": "pdf"
}
```

**Response:** PDF file stream

**Content-Disposition:** `attachment; filename="ai-research-2024.pdf"`

---

### GET `/presentations/{presentation_name}/export/pdf`

Alternative GET endpoint for PDF export.

**Query:** `?sandbox_id=abc123`

**Response:** PDF file download

---

## 5. Thumbnail Generation

### GET `/presentations/{presentation_name}/slides/{slide_number}/thumbnail`

Get thumbnail image of a slide.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sandbox_id` | string | required | Sandbox ID |
| `width` | int | 320 | Thumbnail width |
| `height` | int | 240 | Thumbnail height |
| `format` | string | png | Output format (png/jpeg) |

**Response:** Image file

---

## Error Responses

| Code | Description |
|------|-------------|
| 400 | Invalid request (missing sandbox_id) |
| 401 | Unauthorized |
| 404 | Presentation or slide not found |
| 408 | Timeout |
| 500 | Internal error |

---

## Slide HTML Format

Slides use a standard HTML template:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Slide Title</title>
  <style>
    body {
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 40px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      box-sizing: border-box;
    }
    h1 {
      color: white;
      font-size: 3rem;
      margin-bottom: 1rem;
    }
    .content {
      color: rgba(255,255,255,0.9);
      font-size: 1.5rem;
      line-height: 1.6;
    }
  </style>
</head>
<body>
  <h1>Slide Title</h1>
  <div class="content">
    <ul>
      <li>Point 1</li>
      <li>Point 2</li>
      <li>Point 3</li>
    </ul>
  </div>
</body>
</html>
```

---

## Integration with PPT Generation

The generation API creates slides:

```bash
# Generate presentation from content
curl -X POST http://localhost:8000/api/v1/agent/generation/ppt/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# AI in Healthcare\n\n## Key Points\n- Diagnosis\n- Treatment\n- Research",
    "locale": "en-US"
  }'

# Then list created presentations
curl "http://localhost:8000/api/v1/agent/slides/presentations?sandbox_id=$SANDBOX" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Quick Test Commands

```bash
# List presentations
curl "http://localhost:8000/api/v1/agent/slides/presentations?sandbox_id=$SANDBOX" \
  -H "Authorization: Bearer $TOKEN"

# List slides in presentation
curl "http://localhost:8000/api/v1/agent/slides/presentations/my-presentation/slides?sandbox_id=$SANDBOX" \
  -H "Authorization: Bearer $TOKEN"

# Get slide content
curl "http://localhost:8000/api/v1/agent/slides/presentations/my-presentation/slides/1?sandbox_id=$SANDBOX" \
  -H "Authorization: Bearer $TOKEN"

# Export to PDF
curl -X POST http://localhost:8000/api/v1/agent/slides/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sandbox_id":"'$SANDBOX'","presentation_name":"my-presentation"}' \
  -o presentation.pdf
```
