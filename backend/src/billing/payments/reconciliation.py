"""
Reconciliation Service

Handles payment reconciliation, balance verification, and cleanup.
Features:
- Reconcile failed/orphaned payments
- Verify credit balance consistency
- Detect duplicate charges
- Cleanup expired credits
- Retry failed payments

Based on external_billing/payments/reconciliation.py.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.exceptions import ReconciliationError
from backend.src.billing.credits import credit_manager
from .interfaces import ReconciliationManagerInterface

logger = logging.getLogger(__name__)


class ReconciliationService(ReconciliationManagerInterface):
    """
    Handles payment and credit reconciliation.
    
    Should be run periodically (e.g., hourly via cron/scheduler)
    to catch and fix any discrepancies.
    
    Usage:
        from backend.src.billing.payments import reconciliation_service
        
        # Run full reconciliation
        results = await reconciliation_service.reconcile_failed_payments()
        
        # Verify balances
        balance_check = await reconciliation_service.verify_balance_consistency()
    """
    
    async def reconcile_failed_payments(self, hours: int = 24) -> Dict:
        """
        Reconcile failed or orphaned credit purchases.
        
        Finds pending purchases where Stripe payment succeeded
        but credits were not granted (e.g., webhook failure).
        
        Args:
            hours: Look back period in hours
            
        Returns:
            Dict with checked, fixed, failed counts
        """
        results = {
            'checked': 0,
            'fixed': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            async with async_db_session() as session:
                # Find pending purchases
                result = await session.execute(
                    text("""
                        SELECT id, account_id, amount_dollars, stripe_payment_intent_id, created_at
                        FROM credit_purchases
                        WHERE status = 'pending'
                        AND created_at >= :since
                        AND stripe_payment_intent_id IS NOT NULL
                    """),
                    {"since": since}
                )
                pending = result.fetchall()
                
                if not pending:
                    logger.info("[RECONCILIATION] No pending credit purchases found")
                    return results
                
                results['checked'] = len(pending)
                logger.info(f"[RECONCILIATION] Checking {len(pending)} pending purchases")
                
                for purchase in pending:
                    try:
                        # Check payment status in Stripe
                        payment_intent = await StripeAPIWrapper.retrieve_payment_intent(
                            purchase.stripe_payment_intent_id
                        )
                        
                        if payment_intent.get('status') == 'succeeded':
                            # Payment succeeded but credits not granted
                            logger.warning(
                                f"[RECONCILIATION] Found successful payment without credits: {purchase.id}"
                            )
                            
                            # Check if credits were already added
                            ledger_check = await session.execute(
                                text("""
                                    SELECT id FROM credit_ledger
                                    WHERE stripe_event_id LIKE :pattern
                                """),
                                {"pattern": f"%{purchase.stripe_payment_intent_id}%"}
                            )
                            
                            if not ledger_check.fetchone():
                                # Add missing credits
                                add_result = await credit_manager.add_credits(
                                    account_id=str(purchase.account_id),
                                    amount=Decimal(str(purchase.amount_dollars)),
                                    is_expiring=False,
                                    description=f"Reconciled purchase: ${purchase.amount_dollars} credits",
                                    credit_type='purchase',
                                    stripe_event_id=f"reconciliation_{purchase.id}"
                                )
                                
                                if add_result.get('success'):
                                    # Update purchase status
                                    await session.execute(
                                        text("""
                                            UPDATE credit_purchases
                                            SET status = 'completed',
                                                completed_at = :now
                                            WHERE id = :id::uuid
                                        """),
                                        {"id": str(purchase.id), "now": datetime.now(timezone.utc)}
                                    )
                                    await session.commit()
                                    
                                    results['fixed'] += 1
                                    logger.info(
                                        f"[RECONCILIATION] Fixed missing credits for {purchase.account_id}"
                                    )
                                else:
                                    results['failed'] += 1
                                    results['errors'].append(f"Failed to add credits for {purchase.id}")
                            else:
                                # Credits already added, just update status
                                await session.execute(
                                    text("""
                                        UPDATE credit_purchases
                                        SET status = 'completed',
                                            completed_at = :now
                                        WHERE id = :id::uuid
                                    """),
                                    {"id": str(purchase.id), "now": datetime.now(timezone.utc)}
                                )
                                await session.commit()
                                logger.info(f"[RECONCILIATION] Purchase {purchase.id} already processed")
                        
                        elif payment_intent.get('status') in ['canceled', 'failed']:
                            # Payment failed, mark purchase as failed
                            await session.execute(
                                text("""
                                    UPDATE credit_purchases
                                    SET status = 'failed'
                                    WHERE id = :id::uuid
                                """),
                                {"id": str(purchase.id)}
                            )
                            await session.commit()
                            logger.info(f"[RECONCILIATION] Marked purchase {purchase.id} as failed")
                    
                    except Exception as e:
                        logger.error(f"[RECONCILIATION] Error processing purchase {purchase.id}: {e}")
                        results['errors'].append(str(e))
                        results['failed'] += 1
            
        except Exception as e:
            logger.error(f"[RECONCILIATION] Fatal error: {e}")
            results['errors'].append(f"Fatal error: {str(e)}")
        
        logger.info(
            f"[RECONCILIATION] Complete: checked={results['checked']}, "
            f"fixed={results['fixed']}, failed={results['failed']}"
        )
        return results
    
    async def verify_balance_consistency(self) -> Dict:
        """
        Verify credit account balances are consistent.
        
        Checks: balance == expiring_credits + non_expiring_credits + daily_credits_balance
        
        Returns:
            Dict with checked, fixed counts and discrepancies
        """
        results = {
            'checked': 0,
            'fixed': 0,
            'discrepancies_found': []
        }
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT 
                            account_id, balance, 
                            daily_credits_balance, expiring_credits, non_expiring_credits
                        FROM credit_accounts
                    """)
                )
                accounts = result.fetchall()
                
                results['checked'] = len(accounts)
                
                for account in accounts:
                    expected = (
                        Decimal(str(account.daily_credits_balance or 0)) +
                        Decimal(str(account.expiring_credits or 0)) +
                        Decimal(str(account.non_expiring_credits or 0))
                    )
                    actual = Decimal(str(account.balance or 0))
                    
                    if abs(expected - actual) > Decimal('0.01'):
                        logger.warning(
                            f"[BALANCE CHECK] Discrepancy for {account.account_id}: "
                            f"expected=${expected:.2f}, actual=${actual:.2f}"
                        )
                        
                        results['discrepancies_found'].append({
                            'account_id': str(account.account_id),
                            'expected': float(expected),
                            'actual': float(actual),
                            'difference': float(expected - actual)
                        })
                        
                        # Attempt to fix by updating balance
                        await session.execute(
                            text("""
                                UPDATE credit_accounts
                                SET balance = :balance,
                                    updated_at = :now
                                WHERE account_id = :account_id::uuid
                            """),
                            {
                                "account_id": str(account.account_id),
                                "balance": float(expected),
                                "now": datetime.now(timezone.utc)
                            }
                        )
                        await session.commit()
                        
                        results['fixed'] += 1
                        logger.info(f"[BALANCE CHECK] Fixed balance for {account.account_id}")
        
        except Exception as e:
            logger.error(f"[BALANCE CHECK] Error: {e}")
        
        return results
    
    async def detect_double_charges(self, days: int = 7) -> Dict:
        """
        Detect potential duplicate charges or credits.
        
        Looks for entries with same account, amount, and description
        within a short time window.
        
        Args:
            days: Look back period
            
        Returns:
            Dict with duplicates found
        """
        results = {
            'duplicates_found': [],
            'total_checked': 0
        }
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT id, account_id, amount, description, created_at, stripe_event_id
                        FROM credit_ledger
                        WHERE created_at >= :since
                        ORDER BY created_at DESC
                    """),
                    {"since": since}
                )
                entries = result.fetchall()
                
                results['total_checked'] = len(entries)
                
                # Group by key and check for duplicates
                seen = {}
                for entry in entries:
                    key = f"{entry.account_id}_{entry.amount}_{entry.description}"
                    
                    if key in seen:
                        prev = seen[key]
                        time_diff = abs((entry.created_at - prev['created_at']).total_seconds())
                        
                        # Potential duplicate if within 60 seconds
                        if time_diff < 60:
                            results['duplicates_found'].append({
                                'account_id': str(entry.account_id),
                                'amount': float(entry.amount),
                                'description': entry.description,
                                'entries': [str(entry.id), str(prev['id'])],
                                'time_difference_seconds': time_diff
                            })
                            logger.warning(
                                f"[DUPLICATE CHECK] Potential duplicate for {entry.account_id}: "
                                f"${entry.amount} - {entry.description}"
                            )
                    else:
                        seen[key] = {
                            'id': entry.id,
                            'created_at': entry.created_at
                        }
        
        except Exception as e:
            logger.error(f"[DUPLICATE CHECK] Error: {e}")
        
        return results
    
    async def cleanup_expired_credits(self) -> Dict:
        """
        Remove expired credits from accounts.
        
        Finds credits past their expiry date and removes them.
        
        Returns:
            Dict with accounts cleaned and credits removed
        """
        results = {
            'accounts_cleaned': 0,
            'credits_removed': 0.0
        }
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            now = datetime.now(timezone.utc)
            
            async with async_db_session() as session:
                # Find accounts with expired credits
                # This assumes a stored procedure exists, or we implement inline
                result = await session.execute(
                    text("""
                        SELECT account_id, expiring_credits
                        FROM credit_accounts
                        WHERE expiring_credits > 0
                        AND credit_expiry_date < :now
                    """),
                    {"now": now}
                )
                expired = result.fetchall()
                
                for account in expired:
                    credits_to_remove = float(account.expiring_credits)
                    
                    # Update account
                    await session.execute(
                        text("""
                            UPDATE credit_accounts
                            SET expiring_credits = 0,
                                balance = balance - :amount,
                                updated_at = :now
                            WHERE account_id = :account_id::uuid
                        """),
                        {
                            "account_id": str(account.account_id),
                            "amount": credits_to_remove,
                            "now": now
                        }
                    )
                    
                    # Log expiry
                    await session.execute(
                        text("""
                            INSERT INTO credit_ledger (
                                account_id, amount, balance_after, type, description
                            ) VALUES (
                                :account_id::uuid, :amount, 
                                (SELECT balance FROM credit_accounts WHERE account_id = :account_id::uuid),
                                'expiry', 'Credits expired'
                            )
                        """),
                        {
                            "account_id": str(account.account_id),
                            "amount": -credits_to_remove
                        }
                    )
                    
                    results['accounts_cleaned'] += 1
                    results['credits_removed'] += credits_to_remove
                    
                    logger.info(
                        f"[CLEANUP] Removed ${credits_to_remove:.2f} expired credits "
                        f"from {account.account_id}"
                    )
                
                await session.commit()
        
        except Exception as e:
            logger.error(f"[CLEANUP] Error: {e}")
        
        return results
    
    async def retry_failed_payment(self, payment_id: str) -> Dict:
        """
        Retry processing a specific failed payment.
        
        Args:
            payment_id: Credit purchase ID
            
        Returns:
            Dict with success status
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Get payment record
                result = await session.execute(
                    text("""
                        SELECT * FROM credit_purchases WHERE id = :id::uuid
                    """),
                    {"id": payment_id}
                )
                payment = result.fetchone()
                
                if not payment:
                    return {'success': False, 'error': 'Payment not found'}
                
                if payment.status != 'pending':
                    return {
                        'success': False,
                        'error': f'Payment status is {payment.status}, cannot retry'
                    }
                
                # Check Stripe status
                payment_intent = await StripeAPIWrapper.retrieve_payment_intent(
                    payment.stripe_payment_intent_id
                )
                
                if payment_intent.get('status') == 'succeeded':
                    # Add credits
                    add_result = await credit_manager.add_credits(
                        account_id=str(payment.account_id),
                        amount=Decimal(str(payment.amount_dollars)),
                        is_expiring=False,
                        description=f"Reconciled purchase: ${payment.amount_dollars} credits",
                        credit_type='purchase',
                        stripe_event_id=f"retry_{payment_id}"
                    )
                    
                    # Update purchase record
                    await session.execute(
                        text("""
                            UPDATE credit_purchases
                            SET status = 'completed',
                                completed_at = :now
                            WHERE id = :id::uuid
                        """),
                        {"id": payment_id, "now": datetime.now(timezone.utc)}
                    )
                    await session.commit()
                    
                    logger.info(f"[RETRY] Successfully reconciled payment {payment_id}")
                    return {
                        'success': True,
                        'action': 'reconciled',
                        'credits_added': float(payment.amount_dollars)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Stripe payment status: {payment_intent.get("status")}'
                    }
        
        except Exception as e:
            logger.error(f"[RETRY] Error retrying payment {payment_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def run_full_reconciliation(self) -> Dict:
        """
        Run all reconciliation tasks.
        
        Returns:
            Dict with all reconciliation results
        """
        logger.info("[RECONCILIATION] Starting full reconciliation run")
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'failed_payments': await self.reconcile_failed_payments(),
            'balance_check': await self.verify_balance_consistency(),
            'duplicate_check': await self.detect_double_charges(),
            'expired_cleanup': await self.cleanup_expired_credits()
        }
        
        logger.info("[RECONCILIATION] Full reconciliation complete")
        return results


# Global instance
reconciliation_service = ReconciliationService()
