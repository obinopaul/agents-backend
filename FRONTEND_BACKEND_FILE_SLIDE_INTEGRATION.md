# Frontend-Backend Integration: File System, Upload API & Slide Management

**Document Version:** 1.0
**Last Updated:** January 24, 2026
**Systems Covered:** File Operations, File Upload, Slide Generation & Management

---

## Table of Contents

### Part 1: Architecture Overview
1.1. System Overview
1.2. Technology Stack
1.3. Integration Architecture
1.4. Communication Patterns
1.5. Storage Infrastructure

### Part 2: File System API
2.1. Frontend File Service
2.2. Backend File Routes
2.3. File Operations (List, Read, Save, Create, Delete, Rename, Move, Copy)
2.4. Database Schema for Files
2.5. Complete File Operation Flows

### Part 3: Upload API System
3.1. Upload Service Architecture
3.2. Signed URL Upload Flow (3-Step Process)
3.3. Frontend Upload Hook
3.4. Backend Upload Endpoints
3.5. Direct-to-Cloud Upload
3.6. Upload Progress Tracking
3.7. Multi-File Upload Support
3.8. File Size Validation & Limits

### Part 4: Storage Abstraction Layer
4.1. BaseStorage Interface
4.2. Google Cloud Storage Implementation
4.3. Local Storage Implementation
4.4. Storage Factory Pattern
4.5. Signed URL Generation
4.6. File Streaming & Download

### Part 5: File-Chat Integration
5.1. File Attachments in Messages
5.2. File Association with Sessions
5.3. LLM Provider File Upload
5.4. Chat File Download
5.5. File State Management (Redux)

### Part 6: Slide Management System
6.1. Slide System Architecture
6.2. Slide API Endpoints
6.3. Slide Generation Tools (SlideWrite, SlideEdit, SlideApplyPatch)
6.4. Template System
6.5. AI-Powered Slide Generation

### Part 7: Slide Templates
7.1. Template Database Schema
7.2. Template API Endpoints
7.3. Template Selection UI
7.4. Template Injection into Agent Prompt
7.5. Template Processing Rules

### Part 8: Slide PDF Generation
8.1. PDF Service Architecture (Playwright)
8.2. PDF Generation Flow
8.3. Server-Sent Events Progress Tracking
8.4. PDF Download Endpoints
8.5. Multi-Slide PDF Merging

### Part 9: Slide Content Processing
9.1. Content Hook System
9.2. File URL Replacement
9.3. Cloud Asset Upload
9.4. Content Deduplication
9.5. Database Persistence

### Part 10: UI Components
10.1. File Upload Components
10.2. File Preview Components
10.3. Slide Template Selector
10.4. Slide Viewer & Editor
10.5. PDF Download UI

### Part 11: Error Handling & Security
11.1. File Upload Errors
11.2. Storage Access Control
11.3. Session Ownership Validation
11.4. File Size Limits
11.5. Signed URL Security

### Part 12: Complete Integration Flows
12.1. End-to-End File Upload Flow
12.2. End-to-End File Download Flow
12.3. End-to-End Slide Generation Flow
12.4. End-to-End PDF Export Flow

### Part 13: Code Examples & Reference
13.1. Frontend API Usage Examples
13.2. Backend Service Examples
13.3. Storage Integration Examples
13.4. Common Patterns

### Part 14: Configuration & Deployment
14.1. Environment Variables
14.2. Storage Configuration
14.3. Database Setup
14.4. Playwright Setup for PDF Generation

### Part 15: Debugging & Troubleshooting
15.1. File Upload Issues
15.2. Storage Connection Problems
15.3. Slide Generation Failures
15.4. PDF Export Errors
15.5. Common Error Messages

---

## Part 1: Architecture Overview

### 1.1 System Overview

The II-Agent platform implements three tightly integrated systems for content management:

**1. File System API** - Manages file operations within the sandbox/workspace environment
- File listing and navigation
- File content reading and modification
- File/folder creation and deletion
- File search capabilities

**2. Upload API** - Handles user file uploads to cloud storage
- Signed URL-based direct uploads to GCS/S3
- Multi-file upload support with progress tracking
- File association with chat sessions
- Integration with LLM providers for RAG

**3. Slide Management System** - AI-powered presentation creation and export
- Template-based slide generation
- AI agent tools for slide creation/editing
- Real-time slide previewing
- PDF export with progress tracking

### 1.2 Technology Stack

