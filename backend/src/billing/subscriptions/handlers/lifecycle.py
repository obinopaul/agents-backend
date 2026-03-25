"""
Lifecycle Handler

Manages subscription lifecycle events including:
- Subscription cancellation (downgrade to free at period end)
- Subscription reactivation
- Status transitions (active, past_due, canceled)
- Webhook event processing for subscription changes

Based on external_billing/subscriptions/handlers/lifecycle.py.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.config import get_tier_by_price_id, get_tier_by_name
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
from backend.src.billing.shared.exceptions import BillingError, SubscriptionError

logger = logging.getLogger(__name__)


class LifecycleHandler:
    """
    Handles subscription lifecycle management.
    
    Supports:
    - Cancel subscription (schedule downgrade to free at period end)
    - Reactivate subscription (undo scheduled cancellation)
    - Handle subscription status changes from webhooks
    - Grace period handling for past_due subscriptions
    """
    
    @classmethod
    async def cancel_subscription(
        cls,
        account_id: str,
        feedback: Optional[str] = None
    ) -> Dict:
        """
        Cancel subscription by scheduling downgrade to free tier.
        
        User keeps access until end of billing period, then
        automatically converts to free tier.
        
        Args:
            account_id: User account UUID
            feedback: Optional cancellation reason
            
        Returns:
            Dict with success, message, scheduled_date
        """
        handler = cls()
        return await handler._cancel_subscription(account_id, feedback)
    
    async def _cancel_subscription(
        self,
        account_id: str,
        feedback: Optional[str] = None
    ) -> Dict:
        """Internal implementation of cancel_subscription."""
        logger.info(f"[CANCEL] Processing cancellation for {account_id}")
        
        # Get current subscription
        subscription_info = await self._get_subscription_info(account_id)
        
        if not subscription_info or not subscription_info.get('subscription_id'):
            raise SubscriptionError(
                code="NO_SUBSCRIPTION",
                message="No active subscription found"
            )
        
        subscription_id = subscription_info['subscription_id']
        current_tier = subscription_info.get('tier', 'unknown')
        
        # Don't cancel if already free tier
        if current_tier == 'free':
            return {
                'success': True,
                'message': 'Already on free tier',
                'already_cancelled': True
            }
        
        try:
            # Set subscription to cancel at period end
            subscription = await StripeAPIWrapper.cancel_subscription(
                subscription_id=subscription_id,
                cancel_immediately=False  # Cancel at period end
            )
            
            # Calculate when cancellation takes effect
            period_end = subscription.get('current_period_end')
            scheduled_date = None
            if period_end:
                scheduled_date = datetime.fromtimestamp(period_end, tz=timezone.utc)
            
            # Save cancellation feedback
            if feedback:
                await self._save_cancellation_feedback(account_id, subscription_id, feedback)
            
            # Update database with scheduled downgrade
            await self._update_scheduled_downgrade(
                account_id,
                target_tier='free',
                scheduled_date=scheduled_date
            )
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[CANCEL] Scheduled {account_id} for downgrade to free tier at {scheduled_date}")
            
            return {
                'success': True,
                'message': 'Your plan will be downgraded to the free tier at the end of your billing period',
                'scheduled_date': scheduled_date.isoformat() if scheduled_date else None,
                'downgrade_to_free': True
            }
            
        except Exception as e:
            logger.error(f"[CANCEL] Failed to cancel subscription for {account_id}: {e}")
            raise SubscriptionError(
                code="CANCEL_FAILED",
                message=f"Failed to cancel subscription: {e}",
                details={"account_id": account_id}
            )
    
    @classmethod
    async def reactivate_subscription(cls, account_id: str) -> Dict:
        """
        Reactivate a cancelled subscription.
        
        Undoes scheduled cancellation so subscription continues.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Dict with success and message
        """
        handler = cls()
        return await handler._reactivate_subscription(account_id)
    
    async def _reactivate_subscription(self, account_id: str) -> Dict:
        """Internal implementation of reactivate_subscription."""
        logger.info(f"[REACTIVATE] Processing reactivation for {account_id}")
        
        subscription_info = await self._get_subscription_info(account_id)
        
        if not subscription_info or not subscription_info.get('subscription_id'):
            raise SubscriptionError(
                code="NO_SUBSCRIPTION",
                message="No subscription found to reactivate"
            )
        
        subscription_id = subscription_info['subscription_id']
        
        try:
            # Remove cancel_at_period_end flag
            subscription = await StripeAPIWrapper.modify_subscription(
                subscription_id,
                cancel_at_period_end=False
            )
            
            # Clear scheduled changes in database
            await self._clear_scheduled_changes(account_id)
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[REACTIVATE] Successfully reactivated subscription for {account_id}")
            
            return {
                'success': True,
                'message': 'Subscription reactivated successfully',
                'status': subscription.get('status', 'active')
            }
            
        except Exception as e:
            logger.error(f"[REACTIVATE] Failed to reactivate for {account_id}: {e}")
            raise SubscriptionError(
                code="REACTIVATE_FAILED",
                message=f"Failed to reactivate subscription: {e}"
            )
    
    @classmethod
    async def handle_subscription_change(
        cls,
        subscription: Dict,
        previous_attributes: Optional[Dict] = None
    ) -> Dict:
        """
        Handle subscription change from webhook.
        
        Called when subscription.updated webhook is received.
        Handles:
        - Status changes (active -> past_due -> canceled)
        - Tier upgrades/downgrades
        - Renewal processing
        
        Args:
            subscription: Stripe subscription object
            previous_attributes: Changed attributes (from webhook)
            
        Returns:
            Dict with processing result
        """
        handler = cls()
        return await handler._handle_subscription_change(subscription, previous_attributes)
    
    async def _handle_subscription_change(
        self,
        subscription: Dict,
        previous_attributes: Optional[Dict] = None
    ) -> Dict:
        """Internal implementation of handle_subscription_change."""
        subscription_id = subscription.get('id')
        status = subscription.get('status')
        customer_id = subscription.get('customer')
        
        logger.info(f"[SUBSCRIPTION] Processing change for {subscription_id}, status: {status}")
        
        # Get account_id from subscription metadata or customer lookup
        account_id = await self._get_account_id_from_subscription(subscription, customer_id)
        
        if not account_id:
            logger.warning(f"[SUBSCRIPTION] Could not find account for subscription {subscription_id}")
            return {'success': False, 'reason': 'account_not_found'}
        
        # Get price/tier info
        price_id = None
        if subscription.get('items', {}).get('data'):
            price_id = subscription['items']['data'][0]['price']['id']
        
        tier_info = get_tier_by_price_id(price_id) if price_id else None
        new_tier = tier_info.name if tier_info else 'none'
        
        # Handle different status transitions
        if status == 'past_due':
            await self._handle_past_due(account_id, subscription)
        elif status == 'canceled':
            await self._handle_canceled(account_id, subscription)
        elif status == 'active':
            await self._handle_active(account_id, subscription, new_tier)
        
        # Invalidate caches
        await invalidate_account_state_cache(account_id)
        
        return {
            'success': True,
            'account_id': account_id,
            'status': status,
            'tier': new_tier
        }
    
    async def _handle_past_due(self, account_id: str, subscription: Dict) -> None:
        """Handle subscription entering past_due (payment failed)."""
        logger.warning(f"[GRACE PERIOD] Subscription for {account_id} is past_due")
        
        # Update payment status in database
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            await session.execute(
                text("""
                    UPDATE credit_accounts
                    SET payment_status = 'past_due',
                        updated_at = :now
                    WHERE account_id = :account_id::uuid
                """),
                {"account_id": account_id, "now": datetime.now(timezone.utc)}
            )
            await session.commit()
        
        # Note: Credits are NOT revoked during grace period
        # User keeps access until subscription is fully canceled
    
    async def _handle_canceled(self, account_id: str, subscription: Dict) -> None:
        """Handle subscription being fully canceled."""
        logger.info(f"[CANCELED] Subscription for {account_id} is now canceled")
        
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            # Downgrade to free tier
            await session.execute(
                text("""
                    UPDATE credit_accounts
                    SET tier = 'free',
                        stripe_subscription_id = NULL,
                        payment_status = 'canceled',
                        scheduled_tier_change = NULL,
                        scheduled_change_date = NULL,
                        updated_at = :now
                    WHERE account_id = :account_id::uuid
                """),
                {"account_id": account_id, "now": datetime.now(timezone.utc)}
            )
            await session.commit()
        
        logger.info(f"[CANCELED] Downgraded {account_id} to free tier")
    
    async def _handle_active(self, account_id: str, subscription: Dict, new_tier: str) -> None:
        """Handle subscription becoming/remaining active."""
        logger.info(f"[ACTIVE] Subscription for {account_id} is active, tier: {new_tier}")
        
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            await session.execute(
                text("""
                    UPDATE credit_accounts
                    SET tier = :tier,
                        stripe_subscription_id = :sub_id,
                        payment_status = 'active',
                        updated_at = :now
                    WHERE account_id = :account_id::uuid
                """),
                {
                    "account_id": account_id,
                    "tier": new_tier,
                    "sub_id": subscription.get('id'),
                    "now": datetime.now(timezone.utc)
                }
            )
            await session.commit()
    
    async def _get_subscription_info(self, account_id: str) -> Optional[Dict]:
        """Get subscription info for account."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT tier, stripe_subscription_id, scheduled_tier_change
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        'tier': row.tier,
                        'subscription_id': row.stripe_subscription_id,
                        'scheduled_change': row.scheduled_tier_change
                    }
                return None
                
        except Exception as e:
            logger.error(f"[LIFECYCLE] Error getting subscription info: {e}")
            return None
    
    async def _get_account_id_from_subscription(
        self,
        subscription: Dict,
        customer_id: str
    ) -> Optional[str]:
        """Get account_id from subscription metadata or customer lookup."""
        # Try metadata first
        metadata = subscription.get('metadata', {})
        if metadata.get('account_id'):
            return metadata['account_id']
        
        # Try subscription_data.metadata
        sub_data = subscription.get('subscription_data', {})
        if sub_data.get('metadata', {}).get('account_id'):
            return sub_data['metadata']['account_id']
        
        # Fallback: look up by customer_id
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT account_id::text as account_id
                        FROM billing_customers
                        WHERE id = :customer_id
                    """),
                    {"customer_id": customer_id}
                )
                row = result.fetchone()
                return row.account_id if row else None
                
        except Exception:
            return None
    
    async def _save_cancellation_feedback(
        self,
        account_id: str,
        subscription_id: str,
        feedback: str
    ) -> None:
        """Save cancellation feedback in Stripe metadata."""
        try:
            await StripeAPIWrapper.modify_subscription(
                subscription_id,
                metadata={'cancellation_feedback': feedback}
            )
            logger.info(f"[CANCEL] Saved feedback for {account_id}")
        except Exception as e:
            logger.warning(f"[CANCEL] Could not save feedback: {e}")
    
    async def _update_scheduled_downgrade(
        self,
        account_id: str,
        target_tier: str,
        scheduled_date: Optional[datetime]
    ) -> None:
        """Update database with scheduled tier change."""
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            await session.execute(
                text("""
                    UPDATE credit_accounts
                    SET scheduled_tier_change = :target_tier,
                        scheduled_change_date = :scheduled_date,
                        updated_at = :now
                    WHERE account_id = :account_id::uuid
                """),
                {
                    "account_id": account_id,
                    "target_tier": target_tier,
                    "scheduled_date": scheduled_date,
                    "now": datetime.now(timezone.utc)
                }
            )
            await session.commit()
    
    async def _clear_scheduled_changes(self, account_id: str) -> None:
        """Clear any scheduled tier changes."""
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            await session.execute(
                text("""
                    UPDATE credit_accounts
                    SET scheduled_tier_change = NULL,
                        scheduled_change_date = NULL,
                        updated_at = :now
                    WHERE account_id = :account_id::uuid
                """),
                {"account_id": account_id, "now": datetime.now(timezone.utc)}
            )
            await session.commit()


# Convenience functions
async def cancel_subscription(account_id: str, feedback: Optional[str] = None) -> Dict:
    """Cancel subscription (schedule downgrade to free)."""
    return await LifecycleHandler.cancel_subscription(account_id, feedback)


async def reactivate_subscription(account_id: str) -> Dict:
    """Reactivate a cancelled subscription."""
    return await LifecycleHandler.reactivate_subscription(account_id)


async def handle_subscription_change(subscription: Dict, previous_attributes: Optional[Dict] = None) -> Dict:
    """Handle subscription change from webhook."""
    return await LifecycleHandler.handle_subscription_change(subscription, previous_attributes)
