"""
Refund Webhook Handler

Handles refund-related webhook events:
- charge.refunded
- payment_intent.refunded

Based on external_billing/external/stripe/handlers/refund.py.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal

from backend.src.billing.shared.cache_utils import invalidate_account_state_cache

logger = logging.getLogger(__name__)


class RefundHandler:
    """
    Handler for Stripe refund webhook events.
    
    When a refund is processed, we need to:
    - Deduct the refunded credits from the account
    - Record the refund in the ledger
    - Update account state
    """
    
    @classmethod
    async def handle_refund(cls, event) -> None:
        """
        Handle charge.refunded or payment_intent.refunded event.
        
        Args:
            event: Stripe event object
        """
        event_type = event.type
        data_object = event.data.object
        
        logger.info(f"[REFUND] Processing {event_type}")
        
        if event_type == 'charge.refunded':
            await cls._handle_charge_refund(data_object)
        elif event_type == 'payment_intent.refunded':
            await cls._handle_payment_intent_refund(data_object)
    
    @classmethod
    async def _handle_charge_refund(cls, charge: Dict) -> None:
        """Handle charge.refunded event."""
        charge_id = charge.get('id')
        customer_id = charge.get('customer')
        amount_refunded = charge.get('amount_refunded', 0)  # In cents
        refunded = charge.get('refunded', False)
        
        if not refunded or amount_refunded == 0:
            logger.info(f"[REFUND] Charge {charge_id} not fully refunded, no action needed")
            return
        
        # Convert cents to dollars
        refund_amount = Decimal(amount_refunded) / 100
        
        # Find account
        account_id = await cls._find_account_by_customer(customer_id)
        if not account_id:
            logger.warning(f"[REFUND] No account found for customer {customer_id}")
            return
        
        logger.info(f"[REFUND] Processing refund of ${refund_amount} for {account_id}")
        
        await cls._process_refund(account_id, refund_amount, charge_id)
    
    @classmethod
    async def _handle_payment_intent_refund(cls, payment_intent: Dict) -> None:
        """Handle payment_intent.refunded event."""
        pi_id = payment_intent.get('id')
        customer_id = payment_intent.get('customer')
        
        # Get refund amount from charges
        charges = payment_intent.get('charges', {}).get('data', [])
        total_refunded = 0
        
        for charge in charges:
            total_refunded += charge.get('amount_refunded', 0)
        
        if total_refunded == 0:
            logger.info(f"[REFUND] Payment intent {pi_id} has no refunds")
            return
        
        refund_amount = Decimal(total_refunded) / 100
        
        # Find account
        account_id = await cls._find_account_by_customer(customer_id)
        if not account_id:
            # Try finding by payment intent in credit_purchases
            account_id = await cls._find_account_by_payment_intent(pi_id)
        
        if not account_id:
            logger.warning(f"[REFUND] No account found for payment intent {pi_id}")
            return
        
        logger.info(f"[REFUND] Processing refund of ${refund_amount} for {account_id}")
        
        await cls._process_refund(account_id, refund_amount, pi_id)
    
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
            logger.error(f"[REFUND] Error finding account by customer: {e}")
            return None
    
    @classmethod
    async def _find_account_by_payment_intent(cls, payment_intent_id: str) -> Optional[str]:
        """Find account ID by payment intent from credit_purchases."""
        if not payment_intent_id:
            return None
            
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                result = await db.execute(
                    text("""
                        SELECT account_id::text 
                        FROM credit_purchases 
                        WHERE stripe_payment_intent_id = :pi_id
                    """),
                    {"pi_id": payment_intent_id}
                )
                row = result.fetchone()
                return row.account_id if row else None
                
        except Exception as e:
            logger.error(f"[REFUND] Error finding account by payment intent: {e}")
            return None
    
    @classmethod
    async def _process_refund(cls, account_id: str, refund_amount: Decimal, reference_id: str) -> None:
        """
        Process refund by deducting credits.
        
        Refunds are deducted from non-expiring credits first (as those are purchased),
        then from expiring credits if needed.
        
        Args:
            account_id: User account ID
            refund_amount: Amount to deduct in dollars
            reference_id: Stripe charge or payment intent ID
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as db:
                # Get current credit state
                result = await db.execute(
                    text("""
                        SELECT balance, expiring_credits, non_expiring_credits, daily_credits_balance
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    logger.error(f"[REFUND] No credit account found for {account_id}")
                    return
                
                current_balance = Decimal(str(row.balance))
                non_expiring = Decimal(str(row.non_expiring_credits))
                expiring = Decimal(str(row.expiring_credits))
                daily = Decimal(str(row.daily_credits_balance))
                
                # Calculate how to deduct
                remaining_to_deduct = refund_amount
                new_non_expiring = non_expiring
                new_expiring = expiring
                
                # Deduct from non-expiring first (purchased credits)
                if remaining_to_deduct > 0 and new_non_expiring > 0:
                    deduct_from_non_expiring = min(remaining_to_deduct, new_non_expiring)
                    new_non_expiring -= deduct_from_non_expiring
                    remaining_to_deduct -= deduct_from_non_expiring
                
                # Then from expiring if still needed
                if remaining_to_deduct > 0 and new_expiring > 0:
                    deduct_from_expiring = min(remaining_to_deduct, new_expiring)
                    new_expiring -= deduct_from_expiring
                    remaining_to_deduct -= deduct_from_expiring
                
                # Recalculate total balance
                new_balance = new_expiring + new_non_expiring + daily
                
                # Update credits
                await db.execute(
                    text("""
                        UPDATE credit_accounts
                        SET balance = :balance,
                            expiring_credits = :expiring,
                            non_expiring_credits = :non_expiring,
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "balance": float(new_balance),
                        "expiring": float(new_expiring),
                        "non_expiring": float(new_non_expiring),
                        "now": datetime.now(timezone.utc)
                    }
                )
                
                # Update credit purchase status if applicable
                await db.execute(
                    text("""
                        UPDATE credit_purchases
                        SET status = 'refunded'
                        WHERE stripe_payment_intent_id = :ref_id
                        OR stripe_checkout_session_id = :ref_id
                    """),
                    {"ref_id": reference_id}
                )
                
                # Record in ledger
                await db.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            account_id, amount, balance_after, type, description,
                            is_expiring, stripe_event_id
                        )
                        VALUES (
                            :account_id::uuid, :amount, :balance_after, 'refund',
                            :description, false, :event_id
                        )
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(-refund_amount),  # Negative for deduction
                        "balance_after": float(new_balance),
                        "description": f"Refund: ${refund_amount}",
                        "event_id": reference_id
                    }
                )
                
                await db.commit()
            
            logger.info(f"[REFUND] ✅ Deducted ${refund_amount} from {account_id} (new balance: ${new_balance})")
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
        except Exception as e:
            logger.error(f"[REFUND] Error processing refund: {e}", exc_info=True)
            raise
