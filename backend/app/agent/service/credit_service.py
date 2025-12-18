"""Credit management service functions.

Adapted from ii-agent credit service for the FastAPI backend.
Provides atomic credit operations with bonus credits used first.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, update, case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.user import User
from backend.app.agent.model.agent_models import SessionMetrics

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for API responses
# =============================================================================

from pydantic import BaseModel, Field


class CreditBalance(BaseModel):
    """User's current credit balance."""
    user_id: int
    credits: float = Field(description="Current credit balance")
    bonus_credits: float = Field(description="Current bonus credit balance", default=0.0)
    total_credits: float = Field(description="Total available credits")
    updated_at: Optional[datetime] = None


class SessionCreditHistory(BaseModel):
    """Credit history for a specific session."""
    session_id: str
    session_title: str = Field(description="Name/title of the session", default="Untitled Session")
    credits: float = Field(description="Total credits used in this session")
    updated_at: Optional[datetime] = None


class CreditHistory(BaseModel):
    """User's credit transaction history with pagination."""
    sessions: list[SessionCreditHistory] = Field(default_factory=list)
    total: int = Field(description="Total number of sessions with credit usage")


# =============================================================================
# Credit Service Functions
# =============================================================================

async def get_user_credits(
    *, db_session: AsyncSession, user_id: int
) -> Optional[CreditBalance]:
    """Get the current credit balance for a user.

    Args:
        db_session: Database session
        user_id: User ID to get credits for

    Returns:
        CreditBalance object or None if user not found
    """
    try:
        result = await db_session.execute(
            select(User.credits, User.bonus_credits, User.last_login_time).where(
                User.id == user_id
            )
        )
        user_data = result.first()

        if user_data:
            return CreditBalance(
                user_id=user_id,
                credits=user_data.credits,
                bonus_credits=user_data.bonus_credits,
                total_credits=user_data.credits + user_data.bonus_credits,
                updated_at=user_data.last_login_time,
            )

        return None

    except Exception as e:
        logger.error(f"Error getting user credits for {user_id}: {e}", exc_info=True)
        raise


async def has_sufficient_credits(
    *, db_session: AsyncSession, user_id: int, amount: float
) -> bool:
    """Check if user has sufficient credits for a transaction.

    Args:
        db_session: Database session
        user_id: User ID to check
        amount: Amount of credits needed

    Returns:
        True if user has sufficient credits, False otherwise
    """
    try:
        credit_balance = await get_user_credits(db_session=db_session, user_id=user_id)
        if not credit_balance:
            return False

        return credit_balance.total_credits >= amount

    except Exception as e:
        logger.error(
            f"Error checking credit sufficiency for {user_id}: {e}", exc_info=True
        )
        return False


async def deduct_user_credits(
    *,
    db_session: AsyncSession,
    user_id: int,
    amount: float,
    description: Optional[str] = None,
) -> bool:
    """Deduct credits from a user's balance.

    Credits are deducted in the following order:
    1. First, deduct from bonus_credits
    2. If bonus_credits are insufficient, deduct remaining from regular credits
    3. Bonus credits never go below 0

    This operation is atomic - it uses a single SQL statement with CASE expressions
    to prevent race conditions.

    Args:
        db_session: Database session
        user_id: User ID to deduct credits from
        amount: Amount of credits to deduct (positive number)
        description: Optional description of the transaction

    Returns:
        True if deduction was successful, False otherwise
    """
    try:
        result = await db_session.execute(
            update(User)
            .where(
                (User.id == user_id)
                & ((User.credits + User.bonus_credits) >= amount)
            )
            .values(
                # If bonus_credits >= amount, deduct from bonus only
                # Otherwise, set bonus to 0 and deduct remaining from credits
                bonus_credits=case(
                    (User.bonus_credits >= amount, User.bonus_credits - amount),
                    else_=0.0,
                ),
                credits=case(
                    (User.bonus_credits >= amount, User.credits),
                    else_=User.credits - (amount - User.bonus_credits),
                ),
            )
            .returning(User.credits, User.bonus_credits)
        )

        updated_data = result.first()
        if updated_data:
            logger.info(
                f"Deducted {amount} credits from user {user_id}. "
                f"New balance: {updated_data.credits} (regular), "
                f"{updated_data.bonus_credits} (bonus)"
            )
            return True
        else:
            # Either user not found or insufficient credits
            check_result = await db_session.execute(
                select(User.credits, User.bonus_credits).where(User.id == user_id)
            )
            user_data = check_result.first()

            if not user_data:
                logger.error(f"User {user_id} not found")
            else:
                total = user_data.credits + user_data.bonus_credits
                logger.warning(
                    f"Insufficient credits for user {user_id}: "
                    f"requested {amount}, available {total}"
                )
            return False

    except SQLAlchemyError as e:
        logger.error(
            f"Database error deducting credits for {user_id}: {e}", exc_info=True
        )
        await db_session.rollback()
        return False
    except Exception as e:
        logger.error(f"Error deducting credits for {user_id}: {e}", exc_info=True)
        return False


