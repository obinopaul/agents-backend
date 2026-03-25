# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Chat Session REST API endpoints.

Provides endpoints for managing chat sessions:
- List user's sessions
- Get session details
- Delete sessions
- Get session events/history
- Publish/unpublish sessions
- Public session access (no auth)
"""

import math
import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.app.agent.crud.crud_chat_session import chat_session_dao
from backend.app.agent.crud.crud_chat_event import chat_event_dao
from backend.app.agent.service.chat_session_service import chat_session_service
from backend.app.agent.schema.chat_session import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionInfo,
    ChatSessionList,
    ChatSessionPublish,
    ChatEventInfo,
    ChatEventList,
    ChatHistoryMessage,
    ChatHistoryMessageList,
    ContentPart,
    FileInfo,
    DeleteResponse,
    SuccessResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/chat-sessions', tags=['Chat Sessions'])


# =============================================================================
# Session CRUD Endpoints
# =============================================================================

@router.get(
    '',
    summary='List user chat sessions',
    response_model=ResponseModel[ChatSessionList],
    dependencies=[DependsJwtAuth]
)
async def list_chat_sessions(
    request: Request,
    db: CurrentSession,
    query: Optional[str] = Query(None, description="Search in name/description"),
    status: Optional[str] = Query(None, description="Filter by status"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List the current user's chat sessions with pagination and optional filters.
    """
    user_id = request.user.id
    
    sessions, total = await chat_session_dao.get_user_sessions(
        db=db,
        user_id=user_id,
        search_term=query,
        status=status,
        agent_type=agent_type,
        page=page,
        per_page=per_page
    )
    
    session_infos = [
        ChatSessionInfo(
            id=s.uuid,
            user_id=s.user_id,
            name=s.name,
            description=s.description,
            status=s.status,
            agent_type=s.agent_type,
            sandbox_id=s.sandbox_id,
            workspace_dir=s.workspace_path,
            is_public=s.is_public,
            public_slug=s.public_slug,
            message_count=s.message_count or 0,
            total_tokens=s.total_tokens,
            total_credits_used=s.total_credits_used or 0.0,
            created_at=s.created_time,
            updated_at=s.updated_time,
            last_activity_at=s.last_activity_at,
        )
        for s in sessions
    ]
    
    return response_base.success(
        data=ChatSessionList(
            sessions=session_infos,
            total=total,
            page=page,
            per_page=per_page,
            pages=math.ceil(total / per_page) if total > 0 else 0
        )
    )


@router.post(
    '',
    summary='Create a new chat session',
    response_model=ResponseModel[ChatSessionInfo],
    dependencies=[DependsJwtAuth]
)
async def create_chat_session(
    request: Request,
    db: CurrentSession,
    data: ChatSessionCreate,
):
    """
    Create a new chat session for the current user.
    """
    session = await chat_session_service.create_session(
        db=db,
        user_id=request.user.id,
        name=data.name,
        agent_type=data.agent_type,
        llm_setting_id=data.llm_setting_id
    )
    await db.commit()
    
    return response_base.success(
        data=ChatSessionInfo(
            id=session.uuid,
            user_id=session.user_id,
            name=session.name,
            description=session.description,
            status=session.status,
            agent_type=session.agent_type,
            sandbox_id=session.sandbox_id,
            workspace_dir=session.workspace_path,
            is_public=session.is_public,
            public_slug=session.public_slug,
            message_count=session.message_count or 0,
            total_tokens=session.total_tokens,
            total_credits_used=session.total_credits_used or 0.0,
            created_at=session.created_time,
            updated_at=session.updated_time,
            last_activity_at=session.last_activity_at,
        )
    )


