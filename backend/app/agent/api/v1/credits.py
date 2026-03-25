"""Credit management API endpoints."""

from typing import Any
from fastapi import APIRouter, HTTPException, status, Query, Request

from backend.database.db_mysql import CurrentSession
from backend.common.security.jwt import DependsJwtAuth

from backend.app.agent.service.credit_service import (
    get_user_credits,
    get_user_credit_history,
    CreditBalance,
    CreditHistory,
    SessionCreditHistory,
)

router = APIRouter(prefix="/credits", tags=["Credits"])


@router.get("/balance", response_model=CreditBalance, dependencies=[DependsJwtAuth])
async def get_credit_balance(
    request: Request,
    db: CurrentSession,
) -> Any:
    """Get the current user's credit balance.
    
    Returns the user's regular credits, bonus credits, and total available.
    """
    # Get current user from JWT authentication (set by middleware)
    user_id = request.user.id
    
    credit_balance = await get_user_credits(db_session=db, user_id=user_id)

    if not credit_balance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User credit balance not found",
        )

    return credit_balance


@router.get("/usage", response_model=CreditHistory, dependencies=[DependsJwtAuth])
async def get_credit_usage(
    request: Request,
    db: CurrentSession,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
) -> Any:
    """Get the current user's credit usage by session with pagination.

    Args:
        page: Page number for pagination (1-indexed)
        per_page: Number of items per page (max 100)

    Returns:
        Paginated credit usage history with session details
    """
    # Get current user from JWT authentication
    user_id = request.user.id

    # Get current balance first
    credit_balance = await get_user_credits(db_session=db, user_id=user_id)

    if not credit_balance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User credit balance not found",
        )

    # Get session-based credit history with pagination
    session_history, total = await get_user_credit_history(
        db_session=db,
        user_id=user_id,
        page=page,
        per_page=per_page,
    )

    # Convert to Pydantic models
    sessions = [
        SessionCreditHistory(
            session_id=session["session_id"],
            session_title=session["session_title"],
            credits=session["credits"],
            updated_at=session["updated_at"],
        )
        for session in session_history
    ]

    return CreditHistory(
        sessions=sessions,
        total=total,
    )
