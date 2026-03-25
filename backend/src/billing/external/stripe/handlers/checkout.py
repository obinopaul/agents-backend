"""
Checkout Session Webhook Handler

Handles checkout.session.completed and checkout.session.expired events.
This is where we process successful payments and set up subscriptions/credits.

Based on external_billing/external/stripe/handlers/checkout.py.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal

from backend.src.billing.shared.config import (
    get_tier_by_price_id,
    CREDIT_PACKAGES,
)
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache

logger = logging.getLogger(__name__)


class CheckoutHandler:
    """
    Handler for Stripe Checkout session webhook events.
    
    Handles:
    - checkout.session.completed: Successful payment
    - checkout.session.expired: Checkout abandoned
    """
    
    @classmethod
    async def handle_checkout_completed(cls, event) -> None:
        """
        Handle checkout.session.completed event.
        
        This is the main entry point for successful payments.
        Routes to appropriate handler based on checkout mode.
        
        Args:
            event: Stripe event object
        """
        session = event.data.object
        
        # Extract key information
        mode = session.get('mode')  # 'subscription', 'payment', or 'setup'
        metadata = session.get('metadata', {})
        customer_id = session.get('customer')
        
        logger.info(f"[CHECKOUT] Processing completed checkout: mode={mode}, session_id={session.id}")
        
        try:
            if mode == 'subscription':
                await cls._handle_subscription_checkout(session, metadata)
            elif mode == 'payment':
                await cls._handle_payment_checkout(session, metadata)
            elif mode == 'setup':
                await cls._handle_setup_checkout(session, metadata)
            else:
                logger.warning(f"[CHECKOUT] Unknown checkout mode: {mode}")
            
            # Invalidate cache for account
            account_id = metadata.get('account_id')
            if account_id:
                await invalidate_account_state_cache(account_id)
                
        except Exception as e:
            logger.error(f"[CHECKOUT] Error processing checkout: {e}", exc_info=True)
            raise
    
    @classmethod
    async def _handle_subscription_checkout(cls, session: Dict, metadata: Dict) -> None:
        """
        Handle subscription checkout completion.
        
        This is triggered for:
        - New subscriptions
        - Trial signups
        - Subscription upgrades (via new checkout)
        """
        account_id = metadata.get('account_id')
        checkout_type = metadata.get('checkout_type', 'subscription')
        
        if not account_id:
            logger.warning("[CHECKOUT] No account_id in subscription checkout metadata")
            return
        
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        
        logger.info(f"[CHECKOUT] Subscription checkout complete: account={account_id}, sub={subscription_id}, type={checkout_type}")
        
        # The subscription.created webhook will handle the actual setup
        # Here we just log and potentially update checkout status
        
        if checkout_type == 'trial':
            await cls._process_trial_checkout(account_id, subscription_id, session)
        elif checkout_type == 'upgrade':
            await cls._process_upgrade_checkout(account_id, subscription_id, session)
        else:
            await cls._process_new_subscription_checkout(account_id, subscription_id, session)
    
    @classmethod
    async def _handle_payment_checkout(cls, session: Dict, metadata: Dict) -> None:
        """
        Handle one-time payment checkout completion.
        
        This is triggered for credit purchases.
        """
        account_id = metadata.get('account_id')
        checkout_type = metadata.get('checkout_type', 'credit_purchase')
        
        if not account_id:
            logger.warning("[CHECKOUT] No account_id in payment checkout metadata")
            return
        
        payment_intent_id = session.get('payment_intent')
        amount_total = session.get('amount_total', 0)  # In cents
        
        logger.info(f"[CHECKOUT] Payment checkout complete: account={account_id}, amount=${amount_total/100:.2f}")
        
        if checkout_type == 'credit_purchase':
            await cls._process_credit_purchase(account_id, session)
        else:
            logger.info(f"[CHECKOUT] Unhandled payment checkout type: {checkout_type}")
    
    @classmethod
    async def _handle_setup_checkout(cls, session: Dict, metadata: Dict) -> None:
        """Handle setup mode checkout (payment method collection only)."""
        account_id = metadata.get('account_id')
        logger.info(f"[CHECKOUT] Setup checkout complete: account={account_id}")
        # Setup intents are typically handled elsewhere
    
    @classmethod
    async def _process_trial_checkout(cls, account_id: str, subscription_id: str, session: Dict) -> None:
        """Process trial signup checkout."""
        logger.info(f"[CHECKOUT] Trial checkout processed for {account_id}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                # Update trial history
                await db.execute(
                    text("""
                        UPDATE trial_history
                        SET status = 'active',
                            stripe_subscription_id = :sub_id,
                            stripe_checkout_session_id = :session_id
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "sub_id": subscription_id,
                        "session_id": session.get('id')
                    }
                )
                await db.commit()
                
        except Exception as e:
            logger.error(f"[CHECKOUT] Error updating trial checkout: {e}")
    
    @classmethod
    async def _process_upgrade_checkout(cls, account_id: str, subscription_id: str, session: Dict) -> None:
        """Process upgrade checkout."""
        logger.info(f"[CHECKOUT] Upgrade checkout processed for {account_id}")
        # Upgrade is handled by subscription.created webhook
    
    @classmethod
    async def _process_new_subscription_checkout(cls, account_id: str, subscription_id: str, session: Dict) -> None:
        """Process new subscription checkout."""
        logger.info(f"[CHECKOUT] New subscription checkout processed for {account_id}")
        # New subscription is handled by subscription.created webhook
    
    @classmethod
    async def _process_credit_purchase(cls, account_id: str, session: Dict) -> None:
        """
        Process credit purchase and add credits to account.
        
        Args:
            account_id: User account ID
            session: Stripe checkout session object
        """
        payment_intent_id = session.get('payment_intent')
        amount_total = session.get('amount_total', 0)  # In cents
        amount_dollars = Decimal(amount_total) / 100
        
        logger.info(f"[CHECKOUT] Processing credit purchase: {account_id} buying ${amount_dollars}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                # Update credit purchases table
                await db.execute(
                    text("""
                        INSERT INTO credit_purchases (
                            account_id, amount_dollars, status, 
                            stripe_payment_intent_id, stripe_checkout_session_id,
                            completed_at
                        )
                        VALUES (
                            :account_id::uuid, :amount, 'completed',
                            :payment_intent, :session_id, :now
                        )
                        ON CONFLICT (stripe_payment_intent_id) DO UPDATE SET
                            status = 'completed',
                            completed_at = :now
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(amount_dollars),
                        "payment_intent": payment_intent_id,
                        "session_id": session.get('id'),
                        "now": datetime.now(timezone.utc)
                    }
                )
                
                # Add credits to account (non-expiring)
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET non_expiring_credits = non_expiring_credits + :amount,
                            balance = balance + :amount,
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(amount_dollars),
                        "now": datetime.now(timezone.utc)
                    }
                )
                
                # Record in ledger
                await db.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            account_id, amount, type, description,
                            is_expiring, stripe_event_id
                        )
                        VALUES (
                            :account_id::uuid, :amount, 'purchase',
                            :description, false, :event_id
                        )
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(amount_dollars),
                        "description": f"Credit purchase: ${amount_dollars}",
                        "event_id": session.get('id')
                    }
                )
                
                await db.commit()
                
            logger.info(f"[CHECKOUT] ✅ Added ${amount_dollars} credits to {account_id}")
            
        except Exception as e:
            logger.error(f"[CHECKOUT] Error processing credit purchase: {e}", exc_info=True)
            raise
    
    @classmethod
    async def handle_checkout_expired(cls, event) -> None:
        """
        Handle checkout.session.expired event.
        
        Args:
            event: Stripe event object
        """
        session = event.data.object
        metadata = session.get('metadata', {})
        account_id = metadata.get('account_id')
        checkout_type = metadata.get('checkout_type')
        
        logger.info(f"[CHECKOUT] Checkout expired: account={account_id}, type={checkout_type}")
        
        if checkout_type == 'trial':
            await cls._handle_trial_checkout_expired(account_id, session)
        elif checkout_type == 'credit_purchase':
            await cls._handle_credit_purchase_expired(account_id, session)
    
    @classmethod
    async def _handle_trial_checkout_expired(cls, account_id: str, session: Dict) -> None:
        """Handle expired trial checkout."""
        if not account_id:
            return
            
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                await db.execute(
                    text("""
                        UPDATE trial_history
                        SET status = 'checkout_expired'
                        WHERE account_id = :account_id::uuid
                        AND status = 'checkout_pending'
                    """),
                    {"account_id": account_id}
                )
                await db.commit()
                
        except Exception as e:
            logger.error(f"[CHECKOUT] Error handling expired trial checkout: {e}")
    
    @classmethod
    async def _handle_credit_purchase_expired(cls, account_id: str, session: Dict) -> None:
        """Handle expired credit purchase checkout."""
        logger.info(f"[CHECKOUT] Credit purchase checkout expired for {account_id}")
        # No special handling needed - purchase just wasn't completed
