# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Chat Session service layer.

Provides business logic for managing chat sessions including:
- Session lifecycle (create, get, update, delete)
- Session-sandbox linking for warm start optimization
- Event tracking and history
- Public sharing / publishing
"""

import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.crud.crud_chat_session import chat_session_dao
from backend.app.agent.crud.crud_chat_event import chat_event_dao
from backend.app.agent.model.chat_session import ChatSession, ChatSessionStatus, AgentType
from backend.app.agent.model.chat_event import ChatEvent, ChatEventType
from backend.common.exception import errors
from backend.common.log import log
from backend.utils.timezone import timezone


class ChatSessionService:
    """
    Service for managing chat sessions.
    
    This service provides the business logic layer for chat session operations,
    integrating CRUD operations with validation, error handling, and cross-cutting
    concerns like sandbox linking and event tracking.
    """

    # =========================================================================
    # Session Lifecycle
    # =========================================================================

    @staticmethod
    async def find_by_uuid(
        db: AsyncSession,
        session_uuid: str,
        user_id: Optional[int] = None
    ) -> Optional[ChatSession]:
        """
        Find session by UUID with optional user ownership verification.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param user_id: Optional user ID for ownership check
        :return: ChatSession or None
        """
        if user_id:
            return await chat_session_dao.get_by_uuid_and_user(db, session_uuid, user_id)
        return await chat_session_dao.get_by_uuid(db, session_uuid)

    @staticmethod
    async def get_or_create(
        db: AsyncSession,
        session_uuid: Optional[str],
        user_id: int,
        agent_type: Optional[str] = None,
        llm_setting_id: Optional[str] = None
    ) -> Tuple[ChatSession, bool]:
        """
        Get existing session or create a new one.
        
        This is the primary method for socket.io handlers to ensure a session exists
        before processing messages.
        
        :param db: Database session
        :param session_uuid: Optional session UUID (generates new if None)
        :param user_id: User ID who owns the session
        :param agent_type: Optional agent type for new sessions
        :param llm_setting_id: Optional LLM configuration for new sessions
        :return: Tuple of (ChatSession, created: bool)
        """
        if session_uuid:
            # Try to find existing session (including deleted ones to avoid unique constraint violations)
            existing = await chat_session_dao.get_by_uuid(db, session_uuid, include_deleted=True)
            if existing:
                # Verify ownership
                if existing.user_id != user_id:
                    raise errors.ForbiddenError(msg="Session not owned by user")
                
                # Reactivate if deleted
                if existing.deleted_at:
                    existing.deleted_at = None
                    existing.status = ChatSessionStatus.ACTIVE.value
                    db.add(existing)
                    await db.flush()
                    log.info(f"Reactivated soft-deleted session {session_uuid}")

                return existing, False
        else:
            # Generate new UUID
            session_uuid = str(uuid.uuid4())
        
        # Create new session (with race condition handling)
        try:
            session = await chat_session_dao.create_session(
                db=db,
                user_id=user_id,
                agent_type=agent_type or AgentType.GENERAL.value,
                llm_setting_id=llm_setting_id
            )
            
            # Override UUID if provided
            if session_uuid and session.uuid != session_uuid:
                session.uuid = session_uuid
                await db.flush()
                await db.refresh(session)
            
            log.info(f"Created new chat session {session.uuid} for user {user_id}")
            return session, True

        except Exception as e:
            # Check for IntegrityError (Unique Violation)
            # We catch generic Exception here because importing IntegrityError from sqlalchemy.exc 
            # might be cleaner than adding imports everywhere, but checking message is safer.
            if "IntegrityError" in type(e).__name__ or "unique constraint" in str(e).lower():
                log.warning(f"Race condition detected creating session {session_uuid}, retrying fetch...")
                # Retry fetch
                existing = await chat_session_dao.get_by_uuid(db, session_uuid, include_deleted=True)
                if existing:
                    # Verify ownership
                    if existing.user_id != user_id:
                        raise errors.ForbiddenError(msg="Session not owned by user")
                    
                    # Reactivate if deleted (handle corner case where race was with a delete?)
                    if existing.deleted_at:
                        existing.deleted_at = None
                        db.add(existing)
                        await db.flush()
                        
                    return existing, False
            
            # If not a unique violation or fetch failed, re-raise
            raise e

    @staticmethod
    async def ensure_session_exists(
        db: AsyncSession,
        session_uuid: str,
        user_id: int
    ) -> ChatSession:
        """
        Ensure a session exists, creating if necessary.
        
        Unlike get_or_create, this always uses the provided UUID.
        
        :param db: Database session
        :param session_uuid: Session UUID (required)
        :param user_id: User ID
        :return: ChatSession (existing or new)
        """
        existing = await chat_session_dao.get_by_uuid(db, session_uuid)
        if existing:
            # Verify ownership
            if existing.user_id != user_id:
                raise errors.ForbiddenError(msg="Session not owned by user")
            log.debug(f"Found existing session {session_uuid} for user {user_id}")
            return existing
        
        # Create new session with specific UUID
        session, _ = await chat_session_dao.get_or_create(
            db=db,
            uuid=session_uuid,
            user_id=user_id
        )
        
        log.info(f"Created session {session_uuid} for user {user_id}")
        return session

    @staticmethod
    async def create_session(
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
        :param user_id: User ID
        :param name: Optional session name
        :param agent_type: Optional agent type
        :param llm_setting_id: Optional LLM configuration ID
        :param kwargs: Additional fields
        :return: Created ChatSession
        """
        session = await chat_session_dao.create_session(
            db=db,
            user_id=user_id,
            name=name,
            agent_type=agent_type or AgentType.GENERAL.value,
            llm_setting_id=llm_setting_id,
            **kwargs
        )
        log.info(f"Created chat session {session.uuid} for user {user_id}")
        return session

    # =========================================================================
    # Session Listing
    # =========================================================================

    @staticmethod
    async def get_user_sessions(
        db: AsyncSession,
        user_id: int,
        search_term: Optional[str] = None,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[Sequence[ChatSession], int]:
        """
        Get paginated sessions for a user.
        
        :param db: Database session
        :param user_id: User ID
        :param search_term: Optional search in name/description
        :param status: Optional status filter
        :param agent_type: Optional agent type filter
        :param page: Page number
        :param per_page: Items per page
        :return: Tuple of (sessions, total_count)
        """
        return await chat_session_dao.get_user_sessions(
            db=db,
            user_id=user_id,
            search_term=search_term,
            status=status,
            agent_type=agent_type,
            page=page,
            per_page=per_page
        )

    # =========================================================================
    # Session Updates
    # =========================================================================

    @staticmethod
    async def update_session_name(
        db: AsyncSession,
        session_uuid: str,
        name: str,
        user_id: Optional[int] = None
    ) -> Optional[ChatSession]:
        """
        Update session name.
        
        Often called after the first user message to set a meaningful title.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param name: New name
        :param user_id: Optional user ID for ownership verification
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return None
        
        if user_id and session.user_id != user_id:
            raise errors.ForbiddenError(msg="Session not owned by user")
        
        session.name = name
        await db.flush()
        await db.refresh(session)
        
        log.debug(f"Updated session {session_uuid} name to: {name[:50]}...")
        return session

    @staticmethod
    async def update_session_name_from_message(
        db: AsyncSession,
        session_id: int,
        message: str
    ) -> Optional[ChatSession]:
        """
        Generate and update session name from first message.
        
        Uses the first ~50 characters of the message as the session name.
        Only updates if the session doesn't already have a name.
        
        :param db: Database session
        :param session_id: Internal session ID
        :param message: User's message
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get(db, session_id)
        if not session or session.name:
            return session
        
        # Generate name from message (truncate to 50 chars)
        name = message.strip()[:50]
        if len(message) > 50:
            name += "..."
        
        return await chat_session_dao.update_name(db, session_id, name)

    @staticmethod
    async def update_agent_type(
        db: AsyncSession,
        session_uuid: str,
        agent_type: str,
        user_id: Optional[int] = None
    ) -> Optional[ChatSession]:
        """
        Update session agent type.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param agent_type: New agent type
        :param user_id: Optional user ID for ownership verification
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return None
        
        if user_id and session.user_id != user_id:
            raise errors.ForbiddenError(msg="Session not owned by user")
        
        session.agent_type = agent_type
        await db.flush()
        await db.refresh(session)
        
        log.debug(f"Updated session {session_uuid} agent_type to: {agent_type}")
        return session

    @staticmethod
    async def update_llm_setting(
        db: AsyncSession,
        session_uuid: str,
        llm_setting_id: Optional[str],
        user_id: Optional[int] = None
    ) -> Optional[ChatSession]:
        """
        Update session LLM configuration.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param llm_setting_id: LLM configuration ID
        :param user_id: Optional user ID for ownership verification
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return None
        
        if user_id and session.user_id != user_id:
            raise errors.ForbiddenError(msg="Session not owned by user")
        
        session.llm_setting_id = llm_setting_id
        await db.flush()
        await db.refresh(session)
        
        return session

    # =========================================================================
    # Sandbox Linking (for Warm Start Optimization)
    # =========================================================================

    @staticmethod
    async def link_sandbox(
        db: AsyncSession,
        session_uuid: str,
        sandbox_id: str,
        workspace_dir: Optional[str] = None
    ) -> Optional[ChatSession]:
        """
        Link a sandbox to the session for warm start optimization.
        
        This enables session-based sandbox reuse - subsequent messages in the
        same session can reuse the existing sandbox instead of creating a new one.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param sandbox_id: Sandbox ID to link
        :param workspace_dir: Optional workspace directory path
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return None
        
        session.sandbox_id = sandbox_id
        if workspace_dir:
            session.workspace_dir = workspace_dir
        
        await db.flush()
        await db.refresh(session)
        
        log.info(f"Linked sandbox {sandbox_id} to session {session_uuid}")
        return session

    @staticmethod
    async def get_session_sandbox(
        db: AsyncSession,
        session_uuid: str
    ) -> Optional[str]:
        """
        Get the sandbox ID linked to a session.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :return: Sandbox ID or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        return session.sandbox_id if session else None

    # =========================================================================
    # Token/Credit Tracking
    # =========================================================================

    @staticmethod
    async def update_token_usage(
        db: AsyncSession,
        session_id: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        credits_used: float = 0.0
    ) -> Optional[ChatSession]:
        """
        Update token and credit usage for a session.
        
        :param db: Database session
        :param session_id: Session ID
        :param prompt_tokens: Prompt tokens to add
        :param completion_tokens: Completion tokens to add
        :param credits_used: Credits used to add
        :return: Updated ChatSession or None
        """
        return await chat_session_dao.update_token_usage(
            db=db,
            session_id=session_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            credits_used=credits_used
        )

    # =========================================================================
    # Visibility / Publishing
    # =========================================================================

    @staticmethod
    async def publish_session(
        db: AsyncSession,
        session_uuid: str,
        user_id: int,
        public_slug: Optional[str] = None
    ) -> Optional[ChatSession]:
        """
        Make a session publicly viewable.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param user_id: User ID for ownership verification
        :param public_slug: Optional custom URL slug
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get_by_uuid_and_user(db, session_uuid, user_id)
        if not session:
            return None
        
        session.is_public = True
        if public_slug:
            # Verify slug is unique
            existing = await chat_session_dao.get_by_public_slug(db, public_slug)
            if existing and existing.id != session.id:
                raise errors.RequestError(msg=f"Slug '{public_slug}' is already in use")
            session.public_slug = public_slug
        
        await db.flush()
        await db.refresh(session)
        
        log.info(f"Published session {session_uuid}")
        return session

    @staticmethod
    async def unpublish_session(
        db: AsyncSession,
        session_uuid: str,
        user_id: int
    ) -> Optional[ChatSession]:
        """
        Make a session private.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param user_id: User ID for ownership verification
        :return: Updated ChatSession or None
        """
        session = await chat_session_dao.get_by_uuid_and_user(db, session_uuid, user_id)
        if not session:
            return None
        
        session.is_public = False
        session.public_slug = None
        
        await db.flush()
        await db.refresh(session)
        
        log.info(f"Unpublished session {session_uuid}")
        return session

    @staticmethod
    async def get_public_session(
        db: AsyncSession,
        session_uuid: str
    ) -> Optional[ChatSession]:
        """
        Get a public session by UUID (no auth required).
        
        :param db: Database session
        :param session_uuid: Session UUID
        :return: ChatSession if public, None otherwise
        """
        return await chat_session_dao.get_public_session(db, session_uuid)

    @staticmethod
    async def get_by_public_slug(
        db: AsyncSession,
        slug: str
    ) -> Optional[ChatSession]:
        """
        Get a public session by its public slug.
        
        :param db: Database session
        :param slug: Public URL slug
        :return: ChatSession if found and public, None otherwise
        """
        return await chat_session_dao.get_by_public_slug(db, slug)

    # =========================================================================
    # Deletion
    # =========================================================================

    @staticmethod
    async def delete_session(
        db: AsyncSession,
        session_uuid: str,
        user_id: int
    ) -> bool:
        """
        Soft delete a session.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param user_id: User ID for ownership verification
        :return: True if deleted, False otherwise
        """
        result = await chat_session_dao.soft_delete_by_uuid(db, session_uuid, user_id)
        if result:
            log.info(f"Deleted session {session_uuid}")
        return result

    # =========================================================================
    # Event Operations
    # =========================================================================

    @staticmethod
    async def get_session_events(
        db: AsyncSession,
        session_uuid: str,
        user_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 100
    ) -> Tuple[Sequence[ChatEvent], int]:
        """
        Get events for a session.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param user_id: Optional user ID for ownership verification
        :param page: Page number
        :param per_page: Items per page
        :return: Tuple of (events, total_count)
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return [], 0
        
        if user_id and session.user_id != user_id:
            # Check if public
            if not session.is_public:
                raise errors.ForbiddenError(msg="Session not accessible")
        
        return await chat_event_dao.get_session_events(
            db=db,
            session_id=session.id,
            page=page,
            per_page=per_page
        )

    @staticmethod
    async def add_user_message(
        db: AsyncSession,
        session_uuid: str,
        message: str,
        file_ids: Optional[List[str]] = None,
        run_id: Optional[str] = None
    ) -> Optional[ChatEvent]:
        """
        Add a user message event to the session.
        
        Also updates the session name from the first message and increments message count.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param message: Message content
        :param file_ids: Optional attached file IDs
        :param run_id: Optional agent run ID
        :return: Created ChatEvent or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return None
        
        # Create user message event
        event = await chat_event_dao.create_user_message(
            db=db,
            session_id=session.id,
            text=message,
            file_ids=file_ids,
            run_id=run_id
        )
        
        # Update session name from first message
        if not session.name:
            await ChatSessionService.update_session_name_from_message(
                db, session.id, message
            )
        
        # Increment message count and update activity
        await chat_session_dao.increment_message_count(db, session.id)
        
        return event

    @staticmethod
    async def add_agent_message(
        db: AsyncSession,
        session_uuid: str,
        message: str,
        run_id: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: Optional[int] = None
    ) -> Optional[ChatEvent]:
        """
        Add an agent message event to the session.
        
        Also updates token usage for the session.
        
        :param db: Database session
        :param session_uuid: Session UUID
        :param message: Message content
        :param run_id: Optional agent run ID
        :param model_name: LLM model used
        :param prompt_tokens: Prompt tokens used
        :param completion_tokens: Completion tokens used
        :param latency_ms: Processing latency
        :return: Created ChatEvent or None
        """
        session = await chat_session_dao.get_by_uuid(db, session_uuid)
        if not session:
            return None
        
        # Create agent message event
        event = await chat_event_dao.create_agent_message(
            db=db,
            session_id=session.id,
            text=message,
            run_id=run_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )
        
        # Increment message count and update activity
        await chat_session_dao.increment_message_count(db, session.id)
        
        # Update token usage
        if prompt_tokens or completion_tokens:
            await chat_session_dao.update_token_usage(
                db=db,
                session_id=session.id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )
        
        return event

    @staticmethod
    async def to_session_info(session: ChatSession) -> Dict[str, Any]:
        """
        Convert ChatSession to II-Agent SessionInfo-compatible format.
        
        :param session: ChatSession instance
        :return: SessionInfo-compatible dict
        """
        return session.to_session_info()


# Singleton instance
chat_session_service: ChatSessionService = ChatSessionService()
