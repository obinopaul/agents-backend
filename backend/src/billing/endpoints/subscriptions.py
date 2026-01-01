"""
Subscription Endpoints

API endpoints for subscription management.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from backend.src.billing.subscriptions import subscription_service
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
from .dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing-subscriptions"])


# ============================================================================
# Request Models
# ============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request for checkout session creation."""
    tier_key: str
    success_url: str
    cancel_url: Optional[str] = None
    commitment_type: Optional[str] = None  # 'monthly', 'yearly', 'yearly_commitment'
    locale: Optional[str] = None


class CreatePortalRequest(BaseModel):
    """Request for customer portal session."""
    return_url: str


class CancelSubscriptionRequest(BaseModel):
    """Request for subscription cancellation."""
    feedback: Optional[str] = None


class ScheduleDowngradeRequest(BaseModel):
    """Request for tier downgrade."""
    target_tier_key: str
    commitment_type: Optional[str] = None


class StartTrialRequest(BaseModel):
    """Request for trial start."""
    success_url: str
    cancel_url: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutRequest,
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """
    Create Stripe checkout session for subscription.
    
    Handles:
    - New subscriptions
    - Tier upgrades
    - Trial conversions
    - Free tier auto-enrollment
    """
    try:
        from backend.src.billing.shared.config import get_tier_by_name
        
        tier = get_tier_by_name(request.tier_key)
        if not tier:
            raise HTTPException(status_code=400, detail="Invalid tier")
        
        # Handle free tier separately
        if tier.name == 'free':
            from backend.src.billing.subscriptions import ensure_free_tier_subscription
            result = await ensure_free_tier_subscription(user_id)
            if result.get('success'):
                await invalidate_account_state_cache(user_id)
                return {
                    'success': True,
                    'checkout_url': request.success_url,
                    'message': 'Successfully subscribed to free tier'
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.get('error', 'Failed to subscribe to free tier')
                )
        
        # Get price ID based on commitment type
        price_id = _get_price_id_for_tier(tier, request.commitment_type)
        
        result = await subscription_service.create_checkout_session(
            account_id=user_id,
            price_id=price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url or request.success_url,
            commitment_type=request.commitment_type,
            locale=request.locale
        )
        
        # Invalidate cache if subscription changed
        if result.get('flow_type') in ['upgrade', 'immediate']:
            await invalidate_account_state_cache(user_id)
        
        return {
            'success': True,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BILLING] Error creating checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-portal-session")
async def create_portal_session(
    request: CreatePortalRequest,
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """Create Stripe customer portal session."""
    try:
        result = await subscription_service.create_portal_session(
            user_id, request.return_url
        )
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error creating portal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel-subscription")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """
    Cancel subscription.
    
    User keeps access until end of billing period.
    """
    try:
        result = await subscription_service.cancel_subscription(
            user_id, request.feedback
        )
        await invalidate_account_state_cache(user_id)
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error cancelling: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reactivate-subscription")
async def reactivate_subscription(
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """Reactivate a cancelled subscription."""
    try:
        result = await subscription_service.reactivate_subscription(user_id)
        await invalidate_account_state_cache(user_id)
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error reactivating: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-subscription")
async def sync_subscription(
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """Sync subscription state with Stripe."""
    try:
        result = await subscription_service.sync_subscription(user_id)
        await invalidate_account_state_cache(user_id)
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error syncing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Trial Endpoints
# ============================================================================

@router.get("/trial/status")
async def get_trial_status(
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """Get trial eligibility and status."""
    try:
        return await subscription_service.get_trial_status(user_id)
    except Exception as e:
        logger.error(f"[BILLING] Error getting trial status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trial/start")
async def start_trial(
    request: StartTrialRequest,
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """Start free trial with checkout session."""
    try:
        result = await subscription_service.start_trial(
            user_id, request.success_url, request.cancel_url
        )
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error starting trial: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trial/cancel")
async def cancel_trial(
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """Cancel active trial."""
    try:
        result = await subscription_service.cancel_trial(user_id)
        await invalidate_account_state_cache(user_id)
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error cancelling trial: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Helpers
# ============================================================================

def _get_price_id_for_tier(tier, commitment_type: Optional[str]) -> str:
    """Get the appropriate price ID for a tier and commitment type."""
    from backend.core.conf import settings
    
    if commitment_type == 'yearly_commitment':
        # Look for yearly commitment price
        price_ids = [pid for pid in tier.price_ids if 'yearly_commitment' in pid.lower()]
        if price_ids:
            return price_ids[0]
    
    if commitment_type == 'yearly':
        # Get yearly price from settings
        if tier.name == 'tier_2_20':
            return getattr(settings, 'STRIPE_TIER_2_20_YEARLY_ID', tier.price_ids[0])
        elif tier.name == 'tier_6_50':
            return getattr(settings, 'STRIPE_TIER_6_50_YEARLY_ID', tier.price_ids[0])
        elif tier.name == 'tier_25_200':
            return getattr(settings, 'STRIPE_TIER_25_200_YEARLY_ID', tier.price_ids[0])
        else:
            price_ids = [pid for pid in tier.price_ids if 'yearly' in pid.lower() and 'commitment' not in pid.lower()]
            return price_ids[0] if price_ids else tier.price_ids[0]
    
    # Default to monthly
    price_ids = [pid for pid in tier.price_ids if 'yearly' not in pid.lower()]
    return price_ids[0] if price_ids else tier.price_ids[0]
