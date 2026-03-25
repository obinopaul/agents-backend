# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Session Wishlist model for bookmarking favorite chat sessions.

This model provides a many-to-many relationship between users and chat sessions,
allowing users to bookmark/wishlist their favorite sessions for quick access.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import MappedBase
from backend.database.db import uuid4_str

if TYPE_CHECKING:
    from backend.app.admin.model import User
    from backend.app.agent.model.chat_session import ChatSession


class SessionWishlist(MappedBase):
    """
    Session wishlist entry for bookmarking chat sessions.

    This is a join table that links users to their wishlisted/bookmarked sessions.
    Each entry represents a user's bookmark of a specific session.

    Key features:
    - UUID-based primary key for API references
    - Unique constraint on (user_id, session_id) to prevent duplicates
    - Cascade delete when user or session is deleted
    - Created timestamp for ordering

    Note: Uses MappedBase instead of Base since this is a simple join table
    without the need for dataclass integration or DateTimeMixin fields.
    """

    __tablename__ = 'session_wishlists'

    # Primary key (UUID string)
    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=uuid4_str,
        comment='Unique wishlist entry ID'
    )

    # Foreign key to user
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='User who wishlisted the session'
    )

    # Foreign key to chat session (using uuid instead of id for consistency)
    session_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey('agent_chat_sessions.uuid', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='UUID of the wishlisted session'
    )

    # Timestamp when added to wishlist
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=sa.func.now(),
        comment='When the session was added to wishlist'
    )

    # Relationships (use strings to avoid circular imports)
    user = relationship(
        "User",
        back_populates="session_wishlists",
        lazy="selectin"
    )

    session = relationship(
        "ChatSession",
        back_populates="wishlisted_by",
        lazy="selectin"
    )

    # Table constraints
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'session_id', name='uq_user_session_wishlist'),
        {'comment': 'User session wishlist/bookmarks'}
    )

    def __repr__(self) -> str:
        return f"<SessionWishlist(id={self.id}, user_id={self.user_id}, session_id={self.session_id})>"