**Frontend:**
- **Framework:** React 18 with TypeScript
- **State Management:** Redux Toolkit
- **HTTP Client:** Axios for REST, native fetch() for SSE
- **File Upload:** XMLHttpRequest for progress tracking
- **UI:** Tailwind CSS, Radix UI components

**Backend:**
- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy with async support
- **Database:** PostgreSQL 14+
- **Storage:** Google Cloud Storage / AWS S3 / Local filesystem
- **PDF Generation:** Playwright (headless Chromium) + pypdf

**Cloud Infrastructure:**
- **Storage Providers:** GCS, S3, Local
- **Signed URLs:** Pre-signed PUT/GET URLs (3600s expiry)
- **CDN:** Custom domain support for permanent URLs
- **Streaming:** Server-Sent Events (SSE) for progress updates

### 1.3 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
├─────────────────────────────────────────────────────────────────┤
│  Components                                                      │
│  ├─ QuestionFileUpload (upload UI)                             │
│  ├─ QuestionFilesPreview (file preview)                        │
│  ├─ SlideTemplateSelector (template selection)                 │
│  ├─ SlidesViewer (slide rendering)                             │
│  └─ SlidesResult (PDF export UI)                               │
│                                                                  │
│  Services (API Clients)                                         │
│  ├─ fileService (file operations)                              │
│  ├─ uploadService (file upload/download)                       │
│  ├─ slideService (slide management)                            │
│  └─ chatService (file attachments)                             │
│                                                                  │
│  State Management (Redux)                                       │
│  ├─ files slice (uploaded files, content cache)                │
│  └─ agent slice (slide templates)                              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/HTTPS + SSE
                            │
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
├─────────────────────────────────────────────────────────────────┤
│  API Routes (FastAPI)                                           │
│  ├─ /api/files/* (file system operations)                      │
│  ├─ /chat/generate-upload-url (signed URL)                     │
│  ├─ /chat/upload-complete (finalize upload)                    │
│  ├─ /chat/:sessionId/files/:fileId (download)                  │
│  ├─ /slides (CRUD operations)                                  │
│  ├─ /slides/download (PDF export)                              │
│  ├─ /slides/download/stream (SSE progress)                     │
│  └─ /slide-templates (template management)                     │
│                                                                  │
│  Service Layer                                                  │
│  ├─ FileService (file operations)                              │
│  ├─ SlideService (slide CRUD)                                  │
│  ├─ PDFService (Playwright PDF generation)                     │
│  ├─ TemplateService (template management)                      │
│  └─ ContentProcessor (URL replacement)                         │
│                                                                  │
│  Storage Abstraction                                            │
│  ├─ BaseStorage (interface)                                    │
│  ├─ GCS (Google Cloud Storage)                                 │
│  ├─ S3 (AWS S3)                                                 │
│  └─ LocalStorage (development)                                 │
│                                                                  │
│  Database (PostgreSQL)                                          │
│  ├─ file_uploads (file metadata)                               │
│  ├─ slide_contents (slide data)                                │
│  └─ slide_templates (template definitions)                     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Direct Upload (Signed URL)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUD STORAGE                                 │
├─────────────────────────────────────────────────────────────────┤
│  Google Cloud Storage / AWS S3 / Local Filesystem              │
│  ├─ users/{user_id}/uploads/{file_id}-{filename}              │
│  ├─ users/{user_id}/profile/avatar.{ext}                      │
│  └─ slides/assets/{md5_hash}{extension}                       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Communication Patterns

**Pattern 1: Standard REST API**
- File System Operations (list, read, save, delete)
- Slide CRUD operations
- Template retrieval

**Pattern 2: Signed URL Upload (3-Step)**
1. Frontend requests signed URL from backend
2. Frontend uploads file directly to cloud storage
3. Frontend notifies backend of completion

**Pattern 3: Server-Sent Events (SSE)**
- PDF generation progress updates
- Real-time status streaming
- One-way server → client

**Pattern 4: Streaming Response**
- File downloads with chunking (64KB)
- Large PDF downloads
- Memory-efficient delivery

### 1.5 Storage Infrastructure

**Storage Paths:**

| Content Type | Path Pattern | Example |
|-------------|--------------|---------|
| User Uploads | `users/{user_id}/uploads/{file_id}-{filename}` | `users/abc123/uploads/def456-document.pdf` |
| Avatars | `users/{user_id}/profile/avatar.{ext}` | `users/abc123/profile/avatar.jpg` |
| Slide Assets | `slides/assets/{md5_hash}{extension}` | `slides/assets/a1b2c3d4.png` |

**URL Types:**

| Type | Expiry | Use Case |
|------|--------|----------|
| Signed Upload URL | 3600s (1 hour) | Direct file upload to storage |
| Signed Download URL | 3600s (1 hour) | Temporary file access |
| Permanent URL | None | Public CDN-served content |
| Public URL | None | Publicly readable content |

**Storage Providers:**

| Provider | Configuration | Use Case |
|----------|--------------|----------|
| Google Cloud Storage (GCS) | Project ID + Bucket Name | Production deployments |
| AWS S3 | Bucket Name + Region | Alternative cloud storage |
| Local Filesystem | Base path | Development/testing |

---

## Part 2: File System API

### 2.1 Frontend File Service

**File:** `frontend/src/services/file.service.ts`

The File Service handles file system operations within the sandbox/workspace environment, providing methods for file management separate from user uploads.

#### 2.1.1 Type Definitions

**File:** `frontend/src/typings/file.ts`

```typescript
interface FileStructure {
    name: string
    type: 'file' | 'folder'
    children?: FileStructure[]
    language?: string
    content?: string
    path: string
    size?: number
    lastModified?: number
}

interface FileListResponse {
    files: FileStructure[]
}

interface FileContentResponse {
    content: string
    path: string
    language?: string
}

interface FileSaveRequest {
    path: string
    content: string
}

interface FileCreateRequest {
    path: string
    content?: string
    type: 'file' | 'folder'
}

interface FileDeleteRequest {
    path: string
}

interface FileRenameRequest {
    oldPath: string
    newPath: string
}

interface FileMoveRequest {
    sourcePath: string
    destinationPath: string
}

interface FileCopyRequest {
    sourcePath: string
    destinationPath: string
}

interface FileSearchRequest {
    query: string
    path?: string
}

interface FileSearchResponse {
    results: {
        path: string
        matches: number
        snippets: string[]
    }[]
}
```

#### 2.1.2 API Methods

```typescript
class FileService {
    private baseURL: string

    constructor() {
        this.baseURL = axiosInstance.defaults.baseURL ||
                       import.meta.env.VITE_API_URL ||
                       'http://localhost:9000'
    }

    /**
     * List files and directories in a path
     * POST /api/files
     */
    async listFiles(path?: string): Promise<FileListResponse> {
        const response = await axiosInstance.post<FileListResponse>(
            '/api/files',
            { path: path || '/' }
        )
        return response.data
    }

    /**
     * Get file content
     * POST /api/files/content
     */
    async getFileContent(path: string): Promise<FileContentResponse> {
        const response = await axiosInstance.post<FileContentResponse>(
            '/api/files/content',
            { path }
        )
        return response.data
    }

    /**
     * Save file content
     * POST /api/files/save
     */
    async saveFile(data: FileSaveRequest): Promise<{ success: boolean }> {
        const response = await axiosInstance.post(
            '/api/files/save',
            data
        )
        return response.data
    }

    /**
     * Create new file or folder
     * POST /api/files/create
     */
    async createFile(data: FileCreateRequest): Promise<{ success: boolean, path: string }> {
        const response = await axiosInstance.post(
            '/api/files/create',
            data
        )
        return response.data
    }

    /**
     * Create new folder
     * POST /api/files/create-folder
     */
    async createFolder(path: string): Promise<{ success: boolean }> {
        const response = await axiosInstance.post(
            '/api/files/create-folder',
            { path }
        )
        return response.data
    }

    /**
     * Delete file or folder
     * DELETE /api/files
     */
    async deleteFile(data: FileDeleteRequest): Promise<{ success: boolean }> {
        const response = await axiosInstance.delete(
            '/api/files',
            { data }
        )
        return response.data
    }

    /**
     * Rename file or folder
     * POST /api/files/rename
     */
    async renameFile(data: FileRenameRequest): Promise<{ success: boolean }> {
        const response = await axiosInstance.post(
            '/api/files/rename',
            data
        )
        return response.data
    }

    /**
     * Move file or folder
     * POST /api/files/move
     */
    async moveFile(data: FileMoveRequest): Promise<{ success: boolean }> {
        const response = await axiosInstance.post(
            '/api/files/move',
            data
        )
        return response.data
    }

    /**
     * Copy file or folder
     * POST /api/files/copy
     */
    async copyFile(data: FileCopyRequest): Promise<{ success: boolean }> {
        const response = await axiosInstance.post(
            '/api/files/copy',
            data
        )
        return response.data
    }

    /**
     * Search files
     * POST /api/files/search
     */
    async searchFiles(data: FileSearchRequest): Promise<FileSearchResponse> {
        const response = await axiosInstance.post<FileSearchResponse>(
            '/api/files/search',
            data
        )
        return response.data
    }
}

