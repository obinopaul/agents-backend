"""Metrics service for tracking session token usage and costs.

Adapted from ii-agent metrics service for the FastAPI backend.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.model.agent_models import SessionMetrics

logger = logging.getLogger(__name__)


async def accumulate_session_metrics(
    *, db_session: AsyncSession, session_id: str, credits: float
) -> Optional[SessionMetrics]:
    """Accumulate credits for a session by adding to existing total.

    NOTE: Credits should be passed as NEGATIVE values to represent consumption.
    The function uses += operator, so negative values will decrease the session total.
    For example: passing credits=-5.0 will reduce the session's credit balance by 5.

    Args:
        db_session: Database session
        session_id: The session ID to accumulate credits for
        credits: Number of credits to add to the session (pass negative values for consumption)
        
    Returns:
        Updated SessionMetrics record or None on error
    """
    try:
        # Check if metrics record exists
        metrics_record = (
            await db_session.execute(
                select(SessionMetrics).where(SessionMetrics.session_id == session_id)
            )
        ).scalar_one_or_none()

        if metrics_record:
            # Accumulate to existing record
            metrics_record.credits += credits
            metrics_record.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record with initial credits
            metrics_record = SessionMetrics(
                session_id=session_id,
                credits=credits,
            )
            db_session.add(metrics_record)
            await db_session.flush()
            await db_session.refresh(metrics_record)

        logger.debug(f"Accumulated {credits} credits for session {session_id}")
        return metrics_record
        
    except Exception as e:
        logger.error(f"Error accumulating metrics for session {session_id}: {e}", exc_info=True)
        return None


async def get_session_metrics(
    *, db_session: AsyncSession, session_id: str
) -> Optional[Dict[str, Any]]:
    """Get credits metrics for a specific session.

    Args:
        db_session: Database session
        session_id: The session ID to get credits for

    Returns:
        Dictionary containing session credits or None if not found
    """
    try:
        metrics = (
            await db_session.execute(
                select(SessionMetrics).where(SessionMetrics.session_id == session_id)
            )
        ).scalar_one_or_none()

        if metrics:
            return {
                "session_id": metrics.session_id,
                "credits": metrics.credits,
                "total_prompt_tokens": metrics.total_prompt_tokens,
                "total_completion_tokens": metrics.total_completion_tokens,
                "created_at": metrics.created_at,
                "updated_at": metrics.updated_at,
            }

        return None

    except Exception as e:
        logger.error(f"Error getting metrics for session {session_id}: {e}", exc_info=True)
        return None


async def update_token_usage(
    *,
    db_session: AsyncSession,
    session_id: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> bool:
    """Update token usage for a session.

    Args:
        db_session: Database session
        session_id: The session ID
        prompt_tokens: Number of prompt tokens to add
        completion_tokens: Number of completion tokens to add

    Returns:
        True if successful, False otherwise
    """
    try:
        metrics_record = (
            await db_session.execute(
                select(SessionMetrics).where(SessionMetrics.session_id == session_id)
            )
        ).scalar_one_or_none()

        if metrics_record:
            metrics_record.total_prompt_tokens += prompt_tokens
            metrics_record.total_completion_tokens += completion_tokens
            metrics_record.updated_at = datetime.now(timezone.utc)
        else:
            metrics_record = SessionMetrics(
                session_id=session_id,
                total_prompt_tokens=prompt_tokens,
                total_completion_tokens=completion_tokens,
            )
            db_session.add(metrics_record)

        logger.debug(
            f"Updated token usage for session {session_id}: "
            f"+{prompt_tokens} prompt, +{completion_tokens} completion"
        )
        return True

    except Exception as e:
        logger.error(f"Error updating token usage for session {session_id}: {e}", exc_info=True)
        return False
