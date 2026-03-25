"""
Trial Service

Manages trial subscription lifecycle including:
- Trial eligibility checking
- Trial signup with checkout
- Trial cancellation
- Trial conversion to paid plans

Based on external_billing/subscriptions/trial_service.py.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Optional

from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.config import TIERS, get_tier_by_name
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
from backend.src.billing.shared.exceptions import BillingError, TrialError
from backend.src.billing.credits import credit_manager
from .handlers.customer import CustomerHandler

logger = logging.getLogger(__name__)

# Trial configuration
TRIAL_ENABLED = True  # Set to False to disable trials
TRIAL_DURATION_DAYS = 7
TRIAL_TIER = 'tier_2_20'  # Trial gets Plus tier features
TRIAL_CREDITS = Decimal('5.00')


class TrialService:
    """
    Manages trial subscriptions.
    
    Trial flow:
    1. User requests trial -> create checkout session
    2. User completes checkout (card setup) -> trial starts
    3. Trial active for TRIAL_DURATION_DAYS
    4. At end: convert to paid or cancel
    
    Trials are tracked in trial_history table and
    users can only have one trial per lifetime.
    """
    
    @classmethod
    async def get_trial_status(cls, account_id: str) -> Dict:
        """
        Get trial eligibility and status for account.
        
        Returns:
            Dict with has_trial, trial_status, can_start_trial, etc.
        """
        service = cls()
        return await service._get_trial_status(account_id)
    
    async def _get_trial_status(self, account_id: str) -> Dict:
        """Internal implementation of get_trial_status."""
        if not TRIAL_ENABLED:
            return {
                'has_trial': False,
                'message': 'Trials are not currently available'
            }
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Check credit account for current trial status
                result = await session.execute(
                    text("""
                        SELECT tier, trial_status, trial_ends_at, stripe_subscription_id
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                account = result.fetchone()
                
                if account:
                    trial_status = account.trial_status or 'none'
                    
                    if trial_status == 'active':
                        return {
                            'has_trial': True,
                            'trial_status': 'active',
                            'trial_ends_at': account.trial_ends_at.isoformat() if account.trial_ends_at else None,
                            'tier': account.tier,
                            'days_remaining': self._calculate_days_remaining(account.trial_ends_at)
                        }
                    
                    if trial_status in ['expired', 'converted', 'cancelled']:
                        # Check if there's retryable history
                        is_retryable = await self._check_retryable_trial(session, account_id)
                        if is_retryable:
                            return {
                                'has_trial': False,
                                'trial_status': 'none',
                                'can_start_trial': True,
                                'message': 'You can retry starting your free trial'
                            }
                        
                        return {
                            'has_trial': False,
                            'trial_status': 'used',
                            'message': 'You have already used your free trial'
                        }
                
                # Check trial history
                history_result = await session.execute(
                    text("""
                        SELECT status FROM trial_history
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                history = history_result.fetchone()
                
                if history:
                    retryable = ['checkout_pending', 'checkout_created', 'checkout_failed']
                    if history.status in retryable:
                        return {
                            'has_trial': False,
                            'trial_status': 'none',
                            'can_start_trial': True,
                            'message': 'You can retry starting your free trial'
                        }
                    return {
                        'has_trial': False,
                        'trial_status': 'used',
                        'message': 'You have already used your free trial'
                    }
                
                # No history - eligible for trial
                return {
                    'has_trial': False,
                    'trial_status': 'none',
                    'can_start_trial': True,
                    'trial_duration_days': TRIAL_DURATION_DAYS,
                    'trial_credits': float(TRIAL_CREDITS),
                    'message': 'You are eligible for a free trial'
                }
                
        except Exception as e:
            logger.error(f"[TRIAL] Error getting trial status: {e}")
            return {
                'has_trial': False,
                'trial_status': 'unknown',
                'error': str(e)
            }
    
    @classmethod
    async def start_trial(
        cls,
        account_id: str,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Start trial by creating checkout session.
        
        User must complete checkout (add payment method) for trial to start.
        No charge is made until trial ends and converts.
        
        Args:
            account_id: User account UUID
            success_url: URL for successful checkout
            cancel_url: URL for cancelled checkout
            
        Returns:
            Dict with checkout_url
        """
        service = cls()
        return await service._start_trial(account_id, success_url, cancel_url)
    
    async def _start_trial(
        self,
        account_id: str,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """Internal implementation of start_trial."""
        if not TRIAL_ENABLED:
            raise TrialError(
                code="TRIALS_DISABLED",
                message="Trials are not currently available"
            )
        
        # Check eligibility
        status = await self._get_trial_status(account_id)
        if status.get('has_trial'):
            raise TrialError(
                code="TRIAL_ACTIVE",
                message="You already have an active trial"
            )
        if not status.get('can_start_trial'):
            raise TrialError(
                code="TRIAL_USED",
                message="You have already used your free trial"
            )
        
        logger.info(f"[TRIAL] Starting trial for {account_id}")
        
        # Get/create customer
        customer_id = await CustomerHandler.get_or_create_stripe_customer(account_id)
        
        # Get trial tier price ID
        trial_tier = get_tier_by_name(TRIAL_TIER)
        if not trial_tier or not trial_tier.price_ids:
            raise TrialError(
                code="TRIAL_CONFIG_ERROR",
                message="Trial tier not properly configured"
            )
        
        price_id = trial_tier.price_ids[0]
        
        # Record trial start attempt
        await self._record_trial_start_attempt(account_id)
        
        # Create checkout session with trial
        try:
            session = await StripeAPIWrapper.create_checkout_session(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{'price': price_id, 'quantity': 1}],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data={
                    'trial_period_days': TRIAL_DURATION_DAYS,
                    'metadata': {
                        'account_id': account_id,
                        'trial': 'true',
                        'trial_tier': TRIAL_TIER
                    }
                },
                metadata={
                    'account_id': account_id,
                    'checkout_type': 'trial_start'
                }
            )
            
            # Update trial history with checkout
            await self._update_trial_checkout(account_id, session.id)
            
            logger.info(f"[TRIAL] Created checkout session {session.id} for {account_id}")
            
            return {
                'success': True,
                'checkout_url': session.url,
                'session_id': session.id,
                'trial_duration_days': TRIAL_DURATION_DAYS,
                'trial_credits': float(TRIAL_CREDITS)
            }
            
        except Exception as e:
            logger.error(f"[TRIAL] Failed to create trial checkout: {e}")
            raise TrialError(
                code="CHECKOUT_FAILED",
                message=f"Failed to start trial: {e}"
            )
    
    @classmethod
    async def cancel_trial(cls, account_id: str) -> Dict:
        """
        Cancel an active trial.
        
        Immediately cancels trial, removes credits, and
        downgrades to free tier.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Dict with success and message
        """
        service = cls()
        return await service._cancel_trial(account_id)
    
    async def _cancel_trial(self, account_id: str) -> Dict:
        """Internal implementation of cancel_trial."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Get trial info
                result = await session.execute(
                    text("""
                        SELECT trial_status, stripe_subscription_id, balance
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                account = result.fetchone()
                
                if not account:
                    raise TrialError(
                        code="ACCOUNT_NOT_FOUND",
                        message="Account not found"
                    )
                
                if account.trial_status != 'active':
                    raise TrialError(
                        code="NO_ACTIVE_TRIAL",
                        message=f"No active trial to cancel (status: {account.trial_status})"
                    )
                
                subscription_id = account.stripe_subscription_id
                current_balance = float(account.balance or 0)
                
                # Cancel Stripe subscription
                if subscription_id:
                    await StripeAPIWrapper.cancel_subscription(
                        subscription_id, cancel_immediately=True
                    )
                    logger.info(f"[TRIAL] Cancelled subscription {subscription_id}")
                
                now = datetime.now(timezone.utc)
                
                # Update credit account
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET trial_status = 'cancelled',
                            tier = 'free',
                            balance = 0,
                            expiring_credits = 0,
                            stripe_subscription_id = NULL,
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id, "now": now}
                )
                
                # Update trial history
                await session.execute(
                    text("""
                        INSERT INTO trial_history (
                            account_id, started_at, ended_at, converted_to_paid, status
                        ) VALUES (
                            :account_id::uuid, :now, :now, false, 'cancelled'
                        )
                        ON CONFLICT (account_id) DO UPDATE
                        SET ended_at = :now, status = 'cancelled', converted_to_paid = false
                    """),
                    {"account_id": account_id, "now": now}
                )
                
                # Log credit removal
                if current_balance > 0:
                    await session.execute(
                        text("""
                            INSERT INTO credit_ledger (
                                account_id, amount, balance_after, type, description
                            ) VALUES (
                                :account_id::uuid, :amount, 0, 'adjustment', 
                                'Trial cancelled - credits removed'
                            )
                        """),
                        {
                            "account_id": account_id,
                            "amount": -current_balance
                        }
                    )
                
                await session.commit()
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[TRIAL] Successfully cancelled trial for {account_id}")
            
            return {
                'success': True,
                'message': 'Trial cancelled successfully'
            }
            
        except TrialError:
            raise
        except Exception as e:
            logger.error(f"[TRIAL] Error cancelling trial: {e}")
            raise TrialError(
                code="CANCEL_FAILED",
                message=f"Failed to cancel trial: {e}"
            )
    
    @classmethod
    async def activate_trial_from_checkout(
        cls,
        account_id: str,
        subscription_id: str
    ) -> Dict:
        """
        Activate trial after successful checkout.
        
        Called by webhook after checkout.session.completed.
        
        Args:
            account_id: User account UUID
            subscription_id: Stripe subscription ID
            
        Returns:
            Dict with success status
        """
        service = cls()
        return await service._activate_trial(account_id, subscription_id)
    
    async def _activate_trial(
        self,
        account_id: str,
        subscription_id: str
    ) -> Dict:
        """Internal implementation of trial activation."""
        logger.info(f"[TRIAL] Activating trial for {account_id}")
        
        now = datetime.now(timezone.utc)
        trial_ends = now + timedelta(days=TRIAL_DURATION_DAYS)
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Update credit account
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET tier = :tier,
                            trial_status = 'active',
                            trial_ends_at = :trial_ends,
                            stripe_subscription_id = :sub_id,
                            updated_at = :now
                        WHERE account_id = :account_id::uuid
                    """),
                    {
                        "account_id": account_id,
                        "tier": TRIAL_TIER,
                        "trial_ends": trial_ends,
                        "sub_id": subscription_id,
                        "now": now
                    }
                )
                
                # Update trial history
                await session.execute(
                    text("""
                        INSERT INTO trial_history (
                            account_id, started_at, status
                        ) VALUES (
                            :account_id::uuid, :now, 'active'
                        )
                        ON CONFLICT (account_id) DO UPDATE
                        SET started_at = :now, status = 'active'
                    """),
                    {"account_id": account_id, "now": now}
                )
                
                await session.commit()
            
            # Grant trial credits
            await credit_manager.add_credits(
                account_id=account_id,
                amount=TRIAL_CREDITS,
                is_expiring=True,
                description="Trial credits",
                credit_type="trial_grant",
                expires_at=trial_ends
            )
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[TRIAL] ✅ Trial activated for {account_id}, ends {trial_ends}")
            
            return {
                'success': True,
                'trial_ends_at': trial_ends.isoformat(),
                'trial_credits': float(TRIAL_CREDITS)
            }
            
        except Exception as e:
            logger.error(f"[TRIAL] Activation error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_days_remaining(self, ends_at) -> int:
        """Calculate days remaining in trial."""
        if not ends_at:
            return 0
        now = datetime.now(timezone.utc)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        remaining = (ends_at - now).days
        return max(0, remaining)
    
    async def _check_retryable_trial(self, session, account_id: str) -> bool:
        """Check if trial history allows retry."""
        from sqlalchemy import text
        
        result = await session.execute(
            text("SELECT status FROM trial_history WHERE account_id = :account_id::uuid"),
            {"account_id": account_id}
        )
        history = result.fetchone()
        
        if history:
            retryable = ['checkout_pending', 'checkout_created', 'checkout_failed']
            return history.status in retryable
        return True
    
    async def _record_trial_start_attempt(self, account_id: str) -> None:
        """Record trial start attempt in history."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO trial_history (account_id, status)
                        VALUES (:account_id::uuid, 'checkout_pending')
                        ON CONFLICT (account_id) DO UPDATE
                        SET status = 'checkout_pending'
                    """),
                    {"account_id": account_id}
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"[TRIAL] Could not record start attempt: {e}")
    
    async def _update_trial_checkout(self, account_id: str, session_id: str) -> None:
        """Update trial history with checkout session."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        UPDATE trial_history
                        SET status = 'checkout_created',
                            checkout_session_id = :session_id
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id, "session_id": session_id}
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"[TRIAL] Could not update checkout: {e}")


# Global instance
trial_service = TrialService()


# Convenience functions
async def get_trial_status(account_id: str) -> Dict:
    """Get trial eligibility and status."""
    return await TrialService.get_trial_status(account_id)


async def start_trial(account_id: str, success_url: str, cancel_url: str) -> Dict:
    """Start trial with checkout session."""
    return await TrialService.start_trial(account_id, success_url, cancel_url)


async def cancel_trial(account_id: str) -> Dict:
    """Cancel active trial."""
    return await TrialService.cancel_trial(account_id)
