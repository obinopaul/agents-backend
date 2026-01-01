"""
Invoice Webhook Handler

Handles invoice-related webhook events:
- invoice.payment_succeeded / invoice.paid
- invoice.payment_failed
- invoice.upcoming

Based on external_billing/external/stripe/handlers/invoice.py.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal

from backend.src.billing.shared.config import get_tier_by_price_id, get_monthly_credits
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache

logger = logging.getLogger(__name__)


class InvoiceHandler:
    """
    Handler for Stripe invoice webhook events.
    
    Invoice events are critical for:
    - Granting monthly credits on successful renewal
    - Handling failed payments (grace periods)
    - Tracking billing cycles
    """
    
    @classmethod
    async def handle_invoice_paid(cls, event) -> None:
        """
        Handle invoice.payment_succeeded or invoice.paid event.
        
        This is the primary trigger for monthly credit grants on subscription renewal.
        
        Args:
            event: Stripe event object
        """
        invoice = event.data.object
        
        # Skip draft/void invoices
        if invoice.get('status') not in ['paid', 'open']:
            return
        
        # Get subscription info
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        billing_reason = invoice.get('billing_reason')
        
        # Get line items
        lines = invoice.get('lines', {}).get('data', [])
        
        logger.info(f"[INVOICE] Paid: invoice={invoice.get('id')}, reason={billing_reason}, sub={subscription_id}")
        
        # Find account
        account_id = await cls._find_account_by_subscription(subscription_id)
        if not account_id:
            account_id = await cls._find_account_by_customer(customer_id)
        
        if not account_id:
            logger.warning(f"[INVOICE] No account found for invoice {invoice.get('id')}")
            return
        
        try:
            # Handle subscription renewal
            if billing_reason in ['subscription_cycle', 'subscription_create', 'subscription_update']:
                await cls._process_subscription_invoice(account_id, invoice, lines)
            
            # Handle manual payments
            elif billing_reason == 'manual':
                logger.info(f"[INVOICE] Manual invoice paid for {account_id}")
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
        except Exception as e:
            logger.error(f"[INVOICE] Error processing paid invoice: {e}", exc_info=True)
            raise
    
    @classmethod
    async def handle_invoice_failed(cls, event) -> None:
        """
        Handle invoice.payment_failed event.
        
        This triggers when a renewal payment fails.
        Stripe will retry, so we track the failure but don't revoke access yet.
        
        Args:
            event: Stripe event object
        """
        invoice = event.data.object
        
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        attempt_count = invoice.get('attempt_count', 1)
        
        logger.warning(f"[INVOICE] Payment failed: invoice={invoice.get('id')}, attempt={attempt_count}")
        
        # Find account
        account_id = await cls._find_account_by_subscription(subscription_id)
        if not account_id:
            account_id = await cls._find_account_by_customer(customer_id)
        
        if not account_id:
            logger.warning(f"[INVOICE] No account found for failed invoice")
            return
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                # Update payment status to past_due
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET payment_status = 'past_due',
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await db.commit()
            
            logger.info(f"[INVOICE] Marked {account_id} as past_due after payment failure")
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            # TODO: Send notification email about payment failure
            
        except Exception as e:
            logger.error(f"[INVOICE] Error handling failed invoice: {e}")
    
    @classmethod
    async def handle_invoice_upcoming(cls, event) -> None:
        """
        Handle invoice.upcoming event.
        
        This is sent ~3 days before invoice is created.
        Useful for notifications or pre-renewal actions.
        
        Args:
            event: Stripe event object
        """
        invoice = event.data.object
        
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        
        logger.info(f"[INVOICE] Upcoming invoice for subscription {subscription_id}")
        
        # This could trigger an email notification
        # For now, just log it
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    async def _find_account_by_subscription(cls, subscription_id: str) -> Optional[str]:
        """Find account ID by Stripe subscription ID."""
        if not subscription_id:
            return None
            
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                result = await db.execute(
                    text("""
                        SELECT account_id::text 
                        FROM credit_accounts 
                        WHERE stripe_subscription_id = :sub_id
                    """),
                    {"sub_id": subscription_id}
                )
                row = result.fetchone()
                return row.account_id if row else None
                
        except Exception as e:
            logger.error(f"[INVOICE] Error finding account by subscription: {e}")
            return None
    
    @classmethod
    async def _find_account_by_customer(cls, customer_id: str) -> Optional[str]:
        """Find account ID by Stripe customer ID."""
        if not customer_id:
            return None
            
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
            logger.error(f"[INVOICE] Error finding account by customer: {e}")
            return None
    
    @classmethod
    async def _process_subscription_invoice(cls, account_id: str, invoice: Dict, lines: list) -> None:
        """
        Process subscription invoice and grant credits.
        
        This is the critical function that grants monthly credits on renewal.
        """
        billing_reason = invoice.get('billing_reason')
        
        # Get price from line items
        price_id = None
        for line in lines:
            if line.get('type') == 'subscription':
                price = line.get('price', {})
                price_id = price.get('id')
                break
        
        if not price_id:
            logger.warning(f"[INVOICE] No price found in invoice lines")
            return
        
        # Get tier info
        tier_info = get_tier_by_price_id(price_id)
        if not tier_info:
            logger.warning(f"[INVOICE] Unknown price ID in invoice: {price_id}")
            return
        
        # Only grant credits on renewal (not first payment)
        if billing_reason == 'subscription_cycle':
            await cls._grant_monthly_credits(account_id, tier_info, invoice)
        elif billing_reason == 'subscription_create':
            logger.info(f"[INVOICE] Initial subscription invoice - credits handled by subscription.created")
        else:
            logger.info(f"[INVOICE] Invoice reason {billing_reason} - no credit grant")
    
    @classmethod
    async def _grant_monthly_credits(cls, account_id: str, tier_info, invoice: Dict) -> None:
        """
        Grant monthly credits on subscription renewal.
        
        This replaces expiring credits with a fresh allocation.
        """
        monthly_credits = tier_info.monthly_credits
        
        if not monthly_credits or monthly_credits <= 0:
            logger.info(f"[INVOICE] No monthly credits to grant for {tier_info.name}")
            return
        
        logger.info(f"[INVOICE] Granting ${monthly_credits} credits to {account_id}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            # Calculate next renewal date (30 days from now as estimate)
            next_period_end = None
            lines = invoice.get('lines', {}).get('data', [])
            for line in lines:
                period = line.get('period', {})
                end = period.get('end')
                if end:
                    next_period_end = datetime.fromtimestamp(end, tz=timezone.utc)
                    break
            
            async with async_db_session() as db:
                # Get current balance info
                result = await db.execute(
                    text("""
                        SELECT non_expiring_credits, daily_credits_balance
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    logger.error(f"[INVOICE] No credit account found for {account_id}")
                    return
                
                # Reset expiring credits to monthly amount, recalculate total
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET expiring_credits = :monthly,
                            balance = :monthly + non_expiring_credits + daily_credits_balance,
                            last_grant_date = :now,
                            next_credit_grant = :next_grant,
                            payment_status = 'active',
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "monthly": float(monthly_credits),
                        "now": datetime.now(timezone.utc),
                        "next_grant": next_period_end
                    }
                )
                
                # Record in ledger
                await db.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            account_id, amount, type, description,
                            is_expiring, expires_at, stripe_event_id
                        )
                        VALUES (
                            :account_id::uuid, :amount, 'tier_grant',
                            :description, true, :expires_at, :event_id
                        )
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(monthly_credits),
                        "description": f"Monthly renewal: {tier_info.display_name}",
                        "expires_at": next_period_end,
                        "event_id": invoice.get('id')
                    }
                )
                
                await db.commit()
            
            logger.info(f"[INVOICE] ✅ Granted ${monthly_credits} renewal credits to {account_id}")
            
        except Exception as e:
            logger.error(f"[INVOICE] Error granting credits: {e}", exc_info=True)
            raise
