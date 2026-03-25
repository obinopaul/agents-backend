"""
Subscription Webhook Handler

Handles subscription lifecycle webhook events:
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- customer.subscription.trial_will_end

Based on external_billing/external/stripe/handlers/subscription.py.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal

from backend.src.billing.shared.config import (
    get_tier_by_price_id,
    get_tier_by_name,
    get_monthly_credits,
    get_plan_type,
    is_commitment_price_id,
)
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache

logger = logging.getLogger(__name__)


class SubscriptionHandler:
    """
    Handler for Stripe subscription webhook events.
    
    Manages the subscription lifecycle including:
    - Creation (new subscribers, trial conversions)
    - Updates (tier changes, payment method updates, status changes)
    - Deletion (cancellations)
    - Trial management
    """
    
    @classmethod
    async def handle_subscription_created(cls, event) -> None:
        """
        Handle customer.subscription.created event.
        
        This is triggered when:
        - User completes checkout
        - Free tier subscription is created
        - Trial is started
        
        Args:
            event: Stripe event object
        """
        subscription = event.data.object
        
        subscription_id = subscription.get('id')
        customer_id = subscription.get('customer')
        status = subscription.get('status')
        
        # Get price info
        items = subscription.get('items', {}).get('data', [])
        price_id = items[0]['price']['id'] if items else None
        
        # Get account_id from metadata
        metadata = subscription.get('metadata', {})
        account_id = metadata.get('account_id')
        
        logger.info(f"[SUBSCRIPTION] Created: sub={subscription_id}, status={status}, price={price_id}")
        
        if not account_id:
            # Try to find account by customer ID
            account_id = await cls._find_account_by_customer(customer_id)
            if not account_id:
                logger.warning(f"[SUBSCRIPTION] No account found for subscription {subscription_id}")
                return
        
        # Get tier info
        tier_info = get_tier_by_price_id(price_id) if price_id else None
        if not tier_info:
            logger.warning(f"[SUBSCRIPTION] Unknown price ID: {price_id}")
            return
        
        try:
            # Process based on status
            if status == 'trialing':
                await cls._handle_trial_subscription(account_id, subscription, tier_info)
            elif status in ['active', 'incomplete', 'incomplete_expired']:
                await cls._handle_active_subscription(account_id, subscription, tier_info)
            else:
                logger.info(f"[SUBSCRIPTION] Created with status {status} - no action needed")
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error handling subscription created: {e}", exc_info=True)
            raise
    
    @classmethod
    async def handle_subscription_updated(cls, event) -> None:
        """
        Handle customer.subscription.updated event.
        
        This is triggered when:
        - Status changes (trialing -> active, active -> past_due, etc.)
        - Plan changes (upgrades/downgrades)
        - Payment method updates
        - Cancel at period end is set/unset
        
        Args:
            event: Stripe event object
        """
        subscription = event.data.object
        previous_attributes = event.data.get('previous_attributes', {})
        
        subscription_id = subscription.get('id')
        status = subscription.get('status')
        
        # Get account_id
        metadata = subscription.get('metadata', {})
        account_id = metadata.get('account_id')
        
        if not account_id:
            customer_id = subscription.get('customer')
            account_id = await cls._find_account_by_customer(customer_id)
            if not account_id:
                logger.warning(f"[SUBSCRIPTION] No account found for update on {subscription_id}")
                return
        
        logger.info(f"[SUBSCRIPTION] Updated: sub={subscription_id}, status={status}, account={account_id}")
        
        try:
            # Sync status
            await cls._sync_subscription_status(account_id, subscription)
            
            # Check for status transitions
            prev_status = previous_attributes.get('status')
            if prev_status and prev_status != status:
                await cls._handle_status_change(account_id, subscription, prev_status, status)
            
            # Check for plan changes
            if 'items' in previous_attributes:
                await cls._handle_plan_change(account_id, subscription, previous_attributes)
            
            # Check for cancel_at_period_end changes
            if 'cancel_at_period_end' in previous_attributes:
                await cls._handle_cancel_flag_change(account_id, subscription, previous_attributes)
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error handling subscription updated: {e}", exc_info=True)
            raise
    
    @classmethod
    async def handle_subscription_deleted(cls, event) -> None:
        """
        Handle customer.subscription.deleted event.
        
        This is triggered when a subscription is fully canceled.
        
        Args:
            event: Stripe event object
        """
        subscription = event.data.object
        subscription_id = subscription.get('id')
        
        # Get account_id
        metadata = subscription.get('metadata', {})
        account_id = metadata.get('account_id')
        
        if not account_id:
            customer_id = subscription.get('customer')
            account_id = await cls._find_account_by_customer(customer_id)
            if not account_id:
                logger.warning(f"[SUBSCRIPTION] No account found for deletion of {subscription_id}")
                return
        
        logger.info(f"[SUBSCRIPTION] Deleted: sub={subscription_id}, account={account_id}")
        
        try:
            await cls._process_subscription_deletion(account_id, subscription)
            await invalidate_account_state_cache(account_id)
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error handling subscription deleted: {e}", exc_info=True)
            raise
    
    @classmethod
    async def handle_trial_will_end(cls, event) -> None:
        """
        Handle customer.subscription.trial_will_end event.
        
        This is triggered 3 days before a trial ends.
        
        Args:
            event: Stripe event object
        """
        subscription = event.data.object
        
        metadata = subscription.get('metadata', {})
        account_id = metadata.get('account_id')
        
        logger.info(f"[SUBSCRIPTION] Trial will end for account {account_id}")
        
        # This could trigger an email notification
        # For now, just log it
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    async def _find_account_by_customer(cls, customer_id: str) -> Optional[str]:
        """Find account ID by Stripe customer ID."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                result = await db.execute(
                    text("""
                        SELECT account_id::text 
                        FROM credit_accounts 
                        WHERE stripe_customer_id = :customer_id
                    """),
                    {"customer_id": customer_id}
                )
                row = result.fetchone()
                return row.account_id if row else None
                
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error finding account by customer: {e}")
            return None
    
    @classmethod
    async def _handle_trial_subscription(cls, account_id: str, subscription: Dict, tier_info) -> None:
        """Handle new trial subscription."""
        subscription_id = subscription.get('id')
        customer_id = subscription.get('customer')
        trial_end = subscription.get('trial_end')
        
        logger.info(f"[SUBSCRIPTION] Setting up trial for {account_id}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            trial_end_dt = datetime.fromtimestamp(trial_end, tz=timezone.utc) if trial_end else None
            
            async with async_db_session() as db:
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET tier = :tier,
                            stripe_subscription_id = :sub_id,
                            stripe_customer_id = :customer_id,
                            trial_status = 'active',
                            trial_ends_at = :trial_end,
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "tier": tier_info.name,
                        "sub_id": subscription_id,
                        "customer_id": customer_id,
                        "trial_end": trial_end_dt,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await db.commit()
                
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error setting up trial: {e}")
            raise
    
    @classmethod
    async def _handle_active_subscription(cls, account_id: str, subscription: Dict, tier_info) -> None:
        """Handle new active subscription."""
        subscription_id = subscription.get('id')
        customer_id = subscription.get('customer')
        current_period_start = subscription.get('current_period_start')
        current_period_end = subscription.get('current_period_end')
        
        # Get price ID for plan type detection
        items = subscription.get('items', {}).get('data', [])
        price_id = items[0]['price']['id'] if items else None
        plan_type = get_plan_type(price_id) if price_id else 'monthly'
        
        logger.info(f"[SUBSCRIPTION] Setting up active subscription for {account_id}: tier={tier_info.name}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            period_start_dt = datetime.fromtimestamp(current_period_start, tz=timezone.utc) if current_period_start else None
            period_end_dt = datetime.fromtimestamp(current_period_end, tz=timezone.utc) if current_period_end else None
            
            async with async_db_session() as db:
                # Update credit account
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET tier = :tier,
                            stripe_subscription_id = :sub_id,
                            stripe_customer_id = :customer_id,
                            plan_type = :plan_type,
                            billing_cycle_anchor = :period_start,
                            next_credit_grant = :period_end,
                            trial_status = CASE 
                                WHEN trial_status = 'active' THEN 'converted'
                                ELSE trial_status
                            END,
                            payment_status = 'active',
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "tier": tier_info.name,
                        "sub_id": subscription_id,
                        "customer_id": customer_id,
                        "plan_type": plan_type,
                        "period_start": period_start_dt,
                        "period_end": period_end_dt,
                        "now": datetime.now(timezone.utc)
                    }
                )
                
                # Grant monthly credits if this is a new subscription
                monthly_credits = tier_info.monthly_credits
                if monthly_credits and monthly_credits > 0:
                    await db.execute(
                        text("""
                            UPDATE credit_accounts
                            SET expiring_credits = :credits,
                                balance = non_expiring_credits + :credits + daily_credits_balance,
                                last_grant_date = :now
                            WHERE account_id = :account_id::uuid
                        """),
                        {
                            "account_id": account_id,
                            "credits": float(monthly_credits),
                            "now": datetime.now(timezone.utc)
                        }
                    )
                    
                    # Record in ledger
                    await db.execute(
                        text("""
                            INSERT INTO credit_ledger (
                                account_id, amount, type, description,
                                is_expiring, expires_at
                            )
                            VALUES (
                                :account_id::uuid, :amount, 'tier_grant',
                                :description, true, :expires_at
                            )
                        """),
                        {
                            "account_id": account_id,
                            "amount": float(monthly_credits),
                            "description": f"Monthly credits for {tier_info.display_name} tier",
                            "expires_at": period_end_dt
                        }
                    )
                
                await db.commit()
                
            logger.info(f"[SUBSCRIPTION] ✅ Set up {tier_info.display_name} subscription for {account_id}")
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error setting up subscription: {e}")
            raise
    
    @classmethod
    async def _sync_subscription_status(cls, account_id: str, subscription: Dict) -> None:
        """Sync subscription status to database."""
        status = subscription.get('status')
        billing_anchor = subscription.get('billing_cycle_anchor')
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            billing_anchor_dt = datetime.fromtimestamp(billing_anchor, tz=timezone.utc) if billing_anchor else None
            
            payment_status = 'active'
            if status in ['past_due', 'unpaid']:
                payment_status = 'past_due'
            elif status in ['canceled', 'incomplete_expired']:
                payment_status = 'cancelled'
            
            async with async_db_session() as db:
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET payment_status = :payment_status,
                            billing_cycle_anchor = COALESCE(:anchor, billing_cycle_anchor),
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "payment_status": payment_status,
                        "anchor": billing_anchor_dt,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await db.commit()
                
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error syncing status: {e}")
    
    @classmethod
    async def _handle_status_change(
        cls, 
        account_id: str, 
        subscription: Dict, 
        prev_status: str, 
        new_status: str
    ) -> None:
        """Handle subscription status transitions."""
        logger.info(f"[SUBSCRIPTION] Status change for {account_id}: {prev_status} -> {new_status}")
        
        # Trial ended and converted to paid
        if prev_status == 'trialing' and new_status == 'active':
            logger.info(f"[SUBSCRIPTION] Trial converted for {account_id}")
            # Credits are granted by _handle_active_subscription
        
        # Subscription became past due (payment failed)
        elif new_status == 'past_due':
            logger.warning(f"[SUBSCRIPTION] Subscription past due for {account_id}")
            # Could send notification here
        
        # Subscription became unpaid (grace period ended)
        elif new_status == 'unpaid':
            logger.warning(f"[SUBSCRIPTION] Subscription unpaid for {account_id} - revoking access")
            await cls._revoke_subscription_access(account_id)
    
    @classmethod
    async def _handle_plan_change(cls, account_id: str, subscription: Dict, previous_attributes: Dict) -> None:
        """Handle plan/tier changes."""
        items = subscription.get('items', {}).get('data', [])
        new_price_id = items[0]['price']['id'] if items else None
        
        prev_items = previous_attributes.get('items', {}).get('data', [])
        old_price_id = prev_items[0]['price']['id'] if prev_items else None
        
        if new_price_id == old_price_id:
            return
        
        new_tier = get_tier_by_price_id(new_price_id)
        old_tier = get_tier_by_price_id(old_price_id)
        
        if new_tier and old_tier:
            logger.info(f"[SUBSCRIPTION] Plan change for {account_id}: {old_tier.display_name} -> {new_tier.display_name}")
            
            # Update tier in database
            try:
                from backend.database.db import async_db_session
                from sqlalchemy import text
                
                async with async_db_session() as db:
                    await db.execute(
                        text("""
                            UPDATE credit_accounts
                            SET tier = :tier,
                                updated_at = :now
                            WHERE account_id = :account_id::uuid
                        """),
                        {
                            "account_id": account_id,
                            "tier": new_tier.name,
                            "now": datetime.now(timezone.utc)
                        }
                    )
                    await db.commit()
                    
            except Exception as e:
                logger.error(f"[SUBSCRIPTION] Error updating tier: {e}")
    
    @classmethod
    async def _handle_cancel_flag_change(cls, account_id: str, subscription: Dict, previous_attributes: Dict) -> None:
        """Handle cancel_at_period_end changes."""
        cancel_at_period_end = subscription.get('cancel_at_period_end')
        prev_cancel = previous_attributes.get('cancel_at_period_end')
        
        if cancel_at_period_end and not prev_cancel:
            logger.info(f"[SUBSCRIPTION] Cancellation scheduled for {account_id}")
        elif not cancel_at_period_end and prev_cancel:
            logger.info(f"[SUBSCRIPTION] Cancellation reverted for {account_id}")
    
    @classmethod
    async def _process_subscription_deletion(cls, account_id: str, subscription: Dict) -> None:
        """Process full subscription deletion."""
        subscription_id = subscription.get('id')
        
        logger.info(f"[SUBSCRIPTION] Processing deletion for {account_id}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                # Downgrade to free tier
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET tier = 'free',
                            stripe_subscription_id = NULL,
                            expiring_credits = 0,
                            balance = non_expiring_credits + daily_credits_balance,
                            payment_status = 'cancelled',
                            trial_status = CASE
                                WHEN trial_status = 'active' THEN 'cancelled'
                                ELSE trial_status
                            END,
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                        AND stripe_subscription_id = :sub_id
                    """),
                    {
                        "account_id": account_id,
                        "sub_id": subscription_id,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await db.commit()
                
            logger.info(f"[SUBSCRIPTION] ✅ Downgraded {account_id} to free tier")
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error processing deletion: {e}")
            raise
    
    @classmethod
    async def _revoke_subscription_access(cls, account_id: str) -> None:
        """Revoke subscription access for unpaid accounts."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET tier = 'none',
                            expiring_credits = 0,
                            balance = non_expiring_credits,
                            payment_status = 'cancelled',
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await db.commit()
                
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error revoking access: {e}")
