# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
CRUD operations for Chat Sessions.

Provides database operations for managing chat sessions including:
- Create, read, update, delete (soft)
- Pagination with search
- Public session access
- Sandbox linkage
- Token/credit tracking
"""

from typing import Optional, Sequence, Tuple, List
from datetime import datetime

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.agent.model.chat_session import ChatSession, ChatSessionStatus
from backend.utils.timezone import timezone


class CRUDChatSession(CRUDPlus[ChatSession]):
    """CRUD operations for ChatSession model."""

    # =========================================================================
    # Basic Operations
    # =========================================================================

    async def get(self, db: AsyncSession, session_id: int) -> Optional[ChatSession]:
        """
        Get session by internal ID.
        
        :param db: Database session
        :param session_id: Internal session ID
        :return: ChatSession or None
        """
        return await self.select_model(db, session_id)

    async def get_by_uuid(
        self, 
        db: AsyncSession, 
        uuid: str,
        include_deleted: bool = False
    ) -> Optional[ChatSession]:
        """
        Get session by UUID.
        
        :param db: Database session
        :param uuid: Session UUID
        :param include_deleted: Whether to include soft-deleted sessions
        :return: ChatSession or None
        """
        query = select(ChatSession).where(ChatSession.uuid == uuid)
        
        if not include_deleted:
            query = query.where(ChatSession.deleted_at.is_(None))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self, 
        db: AsyncSession, 
        session_id: int, 
        user_id: int
    ) -> Optional[ChatSession]:
        """
        Get session by ID with user ownership verification.
        
        :param db: Database session
        :param session_id: Internal session ID
        :param user_id: User ID for ownership check
        :return: ChatSession or None if not found or not owned by user
        """
        result = await db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_uuid_and_user(
        self, 
        db: AsyncSession, 
        uuid: str, 
        user_id: int
    ) -> Optional[ChatSession]:
        """
        Get session by UUID with user ownership verification.
        
        :param db: Database session
        :param uuid: Session UUID
        :param user_id: User ID for ownership check
        :return: ChatSession or None if not found or not owned by user
        """
        result = await db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.uuid == uuid,
                    ChatSession.user_id == user_id,
                    ChatSession.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # List Operations
    # =========================================================================

    async def get_user_sessions(
        self,
        db: AsyncSession,
        user_id: int,
        search_term: Optional[str] = None,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        order_by: str = "last_activity_at",
        order_dir: str = "desc"
    ) -> Tuple[Sequence[ChatSession], int]:
        """
        Get paginated sessions for a user with optional filters.
        
        :param db: Database session
        :param user_id: User ID
        :param search_term: Optional search term for name/description
        :param status: Optional status filter
        :param agent_type: Optional agent type filter
        :param page: Page number (1-indexed)
        :param per_page: Items per page
        :param order_by: Field to order by
        :param order_dir: Order direction ('asc' or 'desc')
        :return: Tuple of (sessions list, total count)
        """
        # Base query - exclude deleted sessions
        base_filter = and_(
            ChatSession.user_id == user_id,
            ChatSession.deleted_at.is_(None)
        )
        
        # Add optional filters
        filters = [base_filter]
        
        if search_term:
            search_filter = or_(
                ChatSession.name.ilike(f"%{search_term}%"),
                ChatSession.description.ilike(f"%{search_term}%")
            )
            filters.append(search_filter)
        
        if status:
            filters.append(ChatSession.status == status)
        
        if agent_type:
            filters.append(ChatSession.agent_type == agent_type)
        
        combined_filter = and_(*filters)
        
        # Get total count
        count_query = select(func.count()).select_from(ChatSession).where(combined_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Build order clause
        order_column = getattr(ChatSession, order_by, ChatSession.created_time)
        order_clause = desc(order_column) if order_dir == "desc" else order_column
        
        # Get paginated results
        offset = (page - 1) * per_page
        query = (
            select(ChatSession)
            .where(combined_filter)
            .order_by(order_clause)
            .offset(offset)
            .limit(per_page)
        )
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        return sessions, total

    async def get_public_sessions(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[Sequence[ChatSession], int]:
        """
        Get paginated public sessions.
        
        :param db: Database session
        :param page: Page number
        :param per_page: Items per page
        :return: Tuple of (sessions list, total count)
        """
        base_filter = and_(
            ChatSession.is_public == True,
            ChatSession.deleted_at.is_(None)
        )
        
        # Get total count
        count_query = select(func.count()).select_from(ChatSession).where(base_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        offset = (page - 1) * per_page
        query = (
            select(ChatSession)
            .where(base_filter)
            .order_by(desc(ChatSession.created_time))
            .offset(offset)
            .limit(per_page)
        )
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        return sessions, total

    # =========================================================================
    # Create Operations
    # =========================================================================

    async def create_session(
        self,
        db: AsyncSession,
        user_id: int,
        name: Optional[str] = None,
        agent_type: Optional[str] = None,
        llm_setting_id: Optional[str] = None,
        **kwargs
    ) -> ChatSession:
        """
        Create a new chat session.
        
        :param db: Database session
        :param user_id: User ID who owns the session
        :param name: Optional session name
        :param agent_type: Optional agent type
        :param llm_setting_id: Optional LLM configuration ID
        :param kwargs: Additional fields
        :return: Created ChatSession
        """
        session = ChatSession(
            user_id=user_id,
            name=name,
            agent_type=agent_type,
            llm_setting_id=llm_setting_id,
            last_activity_at=timezone.now(),
            **kwargs
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def get_or_create(
        self,
        db: AsyncSession,
        uuid: str,
        user_id: int,
        **create_kwargs
    ) -> Tuple[ChatSession, bool]:
        """
        Get existing session or create new one.
        
        :param db: Database session
        :param uuid: Session UUID
        :param user_id: User ID
        :param create_kwargs: Additional fields for creation
        :return: Tuple of (ChatSession, created: bool)
        """
        existing = await self.get_by_uuid(db, uuid)
        
        if existing:
            # Verify ownership
            if existing.user_id != user_id:
                raise ValueError(f"Session {uuid} not owned by user {user_id}")
            return existing, False
        
        # Create new session with the specified UUID
        session = ChatSession(
            user_id=user_id,
            last_activity_at=timezone.now(),
            **create_kwargs
        )
        # Override the auto-generated UUID
        session.uuid = uuid
        
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session, True

    # =========================================================================
    # Update Operations
    # =========================================================================

    async def update_session(
        self,
        db: AsyncSession,
        session_id: int,
        **kwargs
    ) -> Optional[ChatSession]:
        """
        Update session fields.
        
        :param db: Database session
        :param session_id: Session ID
        :param kwargs: Fields to update
        :return: Updated session or None
        """
        session = await self.get(db, session_id)
        if not session:
            return None
        
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        await db.flush()
        await db.refresh(session)
        return session

    async def update_session_by_uuid(
        self,
        db: AsyncSession,
        uuid: str,
        user_id: int,
        **kwargs
    ) -> Optional[ChatSession]:
        """
        Update session by UUID with ownership verification.
        
        :param db: Database session
        :param uuid: Session UUID
        :param user_id: User ID for ownership check
        :param kwargs: Fields to update
        :return: Updated session or None
        """
        session = await self.get_by_uuid_and_user(db, uuid, user_id)
        if not session:
            return None
        
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        await db.flush()
        await db.refresh(session)
        return session

    async def update_name(
        self,
        db: AsyncSession,
        session_id: int,
        name: str
    ) -> Optional[ChatSession]:
        """
        Update session name.
        
        :param db: Database session
        :param session_id: Session ID
        :param name: New name
        :return: Updated session or None
        """
        return await self.update_session(db, session_id, name=name)

    async def update_last_activity(
        self,
        db: AsyncSession,
        session_id: int
    ) -> Optional[ChatSession]:
        """
        Update session last activity timestamp.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Updated session or None
        """
        return await self.update_session(
            db, 
            session_id, 
            last_activity_at=timezone.now()
        )

    async def link_sandbox(
        self,
        db: AsyncSession,
        session_id: int,
        sandbox_id: str,
        workspace_dir: Optional[str] = None
    ) -> Optional[ChatSession]:
        """
        Link a sandbox to the session.
        
        :param db: Database session
        :param session_id: Session ID
        :param sandbox_id: Sandbox ID to link
        :param workspace_dir: Optional workspace directory
        :return: Updated session or None
        """
        return await self.update_session(
            db,
            session_id,
            sandbox_id=sandbox_id,
            workspace_dir=workspace_dir
        )

    async def increment_message_count(
        self,
        db: AsyncSession,
        session_id: int
    ) -> Optional[ChatSession]:
        """
        Increment the message count for a session.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Updated session or None
        """
        session = await self.get(db, session_id)
        if not session:
            return None
        
        session.message_count = (session.message_count or 0) + 1
        session.last_activity_at = timezone.now()
        
        await db.flush()
        await db.refresh(session)
        return session

    async def update_token_usage(
        self,
        db: AsyncSession,
        session_id: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        credits_used: float = 0.0
    ) -> Optional[ChatSession]:
        """
        Update session token and credit usage.
        
        :param db: Database session
        :param session_id: Session ID
        :param prompt_tokens: Prompt tokens to add
        :param completion_tokens: Completion tokens to add
        :param credits_used: Credits used to add
        :return: Updated session or None
        """
        session = await self.get(db, session_id)
        if not session:
            return None
        
        session.total_prompt_tokens = (session.total_prompt_tokens or 0) + prompt_tokens
        session.total_completion_tokens = (session.total_completion_tokens or 0) + completion_tokens
        session.total_credits_used = (session.total_credits_used or 0.0) + credits_used
        session.last_activity_at = timezone.now()
        
        await db.flush()
        await db.refresh(session)
        return session

    # =========================================================================
    # Visibility Operations
    # =========================================================================

    async def set_public(
        self,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        is_public: bool,
        public_slug: Optional[str] = None
    ) -> Optional[ChatSession]:
        """
        Set session visibility.
        
        :param db: Database session
        :param session_id: Session ID
        :param user_id: User ID for ownership check
        :param is_public: Whether to make public
        :param public_slug: Optional public URL slug
        :return: Updated session or None
        """
        session = await self.get_by_id_and_user(db, session_id, user_id)
        if not session:
            return None
        
        session.is_public = is_public
        if public_slug:
            session.public_slug = public_slug
        elif not is_public:
            session.public_slug = None
        
        await db.flush()
        await db.refresh(session)
        return session

    async def get_public_session(
        self,
        db: AsyncSession,
        uuid: str
    ) -> Optional[ChatSession]:
        """
        Get a public session by UUID.
        
        :param db: Database session
        :param uuid: Session UUID
        :return: ChatSession if public, None otherwise
        """
        result = await db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.uuid == uuid,
                    ChatSession.is_public == True,
                    ChatSession.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_public_slug(
        self,
        db: AsyncSession,
        slug: str
    ) -> Optional[ChatSession]:
        """
        Get a public session by its public slug.
        
        :param db: Database session
        :param slug: Public URL slug
        :return: ChatSession if found and public, None otherwise
        """
        result = await db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.public_slug == slug,
                    ChatSession.is_public == True,
                    ChatSession.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Delete Operations
    # =========================================================================

    async def soft_delete(
        self,
        db: AsyncSession,
        session_id: int,
        user_id: int
    ) -> bool:
        """
        Soft delete a session.
        
        :param db: Database session
        :param session_id: Session ID
        :param user_id: User ID for ownership check
        :return: True if deleted, False otherwise
        """
        session = await self.get_by_id_and_user(db, session_id, user_id)
        if not session:
            return False
        
        session.deleted_at = timezone.now()
        session.status = ChatSessionStatus.DELETED.value
        await db.flush()
        return True

    async def soft_delete_by_uuid(
        self,
        db: AsyncSession,
        uuid: str,
        user_id: int
    ) -> bool:
        """
        Soft delete a session by UUID.
        
        :param db: Database session
        :param uuid: Session UUID
        :param user_id: User ID for ownership check
        :return: True if deleted, False otherwise
        """
        session = await self.get_by_uuid_and_user(db, uuid, user_id)
        if not session:
            return False
        
        session.deleted_at = timezone.now()
        session.status = ChatSessionStatus.DELETED.value
        await db.flush()
        return True

    async def hard_delete(
        self,
        db: AsyncSession,
        session_id: int
    ) -> bool:
        """
        Permanently delete a session (use with caution).
        
        :param db: Database session
        :param session_id: Session ID
        :return: True if deleted, False otherwise
        """
        return await self.delete_model(db, session_id) > 0

    # =========================================================================
    # Sandbox Operations
    # =========================================================================

    async def get_by_sandbox_id(
        self,
        db: AsyncSession,
        sandbox_id: str
    ) -> Optional[ChatSession]:
        """
        Get session linked to a sandbox.
        
        :param db: Database session
        :param sandbox_id: Sandbox ID
        :return: ChatSession or None
        """
        result = await db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.sandbox_id == sandbox_id,
                    ChatSession.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()


# Singleton instance
chat_session_dao: CRUDChatSession = CRUDChatSession(ChatSession)
