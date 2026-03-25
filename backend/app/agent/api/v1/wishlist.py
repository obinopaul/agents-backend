# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Wishlist API endpoints for session bookmarking.

Provides endpoints for managing user's wishlisted/bookmarked sessions:
- List wishlisted sessions
- Add session to wishlist
- Remove session from wishlist
"""

import math
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.app.agent.crud.crud_wishlist import wishlist_dao
from backend.app.agent.crud.crud_chat_session import chat_session_dao


logger = logging.getLogger(__name__)

router = APIRouter(prefix='/wishlist', tags=['Wishlist'])


# =============================================================================
# Response Schemas
# =============================================================================

class WishlistSessionInfo(BaseModel):
    """Information about a wishlisted session."""
    id: str
    session_id: str
    name: Optional[str] = None
    agent_type: Optional[str] = None
    workspace_dir: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    wishlisted_at: datetime


class WishlistResponse(BaseModel):
    """Response for wishlist listing."""
    sessions: List[WishlistSessionInfo]
    total: int
    page: int
    per_page: int
    pages: int


class WishlistStatusResponse(BaseModel):
    """Response for wishlist status check."""
    is_wishlisted: bool
    session_id: str


# =============================================================================
# Wishlist Endpoints
# =============================================================================

@router.get(
    '/sessions',
    summary='List wishlisted sessions',
    response_model=ResponseModel[WishlistResponse],
    dependencies=[DependsJwtAuth]
)
async def get_wishlist_sessions(
    request: Request,
    db: CurrentSession,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get all wishlisted sessions for the current user with pagination.

    Returns session details including name, agent type, and when it was wishlisted.
    """
    user_id = request.user.id

    # Get wishlist entries
    wishlists, total = await wishlist_dao.get_user_wishlist(
        db=db,
        user_id=user_id,
        page=page,
        per_page=per_page
    )

    # Build response with session details
    sessions = []
    for w in wishlists:
        # Get the session details
        session = await chat_session_dao.get_by_uuid(db, w.session_id)
        if session:
            sessions.append(WishlistSessionInfo(
                id=w.id,
                session_id=w.session_id,
                name=session.name,
                agent_type=session.agent_type,
                workspace_dir=session.workspace_path,
                message_count=session.message_count or 0,
                created_at=session.created_time,
                wishlisted_at=w.created_at
            ))

    return response_base.success(
        data=WishlistResponse(
            sessions=sessions,
            total=total,
            page=page,
            per_page=per_page,
            pages=math.ceil(total / per_page) if total > 0 else 0
        )
    )


@router.post(
    '/sessions/{session_id}',
    summary='Add session to wishlist',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def add_to_wishlist(
    session_id: str,
    request: Request,
    db: CurrentSession,
):
    """
    Add a session to the current user's wishlist.

    The session must exist and belong to the current user.
    If already wishlisted, returns success without error.
    """
    user_id = request.user.id

    # Verify session exists and belongs to user
    session = await chat_session_dao.get_by_uuid_and_user(db, session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if already wishlisted
    is_wishlisted = await wishlist_dao.is_wishlisted(db, user_id, session_id)
    if is_wishlisted:
        return response_base.success(msg="Already in wishlist")

    # Add to wishlist
    try:
        await wishlist_dao.add_to_wishlist(db, user_id, session_id)
        await db.commit()
        logger.info(f"User {user_id} added session {session_id} to wishlist")
        return response_base.success(msg="Added to wishlist")
    except Exception as e:
        logger.error(f"Error adding to wishlist: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to add to wishlist")


@router.delete(
    '/sessions/{session_id}',
    summary='Remove session from wishlist',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def remove_from_wishlist(
    session_id: str,
    request: Request,
    db: CurrentSession,
):
    """
    Remove a session from the current user's wishlist.

    Returns success even if the session wasn't in the wishlist.
    """
    user_id = request.user.id

    # Remove from wishlist
    removed = await wishlist_dao.remove_from_wishlist(db, user_id, session_id)
    await db.commit()

    if removed:
        logger.info(f"User {user_id} removed session {session_id} from wishlist")
        return response_base.success(msg="Removed from wishlist")
    else:
        return response_base.success(msg="Not in wishlist")


@router.get(
    '/sessions/{session_id}/status',
    summary='Check if session is wishlisted',
    response_model=ResponseModel[WishlistStatusResponse],
    dependencies=[DependsJwtAuth]
)
async def check_wishlist_status(
    session_id: str,
    request: Request,
    db: CurrentSession,
):
    """
    Check if a specific session is in the current user's wishlist.
    """
    user_id = request.user.id

    is_wishlisted = await wishlist_dao.is_wishlisted(db, user_id, session_id)

    return response_base.success(
        data=WishlistStatusResponse(
            is_wishlisted=is_wishlisted,
            session_id=session_id
        )
    )


@router.delete(
    '/sessions',
    summary='Clear entire wishlist',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def clear_wishlist(
    request: Request,
    db: CurrentSession,
):
    """
    Remove all sessions from the current user's wishlist.
    """
    user_id = request.user.id

    count = await wishlist_dao.clear_user_wishlist(db, user_id)
    await db.commit()

    logger.info(f"User {user_id} cleared wishlist ({count} sessions removed)")
    return response_base.success(msg=f"Cleared {count} sessions from wishlist")
