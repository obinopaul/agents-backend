# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
CRUD operations for Chat Events.

Provides database operations for managing chat events including:
- Create events from various sources
- Query events by session, run, type
- Event history retrieval
"""

from typing import Optional, Sequence, Tuple, List
from datetime import datetime

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.agent.model.chat_event import ChatEvent, ChatEventType
from backend.utils.timezone import timezone


class CRUDChatEvent(CRUDPlus[ChatEvent]):
    """CRUD operations for ChatEvent model."""

    # =========================================================================
    # Basic Operations
    # =========================================================================

    async def get(self, db: AsyncSession, event_id: int) -> Optional[ChatEvent]:
        """
        Get event by internal ID.
        
        :param db: Database session
        :param event_id: Internal event ID
        :return: ChatEvent or None
        """
        return await self.select_model(db, event_id)

    async def get_by_uuid(
        self, 
        db: AsyncSession, 
        uuid: str
    ) -> Optional[ChatEvent]:
        """
        Get event by UUID.
        
        :param db: Database session
        :param uuid: Event UUID
        :return: ChatEvent or None
        """
        result = await db.execute(
            select(ChatEvent).where(ChatEvent.uuid == uuid)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Create Operations
    # =========================================================================

    async def create_event(
        self,
        db: AsyncSession,
        session_id: int,
        event_type: str,
        content: dict,
        run_id: Optional[str] = None,
        role: Optional[str] = None,
        text_content: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        **kwargs
    ) -> ChatEvent:
        """
        Create a new chat event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param event_type: Event type
        :param content: Event content as dict
        :param run_id: Optional agent run ID
        :param role: Optional message role
        :param text_content: Optional plain text content
        :param tool_name: Optional tool name for tool events
        :param tool_call_id: Optional tool call ID
        :param kwargs: Additional fields
        :return: Created ChatEvent
        """
        event = ChatEvent(
            session_id=session_id,
            event_type=event_type,
            content=content,
            run_id=run_id,
            role=role,
            text_content=text_content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            **kwargs
        )
        db.add(event)
        await db.flush()
        await db.refresh(event)
        return event

    async def create_user_message(
        self,
        db: AsyncSession,
        session_id: int,
        text: str,
        file_ids: Optional[List[str]] = None,
        run_id: Optional[str] = None
    ) -> ChatEvent:
        """
        Create a user message event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param text: Message text
        :param file_ids: Optional list of attached file IDs
        :param run_id: Optional run ID
        :return: Created ChatEvent
        """
        content = {"text": text}
        if file_ids:
            content["files"] = file_ids
        
        return await self.create_event(
            db=db,
            session_id=session_id,
            event_type=ChatEventType.USER_MESSAGE.value,
            content=content,
            run_id=run_id,
            role="user",
            text_content=text,
            file_ids=file_ids
        )

    async def create_agent_message(
        self,
        db: AsyncSession,
        session_id: int,
        text: str,
        run_id: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: Optional[int] = None
    ) -> ChatEvent:
        """
        Create an agent message event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param text: Message text
        :param run_id: Optional run ID
        :param model_name: LLM model used
        :param prompt_tokens: Prompt tokens used
        :param completion_tokens: Completion tokens used
        :param latency_ms: Processing latency
        :return: Created ChatEvent
        """
        return await self.create_event(
            db=db,
            session_id=session_id,
            event_type=ChatEventType.AGENT_MESSAGE.value,
            content={"text": text},
            run_id=run_id,
            role="assistant",
            text_content=text,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )

    async def create_tool_call(
        self,
        db: AsyncSession,
        session_id: int,
        tool_name: str,
        tool_call_id: str,
        arguments: dict,
        run_id: Optional[str] = None
    ) -> ChatEvent:
        """
        Create a tool call event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param tool_name: Name of the tool being called
        :param tool_call_id: Unique tool call ID
        :param arguments: Tool call arguments
        :param run_id: Optional run ID
        :return: Created ChatEvent
        """
        return await self.create_event(
            db=db,
            session_id=session_id,
            event_type=ChatEventType.TOOL_CALL.value,
            content={"tool_name": tool_name, "arguments": arguments},
            run_id=run_id,
            role="tool",
            tool_name=tool_name,
            tool_call_id=tool_call_id
        )

    async def create_tool_result(
        self,
        db: AsyncSession,
        session_id: int,
        tool_name: str,
        tool_call_id: str,
        result: dict,
        run_id: Optional[str] = None,
        parent_event_id: Optional[int] = None,
        latency_ms: Optional[int] = None
    ) -> ChatEvent:
        """
        Create a tool result event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param tool_name: Name of the tool
        :param tool_call_id: Tool call ID this result is for
        :param result: Tool execution result
        :param run_id: Optional run ID
        :param parent_event_id: Optional parent tool call event ID
        :param latency_ms: Tool execution latency
        :return: Created ChatEvent
        """
        return await self.create_event(
            db=db,
            session_id=session_id,
            event_type=ChatEventType.TOOL_RESULT.value,
            content={"tool_name": tool_name, "result": result},
            run_id=run_id,
            role="tool",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            parent_event_id=parent_event_id,
            latency_ms=latency_ms
        )

    async def create_error_event(
        self,
        db: AsyncSession,
        session_id: int,
        error_type: str,
        error_message: str,
        run_id: Optional[str] = None
    ) -> ChatEvent:
        """
        Create an error event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param error_type: Type of error
        :param error_message: Error message
        :param run_id: Optional run ID
        :return: Created ChatEvent
        """
        return await self.create_event(
            db=db,
            session_id=session_id,
            event_type=ChatEventType.ERROR.value,
            content={"error_type": error_type, "message": error_message},
            run_id=run_id,
            error_type=error_type,
            error_message=error_message
        )

    async def create_system_event(
        self,
        db: AsyncSession,
        session_id: int,
        message: str,
        run_id: Optional[str] = None,
        **extra_content
    ) -> ChatEvent:
        """
        Create a system event.
        
        :param db: Database session
        :param session_id: Parent session ID
        :param message: System message
        :param run_id: Optional run ID
        :param extra_content: Additional content fields
        :return: Created ChatEvent
        """
        content = {"message": message}
        content.update(extra_content)
        
        return await self.create_event(
            db=db,
            session_id=session_id,
            event_type=ChatEventType.SYSTEM.value,
            content=content,
            run_id=run_id,
            role="system",
            text_content=message
        )

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_session_events(
        self,
        db: AsyncSession,
        session_id: int,
        page: int = 1,
        per_page: int = 100,
        event_types: Optional[List[str]] = None,
        order_dir: str = "asc"
    ) -> Tuple[Sequence[ChatEvent], int]:
        """
        Get paginated events for a session.
        
        :param db: Database session
        :param session_id: Session ID
        :param page: Page number
        :param per_page: Items per page
        :param event_types: Optional filter for event types
        :param order_dir: Order direction ('asc' for chronological)
        :return: Tuple of (events list, total count)
        """
        # Base filter
        filters = [ChatEvent.session_id == session_id]
        
        if event_types:
            filters.append(ChatEvent.event_type.in_(event_types))
        
        combined_filter = and_(*filters)
        
        # Get total count
        count_query = select(func.count()).select_from(ChatEvent).where(combined_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Build order clause
        order_clause = ChatEvent.created_at if order_dir == "asc" else desc(ChatEvent.created_at)
        
        # Get paginated results
        offset = (page - 1) * per_page
        query = (
            select(ChatEvent)
            .where(combined_filter)
            .order_by(order_clause)
            .offset(offset)
            .limit(per_page)
        )
        
        result = await db.execute(query)
        events = result.scalars().all()
        
        return events, total

    async def get_run_events(
        self,
        db: AsyncSession,
        session_id: int,
        run_id: str
    ) -> Sequence[ChatEvent]:
        """
        Get all events for a specific agent run.
        
        :param db: Database session
        :param session_id: Session ID
        :param run_id: Run ID
        :return: List of events for the run
        """
        result = await db.execute(
            select(ChatEvent)
            .where(
                and_(
                    ChatEvent.session_id == session_id,
                    ChatEvent.run_id == run_id
                )
            )
            .order_by(ChatEvent.created_at)
        )
        return result.scalars().all()

    async def get_messages_only(
        self,
        db: AsyncSession,
        session_id: int,
        limit: int = 100
    ) -> Sequence[ChatEvent]:
        """
        Get only message events (user and agent) for a session.
        
        :param db: Database session
        :param session_id: Session ID
        :param limit: Maximum number of messages
        :return: List of message events
        """
        result = await db.execute(
            select(ChatEvent)
            .where(
                and_(
                    ChatEvent.session_id == session_id,
                    ChatEvent.event_type.in_([
                        ChatEventType.USER_MESSAGE.value,
                        ChatEventType.AGENT_MESSAGE.value
                    ])
                )
            )
            .order_by(ChatEvent.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_tool_calls_by_run(
        self,
        db: AsyncSession,
        session_id: int,
        run_id: str
    ) -> Sequence[ChatEvent]:
        """
        Get tool call events for a specific run.
        
        :param db: Database session
        :param session_id: Session ID
        :param run_id: Run ID
        :return: List of tool call events
        """
        result = await db.execute(
            select(ChatEvent)
            .where(
                and_(
                    ChatEvent.session_id == session_id,
                    ChatEvent.run_id == run_id,
                    ChatEvent.event_type == ChatEventType.TOOL_CALL.value
                )
            )
            .order_by(ChatEvent.created_at)
        )
        return result.scalars().all()

    async def get_by_tool_call_id(
        self,
        db: AsyncSession,
        tool_call_id: str
    ) -> Optional[ChatEvent]:
        """
        Get event by tool call ID.
        
        :param db: Database session
        :param tool_call_id: Tool call ID
        :return: ChatEvent or None
        """
        result = await db.execute(
            select(ChatEvent).where(ChatEvent.tool_call_id == tool_call_id)
        )
        return result.scalar_one_or_none()

    async def get_last_event(
        self,
        db: AsyncSession,
        session_id: int
    ) -> Optional[ChatEvent]:
        """
        Get the most recent event in a session.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Most recent ChatEvent or None
        """
        result = await db.execute(
            select(ChatEvent)
            .where(ChatEvent.session_id == session_id)
            .order_by(desc(ChatEvent.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_last_user_message(
        self,
        db: AsyncSession,
        session_id: int
    ) -> Optional[ChatEvent]:
        """
        Get the most recent user message in a session.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Most recent user message or None
        """
        result = await db.execute(
            select(ChatEvent)
            .where(
                and_(
                    ChatEvent.session_id == session_id,
                    ChatEvent.event_type == ChatEventType.USER_MESSAGE.value
                )
            )
            .order_by(desc(ChatEvent.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Statistics Operations
    # =========================================================================

    async def get_session_token_usage(
        self,
        db: AsyncSession,
        session_id: int
    ) -> Tuple[int, int]:
        """
        Get total token usage for a session.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Tuple of (prompt_tokens, completion_tokens)
        """
        result = await db.execute(
            select(
                func.coalesce(func.sum(ChatEvent.prompt_tokens), 0),
                func.coalesce(func.sum(ChatEvent.completion_tokens), 0)
            )
            .where(ChatEvent.session_id == session_id)
        )
        row = result.one()
        return int(row[0]), int(row[1])

    async def count_session_messages(
        self,
        db: AsyncSession,
        session_id: int
    ) -> int:
        """
        Count messages in a session.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Message count
        """
        result = await db.execute(
            select(func.count())
            .select_from(ChatEvent)
            .where(
                and_(
                    ChatEvent.session_id == session_id,
                    ChatEvent.event_type.in_([
                        ChatEventType.USER_MESSAGE.value,
                        ChatEventType.AGENT_MESSAGE.value
                    ])
                )
            )
        )
        return result.scalar() or 0

    # =========================================================================
    # Delete Operations
    # =========================================================================

    async def delete_session_events(
        self,
        db: AsyncSession,
        session_id: int
    ) -> int:
        """
        Delete all events for a session.
        
        :param db: Database session
        :param session_id: Session ID
        :return: Number of deleted events
        """
        from sqlalchemy import delete
        result = await db.execute(
            delete(ChatEvent).where(ChatEvent.session_id == session_id)
        )
        return result.rowcount or 0


# Singleton instance
chat_event_dao: CRUDChatEvent = CRUDChatEvent(ChatEvent)