export const fileService = new FileService()
```

### 2.2 Backend File Routes

**File:** `src/ii_agent/server/api/files.py`

The backend File API provides workspace/sandbox file management capabilities through FastAPI endpoints.

**Router Configuration:**
```python
router = APIRouter(prefix="/api/files", tags=["files"])
```

#### 2.2.1 List Files Endpoint

**Endpoint:** `POST /api/files`

**Purpose:** List files and directories in a workspace path

**Request:**
```python
class FileListRequest(BaseModel):
    path: str = Field(default="/", description="Path to list files from")
```

**Response:**
```python
class FileStructure(BaseModel):
    name: str
    type: Literal["file", "folder"]
    children: Optional[List["FileStructure"]] = None
    language: Optional[str] = None
    content: Optional[str] = None
    path: str
    size: Optional[int] = None
    last_modified: Optional[float] = None

class FileListResponse(BaseModel):
    files: List[FileStructure]
```

**Handler Implementation:**
```python
@router.post("/", response_model=FileListResponse)
async def list_files(
    request: FileListRequest,
    current_user: CurrentUser,
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager)
):
    """
    List files in workspace directory.

    Returns hierarchical file structure with metadata.
    """
    workspace_path = workspace_manager.get_workspace_path()
    target_path = Path(workspace_path) / request.path.lstrip("/")

    # Security: Prevent path traversal
    if not str(target_path.resolve()).startswith(str(workspace_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    def build_tree(path: Path) -> FileStructure:
        is_dir = path.is_dir()
        rel_path = str(path.relative_to(workspace_path))

        node = FileStructure(
            name=path.name,
            type="folder" if is_dir else "file",
            path=rel_path,
            size=None if is_dir else path.stat().st_size,
            last_modified=path.stat().st_mtime
        )

        if is_dir:
            children = []
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                children.append(build_tree(item))
            node.children = children
        else:
            # Detect language from extension
            ext = path.suffix.lstrip(".")
            language_map = {
                "py": "python", "js": "javascript", "ts": "typescript",
                "java": "java", "cpp": "cpp", "c": "c",
                "html": "html", "css": "css", "json": "json",
                "md": "markdown", "yaml": "yaml", "yml": "yaml"
            }
            node.language = language_map.get(ext, "text")

        return node

    file_tree = build_tree(target_path)
    return FileListResponse(files=[file_tree])
```

**Wire Format Example:**
```json
{
    "files": [
        {
            "name": "project",
            "type": "folder",
            "path": "project",
            "size": null,
            "last_modified": 1706102400.123,
            "children": [
                {
                    "name": "main.py",
                    "type": "file",
                    "path": "project/main.py",
                    "size": 2048,
                    "last_modified": 1706102500.456,
                    "language": "python",
                    "children": null
                },
                {
                    "name": "utils",
                    "type": "folder",
                    "path": "project/utils",
                    "children": [...]
                }
            ]
        }
    ]
}
```

#### 2.2.2 Get File Content Endpoint

**Endpoint:** `POST /api/files/content`

**Purpose:** Retrieve content of a specific file

**Request:**
```python
class FileContentRequest(BaseModel):
    path: str
```

**Response:**
```python
class FileContentResponse(BaseModel):
    content: str
    path: str
    language: Optional[str] = None
```

**Handler Implementation:**
```python
@router.post("/content", response_model=FileContentResponse)
async def get_file_content(
    request: FileContentRequest,
    current_user: CurrentUser,
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager)
):
    """
    Get content of a file from workspace.
    """
    workspace_path = workspace_manager.get_workspace_path()
    file_path = Path(workspace_path) / request.path.lstrip("/")

    # Security validation
    if not str(file_path.resolve()).startswith(str(workspace_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not text-readable")

    ext = file_path.suffix.lstrip(".")
    language_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "java": "java", "cpp": "cpp", "html": "html", "css": "css"
    }
    language = language_map.get(ext, "text")

    return FileContentResponse(
        content=content,
        path=request.path,
        language=language
    )
```

**Wire Format Example:**
```json
{
    "content": "def hello():\n    print('Hello, world!')\n",
    "path": "project/main.py",
    "language": "python"
}
```

---

