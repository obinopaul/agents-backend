# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
File Storage Backends.

Provides abstract storage interface and implementations:
- LocalFileStorage: Filesystem-based storage
- S3FileStorage: S3-compatible storage (AWS S3, MinIO, etc.)

Usage:
    from backend.src.services.file_processing.storage import get_storage_backend
    
    storage = get_storage_backend()  # Uses config to determine backend
    path = await storage.upload(user_id, file_id, content, filename, mime_type)
"""

import asyncio
import hashlib
import logging
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import aiofiles

logger = logging.getLogger(__name__)


class FileStorageBackend(ABC):
    """
    Abstract base class for file storage backends.
    
    All storage backends must implement these methods.
    """
    
    @abstractmethod
    async def upload(
        self,
        user_id: str,
        file_id: str,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> str:
        """
        Upload a file to storage.
        
        Args:
            user_id: User identifier
            file_id: Unique file identifier
            content: File content bytes
            filename: Original filename
            mime_type: MIME type
            
        Returns:
            Storage path/key for the uploaded file
        """
        pass
    
    @abstractmethod
    async def download(self, storage_path: str) -> Optional[bytes]:
        """
        Download a file from storage.
        
        Args:
            storage_path: Storage path/key from upload
            
        Returns:
            File content bytes or None if not found
        """
        pass
    
    @abstractmethod
    async def delete(self, storage_path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            storage_path: Storage path/key to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            storage_path: Storage path/key
            
        Returns:
            True if file exists
        """
        pass
    
    @abstractmethod
    async def get_url(
        self,
        storage_path: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """
        Get a URL to access the file.
        
        Args:
            storage_path: Storage path/key
            expires_in: URL expiry time in seconds (for signed URLs)
            
        Returns:
            URL to access the file or None if not supported
        """
        pass


class LocalFileStorage(FileStorageBackend):
    """
    Local filesystem storage backend.
    
    Files are stored in a configurable directory with structure:
    {base_path}/{user_id}/{file_id}/{filename}
    
    Args:
        base_path: Base directory for file storage
        base_url: Optional base URL for serving files
    """
    
    def __init__(
        self,
        base_path: str = "./uploads/staged-files",
        base_url: Optional[str] = None,
    ):
        self.base_path = Path(base_path)
        self.base_url = base_url
        
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalFileStorage initialized at {self.base_path.absolute()}")
    
    def _get_file_path(self, storage_path: str) -> Path:
        """Get full filesystem path for a storage path."""
        return self.base_path / storage_path
    
    def _sanitize_path_component(self, component: str) -> str:
        """Sanitize a path component to prevent path traversal."""
        # Remove any path separators
        component = component.replace("/", "_").replace("\\", "_")
        # Remove special characters
        component = "".join(c for c in component if c.isalnum() or c in "._-")
        return component or "unnamed"
    
    async def upload(
        self,
        user_id: str,
        file_id: str,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> str:
        """Upload a file to local storage."""
        # Sanitize path components
        safe_user_id = self._sanitize_path_component(user_id)
        safe_file_id = self._sanitize_path_component(file_id)
        safe_filename = self._sanitize_path_component(filename)
        
        # Construct storage path
        storage_path = f"{safe_user_id}/{safe_file_id}/{safe_filename}"
        file_path = self._get_file_path(storage_path)
        
        # Create directory
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        logger.debug(f"Uploaded file to {file_path}")
        return storage_path
    
    async def download(self, storage_path: str) -> Optional[bytes]:
        """Download a file from local storage."""
        file_path = self._get_file_path(storage_path)
        
        if not file_path.exists():
            logger.debug(f"File not found: {file_path}")
            return None
        
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()
    
    async def delete(self, storage_path: str) -> bool:
        """Delete a file from local storage."""
        file_path = self._get_file_path(storage_path)
        
        if not file_path.exists():
            return False
        
        try:
            file_path.unlink()
            
            # Clean up empty parent directories
            parent = file_path.parent
            while parent != self.base_path:
                if not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
            
            logger.debug(f"Deleted file: {storage_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {storage_path}: {e}")
            return False
    
    async def exists(self, storage_path: str) -> bool:
        """Check if file exists in local storage."""
        return self._get_file_path(storage_path).exists()
    
    async def get_url(
        self,
        storage_path: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Get URL for local file (if base_url is configured)."""
        if not self.base_url:
            return None
        
        file_path = self._get_file_path(storage_path)
        if not file_path.exists():
            return None
        
        # For local storage, we just return a static URL
        # A real implementation would serve these files via an endpoint
        return urljoin(self.base_url, storage_path)
    
    async def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """
        Clean up files older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of files deleted
        """
        deleted = 0
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        for user_dir in self.base_path.iterdir():
            if not user_dir.is_dir():
                continue
            
            for file_dir in user_dir.iterdir():
                if not file_dir.is_dir():
                    continue
                
                for file_path in file_dir.iterdir():
                    if file_path.stat().st_mtime < cutoff:
                        try:
                            file_path.unlink()
                            deleted += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete expired file {file_path}: {e}")
                
                # Clean up empty directories
                if not any(file_dir.iterdir()):
                    try:
                        file_dir.rmdir()
                    except Exception:
                        pass
            
            if not any(user_dir.iterdir()):
                try:
                    user_dir.rmdir()
                except Exception:
                    pass
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired files")
        
        return deleted


class S3FileStorage(FileStorageBackend):
    """
    S3-compatible storage backend.
    
    Works with AWS S3, MinIO, and other S3-compatible services.
    
    Args:
        bucket: S3 bucket name
        endpoint_url: Optional endpoint URL (for MinIO, etc.)
        region: AWS region
        access_key: AWS access key ID
        secret_key: AWS secret access key
        public_url_base: Optional base URL for public access
    """
    
    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        public_url_base: Optional[str] = None,
    ):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self.public_url_base = public_url_base
        
        # Initialize boto3 client
        try:
            import boto3
            from botocore.config import Config
            
            config = Config(
                signature_version="s3v4",
                region_name=region,
            )
            
            client_kwargs = {
                "service_name": "s3",
                "config": config,
            }
            
            if endpoint_url:
                client_kwargs["endpoint_url"] = endpoint_url
            
            if access_key and secret_key:
                client_kwargs["aws_access_key_id"] = access_key
                client_kwargs["aws_secret_access_key"] = secret_key
            
            self._client = boto3.client(**client_kwargs)
            logger.info(f"S3FileStorage initialized for bucket: {bucket}")
            
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
    
    def _sanitize_key(self, key: str) -> str:
        """Sanitize S3 object key."""
        # Remove leading slashes
        return key.lstrip("/")
    
    async def upload(
        self,
        user_id: str,
        file_id: str,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> str:
        """Upload a file to S3."""
        import io
        
        # Construct key
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        key = f"{user_id}/{file_id}/{safe_filename}"
        key = self._sanitize_key(key)
        
        # Upload file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.upload_fileobj(
                io.BytesIO(content),
                self.bucket,
                key,
                ExtraArgs={"ContentType": mime_type},
            ),
        )
        
        logger.debug(f"Uploaded file to S3: {key}")
        return key
    
    async def download(self, storage_path: str) -> Optional[bytes]:
        """Download a file from S3."""
        import io
        
        key = self._sanitize_key(storage_path)
        buffer = io.BytesIO()
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.download_fileobj(self.bucket, key, buffer),
            )
            return buffer.getvalue()
        except Exception as e:
            logger.debug(f"File not found in S3: {key} - {e}")
            return None
    
    async def delete(self, storage_path: str) -> bool:
        """Delete a file from S3."""
        key = self._sanitize_key(storage_path)
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.delete_object(Bucket=self.bucket, Key=key),
            )
            logger.debug(f"Deleted file from S3: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete from S3: {key} - {e}")
            return False
    
    async def exists(self, storage_path: str) -> bool:
        """Check if file exists in S3."""
        key = self._sanitize_key(storage_path)
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.head_object(Bucket=self.bucket, Key=key),
            )
            return True
        except Exception:
            return False
    
    async def get_url(
        self,
        storage_path: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Get a presigned URL for S3 object."""
        key = self._sanitize_key(storage_path)
        
        loop = asyncio.get_event_loop()
        try:
            url = await loop.run_in_executor(
                None,
                lambda: self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expires_in,
                ),
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None


# Storage backend singleton
_storage_instance: Optional[FileStorageBackend] = None


def get_storage_backend(
    backend_type: str = "local",
    **kwargs,
) -> FileStorageBackend:
    """
    Get or create a storage backend instance.
    
    Args:
        backend_type: "local" or "s3"
        **kwargs: Backend-specific configuration
        
    Returns:
        FileStorageBackend instance
    """
    global _storage_instance
    
    if _storage_instance is not None:
        return _storage_instance
    
    if backend_type == "local":
        base_path = kwargs.get("base_path", "./uploads/staged-files")
        base_url = kwargs.get("base_url")
        _storage_instance = LocalFileStorage(base_path=base_path, base_url=base_url)
    
    elif backend_type == "s3":
        _storage_instance = S3FileStorage(
            bucket=kwargs.get("bucket", "staged-files"),
            endpoint_url=kwargs.get("endpoint_url"),
            region=kwargs.get("region", "us-east-1"),
            access_key=kwargs.get("access_key"),
            secret_key=kwargs.get("secret_key"),
            public_url_base=kwargs.get("public_url_base"),
        )
    
    else:
        raise ValueError(f"Unknown storage backend type: {backend_type}")
    
    return _storage_instance


def reset_storage_backend() -> None:
    """Reset the storage backend singleton (for testing)."""
    global _storage_instance
    _storage_instance = None
