"""
Stripe API Client Wrapper

Provides a safe, circuit-breaker-protected interface to the Stripe API.
All Stripe API calls should go through this wrapper for resilience.

Based on external_billing/external/stripe/client.py.
"""

import logging
from typing import Any, Callable, Dict, Optional

from backend.core.conf import settings
from .circuit_breaker import StripeCircuitBreaker, stripe_circuit_breaker

logger = logging.getLogger(__name__)

# Initialize Stripe with API key
try:
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
except ImportError:
    stripe = None
    logger.warning("[STRIPE CLIENT] stripe package not installed - Stripe features disabled")


class StripeAPIWrapper:
    """
    Safe wrapper for Stripe API calls with circuit breaker protection.
    
    All methods are async class methods that can be called directly:
        customer = await StripeAPIWrapper.create_customer(email="test@example.com")
        
    The circuit breaker prevents cascading failures when Stripe is down.
    """
    
    _circuit_breaker = stripe_circuit_breaker
    
    @classmethod
    def _ensure_stripe_available(cls):
        """Raise error if Stripe is not configured."""
        if stripe is None:
            raise ImportError("stripe package is required. Install with: pip install stripe")
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("STRIPE_SECRET_KEY not configured")
    
    @classmethod
    async def safe_stripe_call(cls, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a Stripe API call safely with circuit breaker protection.
        
        Args:
            func: Async Stripe API function
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result from Stripe API
        """
        cls._ensure_stripe_available()
        return await cls._circuit_breaker.safe_call(func, *args, **kwargs)
    
    @classmethod
    async def get_circuit_status(cls) -> Dict:
        """Get the current circuit breaker status."""
        return await cls._circuit_breaker.get_status()
    
    # -------------------------------------------------------------------------
    # Customer Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def create_customer(cls, **kwargs) -> 'stripe.Customer':
        """
        Create a new Stripe customer.
        
        Args:
            email: Customer email
            name: Customer name (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            Stripe Customer object
        """
        return await cls.safe_stripe_call(stripe.Customer.create_async, **kwargs)
    
    @classmethod
    async def retrieve_customer(cls, customer_id: str) -> 'stripe.Customer':
        """Retrieve a Stripe customer by ID."""
        return await cls.safe_stripe_call(stripe.Customer.retrieve_async, customer_id)
    
    @classmethod
    async def update_customer(cls, customer_id: str, **kwargs) -> 'stripe.Customer':
        """Update a Stripe customer."""
        return await cls.safe_stripe_call(stripe.Customer.modify_async, customer_id, **kwargs)
    
    # -------------------------------------------------------------------------
    # Subscription Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def create_subscription(cls, **kwargs) -> 'stripe.Subscription':
        """Create a new subscription."""
        return await cls.safe_stripe_call(stripe.Subscription.create_async, **kwargs)
    
    @classmethod
    async def retrieve_subscription(cls, subscription_id: str, **kwargs) -> 'stripe.Subscription':
        """Retrieve a subscription by ID."""
        return await cls.safe_stripe_call(stripe.Subscription.retrieve_async, subscription_id, **kwargs)
    
    @classmethod
    async def modify_subscription(cls, subscription_id: str, **kwargs) -> 'stripe.Subscription':
        """Modify an existing subscription."""
        return await cls.safe_stripe_call(
            stripe.Subscription.modify_async,
            subscription_id,
            **kwargs
        )
    
    @classmethod
    async def cancel_subscription(
        cls, 
        subscription_id: str, 
        cancel_immediately: bool = False,
        prorate: bool = True
    ) -> 'stripe.Subscription':
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            cancel_immediately: If True, cancel now. If False, cancel at period end.
            prorate: If True and canceling immediately, prorate the refund
            
        Returns:
            Updated Stripe Subscription object
        """
        if cancel_immediately:
            return await cls.safe_stripe_call(
                stripe.Subscription.cancel_async, 
                subscription_id,
                prorate=prorate
            )
        else:
            return await cls.safe_stripe_call(
                stripe.Subscription.modify_async,
                subscription_id,
                cancel_at_period_end=True
            )
    
    @classmethod
    async def reactivate_subscription(cls, subscription_id: str) -> 'stripe.Subscription':
        """Reactivate a subscription that was set to cancel at period end."""
        return await cls.safe_stripe_call(
            stripe.Subscription.modify_async,
            subscription_id,
            cancel_at_period_end=False
        )
    
    @classmethod
    async def list_subscriptions(cls, **kwargs) -> 'stripe.ListObject':
        """List subscriptions with optional filters."""
        return await cls.safe_stripe_call(stripe.Subscription.list_async, **kwargs)
    
    # -------------------------------------------------------------------------
    # Checkout Session Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def create_checkout_session(cls, **kwargs) -> 'stripe.checkout.Session':
        """
        Create a Stripe Checkout session.
        
        Args:
            mode: 'subscription' or 'payment'
            line_items: List of items
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            customer: Existing customer ID (optional)
            customer_email: Customer email if no customer ID
            metadata: Additional metadata
            
        Returns:
            Stripe Checkout Session object
        """
        return await cls.safe_stripe_call(stripe.checkout.Session.create_async, **kwargs)
    
    @classmethod
    async def retrieve_checkout_session(cls, session_id: str, **kwargs) -> 'stripe.checkout.Session':
        """Retrieve a checkout session by ID."""
        return await cls.safe_stripe_call(stripe.checkout.Session.retrieve_async, session_id, **kwargs)
    
    # -------------------------------------------------------------------------
    # Payment Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def retrieve_payment_intent(cls, payment_intent_id: str) -> 'stripe.PaymentIntent':
        """Retrieve a payment intent by ID."""
        return await cls.safe_stripe_call(stripe.PaymentIntent.retrieve_async, payment_intent_id)
    
    @classmethod
    async def create_refund(cls, **kwargs) -> 'stripe.Refund':
        """Create a refund for a payment."""
        return await cls.safe_stripe_call(stripe.Refund.create_async, **kwargs)
    
    # -------------------------------------------------------------------------
    # Invoice Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def list_invoices(cls, **kwargs) -> 'stripe.ListObject':
        """List invoices with optional filters."""
        return await cls.safe_stripe_call(stripe.Invoice.list_async, **kwargs)
    
    @classmethod
    async def retrieve_invoice(cls, invoice_id: str) -> 'stripe.Invoice':
        """Retrieve an invoice by ID."""
        return await cls.safe_stripe_call(stripe.Invoice.retrieve_async, invoice_id)
    
    @classmethod
    async def upcoming_invoice(cls, **kwargs) -> 'stripe.Invoice':
        """Get the upcoming invoice for a customer."""
        return await cls.safe_stripe_call(stripe.Invoice.upcoming_async, **kwargs)
    
    # -------------------------------------------------------------------------
    # Price Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def retrieve_price(cls, price_id: str) -> 'stripe.Price':
        """Retrieve a price by ID."""
        return await cls.safe_stripe_call(stripe.Price.retrieve_async, price_id)
    
    @classmethod
    async def list_prices(cls, **kwargs) -> 'stripe.ListObject':
        """List prices with optional filters."""
        return await cls.safe_stripe_call(stripe.Price.list_async, **kwargs)
    
    # -------------------------------------------------------------------------
    # Billing Portal
    # -------------------------------------------------------------------------
    
    @classmethod
    async def create_billing_portal_session(cls, **kwargs) -> 'stripe.billing_portal.Session':
        """
        Create a billing portal session for self-service.
        
        Args:
            customer: Stripe customer ID
            return_url: URL to return to after portal session
            
        Returns:
            Stripe Billing Portal Session object with url
        """
        return await cls.safe_stripe_call(stripe.billing_portal.Session.create_async, **kwargs)
    
    # -------------------------------------------------------------------------
    # Subscription Schedule Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    async def create_subscription_schedule(cls, **kwargs) -> 'stripe.SubscriptionSchedule':
        """Create a subscription schedule for future changes."""
        return await cls.safe_stripe_call(stripe.SubscriptionSchedule.create_async, **kwargs)
    
    @classmethod
    async def retrieve_subscription_schedule(cls, schedule_id: str) -> 'stripe.SubscriptionSchedule':
        """Retrieve a subscription schedule by ID."""
        return await cls.safe_stripe_call(stripe.SubscriptionSchedule.retrieve_async, schedule_id)
    
    @classmethod
    async def update_subscription_schedule(cls, schedule_id: str, **kwargs) -> 'stripe.SubscriptionSchedule':
        """Update a subscription schedule."""
        return await cls.safe_stripe_call(stripe.SubscriptionSchedule.modify_async, schedule_id, **kwargs)
    
    @classmethod
    async def release_subscription_schedule(cls, schedule_id: str) -> 'stripe.SubscriptionSchedule':
        """Release a subscription schedule, keeping current subscription settings."""
        return await cls.safe_stripe_call(stripe.SubscriptionSchedule.release_async, schedule_id)
    
    @classmethod
    async def cancel_subscription_schedule(cls, schedule_id: str) -> 'stripe.SubscriptionSchedule':
        """Cancel a subscription schedule and the associated subscription."""
        return await cls.safe_stripe_call(stripe.SubscriptionSchedule.cancel_async, schedule_id)


# Convenience function for backward compatibility
async def get_stripe_client() -> StripeAPIWrapper:
    """Get the Stripe API wrapper (no-op, returns class reference)."""
    return StripeAPIWrapper