async def add_user_credits(
    *,
    db_session: AsyncSession,
    user_id: int,
    amount: float,
    description: Optional[str] = None,
    is_bonus: bool = False,
) -> bool:
    """Add credits to a user's balance.

    This operation is atomic - uses a single SQL statement to prevent race conditions.

    Args:
        db_session: Database session
        user_id: User ID to add credits to
        amount: Amount of credits to add (positive number)
        description: Optional description of the transaction
        is_bonus: If True, add to bonus_credits; if False, add to regular credits

    Returns:
        True if addition was successful, False otherwise
    """
    try:
        if is_bonus:
            result = await db_session.execute(
                update(User)
                .where(User.id == user_id)
                .values(bonus_credits=User.bonus_credits + amount)
                .returning(User.credits, User.bonus_credits)
            )
        else:
            result = await db_session.execute(
                update(User)
                .where(User.id == user_id)
                .values(credits=User.credits + amount)
                .returning(User.credits, User.bonus_credits)
            )

        updated_data = result.first()
        if updated_data:
            await db_session.commit()
            credit_type = "bonus" if is_bonus else "regular"
            logger.info(
                f"Added {amount} {credit_type} credits to user {user_id}. "
                f"New balance: {updated_data.credits} (regular), "
                f"{updated_data.bonus_credits} (bonus)"
            )
            return True
        else:
            logger.error(f"Failed to add credits for user {user_id} - user not found")
            return False

    except SQLAlchemyError as e:
        logger.error(f"Database error adding credits for {user_id}: {e}", exc_info=True)
        await db_session.rollback()
        return False
    except Exception as e:
        logger.error(f"Error adding credits for {user_id}: {e}", exc_info=True)
        return False


async def set_user_credits(
    *,
    db_session: AsyncSession,
    user_id: int,
    amount: float,
    bonus_amount: Optional[float] = None,
) -> bool:
    """Set user's credit balance to a specific amount.

    Args:
        db_session: Database session
        user_id: User ID to set credits for
        amount: Amount of regular credits to set
        bonus_amount: Amount of bonus credits to set (if None, bonus credits unchanged)

    Returns:
        True if update was successful, False otherwise
    """
    try:
        update_values = {"credits": amount}
        if bonus_amount is not None:
            update_values["bonus_credits"] = bonus_amount

        result = await db_session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**update_values)
            .returning(User.credits, User.bonus_credits)
        )

        updated_data = result.first()
        if updated_data:
            await db_session.commit()
            logger.info(
                f"Set credits for user {user_id}. "
                f"New balance: {updated_data.credits} (regular), "
                f"{updated_data.bonus_credits} (bonus)"
            )
            return True
        else:
            logger.error(f"Failed to set credits for user {user_id}")
            return False

    except SQLAlchemyError as e:
        logger.error(
            f"Database error setting credits for {user_id}: {e}", exc_info=True
        )
        await db_session.rollback()
        return False
    except Exception as e:
        logger.error(f"Error setting credits for {user_id}: {e}", exc_info=True)
        return False


async def get_user_credit_history(
    *, db_session: AsyncSession, user_id: int, page: int = 1, per_page: int = 20
) -> tuple[list[dict], int]:
    """Get the credit usage history for a user from session metrics.

    Args:
        db_session: Database session
        user_id: User ID to get credit history for
        page: Page number for pagination (1-indexed)
        per_page: Number of items per page

    Returns:
        Tuple of (list of session credit usage, total count)
    """
    try:
        # For now, return empty history until sessions are properly linked to users
        # This will be enhanced when session management is integrated
        return [], 0

    except Exception as e:
        logger.error(f"Error getting credit history for {user_id}: {e}", exc_info=True)
        raise
