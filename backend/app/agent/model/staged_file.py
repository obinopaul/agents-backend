# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Staged File model for managing user-uploaded file attachments.

Files are staged (uploaded and parsed) before being attached to chat messages.
"""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.database.db import uuid4_str
from backend.utils.timezone import timezone


class StagedFile(Base):
    """
    Staged file for chat attachments.
    
    Files are uploaded, parsed, and stored before being attached to messages.
    This allows for:
    - Preview generation before sending
    - Text extraction from documents
    - Image compression and optimization
    - Temporary storage with expiration
    """
    
    __tablename__ = 'agent_staged_files'
    
    # Auto-generated primary key
    id: Mapped[id_key] = mapped_column(init=False)
    
    # -------------------------------------------------------------------------
    # Required fields (no defaults) - must come first for dataclasses
    # -------------------------------------------------------------------------
    
    # User who uploaded the file
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id'),
        index=True,
        comment='User who uploaded the file'
    )
    
    # File information (required)
    filename: Mapped[str] = mapped_column(
        sa.String(512),
        comment='Original filename'
    )
    
    storage_path: Mapped[str] = mapped_column(
        sa.String(1024),
        comment='Path in storage backend'
    )
    
    file_size: Mapped[int] = mapped_column(
        sa.BigInteger,
        comment='File size in bytes'
    )
    
    # -------------------------------------------------------------------------
    # Optional fields (with defaults) - must come after required fields
    # -------------------------------------------------------------------------
    
    # Unique file identifier (for API references)
    file_id: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
        default_factory=uuid4_str,
        comment='Unique file identifier'
    )
    
    # Optional thread association (null = not yet attached)
    thread_id: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        index=True,
        default=None,
        comment='Thread ID if attached to a conversation'
    )
    
    mime_type: Mapped[str] = mapped_column(
        sa.String(256),
        default='application/octet-stream',
        comment='File MIME type'
    )
    
    # Parsed content (for documents)
    parsed_content: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='Extracted text content (truncated)'
    )
    
    # Parsing status
    parse_status: Mapped[str] = mapped_column(
        sa.String(32),
        default='pending',
        comment='Status: pending, completed, failed'
    )
    
    # For images: compressed version URL
    image_url: Mapped[Optional[str]] = mapped_column(
        sa.String(1024),
        default=None,
        comment='Compressed image storage path'
    )
    
    # File metadata (JSON)
    file_metadata: Mapped[Optional[dict]] = mapped_column(
        sa.JSON,
        default=None,
        comment='Additional file metadata (pages, dimensions, etc.)'
    )
    
    # Expiration (for automatic cleanup)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        TimeZone,
        default=None,
        index=True,
        comment='When this file expires (null = never)'
    )
    
    # Timestamps (auto-generated)
    created_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now, onupdate=timezone.now
    )
    
    # Relationship to user
    user = relationship("User", back_populates="staged_files", lazy="selectin")
    
    @property
    def is_image(self) -> bool:
        """Check if this is an image file."""
        return self.mime_type.startswith('image/') if self.mime_type else False
    
    @property
    def is_document(self) -> bool:
        """Check if this is a document with extractable text."""
        document_types = {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/csv',
        }
        return self.mime_type in document_types if self.mime_type else False
    
    @property
    def is_expired(self) -> bool:
        """Check if this file has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(self.expires_at.tzinfo) > self.expires_at
    
    @property
    def has_parsed_content(self) -> bool:
        """Check if this file has parsed text content."""
        return bool(self.parsed_content and self.parsed_content.strip())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'file_id': self.file_id,
            'filename': self.filename,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'parse_status': self.parse_status,
            'has_content': self.has_parsed_content,
            'is_image': self.is_image,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