@router.get(
    '/{session_uuid}',
    summary='Get chat session details',
    response_model=ResponseModel[ChatSessionInfo],
    dependencies=[DependsJwtAuth]
)
async def get_chat_session(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
):
    """
    Get details of a specific chat session.
    """
    session = await chat_session_dao.get_by_uuid_and_user(
        db=db,
        uuid=session_uuid,
        user_id=request.user.id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return response_base.success(
        data=ChatSessionInfo(
            id=session.uuid,
            user_id=session.user_id,
            name=session.name,
            description=session.description,
            status=session.status,
            agent_type=session.agent_type,
            sandbox_id=session.sandbox_id,
            workspace_dir=session.workspace_path,
            is_public=session.is_public,
            public_slug=session.public_slug,
            message_count=session.message_count or 0,
            total_tokens=session.total_tokens,
            total_credits_used=session.total_credits_used or 0.0,
            created_at=session.created_time,
            updated_at=session.updated_time,
            last_activity_at=session.last_activity_at,
        )
    )


@router.patch(
    '/{session_uuid}',
    summary='Update chat session',
    response_model=ResponseModel[ChatSessionInfo],
    dependencies=[DependsJwtAuth]
)
async def update_chat_session(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
    data: ChatSessionUpdate,
):
    """
    Update a chat session's metadata.
    """
    update_data = data.model_dump(exclude_unset=True)
    
    session = await chat_session_dao.update_session_by_uuid(
        db=db,
        uuid=session_uuid,
        user_id=request.user.id,
        **update_data
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.commit()
    
    return response_base.success(
        data=ChatSessionInfo(
            id=session.uuid,
            user_id=session.user_id,
            name=session.name,
            description=session.description,
            status=session.status,
            agent_type=session.agent_type,
            sandbox_id=session.sandbox_id,
            workspace_dir=session.workspace_path,
            is_public=session.is_public,
            public_slug=session.public_slug,
            message_count=session.message_count or 0,
            total_tokens=session.total_tokens,
            total_credits_used=session.total_credits_used or 0.0,
            created_at=session.created_time,
            updated_at=session.updated_time,
            last_activity_at=session.last_activity_at,
        )
    )


@router.delete(
    '/{session_uuid}',
    summary='Delete chat session',
    response_model=ResponseModel[DeleteResponse],
    dependencies=[DependsJwtAuth]
)
async def delete_chat_session(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
):
    """
    Soft delete a chat session.
    """
    deleted = await chat_session_service.delete_session(
        db=db,
        session_uuid=session_uuid,
        user_id=request.user.id
    )
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.commit()
    
    return response_base.success(
        data=DeleteResponse(
            success=True,
            deleted=True,
            session_id=session_uuid
        )
    )


# =============================================================================
# Event Endpoints
# =============================================================================

@router.get(
    '/{session_uuid}/events',
    summary='Get session events/history',
    response_model=ResponseModel[ChatEventList],
    dependencies=[DependsJwtAuth]
)
async def get_chat_session_events(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """
    Get events (message history) for a session.
    """
    # Verify user owns the session
    session = await chat_session_dao.get_by_uuid_and_user(
        db=db,
        uuid=session_uuid,
        user_id=request.user.id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    events, total = await chat_event_dao.get_session_events(
        db=db,
        session_id=session.id,
        page=page,
        per_page=per_page
    )
    
    event_infos = [
        ChatEventInfo(
            id=e.uuid,
            session_id=session_uuid,
            type=e.event_type,
            role=e.role,
            content=e.content,
            text=e.text_content,
            run_id=e.run_id,
            tool_name=e.tool_name,
            tool_call_id=e.tool_call_id,
            file_ids=e.file_ids,
            tokens={
                'prompt': e.prompt_tokens,
                'completion': e.completion_tokens,
                'total': e.total_tokens
            } if e.total_tokens > 0 else None,
            model=e.model_name,
            latency_ms=e.latency_ms,
            error={'type': e.error_type, 'message': e.error_message} if e.error_type else None,
            created_at=e.created_at,
        )
        for e in events
    ]
    
    return response_base.success(
        data=ChatEventList(
            events=event_infos,
            total=total,
            page=page,
            per_page=per_page
        )
    )

# =============================================================================
# Messages Endpoints (Frontend ChatHistoryResponse format)
# =============================================================================

def _event_to_history_message(event, session_uuid: str) -> ChatHistoryMessage:
    """Convert a ChatEvent to a ChatHistoryMessage for frontend consumption."""
    # Extract text from event content or text_content
    text = event.text_content or ""
    if not text and event.content:
        text = event.content.get("text", "") if isinstance(event.content, dict) else str(event.content)

    # Build content parts array (frontend expects ContentPart[])
    content_parts = [ContentPart(type="text", text=text)]

    # Build file info list
    files = []
    if event.file_ids:
        for fid in event.file_ids:
            files.append(FileInfo(
                id=fid,
                file_name=fid,
                file_size=0,
                content_type="application/octet-stream",
                created_at=event.created_at.isoformat() if event.created_at else None,
            ))

    return ChatHistoryMessage(
        id=event.uuid,
        role=event.role or ("user" if event.event_type == "user_message" else "assistant"),
        content=content_parts,
        model=event.model_name,
        created_at=event.created_at.isoformat() if event.created_at else None,
        files=files,
        finish_reason="end_turn" if event.event_type == "agent_message" else None,
    )


@router.get(
    '/{session_uuid}/messages',
    summary='Get session message history (frontend format)',
    response_model=ResponseModel[ChatHistoryMessageList],
    dependencies=[DependsJwtAuth]
)
async def get_chat_session_messages(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """
    Get message history for a session in the format expected by the frontend.

    Returns { messages: [...], has_more, total_count } matching the
    frontend ChatHistoryResponse type. Only returns user_message and
    agent_message events, formatted with ContentPart[] content arrays.
    """
    # Verify user owns the session
    session = await chat_session_dao.get_by_uuid_and_user(
        db=db,
        uuid=session_uuid,
        user_id=request.user.id
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    events, total = await chat_event_dao.get_session_events(
        db=db,
        session_id=session.id,
        page=page,
        per_page=per_page,
        event_types=['user_message', 'agent_message'],
    )

    messages = [_event_to_history_message(e, session_uuid) for e in events]

    return response_base.success(
        data=ChatHistoryMessageList(
            messages=messages,
            has_more=(page * per_page) < total,
            total_count=total,
        )
    )


@router.get(
    '/{session_uuid}/public/messages',
    summary='Get public session messages (frontend format, no auth)',
    response_model=ResponseModel[ChatHistoryMessageList],
)
async def get_public_chat_session_messages(
    db: CurrentSession,
    session_uuid: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """
    Get message history for a public session (no auth required).
    Returns the same ChatHistoryResponse format as the authenticated endpoint.
    """
    session = await chat_session_dao.get_public_session(db, session_uuid)

    if not session:
        raise HTTPException(status_code=404, detail="Public session not found")

    events, total = await chat_event_dao.get_session_events(
        db=db,
        session_id=session.id,
        page=page,
        per_page=per_page,
        event_types=['user_message', 'agent_message'],
    )

    messages = [_event_to_history_message(e, session_uuid) for e in events]

    return response_base.success(
        data=ChatHistoryMessageList(
            messages=messages,
            has_more=(page * per_page) < total,
            total_count=total,
        )
    )


# =============================================================================
# Session Files Endpoint
# =============================================================================

@router.get(
    '/{session_uuid}/files',
    summary='Get session files',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def get_chat_session_files(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
):
    """
    Get files attached to a session.
    
    This endpoint retrieves all staged files associated with the given session
    (thread_id). Files are uploaded via the files API and attached to sessions
    when sent with chat messages.
    
    Returns:
        List of files with metadata including:
        - file_id: Unique file identifier
        - filename: Original filename
        - mime_type: MIME type
        - file_size: Size in bytes
        - status: Processing status
        - image_url: Signed URL for images (if applicable)
    """
    from sqlalchemy import select, and_
    from backend.app.agent.model.staged_file import StagedFile
    from backend.src.services.file_processing.storage import get_storage_backend
    
    SIGNED_URL_EXPIRY = 3600  # 1 hour
    
    # Verify user owns the session
    session = await chat_session_dao.get_by_uuid_and_user(
        db=db,
        uuid=session_uuid,
        user_id=request.user.id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Query staged files for this session (thread_id == session_uuid)
    query = select(StagedFile).where(
        and_(
            StagedFile.user_id == request.user.id,
            StagedFile.thread_id == session_uuid
        )
    ).order_by(StagedFile.created_at.desc())
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    # Build response with signed URLs for images
    storage = get_storage_backend()
    file_list = []
    
    for f in files:
        # Generate signed URL for images if storage supports it
        image_url = None
        if f.image_url:
            try:
                image_url = await storage.get_url(f.image_url, SIGNED_URL_EXPIRY)
            except Exception:
                image_url = f.image_url  # Fallback to raw path
        
        file_list.append({
            'id': f.file_id,
            'file_id': f.file_id,
            'filename': f.filename,
            'name': f.filename,  # II-Agent compatibility
            'mime_type': f.mime_type,
            'content_type': f.mime_type,  # II-Agent compatibility
            'file_size': f.file_size,
            'size': f.file_size,  # II-Agent compatibility
            'status': 'ready' if f.parse_status == 'completed' else f.parse_status,
            'image_url': image_url,
            'url': image_url or f.storage_path,  # II-Agent compatibility
            'is_image': f.is_image,
            'created_at': f.created_at.isoformat() if f.created_at else None,
        })
    
    logger.info(f"Retrieved {len(file_list)} files for session {session_uuid}")
    
    return response_base.success(data={
        'files': file_list,
        'total': len(file_list)
    })


# =============================================================================
# Publishing Endpoints
# =============================================================================

@router.post(
    '/{session_uuid}/publish',
    summary='Make session public',
    response_model=ResponseModel[ChatSessionInfo],
    dependencies=[DependsJwtAuth]
)
async def publish_chat_session(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
    data: ChatSessionPublish = ChatSessionPublish(),
):
    """
    Make a session publicly accessible.
    """
    session = await chat_session_service.publish_session(
        db=db,
        session_uuid=session_uuid,
        user_id=request.user.id,
        public_slug=data.public_slug
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.commit()
    
    return response_base.success(
        data=ChatSessionInfo(
            id=session.uuid,
            user_id=session.user_id,
            name=session.name,
            description=session.description,
            status=session.status,
            agent_type=session.agent_type,
            sandbox_id=session.sandbox_id,
            workspace_dir=session.workspace_path,
            is_public=session.is_public,
            public_slug=session.public_slug,
            message_count=session.message_count or 0,
            total_tokens=session.total_tokens,
            total_credits_used=session.total_credits_used or 0.0,
            created_at=session.created_time,
            updated_at=session.updated_time,
            last_activity_at=session.last_activity_at,
        )
    )


@router.post(
    '/{session_uuid}/unpublish',
    summary='Make session private',
    response_model=ResponseModel[ChatSessionInfo],
    dependencies=[DependsJwtAuth]
)
async def unpublish_chat_session(
    request: Request,
    db: CurrentSession,
    session_uuid: str,
):
    """
    Make a session private (remove public access).
    """
    session = await chat_session_service.unpublish_session(
        db=db,
        session_uuid=session_uuid,
        user_id=request.user.id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.commit()
    
    return response_base.success(
        data=ChatSessionInfo(
            id=session.uuid,
            user_id=session.user_id,
            name=session.name,
            description=session.description,
            status=session.status,
            agent_type=session.agent_type,
            sandbox_id=session.sandbox_id,
            workspace_dir=session.workspace_path,
            is_public=session.is_public,
            public_slug=session.public_slug,
            message_count=session.message_count or 0,
            total_tokens=session.total_tokens,
            total_credits_used=session.total_credits_used or 0.0,
            created_at=session.created_time,
            updated_at=session.updated_time,
            last_activity_at=session.last_activity_at,
        )
    )


# =============================================================================
# Public Access Endpoints (No Auth Required)
# =============================================================================

@router.get(
    '/{session_uuid}/public',
    summary='Get public session (no auth)',
    response_model=ResponseModel[ChatSessionInfo],
)
async def get_public_chat_session(
    db: CurrentSession,
    session_uuid: str,
):
    """
    Get a public session's details (no authentication required).
    """
    session = await chat_session_dao.get_public_session(db, session_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Public session not found")
    
    return response_base.success(
        data=ChatSessionInfo(
            id=session.uuid,
            user_id=session.user_id,
            name=session.name,
            description=session.description,
            status=session.status,
            agent_type=session.agent_type,
            sandbox_id=None,  # Hide sandbox details for public access
            workspace_dir=None,
            is_public=session.is_public,
            public_slug=session.public_slug,
            message_count=session.message_count or 0,
            total_tokens=0,  # Hide token usage
            total_credits_used=0.0,
            created_at=session.created_time,
            updated_at=session.updated_time,
            last_activity_at=session.last_activity_at,
        )
    )


@router.get(
    '/{session_uuid}/public/events',
    summary='Get public session events (no auth)',
    response_model=ResponseModel[ChatEventList],
)
async def get_public_chat_session_events(
    db: CurrentSession,
    session_uuid: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """
    Get events (message history) for a public session (no authentication required).
    """
    session = await chat_session_dao.get_public_session(db, session_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Public session not found")
    
    events, total = await chat_event_dao.get_session_events(
        db=db,
        session_id=session.id,
        page=page,
        per_page=per_page
    )
    
    # Only include message events for public access (no tool details)
    event_infos = [
        ChatEventInfo(
            id=e.uuid,
            session_id=session_uuid,
            type=e.event_type,
            role=e.role,
            content=e.content if e.event_type in ('user_message', 'agent_message') else {},
            text=e.text_content,
            run_id=None,  # Hide run details
            tool_name=None,  # Hide tool details for public
            tool_call_id=None,
            file_ids=None,
            tokens=None,  # Hide token usage
            model=None,
            latency_ms=None,
            error=None,
            created_at=e.created_at,
        )
        for e in events
        if e.event_type in ('user_message', 'agent_message', 'system')
    ]
    
    return response_base.success(
        data=ChatEventList(
            events=event_infos,
            total=len(event_infos),  # Recalculate since we filtered
            page=page,
            per_page=per_page
        )
    )
