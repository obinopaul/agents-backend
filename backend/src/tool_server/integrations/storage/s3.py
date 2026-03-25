# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
S3-compatible storage provider implementation.

Supports AWS S3, MinIO, Supabase Storage, Wasabi, DigitalOcean Spaces,
and other S3-compatible storage services.
"""

import asyncio
import io
import logging
from typing import BinaryIO, Optional

import aiohttp

from .base import BaseStorage

logger = logging.getLogger(__name__)


class S3Storage(BaseStorage):
    """
    Asynchronous S3-compatible storage provider.
    
    Works with:
        - AWS S3
        - MinIO
        - Supabase Storage
        - DigitalOcean Spaces
        - Wasabi
        - Any S3-compatible service
        
    Args:
        bucket: S3 bucket name
        endpoint_url: Optional endpoint URL (required for non-AWS services)
        region: AWS region (default: us-east-1)
        access_key: AWS access key ID or service account key
        secret_key: AWS secret access key or service account secret
        public_url_base: Optional base URL for public access (e.g., CDN URL)
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
        self.access_key = access_key
        self.secret_key = secret_key
        self.public_url_base = public_url_base
        
        # Lazy-loaded boto3 client
        self._client = None
        self._client_initialized = False
        
        logger.info(
            f"S3Storage initialized for bucket: {bucket} "
            f"(endpoint: {endpoint_url or 'AWS default'})"
        )
    
    def _get_client(self):
        """
        Lazy-load the boto3 S3 client.
        
        Returns:
            boto3 S3 client
        """
        if not self._client_initialized:
            try:
                import boto3
                from botocore.config import Config
                
                config = Config(
                    signature_version="s3v4",
                    region_name=self.region,
                )
                
                client_kwargs = {
                    "service_name": "s3",
                    "config": config,
                }
                
                if self.endpoint_url:
                    client_kwargs["endpoint_url"] = self.endpoint_url
                
                if self.access_key and self.secret_key:
                    client_kwargs["aws_access_key_id"] = self.access_key
                    client_kwargs["aws_secret_access_key"] = self.secret_key
                
                self._client = boto3.client(**client_kwargs)
                logger.debug(f"Initialized boto3 S3 client for bucket: {self.bucket}")
                
            except ImportError:
                raise ImportError(
                    "boto3 is required for S3 storage. Install with: pip install boto3"
                )
            
            self._client_initialized = True
            
        return self._client
    
    def _sanitize_key(self, key: str) -> str:
        """
        Sanitize S3 object key.
        
        Args:
            key: Raw object key
            
        Returns:
            Sanitized key without leading slashes
        """
        return key.lstrip("/")
    
    async def write(self, content: BinaryIO, path: str, content_type: str | None = None):
        """
        Write a file-like object to S3.
        
        Args:
            content: File-like object to upload
            path: Target path/key in bucket
            content_type: Optional MIME type
        """
        key = self._sanitize_key(path)
        client = self._get_client()
        
        # Reset file pointer
        content.seek(0)
        file_content = content.read()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: client.upload_fileobj(
                io.BytesIO(file_content),
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type} if content_type else None,
            ),
        )
        
        logger.debug(f"Uploaded to S3: {key}")
    
    async def write_bytes(self, content: bytes, path: str, content_type: str | None = None) -> str:
        """
        Write raw bytes to S3 and return public URL.
        
        Args:
            content: Raw bytes to upload
            path: Target path/key in bucket
            content_type: Optional MIME type
            
        Returns:
            Public URL for the uploaded file
        """
        key = self._sanitize_key(path)
        client = self._get_client()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: client.upload_fileobj(
                io.BytesIO(content),
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type} if content_type else None,
            ),
        )
        
        logger.debug(f"Uploaded bytes to S3: {key} ({len(content):,} bytes)")
        return self.get_public_url(key)
    
    async def write_from_url(self, url: str, path: str, content_type: str | None = None) -> str:
        """
        Download from URL and upload to S3.
        
        Args:
            url: Source URL to download from
            path: Target path/key in bucket
            content_type: Optional MIME type
            
        Returns:
            Public URL for the uploaded file
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                content = await response.read()
                
                # Use content-type from response if not provided
                if not content_type:
                    content_type = response.headers.get("Content-Type")
        
        return await self.write_bytes(content, path, content_type)
    
    async def write_from_local_path(
        self, local_path: str, target_path: str, content_type: str | None = None
    ) -> str:
        """
        Upload a local file to S3.
        
        Args:
            local_path: Path to local file
            target_path: Target path/key in bucket
            content_type: Optional MIME type
            
        Returns:
            Public URL for the uploaded file
        """
        with open(local_path, "rb") as f:
            content = f.read()
        
        return await self.write_bytes(content, target_path, content_type)
    
    def get_public_url(self, path: str) -> str:
        """
        Get public URL for a stored file.
        
        If public_url_base is configured, uses that as the base.
        Otherwise, constructs a standard S3 URL.
        
        Args:
            path: Object path/key in bucket
            
        Returns:
            Public URL string
        """
        key = self._sanitize_key(path)
        
        if self.public_url_base:
            # Use configured public URL base (e.g., CDN)
            base = self.public_url_base.rstrip("/")
            return f"{base}/{key}"
        
        if self.endpoint_url:
            # Use custom endpoint (MinIO, Supabase, etc.)
            endpoint = self.endpoint_url.rstrip("/")
            return f"{endpoint}/{self.bucket}/{key}"
        
        # Standard AWS S3 URL
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
    
    async def generate_presigned_url(self, path: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            path: Object path/key in bucket
            expires_in: URL expiry time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        key = self._sanitize_key(path)
        client = self._get_client()
        
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            ),
        )
        
        return url
    
    async def exists(self, path: str) -> bool:
        """
        Check if an object exists in S3.
        
        Args:
            path: Object path/key in bucket
            
        Returns:
            True if object exists
        """
        key = self._sanitize_key(path)
        client = self._get_client()
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: client.head_object(Bucket=self.bucket, Key=key),
            )
            return True
        except Exception:
            return False
    
    async def delete(self, path: str) -> bool:
        """
        Delete an object from S3.
        
        Args:
            path: Object path/key in bucket
            
        Returns:
            True if deleted successfully
        """
        key = self._sanitize_key(path)
        client = self._get_client()
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: client.delete_object(Bucket=self.bucket, Key=key),
            )
            logger.debug(f"Deleted from S3: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete from S3: {key} - {e}")
            return False
