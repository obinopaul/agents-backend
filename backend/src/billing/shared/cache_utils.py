"""
Cache Utilities for Billing

Provides cache key management and invalidation functions for billing data.
Uses Redis for caching account state, credit balances, and subscription info.
"""

import logging
from typing import Optional

# Cache TTL constants (in seconds)
ACCOUNT_STATE_CACHE_TTL: int = 300  # 5 minutes
CREDIT_BALANCE_CACHE_TTL: int = 300  # 5 minutes  
CREDIT_SUMMARY_CACHE_TTL: int = 300  # 5 minutes
SUBSCRIPTION_CACHE_TTL: int = 600  # 10 minutes
TIER_CACHE_TTL: int = 600  # 10 minutes

logger = logging.getLogger(__name__)


async def invalidate_account_state_cache(account_id: str) -> bool:
    """
    Invalidate the cached account state for a user.
    
    Should be called whenever:
    - Credits are added or deducted
    - Subscription changes
    - Tier changes
    - Daily credits are refreshed
    
    Args:
        account_id: The account/user ID whose cache should be invalidated
        
    Returns:
        True if cache was invalidated, False on error
    """
    try:
        from backend.database.redis import redis_client
        
        cache_key = f"account_state:{account_id}"
        await redis_client.delete(cache_key)
        
        logger.debug(f"[CACHE] Invalidated account state cache for {account_id}")
        return True
        
    except Exception as e:
        logger.warning(f"[CACHE] Failed to invalidate account state cache for {account_id}: {e}")
        return False


async def invalidate_credit_caches(account_id: str) -> bool:
    """
    Invalidate all credit-related caches for a user.
    
    This invalidates:
    - Credit balance cache
    - Credit summary cache
    - Account state cache
    
    Args:
        account_id: The account/user ID whose caches should be invalidated
        
    Returns:
        True if all caches were invalidated, False on error
    """
    try:
        from backend.database.redis import redis_client
        
        cache_keys = [
            f"credit_balance:{account_id}",
            f"credit_summary:{account_id}",
            f"account_state:{account_id}",
        ]
        
        for key in cache_keys:
            await redis_client.delete(key)
        
        logger.debug(f"[CACHE] Invalidated credit caches for {account_id}")
        return True
        
    except Exception as e:
        logger.warning(f"[CACHE] Failed to invalidate credit caches for {account_id}: {e}")
        return False


async def invalidate_subscription_cache(account_id: str) -> bool:
    """
    Invalidate subscription-related caches for a user.
    
    Args:
        account_id: The account/user ID whose subscription cache should be invalidated
        
    Returns:
        True if cache was invalidated, False on error
    """
    try:
        from backend.database.redis import redis_client
        
        cache_keys = [
            f"subscription:{account_id}",
            f"tier:{account_id}",
            f"account_state:{account_id}",
        ]
        
        for key in cache_keys:
            await redis_client.delete(key)
        
        logger.debug(f"[CACHE] Invalidated subscription caches for {account_id}")
        return True
        
    except Exception as e:
        logger.warning(f"[CACHE] Failed to invalidate subscription caches for {account_id}: {e}")
        return False


async def get_cached_value(key: str) -> Optional[dict]:
    """
    Get a cached value from Redis.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value as dict, or None if not found
    """
    try:
        from backend.database.redis import redis_client
        import json
        
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None
        
    except Exception as e:
        logger.warning(f"[CACHE] Failed to get cached value for {key}: {e}")
        return None


async def set_cached_value(key: str, value: dict, ttl: int = ACCOUNT_STATE_CACHE_TTL) -> bool:
    """
    Set a cached value in Redis.
    
    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        ttl: Time-to-live in seconds
        
    Returns:
        True if cached successfully, False on error
    """
    try:
        from backend.database.redis import redis_client
        import json
        
        await redis_client.setex(key, ttl, json.dumps(value))
        return True
        
    except Exception as e:
        logger.warning(f"[CACHE] Failed to set cached value for {key}: {e}")
        return False


async def cache_account_state(account_id: str, state: dict) -> bool:
    """
    Cache the account state for a user.
    
    Args:
        account_id: User/Account ID
        state: Account state dictionary to cache
        
    Returns:
        True if successful
    """
    return await set_cached_value(f"account_state:{account_id}", state, ACCOUNT_STATE_CACHE_TTL)


async def get_cached_account_state(account_id: str) -> Optional[dict]:
    """
    Get cached account state for a user.
    
    Args:
        account_id: User/Account ID
        
    Returns:
        Account state dict or None
    """
    return await get_cached_value(f"account_state:{account_id}")
