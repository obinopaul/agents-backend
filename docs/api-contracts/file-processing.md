# File Processing API

This document describes the file upload, staging, and management API for chat attachments.

## Overview

The File Processing API allows users to:
- Upload files and stage them for later attachment to chat messages
- Parse and extract text content from documents (PDF, Word, Excel, etc.)
- Compress and optimize images
- List, retrieve, and delete staged files

## Base URL

All endpoints are under: `/agent/files`

## Authentication

All endpoints require JWT authentication. Include the Bearer token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

## Endpoints

### Test Endpoint

**GET** `/agent/files/test`

Simple test endpoint to verify the router is working.

**Response:**
```json
{"status": "files router works!"}
```

---

### Upload File

**POST** `/agent/files/upload`

Upload and stage a file for later attachment to chat messages.

**Request:**
- Content-Type: `multipart/form-data`
- `file` (required): The file to upload
- `file_id` (optional): Custom file ID

**Example:**
```bash
curl -X POST "http://localhost:8000/agent/files/upload" \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "file_id": "abc123...",
  "filename": "document.pdf",
  "storage_path": "/uploads/staged-files/...",
  "mime_type": "application/pdf",
  "file_size": 102400,
  "parsed_preview": "This is the extracted content...",
  "status": "ready",
  "created_at": "2025-12-31T12:00:00Z"
}
```

**Error Responses:**
- `400`: Filename is required
- `400`: File exceeds maximum size (50MB)
- `422`: Validation error

---

### List Staged Files

**GET** `/agent/files/staged`

List all staged files for the current user.

**Query Parameters:**
- `thread_id` (optional): Filter by thread ID

**Example:**
```bash
curl "http://localhost:8000/agent/files/staged" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "files": [
    {
      "file_id": "abc123...",
      "filename": "document.pdf",
      "storage_path": "/uploads/staged-files/...",
      "mime_type": "application/pdf",
      "file_size": 102400,
      "parsed_preview": "This is the extracted content...",
      "status": "ready",
      "created_at": "2025-12-31T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### Get File by ID

**GET** `/agent/files/{file_id}`

Retrieve a specific staged file by its ID.

**Path Parameters:**
- `file_id`: The unique file identifier

**Example:**
```bash
curl "http://localhost:8000/agent/files/abc123" \
  -H "Authorization: Bearer <token>"
```

**Response:** Same as single file in upload response.

**Error Responses:**
- `404`: File not found

---

### Delete File

**DELETE** `/agent/files/{file_id}`

Delete a staged file.

**Path Parameters:**
- `file_id`: The unique file identifier

**Example:**
```bash
curl -X DELETE "http://localhost:8000/agent/files/abc123" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "status": "deleted",
  "file_id": "abc123..."
}
```

**Error Responses:**
- `404`: File not found

---

## File Processing

### Supported Formats

| Category | Formats |
|----------|---------|
| Documents | PDF, DOCX, DOC, TXT, MD, RTF |
| Spreadsheets | XLSX, XLS, CSV |
| Images | JPEG, PNG, GIF, WebP |
| Archives | ZIP, TAR, GZ |
| Code | PY, JS, TS, JSON, XML, HTML |

### Image Compression

Images are automatically compressed to:
- Max dimensions: 2048x2048 pixels
- JPEG quality: 85%
- Format conversion as needed

### Content Extraction

The API automatically extracts text content from:
- **PDF**: All text and OCR for scanned pages
- **Word/DOCX**: Paragraphs and tables
- **Excel/XLSX**: All sheets with headers
- **Text files**: Direct content

### Storage

Files are stored using the configured storage backend:
- **Local**: `./uploads/staged-files/` (development)
- **S3**: Configurable S3-compatible bucket (production)

### Expiration

Staged files expire after 24 hours by default. Configure via:
```env
FILE_STAGED_EXPIRY_HOURS=24
```

---

## Configuration

Key environment variables for file processing:

```env
# Storage Backend
FILE_STORAGE_BACKEND=local  # or 's3'
FILE_STORAGE_LOCAL_PATH=./uploads/staged-files

# Limits
FILE_MAX_SIZE_MB=50
FILE_MAX_PARSED_CONTENT_LENGTH=100000

# Image Processing
FILE_IMAGE_MAX_WIDTH=2048
FILE_IMAGE_MAX_HEIGHT=2048
FILE_IMAGE_JPEG_QUALITY=85
```

---

## Integration with Chat

To attach a staged file to a chat message:

1. Upload the file via `/agent/files/upload`
2. Get the `file_id` from the response
3. Include the `file_id` in your chat request:

```json
{
  "thread_id": "thread_123",
  "message": "Analyze this document",
  "file_ids": ["abc123..."]
}
```

The agent will receive the parsed content automatically.
