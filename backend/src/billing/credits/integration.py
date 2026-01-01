"""
Billing Integration Service

High-level interface for billing operations from the application layer.
Provides:
- Pre-flight billing checks before LLM calls
- Model access validation based on subscription tier
- Usage deduction after LLM calls
- Credit summary retrieval

This is the main entry point for other parts of the application
to interact with the billing system.

Based on external_billing/credits/integration.py.
"""

import logging
import time
from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timezone

from backend.core.conf import settings
from backend.src.billing.shared.config import is_model_allowed, get_tier_by_name
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
from backend.src.billing.shared.exceptions import (
    InsufficientCreditsError,
    BillingError,
)
from .manager import credit_manager
from .calculator import calculate_token_cost, calculate_cached_token_cost, calculate_cache_write_cost
from .daily_refresh import check_and_refresh_daily_credits

logger = logging.getLogger(__name__)


class BillingIntegration:
    """
    High-level billing integration for the application.
    
    This class provides the main interface for:
    1. Pre-checking credits before running operations
    2. Validating model access based on subscription
    3. Deducting usage costs after operations
    4. Retrieving credit summaries
    
    Usage:
        # Before running an LLM call
        can_run, message, info = await BillingIntegration.check_model_and_billing_access(
            account_id=user_id,
            model_name="gpt-4"
        )
        
        if not can_run:
            raise HTTPError(402, message)
        
        # After LLM call completes
        result = await BillingIntegration.deduct_usage(
            account_id=user_id,
            prompt_tokens=1000,
            completion_tokens=500,
            model="gpt-4"
        )
    """
    
    @staticmethod
    def _is_local_mode() -> bool:
        """Check if running in local/development mode where billing is disabled."""
        return getattr(settings, 'ENV', 'production') == 'local' or not getattr(settings, 'BILLING_ENABLED', True)
    
    @staticmethod
    async def check_and_reserve_credits(
        account_id: str,
        estimated_cost: Optional[Decimal] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Pre-flight check for credit availability.
        
        Also triggers daily credit refresh if applicable.
        
        Args:
            account_id: User account UUID
            estimated_cost: Optional estimated cost to verify
            
        Returns:
            Tuple of (can_run: bool, message: str, reservation_id: Optional[str])
        """
        # Skip in local mode
        if BillingIntegration._is_local_mode():
            return True, "Local mode - billing disabled", None
        
        try:
            # Check and refresh daily credits if needed
            try:
                refreshed, amount = await check_and_refresh_daily_credits(account_id)
                if refreshed and amount > 0:
                    logger.info(f"[BILLING] Daily credits refreshed: ${amount} for {account_id}")
            except Exception as e:
                logger.warning(f"[BILLING] Failed to check/refresh daily credits: {e}")
            
            # Get current balance
            start = time.time()
            balance_info = await credit_manager.get_balance(account_id, use_cache=True)
            elapsed = (time.time() - start) * 1000
            logger.debug(f"[BILLING] Balance check took {elapsed:.1f}ms")
            
            balance = balance_info.get('total', Decimal('0'))
            
            # Check if sufficient credits
            if balance < 0:
                return False, (
                    f"Insufficient credits. Your balance is ${balance:.2f}. "
                    "Please add credits to continue."
                ), None
            
            if estimated_cost and balance < estimated_cost:
                return False, (
                    f"Insufficient credits for this operation. "
                    f"Required: ${estimated_cost:.2f}, Available: ${balance:.2f}"
                ), None
            
            return True, f"Credits available: ${balance:.2f}", None
            
        except Exception as e:
            logger.error(f"[BILLING] Error checking credits for {account_id}: {e}")
            # Fail open in case of errors (allow the operation)
            return True, f"Credit check error (proceeding): {e}", None
    
    @staticmethod
    async def check_model_and_billing_access(
        account_id: str,
        model_name: Optional[str] = None,
        estimated_cost: Optional[Decimal] = None
    ) -> Tuple[bool, str, Dict]:
        """
        Combined check for model access and billing status.
        
        This is the main pre-flight check before any billable operation.
        
        Args:
            account_id: User account UUID
            model_name: LLM model being requested
            estimated_cost: Optional estimated cost
            
        Returns:
            Tuple of (allowed: bool, message: str, details: Dict)
        """
        # Skip in local mode
        if BillingIntegration._is_local_mode():
            logger.debug("[BILLING] Local mode - skipping all billing checks")
            return True, "Local development mode", {"local_mode": True}
        
        try:
            # Validate model is specified
            if not model_name:
                return False, "No model specified", {"error_type": "no_model"}
            
            # Get user's subscription tier
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT tier, stripe_subscription_id
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
            
            if not row:
                # No credit account - might be a new user
                return False, "Account not found. Please set up billing.", {
                    "error_type": "no_account"
                }
            
            tier_name = row.tier or 'none'
            tier_info = get_tier_by_name(tier_name)
            
            # Check model access
            if not is_model_allowed(tier_name, model_name):
                available_models = tier_info.models if tier_info else []
                return False, (
                    f"Your current subscription plan ({tier_name}) does not include "
                    f"access to {model_name}. Please upgrade your subscription."
                ), {
                    "allowed_models": available_models,
                    "tier_name": tier_name,
                    "error_type": "model_access_denied",
                    "error_code": "MODEL_ACCESS_DENIED"
                }
            
            # Check billing/credits
            can_run, message, reservation_id = await BillingIntegration.check_and_reserve_credits(
                account_id, estimated_cost
            )
            
            if not can_run:
                return False, f"Billing check failed: {message}", {
                    "tier_name": tier_name,
                    "error_type": "insufficient_credits"
                }
            
            # All checks passed
            return True, "Access granted", {
                "tier_name": tier_name,
                "tier_info": {
                    "name": tier_info.name if tier_info else tier_name,
                    "display_name": tier_info.display_name if tier_info else tier_name,
                    "models": tier_info.models if tier_info else []
                },
                "reservation_id": reservation_id
            }
            
        except Exception as e:
            logger.error(f"[BILLING] Error in unified billing check for {account_id}: {e}")
            # Fail open for system errors
            return True, f"Warning: billing check error - {e}", {"error_type": "system_error"}
    
    @staticmethod
    async def deduct_usage(
        account_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0
    ) -> Dict:
        """
        Deduct credits for LLM usage.
        
        Call this after an LLM call completes with token usage.
        
        Args:
            account_id: User account UUID
            prompt_tokens: Total input tokens
            completion_tokens: Output tokens
            model: Model used
            thread_id: Associated conversation thread
            message_id: Associated message
            cache_read_tokens: Tokens read from cache (cheaper)
            cache_creation_tokens: Tokens written to cache
            
        Returns:
            Dict with success, cost, new_balance, breakdown
        """
        # Skip in local mode
        if BillingIntegration._is_local_mode():
            return {'success': True, 'cost': 0, 'new_balance': 999999, 'local_mode': True}
        
        try:
            # Calculate cost with cache handling
            if cache_read_tokens > 0 or cache_creation_tokens > 0:
                # Non-cached portion
                non_cached_prompt_tokens = max(0, prompt_tokens - cache_read_tokens - cache_creation_tokens)
                
                # Component costs
                cached_read_cost = calculate_cached_token_cost(cache_read_tokens, model) if cache_read_tokens > 0 else Decimal('0')
                cache_write_cost = calculate_cache_write_cost(cache_creation_tokens, model) if cache_creation_tokens > 0 else Decimal('0')
                regular_cost = calculate_token_cost(non_cached_prompt_tokens, completion_tokens, model)
                
                cost = cached_read_cost + cache_write_cost + regular_cost
                
                logger.debug(
                    f"[BILLING] Cost breakdown: cached_read=${cached_read_cost:.6f}, "
                    f"cache_write=${cache_write_cost:.6f}, regular=${regular_cost:.6f}, "
                    f"total=${cost:.6f}"
                )
            else:
                cost = calculate_token_cost(prompt_tokens, completion_tokens, model)
            
            # Skip if zero cost
            if cost <= 0:
                logger.debug(f"[BILLING] Zero cost for {model} - skipping deduction")
                balance = await credit_manager.get_balance(account_id)
                return {
                    'success': True,
                    'cost': 0,
                    'new_balance': float(balance['total'])
                }
            
            logger.debug(f"[BILLING] Deducting ${cost:.6f} for {model} usage from {account_id}")
            
            # Perform deduction
            result = await credit_manager.deduct_credits(
                account_id=account_id,
                amount=cost,
                description=f"{model} usage",
                deduction_type='usage',
                thread_id=thread_id,
                message_id=message_id,
                model=model,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens
            )
            
            if result.get('success'):
                logger.debug(
                    f"[BILLING] ✅ Deducted ${cost:.6f} from {account_id}. "
                    f"New balance: ${result.get('new_balance', 0):.2f} "
                    f"(from: daily=${result.get('from_daily', 0):.2f}, "
                    f"expiring=${result.get('from_expiring', 0):.2f}, "
                    f"non_expiring=${result.get('from_non_expiring', 0):.2f})"
                )
                
                # Invalidate cache
                await invalidate_account_state_cache(account_id)
            else:
                logger.error(f"[BILLING] ❌ Failed to deduct credits for {account_id}")
            
            return {
                'success': result.get('success', False),
                'cost': float(cost),
                'new_balance': result.get('new_total', result.get('new_balance', 0)),
                'from_daily': result.get('from_daily', 0),
                'from_expiring': result.get('from_expiring', 0),
                'from_non_expiring': result.get('from_non_expiring', 0),
                'transaction_id': result.get('transaction_id')
            }
            
        except InsufficientCreditsError as e:
            logger.warning(f"[BILLING] Insufficient credits for {account_id}: {e}")
            return {
                'success': False,
                'error': 'insufficient_credits',
                'required': float(e.required),
                'available': float(e.available)
            }
        except Exception as e:
            logger.error(f"[BILLING] Error deducting usage for {account_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_credit_summary(account_id: str) -> Dict:
        """
        Get detailed credit summary for an account.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Dict with balance breakdown, tier info, usage statistics
        """
        return await credit_manager.get_credit_summary(account_id)
    
    @staticmethod
    async def add_credits(
        account_id: str,
        amount: Decimal,
        description: str = "Credits added",
        is_expiring: bool = True,
        **kwargs
    ) -> Dict:
        """
        Add credits to an account.
        
        Args:
            account_id: User account UUID
            amount: Amount to add
            description: Reason for addition
            is_expiring: Whether credits expire (False for purchases)
            **kwargs: Additional arguments for credit_manager.add_credits
            
        Returns:
            Dict with success and new balance
        """
        result = await credit_manager.add_credits(
            account_id=account_id,
            amount=amount,
            description=description,
            is_expiring=is_expiring,
            **kwargs
        )
        
        # Invalidate cache
        await invalidate_account_state_cache(account_id)
        
        return result
    
    @staticmethod
    async def can_afford(account_id: str, estimated_cost: Decimal) -> bool:
        """
        Quick check if account can afford an operation.
        
        Args:
            account_id: User account UUID
            estimated_cost: Estimated cost of operation
            
        Returns:
            True if account has sufficient credits
        """
        if BillingIntegration._is_local_mode():
            return True
        
        try:
            balance = await credit_manager.get_balance(account_id)
            return balance['total'] >= estimated_cost
        except Exception:
            return True  # Fail open


# Global instance
billing_integration = BillingIntegration()


# Convenience functions for external use
async def check_and_reserve_credits(account_id: str, estimated_cost: Optional[Decimal] = None) -> Tuple[bool, str, Optional[str]]:
    """Check credit availability and optionally reserve."""
    return await BillingIntegration.check_and_reserve_credits(account_id, estimated_cost)


async def check_model_and_billing_access(
    account_id: str,
    model_name: Optional[str] = None,
    estimated_cost: Optional[Decimal] = None
) -> Tuple[bool, str, Dict]:
    """Combined model access and billing check."""
    return await BillingIntegration.check_model_and_billing_access(account_id, model_name, estimated_cost)


async def deduct_usage(
    account_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    **kwargs
) -> Dict:
    """Deduct credits for LLM usage."""
    return await BillingIntegration.deduct_usage(
        account_id, prompt_tokens, completion_tokens, model, **kwargs
    )


async def get_credit_summary(account_id: str) -> Dict:
    """Get credit summary for an account."""
    return await BillingIntegration.get_credit_summary(account_id)


async def add_credits(account_id: str, amount: Decimal, **kwargs) -> Dict:
    """Add credits to an account."""
    return await BillingIntegration.add_credits(account_id, amount, **kwargs)


async def can_afford(account_id: str, estimated_cost: Decimal) -> bool:
    """Quick affordability check."""
    return await BillingIntegration.can_afford(account_id, estimated_cost)
