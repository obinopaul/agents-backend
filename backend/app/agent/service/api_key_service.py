"""API Key service for tool server authentication.

Provides functions to create, validate, and manage API keys.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.user import User
from backend.app.agent.model.agent_models import APIKey

logger = logging.getLogger(__name__)


async def create_api_key(
    *,
    db_session: AsyncSession,
    user_id: int,
    name: str = "Default",
    expires_at: Optional[datetime] = None,
) -> Optional[APIKey]:
    """Create a new API key for a user.

    Args:
        db_session: Database session
        user_id: User ID to create key for
        name: Friendly name for the key
        expires_at: Optional expiration datetime

    Returns:
        Created APIKey or None on error
    """
    try:
        api_key = APIKey(
            user_id=user_id,
            name=name,
            expires_at=expires_at,
        )
        db_session.add(api_key)
        await db_session.flush()
        await db_session.refresh(api_key)
        
        logger.info(f"Created API key for user {user_id}: {api_key.api_key[:20]}...")
        return api_key

    except Exception as e:
        logger.error(f"Error creating API key for user {user_id}: {e}", exc_info=True)
        return None


async def get_user_by_api_key(
    *, db_session: AsyncSession, api_key: str
) -> Optional[User]:
    """Resolve a user from their API key.

    Args:
        db_session: Database session
        api_key: The API key to validate

    Returns:
        User object if valid, None if invalid or expired
    """
    try:
        result = await db_session.execute(
            select(APIKey)
            .options(selectinload(APIKey.user))
            .where(
                APIKey.api_key == api_key,
                APIKey.is_active == True,
            )
        )
        api_key_obj = result.scalar_one_or_none()

        if not api_key_obj:
            logger.debug(f"API key not found or inactive: {api_key[:20]}...")
            return None

        # Check expiration
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
            logger.debug(f"API key expired: {api_key[:20]}...")
            return None

        # Check user is active
        if not api_key_obj.user or api_key_obj.user.status != 1:
            logger.debug(f"User not active for API key: {api_key[:20]}...")
            return None

        # Update last used timestamp
        api_key_obj.last_used_at = datetime.now(timezone.utc)

        return api_key_obj.user

    except Exception as e:
        logger.error(f"Error validating API key: {e}", exc_info=True)
        return None


async def get_user_api_keys(
    *, db_session: AsyncSession, user_id: int
) -> list[APIKey]:
    """Get all API keys for a user.

    Args:
        db_session: Database session
        user_id: User ID

    Returns:
        List of APIKey objects
    """
    try:
        result = await db_session.execute(
            select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    except Exception as e:
        logger.error(f"Error getting API keys for user {user_id}: {e}", exc_info=True)
        return []


async def revoke_api_key(
    *, db_session: AsyncSession, key_id: int, user_id: int
) -> bool:
    """Revoke (deactivate) an API key.

    Args:
        db_session: Database session
        key_id: API key ID to revoke
        user_id: User ID (for authorization check)

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db_session.execute(
            update(APIKey)
            .where(APIKey.id == key_id, APIKey.user_id == user_id)
            .values(is_active=False)
            .returning(APIKey.id)
        )
        
        revoked = result.first()
        if revoked:
            logger.info(f"Revoked API key {key_id} for user {user_id}")
            return True
        else:
            logger.warning(f"API key {key_id} not found for user {user_id}")
            return False

    except Exception as e:
        logger.error(f"Error revoking API key {key_id}: {e}", exc_info=True)
        return False


async def delete_api_key(
    *, db_session: AsyncSession, key_id: int, user_id: int
) -> bool:
    """Permanently delete an API key.

    Args:
        db_session: Database session
        key_id: API key ID to delete
        user_id: User ID (for authorization check)

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db_session.execute(
            select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id)
        )
        api_key = result.scalar_one_or_none()
        
        if api_key:
            await db_session.delete(api_key)
            logger.info(f"Deleted API key {key_id} for user {user_id}")
            return True
        else:
            logger.warning(f"API key {key_id} not found for user {user_id}")
            return False

    except Exception as e:
        logger.error(f"Error deleting API key {key_id}: {e}", exc_info=True)
        return False
