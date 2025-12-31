# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Staged Files API - File upload, staging, and management endpoints.

This API allows users to:
- Upload files for later attachment to chat messages
- Parse and extract text from documents
- Compress and optimize images
- List, retrieve, and delete staged files

Adapted from SUNA project's staged_files_api.py.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.model.staged_file import StagedFile
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, get_db
from backend.src.services.file_processing import (
    compress_image,
    is_image_mime,
    parse,
    format_file_size,
    sanitize_filename_for_path,
)
from backend.src.services.file_processing.storage import (
    get_storage_backend,
    LocalFileStorage,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple test endpoint
@router.get("/test")
async def test_files_router():
    """Simple test endpoint to verify files router is working."""
    return {"status": "files router works!"}

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_PARSED_CONTENT_LENGTH = 100_000  # 100K chars stored in DB
STAGED_FILE_EXPIRY_HOURS = 24
SIGNED_URL_EXPIRY = 3600  # 1 hour


def sanitize_for_postgres(text: Optional[str]) -> Optional[str]:
    """Remove null bytes that would cause PostgreSQL errors."""
    if text is None:
        return None
    return text.replace('\x00', '')


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class StagedFileResponse(BaseModel):
    """Response for a single staged file."""
    file_id: str
    filename: str
    storage_path: str
    mime_type: str
    file_size: int
    parsed_preview: Optional[str] = None
    image_url: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class StagedFilesListResponse(BaseModel):
    """Response for listing staged files."""
    files: List[StagedFileResponse]
    total: int = 0


class FileDeleteResponse(BaseModel):
    """Response for file deletion."""
    status: str
    file_id: str


class FileContentResponse(BaseModel):
    """Response with file content for chat integration."""
    file_id: str
    filename: str
    mime_type: str
    file_size: int
    parsed_content: Optional[str] = None
    image_url: Optional[str] = None
    is_image: bool = False


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_current_user_id(request_user=DependsJwtAuth) -> int:
    """Extract user ID from JWT token."""
    return request_user.id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=StagedFileResponse, summary="Upload and stage a file", dependencies=[DependsJwtAuth])
