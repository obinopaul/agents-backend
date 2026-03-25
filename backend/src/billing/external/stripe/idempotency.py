"""
Stripe Idempotency Key Generation

Generates unique, deterministic idempotency keys for Stripe API calls
to prevent duplicate charges and operations.

Based on external_billing/external/stripe/idempotency.py.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class StripeIdempotencyManager:
    """
    Generates deterministic idempotency keys for Stripe operations.
    
    Keys are designed to:
    - Be unique per operation + account + parameters
    - Include a time bucket to allow retries within a window
    - Prevent duplicate charges if the same request is sent twice
    
    Usage:
        key = stripe_idempotency_manager.generate_checkout_key(account_id, price_id)
        session = await stripe.checkout.Session.create_async(
            idempotency_key=key,
            ...
        )
    """
    
    def generate_key(
        self,
        operation: str,
        account_id: str,
        *args,
        time_bucket_minutes: int = 5,
        **kwargs
    ) -> str:
        """
        Generate a unique idempotency key.
        
        Args:
            operation: Operation type (e.g., 'checkout', 'credit_purchase')
            account_id: User/account identifier
            *args: Additional positional arguments to include in key
            time_bucket_minutes: Time window for key reuse
            **kwargs: Additional keyword arguments to include in key
            
        Returns:
            40-character hex idempotency key
        """
        # Create time bucket (allows retries within window)
        timestamp_bucket = int(datetime.now(timezone.utc).timestamp() // (time_bucket_minutes * 60))
        
        # Sort kwargs for deterministic ordering
        sorted_kwargs = sorted(kwargs.items())
        
        # Build key components
        components = [
            operation,
            account_id,
            *[str(arg) for arg in args],
            *[f"{k}={v}" for k, v in sorted_kwargs],
            str(timestamp_bucket),
            # Add milliseconds component for additional uniqueness
            str(int(datetime.now(timezone.utc).timestamp() * 1000) % 10000)
        ]
        
        # Hash to create fixed-length key
        idempotency_base = "_".join(components)
        return hashlib.sha256(idempotency_base.encode()).hexdigest()[:40]

    def generate_checkout_key(
        self,
        account_id: str,
        price_id: str,
        commitment_type: Optional[str] = None
    ) -> str:
        """
        Generate idempotency key for subscription checkout.
        
        Args:
            account_id: User account ID
            price_id: Stripe price ID
            commitment_type: 'monthly', 'yearly', or 'yearly_commitment'
        """
        return self.generate_key(
            'checkout',
            account_id,
            price_id,
            commitment_type=commitment_type or 'none'
        )

    def generate_trial_key(self, account_id: str, trial_days: int) -> str:
        """Generate idempotency key for trial signup."""
        return self.generate_key(
            'trial_checkout',
            account_id,
            trial_days
        )

    def generate_credit_purchase_key(
        self,
        account_id: str,
        amount: float
    ) -> str:
        """Generate idempotency key for credit purchase."""
        return self.generate_key(
            'credit_purchase',
            account_id,
            amount
        )

    def generate_subscription_modify_key(
        self,
        subscription_id: str,
        new_price_id: str
    ) -> str:
        """Generate idempotency key for subscription modification."""
        return self.generate_key(
            'modify_subscription',
            subscription_id,
            new_price_id
        )

    def generate_subscription_cancel_key(
        self,
        subscription_id: str,
        cancel_type: str = 'at_period_end'
    ) -> str:
        """Generate idempotency key for subscription cancellation."""
        return self.generate_key(
            'cancel_subscription',
            subscription_id,
            cancel_type
        )

    def generate_refund_key(
        self,
        payment_intent_id: str,
        amount: Optional[float] = None
    ) -> str:
        """Generate idempotency key for refund."""
        return self.generate_key(
            'refund',
            payment_intent_id,
            amount or 'full'
        )

    def generate_free_tier_setup_key(self, account_id: str) -> str:
        """Generate idempotency key for free tier setup."""
        return self.generate_key(
            'free_tier_setup',
            account_id,
            time_bucket_minutes=60  # Longer window for setup
        )

    def generate_credit_grant_key(
        self,
        account_id: str,
        grant_type: str,
        amount: float,
        period_start: Optional[str] = None
    ) -> str:
        """Generate idempotency key for credit grant operations."""
        return self.generate_key(
            'credit_grant',
            account_id,
            grant_type,
            amount,
            period_start=period_start or 'none',
            time_bucket_minutes=60  # Hourly bucket for grants
        )


# Global instance
stripe_idempotency_manager = StripeIdempotencyManager()


# Convenience functions
def generate_idempotency_key(operation: str, account_id: str, *args, **kwargs) -> str:
    """Generate a generic idempotency key."""
    return stripe_idempotency_manager.generate_key(operation, account_id, *args, **kwargs)


def generate_checkout_idempotency_key(
    account_id: str, 
    price_id: str, 
    commitment_type: Optional[str] = None
) -> str:
    """Generate idempotency key for checkout session."""
    return stripe_idempotency_manager.generate_checkout_key(account_id, price_id, commitment_type)


def generate_trial_idempotency_key(account_id: str, trial_days: int) -> str:
    """Generate idempotency key for trial checkout."""
    return stripe_idempotency_manager.generate_trial_key(account_id, trial_days)


def generate_credit_purchase_idempotency_key(account_id: str, amount: float) -> str:
    """Generate idempotency key for credit purchase."""
    return stripe_idempotency_manager.generate_credit_purchase_key(account_id, amount)


def generate_subscription_modify_idempotency_key(subscription_id: str, new_price_id: str) -> str:
    """Generate idempotency key for subscription modification."""
    return stripe_idempotency_manager.generate_subscription_modify_key(subscription_id, new_price_id)


def generate_subscription_cancel_idempotency_key(
    subscription_id: str, 
    cancel_type: str = 'at_period_end'
) -> str:
    """Generate idempotency key for subscription cancellation."""
    return stripe_idempotency_manager.generate_subscription_cancel_key(subscription_id, cancel_type)


def generate_refund_idempotency_key(payment_intent_id: str, amount: Optional[float] = None) -> str:
    """Generate idempotency key for refund."""
    return stripe_idempotency_manager.generate_refund_key(payment_intent_id, amount)
