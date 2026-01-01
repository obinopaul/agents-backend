"""
Account State Endpoint

Unified endpoint for all billing-related account data.
Combines credits, subscription, models, and limits into a single cached response.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query

from backend.src.billing.shared.config import TIERS, get_tier_by_name, is_model_allowed, CREDITS_PER_DOLLAR
from backend.src.billing.shared.cache_utils import (
    get_cached_account_state,
    cache_account_state,
    ACCOUNT_STATE_CACHE_TTL
)
from backend.src.billing.credits import check_and_refresh_daily_credits
from .dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing-account-state"])


@router.get("/account-state")
async def get_account_state(
    user_id: str = Depends(get_current_user_id),
    skip_cache: bool = Query(False, description="Bypass cache")
) -> Dict:
    """
    Get unified account state.
    
    Single source of truth for all billing-related frontend data:
    - Credit balance (daily, monthly, extra)
    - Subscription info (tier, status)
    - Available models
    - Resource limits
    
    Data cached for 5 minutes.
    """
    from backend.core.conf import settings
    
    # Local mode returns mock data
    if settings.ENV == 'local':
        return _get_local_mode_response()
    
    try:
        # Check cache
        if not skip_cache:
            cached = await get_cached_account_state(user_id)
            if cached:
                cached['_cache'] = {'cached': True, 'ttl_seconds': ACCOUNT_STATE_CACHE_TTL}
                return cached
        
        # Refresh daily credits if needed
        await check_and_refresh_daily_credits(user_id)
        
        # Build fresh state
        account_state = await _build_account_state(user_id)
        
        # Cache the result
        await cache_account_state(user_id, account_state, ttl=ACCOUNT_STATE_CACHE_TTL)
        
        account_state['_cache'] = {'cached': False, 'ttl_seconds': ACCOUNT_STATE_CACHE_TTL}
        return account_state
        
    except Exception as e:
        logger.error(f"[ACCOUNT_STATE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _build_account_state(user_id: str) -> Dict:
    """Build the complete account state response."""
    from backend.database.db import async_db_session
    from sqlalchemy import text
    
    async with async_db_session() as session:
        # Get credit account
        result = await session.execute(
            text("""
                SELECT 
                    tier, trial_status, trial_ends_at,
                    balance, daily_credits_balance, expiring_credits, non_expiring_credits,
                    stripe_subscription_id, stripe_customer_id,
                    last_daily_refresh, payment_status
                FROM credit_accounts
                WHERE account_id = :user_id
            """),
            {"user_id": uuid.UUID(user_id)}
        )
        account = result.fetchone()
    
    if not account:
        # Return empty state for new users
        return _get_empty_state()
    
    # Extract tier info
    tier_name = account.tier or 'none'
    tier_info = get_tier_by_name(tier_name) or TIERS.get('none')
    
    # Trial status
    is_trial = account.trial_status == 'active'
    
    # Balance calculations (stored in dollars, convert to credits)
    balance = float(account.balance or 0)
    daily = float(account.daily_credits_balance or 0)
    monthly = float(account.expiring_credits or 0)
    extra = float(account.non_expiring_credits or 0)
    
    # Convert to credits (100 credits = $1)
    daily_credits = daily * CREDITS_PER_DOLLAR
    monthly_credits = monthly * CREDITS_PER_DOLLAR
    extra_credits = extra * CREDITS_PER_DOLLAR
    total_credits = daily_credits + monthly_credits + extra_credits
    
    # Daily refresh info
    daily_refresh_info = None
    if tier_info and tier_info.daily_credit_config and tier_info.daily_credit_config.get('enabled'):
        refresh_hours = tier_info.daily_credit_config.get('refresh_interval_hours', 24)
        daily_amount = float(tier_info.daily_credit_config.get('amount', 0)) * CREDITS_PER_DOLLAR
        
        next_refresh = None
        seconds_until = None
        if account.last_daily_refresh:
            next_dt = account.last_daily_refresh + timedelta(hours=refresh_hours)
            next_refresh = next_dt.isoformat()
            diff = (next_dt - datetime.now(timezone.utc)).total_seconds()
            seconds_until = max(0, int(diff))
        
        daily_refresh_info = {
            'enabled': True,
            'daily_amount': daily_amount,
            'refresh_interval_hours': refresh_hours,
            'last_refresh': account.last_daily_refresh.isoformat() if account.last_daily_refresh else None,
            'next_refresh_at': next_refresh,
            'seconds_until_refresh': seconds_until
        }
    
    # Determine status
    if is_trial:
        status = 'trialing'
    elif tier_name in ['none', 'free']:
        status = 'active' if tier_name == 'free' else 'no_subscription'
    else:
        status = 'active'
    
    # Display name
    display_name = tier_info.display_name if tier_info else 'No Plan'
    if is_trial:
        display_name += ' (Trial)'
    
    # Get available models
    models = await _get_available_models(tier_name)
    
    # Get limits
    limits = _get_tier_limits(tier_info) if tier_info else {}
    
    return {
        'credits': {
            'total': total_credits,
            'daily': daily_credits,
            'monthly': monthly_credits,
            'extra': extra_credits,
            'can_run': total_credits >= 1,
            'daily_refresh': daily_refresh_info
        },
        'subscription': {
            'tier_key': tier_name,
            'tier_display_name': display_name,
            'status': status,
            'is_trial': is_trial,
            'trial_status': account.trial_status,
            'trial_ends_at': account.trial_ends_at.isoformat() if account.trial_ends_at else None,
            'can_purchase_credits': tier_info.can_purchase_credits if tier_info else False
        },
        'models': models,
        'limits': limits,
        'tier': {
            'name': tier_name,
            'display_name': tier_info.display_name if tier_info else 'Unknown',
            'monthly_credits': float(tier_info.monthly_credits) * CREDITS_PER_DOLLAR if tier_info else 0,
            'can_purchase_credits': tier_info.can_purchase_credits if tier_info else False
        }
    }


async def _get_available_models(tier_name: str) -> list:
    """Get models available for a tier."""
    try:
        from backend.src.llms import model_manager
        all_models = model_manager.list_available_models(include_disabled=True)
        
        models = []
        for model in all_models:
            allowed = is_model_allowed(tier_name, model.get('id', ''))
            models.append({
                'id': model.get('id'),
                'name': model.get('name'),
                'allowed': allowed,
                'context_window': model.get('context_window', 128000),
                'capabilities': model.get('capabilities', []),
                'priority': model.get('priority', 0),
                'recommended': model.get('recommended', False)
            })
        return models
    except ImportError:
        return []


def _get_tier_limits(tier_info) -> Dict:
    """Get resource limits for a tier."""
    return {
        'projects': {
            'max': tier_info.project_limit,
            'can_create': True
        },
        'threads': {
            'max': tier_info.thread_limit,
            'can_create': True
        },
        'concurrent_runs': {
            'limit': tier_info.concurrent_runs,
            'can_start': True
        }
    }


def _get_empty_state() -> Dict:
    """Get state for users without credit account."""
    return {
        'credits': {
            'total': 0,
            'daily': 0,
            'monthly': 0,
            'extra': 0,
            'can_run': False,
            'daily_refresh': None
        },
        'subscription': {
            'tier_key': 'none',
            'tier_display_name': 'No Plan',
            'status': 'no_subscription',
            'is_trial': False,
            'trial_status': None,
            'trial_ends_at': None,
            'can_purchase_credits': False
        },
        'models': [],
        'limits': {},
        'tier': {
            'name': 'none',
            'display_name': 'No Plan',
            'monthly_credits': 0,
            'can_purchase_credits': False
        }
    }


def _get_local_mode_response() -> Dict:
    """Get mock response for local development."""
    return {
        'credits': {
            'total': 999999,
            'daily': 200,
            'monthly': 999799,
            'extra': 0,
            'can_run': True,
            'daily_refresh': None
        },
        'subscription': {
            'tier_key': 'tier_25_200',
            'tier_display_name': 'Local Development',
            'status': 'active',
            'is_trial': False,
            'trial_status': None,
            'trial_ends_at': None,
            'can_purchase_credits': True
        },
        'models': [],
        'limits': {
            'projects': {'max': 99999, 'can_create': True},
            'threads': {'max': 99999, 'can_create': True},
            'concurrent_runs': {'limit': 99999, 'can_start': True}
        },
        'tier': {
            'name': 'tier_25_200',
            'display_name': 'Local Development',
            'monthly_credits': 40000,
            'can_purchase_credits': True
        },
        '_cache': {'cached': False, 'local_mode': True}
    }
