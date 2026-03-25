# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
CRUD operations for Session Wishlists.

Provides database operations for managing user session wishlists including:
- Get user's wishlisted sessions
- Add session to wishlist
- Remove session from wishlist
- Check if session is wishlisted
"""

from typing import Optional, Sequence, List
from datetime import datetime

from sqlalchemy import select, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.model.session_wishlist import SessionWishlist
from backend.app.agent.model.chat_session import ChatSession


class CRUDWishlist:
    """CRUD operations for SessionWishlist model."""

    async def get_user_wishlist(
        self,
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        per_page: int = 50
    ) -> tuple[Sequence[SessionWishlist], int]:
        """
        Get all wishlisted sessions for a user with pagination.

        Args:
            db: Database session
            user_id: User ID
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Tuple of (wishlist entries, total count)
        """
        # Count total
        count_query = select(func.count()).select_from(SessionWishlist).where(
            SessionWishlist.user_id == user_id
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * per_page
        query = (
            select(SessionWishlist)
            .where(SessionWishlist.user_id == user_id)
            .order_by(SessionWishlist.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )

        result = await db.execute(query)
        wishlists = result.scalars().all()

        return wishlists, total

    async def get_user_wishlist_session_ids(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[str]:
        """
        Get all wishlisted session IDs for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of session UUIDs that are wishlisted
        """
        query = select(SessionWishlist.session_id).where(
            SessionWishlist.user_id == user_id
        )
        result = await db.execute(query)
        return [row[0] for row in result.fetchall()]

    async def add_to_wishlist(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> SessionWishlist:
        """
        Add a session to user's wishlist.

        Args:
            db: Database session
            user_id: User ID
            session_id: Session UUID to wishlist

        Returns:
            Created SessionWishlist entry

        Raises:
            IntegrityError: If session is already wishlisted
        """
        wishlist = SessionWishlist(
            user_id=user_id,
            session_id=session_id
        )
        db.add(wishlist)
        await db.flush()
        await db.refresh(wishlist)
        return wishlist

    async def remove_from_wishlist(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> bool:
        """
        Remove a session from user's wishlist.

        Args:
            db: Database session
            user_id: User ID
            session_id: Session UUID to remove

        Returns:
            True if removed, False if not found
        """
        result = await db.execute(
            delete(SessionWishlist).where(
                and_(
                    SessionWishlist.user_id == user_id,
                    SessionWishlist.session_id == session_id
                )
            )
        )
        await db.flush()
        return result.rowcount > 0

    async def is_wishlisted(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> bool:
        """
        Check if a session is in user's wishlist.

        Args:
            db: Database session
            user_id: User ID
            session_id: Session UUID to check

        Returns:
            True if wishlisted, False otherwise
        """
        query = select(SessionWishlist.id).where(
            and_(
                SessionWishlist.user_id == user_id,
                SessionWishlist.session_id == session_id
            )
        ).limit(1)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_wishlist_entry(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> Optional[SessionWishlist]:
        """
        Get a specific wishlist entry.

        Args:
            db: Database session
            user_id: User ID
            session_id: Session UUID

        Returns:
            SessionWishlist if found, None otherwise
        """
        query = select(SessionWishlist).where(
            and_(
                SessionWishlist.user_id == user_id,
                SessionWishlist.session_id == session_id
            )
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def clear_user_wishlist(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """
        Remove all wishlisted sessions for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of entries removed
        """
        result = await db.execute(
            delete(SessionWishlist).where(SessionWishlist.user_id == user_id)
        )
        await db.flush()
        return result.rowcount


# Singleton instance
wishlist_dao = CRUDWishlist()