async def upload_staged_file(
    request: Request,
    file: UploadFile = File(..., description="File to upload"),
    file_id: Optional[str] = Form(None, description="Optional custom file ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and stage a file for later attachment to chat messages.
    
    This endpoint:
    1. Validates file size and type
    2. Parses document content (PDF, Word, Excel, etc.)
    3. Compresses images if needed
    4. Stores the file in the configured storage backend
    5. Saves metadata to the database
    
    The file is staged and ready for attachment via file_id.
    """
    user_id = request.user.id
    
    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({format_file_size(file_size)}) exceeds limit ({format_file_size(MAX_FILE_SIZE)})"
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file not allowed")
    
    # Generate file ID
    generated_file_id = file_id or str(uuid.uuid4())
    original_filename = file.filename.replace('/', '_').replace('\\', '_')
    storage_safe_filename = sanitize_filename_for_path(file.filename)
    mime_type = file.content_type or "application/octet-stream"
    
    # Get storage backend
    storage = get_storage_backend()
    
    # Storage path and image URL
    storage_path = None
    image_storage_path = None
    parsed_content = None
    parsed_preview = None
    parse_status = "pending"
    metadata = {}
    
    try:
        # Upload original file
        storage_path = await storage.upload(
            user_id=str(user_id),
            file_id=generated_file_id,
            content=content,
            filename=storage_safe_filename,
            mime_type=mime_type,
        )
        logger.debug(f"Uploaded file to storage: {storage_path}")
        
        # Parse file content (async in executor for CPU-bound work)
        loop = asyncio.get_event_loop()
        parse_result = await loop.run_in_executor(
            None,
            lambda: parse(content, original_filename, mime_type)
        )
        
        if parse_result.success:
            metadata = parse_result.metadata
            
            if parse_result.file_type.name != "IMAGE":
                # Store extracted text
                full_content = parse_result.content
                if full_content:
                    # Truncate for database storage
                    parsed_content = sanitize_for_postgres(
                        full_content[:MAX_PARSED_CONTENT_LENGTH]
                    )
                    # Generate preview
                    parsed_preview = parsed_content[:5000] if parsed_content else None
                    parse_status = "completed"
                    
                    logger.info(
                        f"✅ Parsed {original_filename}: {len(full_content):,} chars extracted"
                    )
            else:
                # Image file
                parse_status = "completed"
                logger.info(f"📷 Image file: {original_filename}")
        else:
            parse_status = "failed"
            logger.warning(f"⚠️ Parse failed for {original_filename}: {parse_result.error}")
        
        # Compress and store image if applicable
        if is_image_mime(mime_type):
            try:
                compressed_bytes, compressed_mime = await loop.run_in_executor(
                    None,
                    lambda: compress_image(content, mime_type)
                )
                
                # Determine extension
                ext_map = {
                    'image/jpeg': 'jpg',
                    'image/png': 'png',
                    'image/gif': 'gif',
                    'image/webp': 'webp'
                }
                ext = ext_map.get(compressed_mime, 'jpg')
                
                # Upload compressed version
                image_storage_path = await storage.upload(
                    user_id=str(user_id),
                    file_id=generated_file_id,
                    content=compressed_bytes,
                    filename=f"compressed.{ext}",
                    mime_type=compressed_mime,
                )
                
                logger.info(f"📷 Stored compressed image: {image_storage_path}")
                parse_status = "completed"
                
            except Exception as e:
                logger.warning(f"Failed to compress/store image: {e}")
        
        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(hours=STAGED_FILE_EXPIRY_HOURS)
        
        # Create database record
        staged_file = StagedFile(
            file_id=generated_file_id,
            user_id=user_id,
            filename=original_filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            parsed_content=parsed_content,
            parse_status=parse_status,
            image_url=image_storage_path,
            file_metadata=metadata,
            expires_at=expires_at,
        )
        
        db.add(staged_file)
        await db.commit()
        await db.refresh(staged_file)
        
        logger.info(
            f"✅ Staged file {generated_file_id}: {original_filename} "
            f"({format_file_size(file_size)})"
        )
        
        return StagedFileResponse(
            file_id=generated_file_id,
            filename=original_filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            parsed_preview=parsed_preview,
            image_url=image_storage_path,
            status="ready" if parse_status == "completed" else parse_status,
            created_at=staged_file.created_at.isoformat() if staged_file.created_at else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to stage file: {e}")
        # Cleanup storage on failure
        if storage_path:
            try:
                await storage.delete(storage_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to stage file: {str(e)}")


@router.get("/staged", response_model=StagedFilesListResponse, summary="List staged files", dependencies=[DependsJwtAuth])
async def list_staged_files(
    request: Request,
    thread_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all staged files for the current user.
    
    If thread_id is not provided, returns files not yet attached to any thread.
    """
    user_id = request.user.id
    
    # Build query
    conditions = [StagedFile.user_id == user_id]
    
    if thread_id:
        conditions.append(StagedFile.thread_id == thread_id)
    else:
        conditions.append(StagedFile.thread_id.is_(None))
    
    query = select(StagedFile).where(and_(*conditions)).order_by(StagedFile.created_at.desc())
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    response_files = [
        StagedFileResponse(
            file_id=f.file_id,
            filename=f.filename,
            storage_path=f.storage_path,
            mime_type=f.mime_type,
            file_size=f.file_size,
            parsed_preview=f.parsed_content[:500] if f.parsed_content else None,
            image_url=f.image_url,
            status="ready" if f.parse_status == "completed" else f.parse_status,
            created_at=f.created_at.isoformat() if f.created_at else None,
        )
        for f in files
    ]
    
    return StagedFilesListResponse(files=response_files, total=len(response_files))


@router.get("/{file_id}", response_model=StagedFileResponse, summary="Get staged file info", dependencies=[DependsJwtAuth])
async def get_staged_file(
    request: Request,
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get information about a specific staged file."""
    user_id = request.user.id
    
    query = select(StagedFile).where(
        and_(
            StagedFile.file_id == file_id,
            StagedFile.user_id == user_id,
        )
    )
    
    result = await db.execute(query)
    staged_file = result.scalar_one_or_none()
    
    if not staged_file:
        raise HTTPException(status_code=404, detail="Staged file not found")
    
    return StagedFileResponse(
        file_id=staged_file.file_id,
        filename=staged_file.filename,
        storage_path=staged_file.storage_path,
        mime_type=staged_file.mime_type,
        file_size=staged_file.file_size,
        parsed_preview=staged_file.parsed_content[:500] if staged_file.parsed_content else None,
        image_url=staged_file.image_url,
        status="ready" if staged_file.parse_status == "completed" else staged_file.parse_status,
        created_at=staged_file.created_at.isoformat() if staged_file.created_at else None,
    )


@router.delete("/{file_id}", response_model=FileDeleteResponse, summary="Delete staged file", dependencies=[DependsJwtAuth])
async def delete_staged_file(
    request: Request,
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a staged file from storage and database."""
    user_id = request.user.id
    
    query = select(StagedFile).where(
        and_(
            StagedFile.file_id == file_id,
            StagedFile.user_id == user_id,
        )
    )
    
    result = await db.execute(query)
    staged_file = result.scalar_one_or_none()
    
    if not staged_file:
        raise HTTPException(status_code=404, detail="Staged file not found")
    
    storage = get_storage_backend()
    
    # Delete from storage
    try:
        await storage.delete(staged_file.storage_path)
        if staged_file.image_url:
            await storage.delete(staged_file.image_url)
    except Exception as e:
        logger.warning(f"Failed to delete file from storage: {e}")
    
    # Delete from database
    await db.delete(staged_file)
    await db.commit()
    
    logger.info(f"🗑️ Deleted staged file {file_id}")
    
    return FileDeleteResponse(status="deleted", file_id=file_id)


# ---------------------------------------------------------------------------
# Helper Functions for Chat/Agent Integration
# ---------------------------------------------------------------------------

async def get_staged_files_for_thread(
    file_ids: List[str],
    user_id: int,
    thread_id: str,
    db: AsyncSession,
) -> List[FileContentResponse]:
    """
    Retrieve staged files for inclusion in a chat thread.
    
    This function is called by the chat/agent endpoints to fetch
    file content for messages with file attachments.
    
    Args:
        file_ids: List of file IDs to retrieve
        user_id: User ID for authorization
        thread_id: Thread ID to associate files with
        db: Database session
        
    Returns:
        List of FileContentResponse objects with content
    """
    if not file_ids:
        return []
    
    logger.info(f"📎 Retrieving {len(file_ids)} staged files for thread {thread_id}")
    
    query = select(StagedFile).where(
        and_(
            StagedFile.user_id == user_id,
            StagedFile.file_id.in_(file_ids),
        )
    )
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    if not files:
        logger.warning(f"⚠️ No staged files found for file_ids: {file_ids}")
        return []
    
    storage = get_storage_backend()
    responses = []
    
    for f in files:
        # Generate signed URL for images if storage supports it
        image_url = None
        if f.image_url:
            image_url = await storage.get_url(f.image_url, SIGNED_URL_EXPIRY)
            if not image_url:
                image_url = f.image_url  # Fallback to raw path
        
        responses.append(FileContentResponse(
            file_id=f.file_id,
            filename=f.filename,
            mime_type=f.mime_type,
            file_size=f.file_size,
            parsed_content=f.parsed_content,
            image_url=image_url,
            is_image=f.is_image,
        ))
        
        # Associate file with thread (if not already)
        if f.thread_id != thread_id:
            f.thread_id = thread_id
    
    await db.commit()
    
    total_parsed = sum(len(f.parsed_content or '') for f in responses)
    total_images = sum(1 for f in responses if f.is_image)
    logger.info(
        f"✅ Retrieved {len(responses)} files: "
        f"{total_parsed:,} chars parsed, {total_images} images"
    )
    
    return responses


async def get_staged_file_content(
    file_id: str,
    user_id: int,
    db: AsyncSession,
) -> Optional[bytes]:
    """
    Download the actual file content for a staged file.
    
    Args:
        file_id: File ID
        user_id: User ID for authorization
        db: Database session
        
    Returns:
        File bytes or None if not found
    """
    query = select(StagedFile).where(
        and_(
            StagedFile.file_id == file_id,
            StagedFile.user_id == user_id,
        )
    )
    
    result = await db.execute(query)
    staged_file = result.scalar_one_or_none()
    
    if not staged_file:
        return None
    
    storage = get_storage_backend()
    return await storage.download(staged_file.storage_path)
