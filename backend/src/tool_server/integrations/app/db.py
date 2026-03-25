"""Database integration for tool_server.

This module provides database access for the tool server, using the
real implementations from the backend agent services.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

# Import real implementations from backend services
from backend.app.admin.model.user import User
from backend.app.agent.service.api_key_service import get_user_by_api_key as _get_user_by_api_key
from backend.app.agent.service.credit_service import deduct_user_credits as _deduct_user_credits
from backend.app.agent.service.metrics_service import accumulate_session_metrics as _accumulate_session_metrics

logger = logging.getLogger(__name__)


# Re-export User for compatibility with main.py
__all__ = ['User', 'get_user_by_api_key', 'apply_tool_usage']


async def get_user_by_api_key(api_key: str) -> Optional[User]:
    """Resolve a user from their API key.
    
    This is a wrapper that creates a database session and calls the real service.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        User object if valid, None if invalid or expired
    """
    from backend.database.db_mysql import async_db_session
    
    if not api_key:
        return None
    
    try:
        async with async_db_session() as db:
            user = await _get_user_by_api_key(db_session=db, api_key=api_key)
            if user:
                await db.commit()  # Commit the last_used_at update
            return user
    except Exception as e:
        logger.error(f"Error validating API key: {e}", exc_info=True)
        return None


async def apply_tool_usage(user_id: str, session_id: str, amount: float) -> bool:
    """Apply tool usage to the user and session.
    
    This is the main entry point for billing, called after each tool use.
    
    Args:
        user_id: User ID (will be converted to int)
        session_id: Session ID
        amount: Credit amount to deduct
        
    Returns:
        True if both session and user credits were applied successfully
    """
    from backend.database.db_mysql import async_db_session
    
    if amount <= 0:
        return True
    
    try:
        # Convert user_id to int if it's a string
        uid = int(user_id) if isinstance(user_id, str) else user_id
        
        async with async_db_session() as db:
            # Track session metrics
            await _accumulate_session_metrics(
                db_session=db,
                session_id=session_id,
                credits=-amount,  # Negative = consumption
            )
            
            # Deduct from user's credits
            success = await _deduct_user_credits(
                db_session=db,
                user_id=uid,
                amount=amount,
                description=f"Tool usage for session {session_id}",
            )
            
            if success:
                await db.commit()
                logger.info(f"Applied {amount} credits for user {uid}, session {session_id}")
            else:
                logger.warning(f"Failed to deduct credits for user {uid}")
            
            return success
            
    except Exception as e:
        logger.error(f"Failed to apply tool usage: {e}", exc_info=True)
        return False
