"""
Tier Handler

Manages subscription tier lookup and model access validation.
Features:
- Get user's current subscription tier
- Cache tier info for performance
- Get allowed models for user based on tier
- Trial status handling

Based on external_billing/subscriptions/handlers/tier.py.
"""

import logging
from typing import Dict, List, Optional

from backend.src.billing.shared.config import TIERS, get_tier_by_name, is_model_allowed
from backend.src.billing.shared.cache_utils import get_cached_account_state, cache_account_state

logger = logging.getLogger(__name__)


class TierHandler:
    """
    Handles subscription tier operations.
    
    Provides tier lookup with caching and model access validation.
    """
    
    # Cache TTL in seconds
    TIER_CACHE_TTL = 60
    
    @classmethod
    async def get_user_subscription_tier(
        cls,
        account_id: str,
        skip_cache: bool = False
    ) -> Dict:
        """
        Get subscription tier info for a user.
        
        Args:
            account_id: User account UUID
            skip_cache: If True, bypass cache
            
        Returns:
            Dict with tier details (name, limits, models, etc.)
        """
        cache_key = f"subscription_tier:{account_id}"
        
        # Check cache first
        if not skip_cache:
            cached = await get_cached_account_state(account_id)
            if cached and cached.get('tier_info'):
                return cached['tier_info']
        
        # Fetch from database
        tier_info = await cls._fetch_tier_info(account_id)
        
        # Cache the result
        await cache_account_state(account_id, {'tier_info': tier_info}, ttl=cls.TIER_CACHE_TTL)
        
        return tier_info
    
    @classmethod
    async def _fetch_tier_info(cls, account_id: str) -> Dict:
        """Fetch tier info from database."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT tier, trial_status
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                tier_name = 'none'
                trial_status = None
                
                if row:
                    tier_name = row.tier or 'none'
                    trial_status = row.trial_status
                
                # Handle trial users
                if trial_status == 'active' and tier_name == 'none':
                    # Trial users get trial tier benefits
                    tier_name = 'tier_2_20'  # Default trial tier
                    logger.debug(f"[TIER] Trial active for {account_id}, using trial tier")
                
                # Get tier object
                tier_obj = TIERS.get(tier_name, TIERS.get('none'))
                
                if not tier_obj:
                    tier_obj = list(TIERS.values())[0]  # Fallback to first tier
                
                return {
                    'name': tier_obj.name,
                    'display_name': tier_obj.display_name,
                    'credits': float(tier_obj.monthly_credits),
                    'can_purchase_credits': tier_obj.can_purchase_credits,
                    'models': tier_obj.models,
                    'project_limit': tier_obj.project_limit,
                    'thread_limit': tier_obj.thread_limit,
                    'concurrent_runs': tier_obj.concurrent_runs,
                    'custom_workers_limit': tier_obj.custom_workers_limit,
                    'scheduled_triggers_limit': tier_obj.scheduled_triggers_limit,
                    'app_triggers_limit': tier_obj.app_triggers_limit,
                    'is_trial': trial_status == 'active'
                }
                
        except Exception as e:
            logger.error(f"[TIER] Error fetching tier info for {account_id}: {e}")
            # Return minimal tier on error
            return {
                'name': 'none',
                'display_name': 'No Plan',
                'credits': 0,
                'can_purchase_credits': False,
                'models': [],
                'project_limit': 0,
                'thread_limit': 0,
                'concurrent_runs': 0,
                'is_trial': False
            }
    
    @classmethod
    async def get_allowed_models_for_user(
        cls,
        user_id: str,
        include_disabled: bool = False
    ) -> List[str]:
        """
        Get list of LLM models user can access based on tier.
        
        Args:
            user_id: User account UUID
            include_disabled: If True, include disabled models
            
        Returns:
            List of model IDs user can access
        """
        try:
            tier_info = await cls.get_user_subscription_tier(user_id)
            tier_name = tier_info.get('name', 'none')
            
            logger.debug(f"[ALLOWED_MODELS] User {user_id} tier: {tier_name}")
            
            tier_models = tier_info.get('models', [])
            
            if not tier_models:
                logger.debug(f"[ALLOWED_MODELS] User {user_id} has no model access")
                return []
            
            # Try to get available models from model manager
            try:
                from backend.src.llms import model_manager
                all_models = model_manager.list_available_models(include_disabled=include_disabled)
                
                allowed = []
                for model_data in all_models:
                    model_id = model_data.get("id")
                    if model_id and is_model_allowed(tier_name, model_id):
                        allowed.append(model_id)
                
                logger.debug(f"[ALLOWED_MODELS] User {user_id} has access to {len(allowed)} models")
                return allowed
                
            except ImportError:
                # If model manager not available, return tier's model list directly
                return tier_models
                
        except Exception as e:
            logger.error(f"[ALLOWED_MODELS] Error getting allowed models for {user_id}: {e}")
            return []
    
    @classmethod
    async def check_model_access(cls, account_id: str, model_name: str) -> Dict:
        """
        Check if user can access a specific model.
        
        Args:
            account_id: User account UUID
            model_name: Model to check access for
            
        Returns:
            Dict with allowed, tier_name, and message
        """
        tier_info = await cls.get_user_subscription_tier(account_id)
        tier_name = tier_info.get('name', 'none')
        
        allowed = is_model_allowed(tier_name, model_name)
        
        if allowed:
            return {
                'allowed': True,
                'tier_name': tier_name
            }
        else:
            available_models = tier_info.get('models', [])
            return {
                'allowed': False,
                'tier_name': tier_name,
                'message': f"Model '{model_name}' is not available on your current plan ({tier_info.get('display_name', tier_name)})",
                'available_models': available_models
            }
    
    @classmethod
    async def get_tier_limits(cls, account_id: str) -> Dict:
        """
        Get resource limits for user's tier.
        
        Returns:
            Dict with various limits (threads, projects, etc.)
        """
        tier_info = await cls.get_user_subscription_tier(account_id)
        
        return {
            'project_limit': tier_info.get('project_limit', 0),
            'thread_limit': tier_info.get('thread_limit', 0),
            'concurrent_runs': tier_info.get('concurrent_runs', 1),
            'custom_workers_limit': tier_info.get('custom_workers_limit', 0),
            'scheduled_triggers_limit': tier_info.get('scheduled_triggers_limit', 0),
            'app_triggers_limit': tier_info.get('app_triggers_limit', 0),
            'can_purchase_credits': tier_info.get('can_purchase_credits', False)
        }


# Convenience functions
async def get_user_subscription_tier(account_id: str, skip_cache: bool = False) -> Dict:
    """Get user's subscription tier info."""
    return await TierHandler.get_user_subscription_tier(account_id, skip_cache)


async def get_allowed_models_for_user(user_id: str) -> List[str]:
    """Get list of models user can access."""
    return await TierHandler.get_allowed_models_for_user(user_id)


async def check_model_access(account_id: str, model_name: str) -> Dict:
    """Check if user can access a model."""
    return await TierHandler.check_model_access(account_id, model_name)


async def get_tier_limits(account_id: str) -> Dict:
    """Get resource limits for user's tier."""
    return await TierHandler.get_tier_limits(account_id)
