# Slides System - API Contracts

> Complete API reference for the presentation slides system. All endpoints require JWT authentication.

---

## Base URL

All slide endpoints are mounted at `/agent/sandboxes/`.

**Full endpoint pattern:** `http://localhost:8000/agent/sandboxes/{endpoint}`

---

## Authentication

All endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Getting a Token

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login/swagger?username=<user>&password=<pass>" 

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "user": { ... }
}
```

---

## Route Ordering

> [!IMPORTANT]
> Database endpoints (`/db/*`) are defined BEFORE sandbox endpoints (`/{sandbox_id}/*`) in the code.
> This ensures FastAPI matches the static `/db` prefix before treating it as a dynamic `sandbox_id`.

---

# Database-Backed Endpoints

These endpoints read from PostgreSQL. They work even when the sandbox is stopped.

## GET `/db/presentations`

List all presentations for a thread from the database.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `thread_id` | Query | string | ✅ | Thread/session ID |

### Response

```json
{
  "code": 200,
  "msg": "Request success",
  "data": {
    "thread_id": "slide-test-6c9a44b7",
    "presentations": [
      {
        "name": "Python_Presentation",
        "slide_count": 3,
        "last_updated": "2026-01-09T04:07:11.716767Z",
        "slides": [
          {
            "id": 1,
            "thread_id": "slide-test-6c9a44b7",
            "presentation_name": "Python_Presentation",
            "slide_number": 1,
            "slide_title": "Introduction to Python",
            "slide_content": "<!DOCTYPE html>...",
            "metadata": {},
            "created_time": "2026-01-09T04:06:30Z",
            "updated_time": null
          }
        ]
      }
    ],
    "total": 2
  }
}
```

### Example

```bash
# cURL
curl "http://localhost:8000/agent/sandboxes/db/presentations?thread_id=slide-test-6c9a44b7" \
  -H "Authorization: Bearer $TOKEN"
```

```powershell
# PowerShell
$result = Invoke-RestMethod -Uri "http://localhost:8000/agent/sandboxes/db/presentations?thread_id=$threadId" `
  -Headers @{"Authorization"="Bearer $token"}
$result | ConvertTo-Json -Depth 5
```

---

## GET `/db/slide`

Get a specific slide's HTML content.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `thread_id` | Query | string | ✅ | Thread/session ID |
| `presentation_name` | Query | string | ✅ | Presentation name |
| `slide_number` | Query | int | ✅ | Slide number (1-indexed) |

### Response

```json
{
  "code": 200,
  "msg": "Request success",
  "data": {
    "success": true,
    "slide_number": 1,
    "presentation_name": "Python_Presentation",
    "content": "<!DOCTYPE html><html>...",
    "title": "Introduction to Python",
    "message": "Slide content retrieved successfully"
  }
}
```

### Example

```bash
curl "http://localhost:8000/agent/sandboxes/db/slide?thread_id=test-123&presentation_name=Demo&slide_number=1" \
  -H "Authorization: Bearer $TOKEN"
```

---

## POST `/db/slide`

Manually write a slide to the database (primarily for testing).

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `thread_id` | Query | string | ✅ | Thread/session ID |

### Request Body

```json
{
  "presentation_name": "Demo",
  "slide_number": 1,
  "content": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>",
  "title": "Welcome",
  "description": "Optional description"
}
```

### Response

```json
{
  "code": 200,
  "msg": "Request success", 
  "data": {
    "success": true,
    "presentation_name": "Demo",
    "slide_number": 1,
    "slide_id": 42
  }
}
```

### Example

```bash
curl -X POST "http://localhost:8000/agent/sandboxes/db/slide?thread_id=test-123" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "presentation_name": "Demo",
    "slide_number": 1,
    "content": "<html><body><h1>Hello World</h1></body></html>",
    "title": "Welcome"
  }'
```

---

## GET `/db/download`

Export slides from database to PDF.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `thread_id` | Query | string | ✅ | Thread/session ID |
| `presentation_name` | Query | string | ❌ | Specific presentation (optional, exports all if omitted) |

### Response

**Content-Type:** `application/pdf`

Returns a PDF file as binary download.

### Example

```bash
# Download specific presentation
curl "http://localhost:8000/agent/sandboxes/db/download?thread_id=test-123&presentation_name=Demo" \
  -H "Authorization: Bearer $TOKEN" \
  -o Demo.pdf

# Download all presentations for thread
curl "http://localhost:8000/agent/sandboxes/db/download?thread_id=test-123" \
  -H "Authorization: Bearer $TOKEN" \
  -o all_slides.pdf
```

```powershell
# PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/agent/sandboxes/db/download?thread_id=$threadId&presentation_name=Demo" `
  -Headers @{"Authorization"="Bearer $token"} `
  -OutFile "Demo.pdf"
```

---

## GET `/db/download/stream`

Export slides to PDF with Server-Sent Events (SSE) progress updates.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `thread_id` | Query | string | ✅ | Thread/session ID |
| `presentation_name` | Query | string | ❌ | Specific presentation (optional) |

### Response

**Content-Type:** `text/event-stream`

### SSE Events

| Event | Data | Description |
|-------|------|-------------|
| `progress` | `{"current": 2, "total": 5, "percent": 40, "message": "Rendering slide 2..."}` | Progress update |
| `complete` | `{"pdf_base64": "JVBERi0...", "total_pages": 5}` | PDF as base64 |
| `error` | `{"message": "Failed to render"}` | Error occurred |

### Example (JavaScript)

```javascript
const eventSource = new EventSource(
  `/agent/sandboxes/db/download/stream?thread_id=${threadId}&presentation_name=Demo`,
  { headers: { 'Authorization': `Bearer ${token}` } }
);

eventSource.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`${data.percent}% - ${data.message}`);
});

eventSource.addEventListener('complete', (e) => {
  const data = JSON.parse(e.data);
  // Decode base64 and download
  const pdfBytes = atob(data.pdf_base64);
  // ... create blob and download
});

eventSource.addEventListener('error', (e) => {
  console.error('Error:', JSON.parse(e.data).message);
});
```

---

# Sandbox-Backed Endpoints

These endpoints read directly from the sandbox filesystem. They require an active sandbox.

## GET `/{sandbox_id}/presentations`

List all presentations in the sandbox workspace.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `sandbox_id` | Path | string | ✅ | Sandbox ID |

### Response

```json
{
  "code": 200,
  "msg": "Request success",
  "data": {
    "success": true,
    "presentations": [
      {
        "name": "Q4_Report",
        "slide_count": 5,
        "path": "/workspace/presentations/Q4_Report"
      }
    ],
    "message": "Found 1 presentation(s)"
  }
}
```

### Example

```bash
curl "http://localhost:8000/agent/sandboxes/{sandbox_id}/presentations" \
  -H "Authorization: Bearer $TOKEN"
```

---

## GET `/{sandbox_id}/presentations/{presentation_name}`

List all slides in a presentation.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `sandbox_id` | Path | string | ✅ | Sandbox ID |
| `presentation_name` | Path | string | ✅ | Presentation folder name |

### Response

```json
{
  "code": 200,
  "msg": "Request success",
  "data": {
    "success": true,
    "presentation_name": "Q4_Report",
    "slides": [
      {
        "slide_number": 1,
        "filename": "slide_001.html",
        "path": "/workspace/presentations/Q4_Report/slide_001.html"
      },
      {
        "slide_number": 2,
        "filename": "slide_002.html", 
        "path": "/workspace/presentations/Q4_Report/slide_002.html"
      }
    ],
    "message": "Found 2 slide(s)"
  }
}
```

---

## GET `/{sandbox_id}/slides/{presentation_name}/{slide_num}`

Get the HTML content of a specific slide.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `sandbox_id` | Path | string | ✅ | Sandbox ID |
| `presentation_name` | Path | string | ✅ | Presentation folder name |
| `slide_num` | Path | int | ✅ | Slide number (1-indexed) |

### Response

```json
{
  "code": 200,
  "msg": "Request success",
  "data": {
    "success": true,
    "slide_number": 1,
    "presentation_name": "Q4_Report",
    "content": "<!DOCTYPE html>...",
    "message": "Slide content retrieved successfully"
  }
}
```

---

## POST `/{sandbox_id}/slides/export`

Export a presentation to PDF from sandbox.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `sandbox_id` | Path | string | ✅ | Sandbox ID |

### Request Body

```json
{
  "presentation_name": "Q4_Report"
}
```

### Response

**Content-Type:** `application/pdf`

Returns PDF file as binary download.

---

## GET `/{sandbox_id}/slides/download/{presentation_name}`

Download all slides as a ZIP archive.

### Request

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `sandbox_id` | Path | string | ✅ | Sandbox ID |
| `presentation_name` | Path | string | ✅ | Presentation folder name |

### Response

**Content-Type:** `application/zip`

Returns ZIP file containing all HTML slide files.

### Example

```bash
curl "http://localhost:8000/agent/sandboxes/{sandbox_id}/slides/download/Q4_Report" \
  -H "Authorization: Bearer $TOKEN" \
  -o Q4_Report.zip
```

---

# Error Responses

All endpoints return errors in this format:

```json
{
  "code": 404,
  "msg": "Request failed",
  "data": null,
  "detail": "Slide 99 not found in presentation 'Demo'"
}
```

### Common Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 401 | Unauthorized - Invalid or missing token |
| 404 | Not Found - Slide, presentation, or sandbox not found |
| 422 | Validation Error - Invalid parameters |
| 500 | Internal Server Error |

---

# Data Models

## SlideWriteRequest

```typescript
interface SlideWriteRequest {
  presentation_name: string;  // Required
  slide_number: number;       // Required, >= 1
  content: string;            // Required, HTML content
  title?: string;             // Optional
  description?: string;       // Optional
}
```

## PresentationInfo

```typescript
interface PresentationInfo {
  name: string;
  slide_count: number;
  last_updated: string | null;  // ISO 8601 datetime
  slides: SlideContentInfo[];
}
```

## SlideContentInfo

```typescript
interface SlideContentInfo {
  id: number;
  thread_id: string;
  presentation_name: string;
  slide_number: number;
  slide_title: string | null;
  slide_content: string;
  metadata: object;
  created_time: string;
  updated_time: string | null;
}
```

---

# Database Schema

## slide_content Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | BIGINT | NO | Primary key (auto-increment) |
| `thread_id` | VARCHAR(64) | NO | Thread/session ID |
| `presentation_name` | VARCHAR(255) | NO | Presentation name |
| `slide_number` | INT | NO | Slide number (1-indexed) |
| `slide_title` | VARCHAR(500) | YES | Slide title |
| `slide_content` | TEXT | YES | HTML content |
| `slide_metadata` | JSONB | YES | Tool metadata |
| `created_time` | TIMESTAMPTZ | NO | Created timestamp |
| `updated_time` | TIMESTAMPTZ | YES | Last update timestamp |

### Indexes

- Primary Key: `id`
- Unique: `(thread_id, presentation_name, slide_number)`
- Index: `thread_id`
- Index: `presentation_name`

---

# File Locations

## Sandbox Storage

Slides are stored at: `/workspace/presentations/{presentation_name}/slide_{number}.html`

Example:
```
/workspace/presentations/
└── Q4_Report/
    ├── slide_001.html
    ├── slide_002.html
    └── slide_003.html
```

## Database Storage

Slides are stored in the `slide_content` PostgreSQL table, keyed by `(thread_id, presentation_name, slide_number)`.
