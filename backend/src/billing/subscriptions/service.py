"""
Subscription Service

Main orchestrator for all subscription operations.
Provides a unified interface for:
- Customer management
- Checkout session creation
- Subscription lifecycle (cancel, reactivate)
- Tier management and model access
- Billing portal
- Trial management
- Free tier auto-enrollment

Based on external_billing/subscriptions/service.py.
"""

import logging
from typing import Dict, Optional, List

from .handlers import (
    CustomerHandler,
    CheckoutHandler,
    LifecycleHandler,
    TierHandler,
    PortalHandler,
)
from .free_tier_service import FreeTierService
from .trial_service import TrialService

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Unified subscription management service.
    
    Acts as the main entry point for all subscription-related operations.
    Delegates to specialized handlers for specific tasks.
    
    Usage:
        from backend.src.billing.subscriptions import subscription_service
        
        # Create checkout for upgrade
        result = await subscription_service.create_checkout_session(
            account_id=user_id,
            price_id="price_xxx",
            success_url="/billing/success",
            cancel_url="/billing/cancel"
        )
        
        # Cancel subscription
        result = await subscription_service.cancel_subscription(user_id)
    """
    
    # =========================================================================
    # Customer Management
    # =========================================================================
    
    async def get_or_create_stripe_customer(self, account_id: str) -> str:
        """
        Get existing Stripe customer or create new one.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Stripe customer ID (cus_xxx)
        """
        return await CustomerHandler.get_or_create_stripe_customer(account_id)
    
    # =========================================================================
    # Checkout & Subscription Creation
    # =========================================================================
    
    async def create_checkout_session(
        self,
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        commitment_type: Optional[str] = None,
        locale: Optional[str] = None
    ) -> Dict:
        """
        Create Stripe checkout session for subscription.
        
        Handles multiple scenarios:
        - New subscription
        - Trial conversion
        - Free tier upgrade
        - Paid tier upgrade
        
        Args:
            account_id: User account UUID
            price_id: Stripe price ID
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            commitment_type: 'monthly' or 'yearly'
            locale: User locale for checkout page
            
        Returns:
            Dict with checkout_url, session_id, flow_type
        """
        return await CheckoutHandler.create_checkout_session(
            account_id, price_id, success_url, cancel_url, commitment_type, locale
        )
    
    # =========================================================================
    # Subscription Lifecycle
    # =========================================================================
    
    async def cancel_subscription(
        self,
        account_id: str,
        feedback: Optional[str] = None
    ) -> Dict:
        """
        Cancel subscription (downgrade to free at period end).
        
        User keeps access until end of billing period.
        
        Args:
            account_id: User account UUID
            feedback: Optional cancellation reason
            
        Returns:
            Dict with success, message, scheduled_date
        """
        return await LifecycleHandler.cancel_subscription(account_id, feedback)
    
    async def reactivate_subscription(self, account_id: str) -> Dict:
        """
        Reactivate a cancelled subscription.
        
        Undoes scheduled cancellation.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Dict with success and message
        """
        return await LifecycleHandler.reactivate_subscription(account_id)
    
    async def handle_subscription_change(
        self,
        subscription: Dict,
        previous_attributes: Optional[Dict] = None
    ) -> Dict:
        """
        Handle subscription change from webhook.
        
        Called when subscription.updated webhook is received.
        
        Args:
            subscription: Stripe subscription object
            previous_attributes: Changed attributes
            
        Returns:
            Processing result
        """
        return await LifecycleHandler.handle_subscription_change(
            subscription, previous_attributes
        )
    
    # =========================================================================
    # Tier & Model Access
    # =========================================================================
    
    async def get_user_subscription_tier(
        self,
        account_id: str,
        skip_cache: bool = False
    ) -> Dict:
        """
        Get subscription tier info for user.
        
        Args:
            account_id: User account UUID
            skip_cache: If True, bypass cache
            
        Returns:
            Dict with tier details (name, limits, models)
        """
        return await TierHandler.get_user_subscription_tier(account_id, skip_cache)
    
    async def get_allowed_models_for_user(
        self,
        user_id: str,
        include_disabled: bool = False
    ) -> List[str]:
        """
        Get list of LLM models user can access.
        
        Args:
            user_id: User account UUID
            include_disabled: Include disabled models
            
        Returns:
            List of model IDs
        """
        return await TierHandler.get_allowed_models_for_user(user_id, include_disabled)
    
    async def check_model_access(
        self,
        account_id: str,
        model_name: str
    ) -> Dict:
        """
        Check if user can access a specific model.
        
        Args:
            account_id: User account UUID
            model_name: Model identifier
            
        Returns:
            Dict with allowed and details
        """
        return await TierHandler.check_model_access(account_id, model_name)
    
    async def get_tier_limits(self, account_id: str) -> Dict:
        """
        Get resource limits for user's tier.
        
        Returns:
            Dict with thread_limit, project_limit, etc.
        """
        return await TierHandler.get_tier_limits(account_id)
    
    # =========================================================================
    # Billing Portal
    # =========================================================================
    
    async def create_portal_session(
        self,
        account_id: str,
        return_url: str
    ) -> Dict:
        """
        Create Stripe Customer Portal session.
        
        Args:
            account_id: User account UUID
            return_url: URL to return to after portal
            
        Returns:
            Dict with portal_url
        """
        return await PortalHandler.create_portal_session(account_id, return_url)
    
    # =========================================================================
    # Trial Management
    # =========================================================================
    
    async def get_trial_status(self, account_id: str) -> Dict:
        """
        Get trial eligibility and status.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Dict with trial status details
        """
        return await TrialService.get_trial_status(account_id)
    
    async def start_trial(
        self,
        account_id: str,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Start trial with checkout session.
        
        Args:
            account_id: User account UUID
            success_url: Redirect on success
            cancel_url: Redirect on cancel
            
        Returns:
            Dict with checkout_url
        """
        return await TrialService.start_trial(account_id, success_url, cancel_url)
    
    async def cancel_trial(self, account_id: str) -> Dict:
        """
        Cancel active trial.
        
        Returns:
            Dict with success status
        """
        return await TrialService.cancel_trial(account_id)
    
    # =========================================================================
    # Free Tier
    # =========================================================================
    
    async def ensure_free_tier_subscription(
        self,
        account_id: str,
        email: Optional[str] = None
    ) -> Dict:
        """
        Ensure user has at least free tier subscription.
        
        If no subscription exists, creates free tier.
        
        Args:
            account_id: User account UUID
            email: User's email
            
        Returns:
            Dict with tier info
        """
        return await FreeTierService.ensure_free_tier_subscription(account_id, email)
    
    # =========================================================================
    # Subscription Retrieval
    # =========================================================================
    
    async def get_subscription(self, account_id: str) -> Dict:
        """
        Get full subscription details for account.
        
        Returns:
            Dict with subscription info
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT 
                            tier,
                            stripe_subscription_id,
                            stripe_customer_id,
                            trial_status,
                            trial_ends_at,
                            balance,
                            expiring_credits,
                            non_expiring_credits,
                            scheduled_tier_change,
                            scheduled_change_date,
                            payment_status,
                            updated_at
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    return {'has_subscription': False}
                
                return {
                    'has_subscription': row.stripe_subscription_id is not None,
                    'tier': row.tier,
                    'subscription_id': row.stripe_subscription_id,
                    'customer_id': row.stripe_customer_id,
                    'trial_status': row.trial_status,
                    'trial_ends_at': row.trial_ends_at.isoformat() if row.trial_ends_at else None,
                    'balance': float(row.balance or 0),
                    'expiring_credits': float(row.expiring_credits or 0),
                    'non_expiring_credits': float(row.non_expiring_credits or 0),
                    'scheduled_tier_change': row.scheduled_tier_change,
                    'scheduled_change_date': row.scheduled_change_date.isoformat() if row.scheduled_change_date else None,
                    'payment_status': row.payment_status,
                    'updated_at': row.updated_at.isoformat() if row.updated_at else None
                }
                
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error getting subscription: {e}")
            return {'has_subscription': False, 'error': str(e)}
    
    async def sync_subscription(self, account_id: str) -> Dict:
        """
        Sync subscription state with Stripe.
        
        Useful for resolving discrepancies.
        
        Returns:
            Dict with sync result
        """
        from backend.src.billing.external.stripe import StripeAPIWrapper
        from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
        
        try:
            sub_info = await self.get_subscription(account_id)
            
            if not sub_info.get('subscription_id'):
                return {'success': True, 'message': 'No subscription to sync'}
            
            subscription = await StripeAPIWrapper.retrieve_subscription(
                sub_info['subscription_id']
            )
            
            # Process the subscription update
            await self.handle_subscription_change(subscription)
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            return {
                'success': True,
                'status': subscription.get('status'),
                'synced': True
            }
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Sync error: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
subscription_service = SubscriptionService()
