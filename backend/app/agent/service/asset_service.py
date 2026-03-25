
import asyncio
import logging
import uuid
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.model.staged_file import StagedFile
from backend.src.services.file_processing import (
    compress_image,
    is_image_mime,
    sanitize_filename_for_path,
)
from backend.src.services.file_processing.storage import get_storage_backend

logger = logging.getLogger(__name__)

STAGED_FILE_EXPIRY_HOURS = 24

async def process_and_stage_asset(
    user_id: str,
    content: bytes,
    mime_type: str,
    filename: str,
    db: AsyncSession,
    thread_id: Optional[str] = None,
) -> Tuple[str, Optional[StagedFile]]:
    """
    Process raw asset content (resize images), uploads to storage, and stages it.
    
    Returns:
        Tuple[str, Optional[StagedFile]]: (public_url, staged_file_record)
    """
    storage = get_storage_backend()
    file_id = str(uuid.uuid4())
    storage_safe_filename = sanitize_filename_for_path(filename)
    
    # Defaults
    storage_path = None
    image_storage_path = None
    parse_status = "pending"
    
    try:
        # Compress if image
        if is_image_mime(mime_type):
            loop = asyncio.get_event_loop()
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
                
                # Upload compressed version (prefer compressed for serving)
                filename = f"tool_result_{file_id[:8]}.{ext}"
                mime_type = compressed_mime
                content = compressed_bytes
                
                logger.debug(f"Compressed image asset: {len(content)} bytes")
                parse_status = "completed"
            except Exception as e:
                logger.warning(f"Failed to compress asset image: {e}")
                # Proceed with original content

        # Upload
        storage_path = await storage.upload(
            user_id=str(user_id),
            file_id=file_id,
            content=content,
            filename=filename,
            mime_type=mime_type,
        )
        
        # Determine URL
        # For S3, get_url returns the presigned or public URL
        url = await storage.get_url(storage_path)
        
        # Stage in DB
        expires_at = datetime.now(timezone.utc) + timedelta(hours=STAGED_FILE_EXPIRY_HOURS)
        
        staged_file = StagedFile(
            file_id=file_id,
            user_id=user_id,
            thread_id=thread_id,
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=len(content),
            parse_status=parse_status,
            image_url=storage_path if is_image_mime(mime_type) else None,
            expires_at=expires_at,
        )
        
        db.add(staged_file)
        # Note: We rely on caller to commit if they want atomic transaction, 
        # or we commit here. Since this is often in a loop/stream, we should probably commit/flush here 
        # to ensure ID is valid if used immediately.
        # But caller (chat loop) controls the transaction. 
        # Ideally, we flush.
        await db.flush()
        
        return url, staged_file

    except Exception as e:
        logger.exception(f"Failed to process and stage asset: {e}")
        raise
