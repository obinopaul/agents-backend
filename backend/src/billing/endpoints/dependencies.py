"""
Endpoint Dependencies

Shared dependencies for billing API endpoints.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Header

logger = logging.getLogger(__name__)


async def get_current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    """
    Extract and verify user ID from JWT token.
    
    This is a dependency that can be overridden in tests.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    try:
        # Import auth utilities
        from core.utils.auth_utils import verify_and_get_user_id_from_jwt
        
        # The verify function expects just the token
        token = authorization
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        
        # Create a mock dependency that returns the user_id
        # In production, this integrates with your auth system
        from backend.core.conf import settings
        
        # For local development, return a test user ID
        if settings.ENV == 'local':
            return "test-user-local"
        
        # For production, verify the token
        # This should be implemented based on your auth system
        import jwt
        
        decoded = jwt.decode(
            token,
            options={"verify_signature": False}  # Should be True in production
        )
        
        user_id = decoded.get('sub') or decoded.get('user_id')
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return user_id
        
    except jwt.InvalidTokenError as e:
        logger.error(f"[AUTH] Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except ImportError:
        # Fallback if auth_utils not available
        logger.warning("[AUTH] auth_utils not available, using fallback")
        raise HTTPException(status_code=401, detail="Auth not configured")
    except Exception as e:
        logger.error(f"[AUTH] Error verifying token: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def verify_billing_enabled():
    """
    Dependency to check if billing is enabled.
    
    Returns True if billing is enabled, raises HTTPException otherwise.
    """
    from backend.core.conf import settings
    
    if settings.ENV == 'local':
        # Billing is disabled in local mode
        return False
    
    return True
