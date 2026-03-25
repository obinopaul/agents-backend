# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Connector model for external service integrations (Google Drive, etc.).

This model stores OAuth tokens and metadata for external service connections.
Supports multiple connector types with encrypted token storage.
"""

from datetime import datetime
from typing import Optional
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class ConnectorType(str, Enum):
    """Supported external connector types."""
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"  # Future expansion
    ONEDRIVE = "onedrive"  # Future expansion


class Connector(Base):
    """
    External service connector for OAuth integrations.

    Stores OAuth tokens (access_token, refresh_token) and connection metadata
    for external services like Google Drive.

    Key features:
    - Per-user connector instances (one connection per service per user)
    - Token refresh support with expiry tracking
    - Metadata storage for service-specific information (email, scopes, etc.)
    - Unique constraint on (user_id, connector_type)
    """

    __tablename__ = 'connectors'

    # =========================================================================
    # Primary Key
    # =========================================================================

    id: Mapped[id_key] = mapped_column(init=False)

    # =========================================================================
    # Required fields (no defaults)
    # =========================================================================

    # Foreign key to user
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        index=True,
        comment='User who owns this connector'
    )

    # Connector type
    connector_type: Mapped[str] = mapped_column(
        sa.String(50),
        index=True,
        comment='Type of connector: google_drive, dropbox, etc.'
    )

    # =========================================================================
    # OAuth Token fields
    # =========================================================================

    access_token: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='OAuth access token (encrypted in production)'
    )

    refresh_token: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='OAuth refresh token for token renewal'
    )

    token_expiry: Mapped[Optional[datetime]] = mapped_column(
        TimeZone,
        default=None,
        comment='Access token expiration timestamp'
    )

    # =========================================================================
    # Metadata
    # =========================================================================

    # Using JSONB for PostgreSQL, falls back to JSON for MySQL
    connector_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=None,
        comment='Service-specific metadata (email, name, scopes, etc.)'
    )

    # =========================================================================
    # Table constraints
    # =========================================================================

    __table_args__ = (
        # Ensure one connector per type per user
        sa.UniqueConstraint('user_id', 'connector_type', name='uq_user_connector_type'),
        sa.Index('idx_connector_user_type', 'user_id', 'connector_type'),
        {'comment': 'External service connectors for OAuth integrations'}
    )

    # =========================================================================
    # Relationships
    # =========================================================================

    # User relationship
    user = relationship("User", lazy="selectin")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if self.token_expiry is None:
            return False
        now = timezone.now()
        # Normalize timezone if needed
        expiry = self.token_expiry
        if expiry.tzinfo is None:
            from datetime import timezone as dt_timezone
            expiry = expiry.replace(tzinfo=dt_timezone.utc)
        return now >= expiry

    @property
    def can_refresh(self) -> bool:
        """Check if the token can be refreshed."""
        return self.refresh_token is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'connector_type': self.connector_type,
            'is_connected': self.access_token is not None,
            'is_expired': self.is_expired,
            'metadata': self.connector_metadata,
            'created_at': self.created_time.isoformat() if self.created_time else None,
            'updated_at': self.updated_time.isoformat() if self.updated_time else None,
        }
