# File Processing System Guide

This guide covers the design and usage of the file processing system for handling file attachments in chat conversations.

---

## Overview

The file processing system provides:

1. **FastParse Module** - Multi-format document parsing
2. **Storage Backends** - Local and S3-compatible storage
3. **Image Processing** - Compression and optimization
4. **Staged Files API** - REST endpoints for file management

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Files API                                │
│                    /api/v1/agent/files/*                         │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  FastParse    │       │   Storage     │       │ Image Utils   │
│   Module      │       │   Backend     │       │               │
├───────────────┤       ├───────────────┤       ├───────────────┤
│ - PDF         │       │ - Local       │       │ - Compress    │
│ - Word        │       │ - S3/MinIO    │       │ - Resize      │
│ - Excel       │       │               │       │ - Thumbnail   │
│ - PowerPoint  │       │               │       │               │
│ - Text/Code   │       │               │       │               │
│ - Images      │       │               │       │               │
└───────────────┘       └───────────────┘       └───────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │      PostgreSQL Database       │
                │     agent_staged_files        │
                └───────────────────────────────┘
```

---

## FastParse Module

Location: `backend/src/services/file_processing/fast_parse/`

### Features

- **PDF Parsing** - Text extraction via PyPDF2
- **Word Documents** - python-docx for paragraphs, tables
- **Excel Spreadsheets** - openpyxl for all sheets
- **PowerPoint** - python-pptx for slide text
- **Text/Code Files** - Encoding detection with chardet
- **Images** - Metadata extraction with Pillow

### Usage

```python
from backend.src.services.file_processing import parse

result = parse(file_bytes, "report.pdf", "application/pdf")

if result.success:
    print(f"Type: {result.file_type}")
    print(f"Content: {result.content[:500]}")
    print(f"Metadata: {result.metadata}")
else:
    print(f"Error: {result.error}")
```

### Configuration

```python
from backend.src.services.file_processing.fast_parse import FastParseConfig

config = FastParseConfig(
    max_file_size_bytes=50 * 1024 * 1024,  # 50MB
    max_pdf_pages=500,
    max_excel_rows=100000,
    max_chars=10_000_000,
)
```

---

## Storage Backends

Location: `backend/src/services/file_processing/storage.py`

### Local Storage

```python
from backend.src.services.file_processing.storage import LocalFileStorage

storage = LocalFileStorage(
    base_path="./uploads/staged-files",
    base_url="/static/files"  # Optional
)

# Upload
path = await storage.upload(
    user_id="123",
    file_id="abc-def",
    content=file_bytes,
    filename="report.pdf",
    mime_type="application/pdf"
)

# Download
content = await storage.download(path)

# Delete
await storage.delete(path)
```

### S3 Storage

```python
from backend.src.services.file_processing.storage import S3FileStorage

storage = S3FileStorage(
    bucket="staged-files",
    endpoint_url="http://localhost:9000",  # MinIO
    region="us-east-1",
    access_key="minioadmin",
    secret_key="minioadmin",
)
```

---

## Image Processing

Location: `backend/src/services/file_processing/image_utils.py`

```python
from backend.src.services.file_processing import compress_image

# Compress and resize
compressed, mime = compress_image(
    image_bytes,
    mime_type="image/jpeg",
    max_width=2048,
    max_height=2048,
    quality=85
)
```

---

## Database Model

Location: `backend/app/agent/model/staged_file.py`

```python
class StagedFile(Base):
    __tablename__ = 'agent_staged_files'
    
    id: Mapped[id_key]
    file_id: Mapped[str]       # Unique identifier
    user_id: Mapped[int]       # Owner
    thread_id: Mapped[str]     # Thread association
    filename: Mapped[str]      # Original name
    storage_path: Mapped[str]  # Storage location
    mime_type: Mapped[str]     # MIME type
    file_size: Mapped[int]     # Size in bytes
    parsed_content: Mapped[str] # Extracted text
    parse_status: Mapped[str]  # pending/completed/failed
    image_url: Mapped[str]     # Compressed image path
    file_metadata: Mapped[dict] # JSON metadata
    expires_at: Mapped[datetime] # Expiration
```

---

## Security Features

1. **File Size Limits** - Configurable max size (default 50MB)
2. **Path Sanitization** - Prevents directory traversal
3. **Script Detection** - Warns on potential script injection
4. **User Isolation** - Files are scoped to user ID
5. **Expiration** - Auto-cleanup of old files

---

## Error Handling

```python
from backend.src.services.file_processing.fast_parse.exceptions import (
    FileSizeExceededError,
    UnsupportedFormatError,
    CorruptedFileError,
    EncodingError,
)

try:
    result = parse(content, filename, mime_type)
except FileSizeExceededError as e:
    print(f"File too large: {e.size_limit}")
except UnsupportedFormatError as e:
    print(f"Unsupported: {e.extension}")
except CorruptedFileError as e:
    print(f"Corrupted: {e}")
```

---

## Related Documentation

- [API Reference](../api-contracts/file-processing.md)
- [Environment Variables](environment-variables.md)
- [Sandbox Guide](sandbox-guide.md)
