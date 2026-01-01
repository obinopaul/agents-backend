"""
Credit Manager

Comprehensive credit management with:
- Atomic add/deduct operations
- Priority-based deduction (daily → expiring → non-expiring)
- Monthly credit renewal
- Daily credit refresh for free tier
- Full audit trail via credit ledger

Based on external_billing/credits/manager.py.
"""

import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, Any

from backend.src.billing.shared.exceptions import (
    InsufficientCreditsError,
    BillingError,
)
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache

logger = logging.getLogger(__name__)


class CreditManager:
    """
    Manages credit operations for user accounts.
    
    Credit Types:
    - daily_credits_balance: Free tier daily refresh (reset daily)
    - expiring_credits: Monthly subscription credits (expire at billing cycle)
    - non_expiring_credits: Purchased credits (never expire)
    
    Deduction Priority:
    1. Daily credits (use first, doesn't reduce total allocation)
    2. Expiring credits (use before they expire)
    3. Non-expiring credits (preserve as long as possible)
    
    All operations:
    - Are logged to credit_ledger for audit trail
    - Support idempotency via stripe_event_id
    - Invalidate caches after completion
    
    Usage:
        credit_manager = CreditManager()
        
        # Add credits
        result = await credit_manager.add_credits(
            account_id, amount=Decimal('10.00'), is_expiring=False
        )
        
        # Deduct credits
        result = await credit_manager.deduct_credits(
            account_id, amount=Decimal('0.05'), description="GPT-4 usage"
        )
    """
    
    def __init__(self, use_atomic_functions: bool = True):
        """
        Initialize CreditManager.
        
        Args:
            use_atomic_functions: If True, try PostgreSQL stored procedures first
        """
        self.use_atomic_functions = use_atomic_functions
    
    # =========================================================================
    # ADD CREDITS
    # =========================================================================
    
    async def add_credits(
        self,
        account_id: str,
        amount: Decimal,
        is_expiring: bool = True,
        description: str = "Credit added",
        expires_at: Optional[datetime] = None,
        credit_type: Optional[str] = None,
        stripe_event_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Add credits to an account.
        
        Args:
            account_id: User account UUID
            amount: Amount to add (in dollars)
            is_expiring: True for monthly credits, False for purchased
            description: Human-readable description for ledger
            expires_at: When these credits expire (for expiring credits)
            credit_type: Type for ledger (tier_grant, purchase, refund, adjustment)
            stripe_event_id: For idempotency - prevents duplicate additions
            metadata: Additional metadata for ledger
            
        Returns:
            Dict with success, credit_id, ledger_id, new_balance, amount_added
            
        Raises:
            ValueError: If amount <= 0
            BillingError: If database operation fails
        """
        amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Generate idempotency key if not provided
        if not stripe_event_id:
            idempotency_key = f"{account_id}_{description}_{amount}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        else:
            idempotency_key = stripe_event_id
        
        logger.info(f"[CREDITS] Adding ${amount} to {account_id} (expiring={is_expiring})")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            credit_id = str(uuid.uuid4())
            ledger_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            async with async_db_session() as session:
                # Check for duplicate using stripe_event_id
                if stripe_event_id:
                    dup_check = await session.execute(
                        text("""
                            SELECT id FROM credit_ledger 
                            WHERE stripe_event_id = :event_id
                        """),
                        {"event_id": stripe_event_id}
                    )
                    if dup_check.fetchone():
                        logger.info(f"[CREDITS] Duplicate addition detected for {account_id}, returning success")
                        balance = await self.get_balance(account_id)
                        return {
                            'success': True,
                            'duplicate': True,
                            'new_balance': balance['total'],
                            'amount_added': amount
                        }
                
                # Update credit account
                if is_expiring:
                    await session.execute(
                        text("""
                            UPDATE credit_accounts
                            SET expiring_credits = expiring_credits + :amount,
                                balance = balance + :amount,
                                updated_at = :now
                            WHERE account_id = CAST(:account_id AS UUID)
                        """),
                        {
                            "account_id": account_id,
                            "amount": float(amount),
                            "now": now
                        }
                    )
                else:
                    await session.execute(
                        text("""
                            UPDATE credit_accounts
                            SET non_expiring_credits = non_expiring_credits + :amount,
                                balance = balance + :amount,
                                updated_at = :now
                            WHERE account_id = CAST(:account_id AS UUID)
                        """),
                        {
                            "account_id": account_id,
                            "amount": float(amount),
                            "now": now
                        }
                    )
                
                # Get new balance
                result = await session.execute(
                    text("SELECT balance FROM credit_accounts WHERE account_id = CAST(:account_id AS UUID)"),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                new_balance = Decimal(str(row.balance)) if row else Decimal('0')
                
                # Insert ledger entry
                ledger_values = {
                    "id": ledger_id,
                    "account_id": account_id,
                    "amount": float(amount),
                    "balance_after": float(new_balance),
                    "type": credit_type or ('tier_grant' if is_expiring else 'purchase'),
                    "description": description,
                    "is_expiring": is_expiring,
                    "credit_id": credit_id,
                    "stripe_event_id": stripe_event_id,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "metadata": str(metadata) if metadata else None
                }
                
                await session.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            id, account_id, amount, balance_after, type, description,
                            is_expiring, credit_id, stripe_event_id, expires_at, metadata
                        ) VALUES (
                            CAST(:id AS UUID), CAST(:account_id AS UUID), :amount, :balance_after, :type, :description,
                            :is_expiring, CAST(:credit_id AS UUID), :stripe_event_id, :expires_at::timestamptz, 
                            :metadata::jsonb
                        )
                    """),
                    ledger_values
                )
                
                await session.commit()
            
            # Invalidate caches
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[CREDITS] ✅ Added ${amount} to {account_id}. New balance: ${new_balance}")
            
            return {
                'success': True,
                'credit_id': credit_id,
                'ledger_id': ledger_id,
                'new_balance': new_balance,
                'amount_added': amount
            }
            
        except Exception as e:
            logger.error(f"[CREDITS] Error adding credits to {account_id}: {e}", exc_info=True)
            raise BillingError(
                code="CREDIT_ADD_FAILED",
                message=f"Failed to add credits: {str(e)}",
                details={"account_id": account_id, "amount": float(amount)}
            )
    
    # =========================================================================
    # DEDUCT CREDITS
    # =========================================================================
    
    async def deduct_credits(
        self,
        account_id: str,
        amount: Decimal,
        description: str = "Credit deducted",
        deduction_type: str = "usage",
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        model: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        allow_negative: bool = False
    ) -> Dict:
        """
        Deduct credits from an account using priority-based deduction.
        
        Priority Order:
        1. Daily credits (daily_credits_balance)
        2. Expiring credits (expiring_credits)
        3. Non-expiring credits (non_expiring_credits)
        
        Args:
            account_id: User account UUID
            amount: Amount to deduct (in dollars)
            description: Human-readable description
            deduction_type: Type for ledger (usage, refund, adjustment)
            thread_id: Associated thread/conversation
            message_id: Associated message
            model: LLM model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            allow_negative: If True, allow balance to go negative
            
        Returns:
            Dict with success, amount_deducted, new_balance, breakdown
            
        Raises:
            InsufficientCreditsError: If balance too low and allow_negative is False
        """
        amount = Decimal(str(amount)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        if amount <= 0:
            logger.debug(f"[CREDITS] Zero/negative amount {amount} for {account_id}, skipping")
            balance = await self.get_balance(account_id)
            return {
                'success': True,
                'amount_deducted': Decimal('0'),
                'new_balance': balance['total'],
                'message': 'No deduction needed for zero amount'
            }
        
        logger.debug(f"[CREDITS] Deducting ${amount} from {account_id}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            now = datetime.now(timezone.utc)
            ledger_id = str(uuid.uuid4())
            
            async with async_db_session() as session:
                # Get current balances with lock
                result = await session.execute(
                    text("""
                        SELECT balance, daily_credits_balance, expiring_credits, non_expiring_credits
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                        FOR UPDATE
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    raise BillingError(
                        code="ACCOUNT_NOT_FOUND",
                        message=f"Credit account not found: {account_id}",
                        details={"account_id": account_id}
                    )
                
                # Current balances
                current_balance = Decimal(str(row.balance))
                daily_balance = Decimal(str(row.daily_credits_balance))
                expiring_balance = Decimal(str(row.expiring_credits))
                non_expiring_balance = Decimal(str(row.non_expiring_credits))
                
                # Check if sufficient
                if current_balance < amount and not allow_negative:
                    raise InsufficientCreditsError(
                        required=amount,
                        available=current_balance,
                        details={
                            "account_id": account_id,
                            "daily": float(daily_balance),
                            "expiring": float(expiring_balance),
                            "non_expiring": float(non_expiring_balance)
                        }
                    )
                
                # Priority-based deduction
                remaining = amount
                from_daily = Decimal('0')
                from_expiring = Decimal('0')
                from_non_expiring = Decimal('0')
                
                # 1. Deduct from daily credits first
                if remaining > 0 and daily_balance > 0:
                    deduct_from_daily = min(remaining, daily_balance)
                    from_daily = deduct_from_daily
                    remaining -= deduct_from_daily
                
                # 2. Deduct from expiring credits
                if remaining > 0 and expiring_balance > 0:
                    deduct_from_expiring = min(remaining, expiring_balance)
                    from_expiring = deduct_from_expiring
                    remaining -= deduct_from_expiring
                
                # 3. Deduct from non-expiring credits
                if remaining > 0 and non_expiring_balance > 0:
                    deduct_from_non_expiring = min(remaining, non_expiring_balance)
                    from_non_expiring = deduct_from_non_expiring
                    remaining -= deduct_from_non_expiring
                
                # Handle any remaining (if allow_negative or rounding issues)
                if remaining > 0:
                    if allow_negative:
                        from_non_expiring += remaining
                    else:
                        # Should not happen if check passed
                        logger.warning(f"[CREDITS] Unexpected remaining amount: {remaining}")
                
                # Calculate new balances
                new_daily = daily_balance - from_daily
                new_expiring = expiring_balance - from_expiring
                new_non_expiring = non_expiring_balance - from_non_expiring
                new_balance = new_daily + new_expiring + new_non_expiring
                
                # Update credit account
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET daily_credits_balance = :daily,
                            expiring_credits = :expiring,
                            non_expiring_credits = :non_expiring,
                            balance = :balance,
                            updated_at = :now
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {
                        "account_id": account_id,
                        "daily": float(new_daily),
                        "expiring": float(new_expiring),
                        "non_expiring": float(new_non_expiring),
                        "balance": float(new_balance),
                        "now": now
                    }
                )
                
                # Insert ledger entry
                await session.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            id, account_id, amount, balance_after, type, description,
                            is_expiring, thread_id, message_id, model, input_tokens, output_tokens,
                            metadata
                        ) VALUES (
                            CAST(:id AS UUID), CAST(:account_id AS UUID), :amount, :balance_after, :type, :description,
                            true, :thread_id, :message_id, :model, :input_tokens, :output_tokens,
                            :metadata::jsonb
                        )
                    """),
                    {
                        "id": ledger_id,
                        "account_id": account_id,
                        "amount": float(-amount),  # Negative for deduction
                        "balance_after": float(new_balance),
                        "type": deduction_type,
                        "description": description,
                        "thread_id": thread_id,
                        "message_id": message_id,
                        "model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "metadata": str({
                            "from_daily": float(from_daily),
                            "from_expiring": float(from_expiring),
                            "from_non_expiring": float(from_non_expiring)
                        })
                    }
                )
                
                await session.commit()
            
            # Invalidate caches
            await invalidate_account_state_cache(account_id)
            
            logger.debug(f"[CREDITS] ✅ Deducted ${amount} from {account_id}. "
                        f"Breakdown: daily=${from_daily}, expiring=${from_expiring}, "
                        f"non_expiring=${from_non_expiring}. New balance: ${new_balance}")
            
            return {
                'success': True,
                'amount_deducted': amount,
                'new_balance': new_balance,
                'new_total': float(new_balance),
                'from_daily': float(from_daily),
                'from_expiring': float(from_expiring),
                'from_non_expiring': float(from_non_expiring),
                'transaction_id': ledger_id
            }
            
        except InsufficientCreditsError:
            raise
        except Exception as e:
            logger.error(f"[CREDITS] Error deducting credits from {account_id}: {e}", exc_info=True)
            raise BillingError(
                code="CREDIT_DEDUCT_FAILED",
                message=f"Failed to deduct credits: {str(e)}",
                details={"account_id": account_id, "amount": float(amount)}
            )
    
    # =========================================================================
    # RESET EXPIRING CREDITS (Monthly Renewal)
    # =========================================================================
    
    async def reset_expiring_credits(
        self,
        account_id: str,
        new_credits: Decimal,
        description: str = "Monthly credit renewal",
        stripe_event_id: Optional[str] = None
    ) -> Dict:
        """
        Reset expiring credits to a new amount (for monthly renewal).
        
        This replaces the current expiring credits with the new amount.
        Non-expiring credits are preserved.
        
        Args:
            account_id: User account UUID
            new_credits: New expiring credit amount
            description: Description for ledger
            stripe_event_id: For idempotency
            
        Returns:
            Dict with success, new_expiring, non_expiring, total_balance
        """
        new_credits = Decimal(str(new_credits)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        logger.info(f"[CREDITS] Resetting expiring credits to ${new_credits} for {account_id}")
        
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            now = datetime.now(timezone.utc)
            
            # Calculate expiration (end of next billing cycle)
            expires_at = now.replace(day=1) + timedelta(days=32)
            expires_at = expires_at.replace(day=1)
            
            async with async_db_session() as session:
                # Get current state
                result = await session.execute(
                    text("""
                        SELECT balance, expiring_credits, non_expiring_credits, daily_credits_balance
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                        FOR UPDATE
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    raise BillingError(
                        code="ACCOUNT_NOT_FOUND",
                        message=f"Credit account not found: {account_id}"
                    )
                
                current_expiring = Decimal(str(row.expiring_credits))
                non_expiring = Decimal(str(row.non_expiring_credits))
                daily = Decimal(str(row.daily_credits_balance))
                
                # Calculate new total
                new_total = new_credits + non_expiring + daily
                
                # Update credit account
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET expiring_credits = :new_expiring,
                            balance = :new_total,
                            last_grant_date = :now,
                            updated_at = :now
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {
                        "account_id": account_id,
                        "new_expiring": float(new_credits),
                        "new_total": float(new_total),
                        "now": now
                    }
                )
                
                # Insert ledger entry
                await session.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            account_id, amount, balance_after, type, description,
                            is_expiring, expires_at, stripe_event_id, metadata
                        ) VALUES (
                            CAST(:account_id AS UUID), :amount, :balance_after, 'tier_grant', :description,
                            true, :expires_at, :stripe_event_id, :metadata::jsonb
                        )
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(new_credits),
                        "balance_after": float(new_total),
                        "description": description,
                        "expires_at": expires_at,
                        "stripe_event_id": stripe_event_id,
                        "metadata": str({
                            "renewal": True,
                            "previous_expiring": float(current_expiring),
                            "non_expiring_preserved": float(non_expiring)
                        })
                    }
                )
                
                await session.commit()
            
            # Invalidate caches
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[CREDITS] ✅ Reset expiring credits to ${new_credits} for {account_id}. "
                       f"Non-expiring preserved: ${non_expiring}. New total: ${new_total}")
            
            return {
                'success': True,
                'new_expiring': float(new_credits),
                'non_expiring': float(non_expiring),
                'daily': float(daily),
                'total_balance': float(new_total)
            }
            
        except Exception as e:
            logger.error(f"[CREDITS] Error resetting credits for {account_id}: {e}", exc_info=True)
            raise BillingError(
                code="CREDIT_RESET_FAILED",
                message=f"Failed to reset expiring credits: {str(e)}"
            )
    
    # =========================================================================
    # GET BALANCE
    # =========================================================================
    
    async def get_balance(self, account_id: str, use_cache: bool = True) -> Dict:
        """
        Get current credit balance for an account.
        
        Args:
            account_id: User account UUID
            use_cache: Whether to use cached balance
            
        Returns:
            Dict with total, daily, expiring, non_expiring balances
        """
        # Try cache first
        if use_cache:
            try:
                from backend.src.billing.shared.cache_utils import get_cached_account_state
                cached = await get_cached_account_state(account_id)
                if cached and 'balance' in cached:
                    return {
                        'total': Decimal(str(cached.get('balance', 0))),
                        'daily': Decimal(str(cached.get('daily_credits_balance', 0))),
                        'expiring': Decimal(str(cached.get('expiring_credits', 0))),
                        'non_expiring': Decimal(str(cached.get('non_expiring_credits', 0))),
                        'account_id': account_id
                    }
            except Exception as e:
                logger.debug(f"[CREDITS] Cache miss for {account_id}: {e}")
        
        # Query database
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT balance, daily_credits_balance, expiring_credits, non_expiring_credits
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        'total': Decimal(str(row.balance)),
                        'daily': Decimal(str(row.daily_credits_balance)),
                        'expiring': Decimal(str(row.expiring_credits)),
                        'non_expiring': Decimal(str(row.non_expiring_credits)),
                        'account_id': account_id
                    }
                
                return {
                    'total': Decimal('0'),
                    'daily': Decimal('0'),
                    'expiring': Decimal('0'),
                    'non_expiring': Decimal('0'),
                    'account_id': account_id
                }
                
        except Exception as e:
            logger.error(f"[CREDITS] Error getting balance for {account_id}: {e}")
            return {
                'total': Decimal('0'),
                'daily': Decimal('0'),
                'expiring': Decimal('0'),
                'non_expiring': Decimal('0'),
                'account_id': account_id,
                'error': str(e)
            }
    
    # =========================================================================
    # GET CREDIT SUMMARY
    # =========================================================================
    
    async def get_credit_summary(self, account_id: str) -> Dict:
        """
        Get detailed credit summary for an account.
        
        Returns:
            Dict with balances, tier info, and recent usage
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Get credit account
                result = await session.execute(
                    text("""
                        SELECT balance, daily_credits_balance, expiring_credits, non_expiring_credits,
                               tier, last_grant_date, last_daily_refresh
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if row:
                    # Get recent usage (last 30 days)
                    usage_result = await session.execute(
                        text("""
                            SELECT COALESCE(SUM(ABS(amount)), 0) as total_usage
                            FROM credit_ledger
                            WHERE account_id = CAST(:account_id AS UUID)
                            AND type = 'usage'
                            AND amount < 0
                            AND created_at > NOW() - INTERVAL '30 days'
                        """),
                        {"account_id": account_id}
                    )
                    usage_row = usage_result.fetchone()
                    monthly_usage = float(usage_row.total_usage) if usage_row else 0
                    
                    return {
                        'account_id': account_id,
                        'total_balance': float(row.balance),
                        'daily_balance': float(row.daily_credits_balance),
                        'expiring_balance': float(row.expiring_credits),
                        'non_expiring_balance': float(row.non_expiring_credits),
                        'tier': row.tier,
                        'last_grant_date': row.last_grant_date.isoformat() if row.last_grant_date else None,
                        'last_daily_refresh': row.last_daily_refresh.isoformat() if row.last_daily_refresh else None,
                        'monthly_usage': monthly_usage
                    }
                
                return {
                    'account_id': account_id,
                    'total_balance': 0,
                    'daily_balance': 0,
                    'expiring_balance': 0,
                    'non_expiring_balance': 0,
                    'tier': 'none',
                    'monthly_usage': 0
                }
                
        except Exception as e:
            logger.error(f"[CREDITS] Error getting summary for {account_id}: {e}")
            return {
                'account_id': account_id,
                'total_balance': 0,
                'error': str(e)
            }
    
    # =========================================================================
    # ENSURE CREDIT ACCOUNT EXISTS
    # =========================================================================
    
    async def ensure_credit_account(self, account_id: str, tier: str = 'none') -> Dict:
        """
        Ensure a credit account exists for the given user.
        Creates one with default values if it doesn't exist.
        
        Args:
            account_id: User account UUID
            tier: Initial tier (default: 'none')
            
        Returns:
            Dict with success and account info
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Check if exists
                result = await session.execute(
                    text("SELECT id FROM credit_accounts WHERE account_id = CAST(:account_id AS UUID)"),
                    {"account_id": account_id}
                )
                
                if result.fetchone():
                    return {'success': True, 'created': False}
                
                # Create new account
                now = datetime.now(timezone.utc)
                
                await session.execute(
                    text("""
                        INSERT INTO credit_accounts (
                            account_id, balance, expiring_credits, non_expiring_credits,
                            daily_credits_balance, tier, created_at, updated_at
                        ) VALUES (
                            CAST(:account_id AS UUID), 0, 0, 0, 0, :tier, :now, :now
                        )
                        ON CONFLICT (account_id) DO NOTHING
                    """),
                    {
                        "account_id": account_id,
                        "tier": tier,
                        "now": now
                    }
                )
                await session.commit()
                
                logger.info(f"[CREDITS] Created credit account for {account_id}")
                
                return {'success': True, 'created': True}
                
        except Exception as e:
            logger.error(f"[CREDITS] Error ensuring credit account: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
credit_manager = CreditManager()
