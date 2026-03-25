from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


# Abstract Object Storage Interface
class BaseStorage(ABC):
    """
    Abstract base class for cloud storage providers.
    
    Implementations must provide methods for uploading files
    and generating public URLs.
    """
    
    @abstractmethod
    async def write(self, content: BinaryIO, path: str, content_type: str | None = None):
        """Write a file-like object to storage."""
        pass

    @abstractmethod
    async def write_bytes(self, content: bytes, path: str, content_type: str | None = None) -> str:
        """
        Write raw bytes to storage and return the public URL.
        
        Args:
            content: Raw bytes to upload
            path: Target path/key in storage
            content_type: Optional MIME type
            
        Returns:
            Public URL for the uploaded file
        """
        pass

    @abstractmethod
    async def write_from_url(self, url: str, path: str, content_type: str | None = None) -> str:
        """Download from URL and upload to storage."""
        pass

    @abstractmethod
    async def write_from_local_path(self, local_path: str, target_path: str, content_type: str | None = None) -> str:
        """Upload a local file to storage."""
        pass

    @abstractmethod
    def get_public_url(self, path: str) -> str:
        """Get public URL for a stored file."""
        pass