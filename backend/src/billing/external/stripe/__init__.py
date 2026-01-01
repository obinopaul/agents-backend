"""
Stripe Integration Module

Provides comprehensive Stripe integration for billing:
- Circuit breaker for API resilience
- Async API wrapper with all common operations
- Idempotency key generation
- Webhook processing and event handlers

Usage:
    from backend.src.billing.external.stripe import (
        StripeAPIWrapper,
        webhook_service,
        generate_checkout_idempotency_key,
    )
    
    # Safe API call with circuit breaker
    customer = await StripeAPIWrapper.create_customer(email="user@example.com")
    
    # Create checkout session
    session = await StripeAPIWrapper.create_checkout_session(
        mode='subscription',
        customer=customer.id,
        line_items=[{'price': 'price_xxx', 'quantity': 1}],
        success_url='https://example.com/success',
        cancel_url='https://example.com/cancel',
        idempotency_key=generate_checkout_idempotency_key(account_id, 'price_xxx'),
    )
"""

from .circuit_breaker import (
    CircuitState,
    StripeCircuitBreaker,
    stripe_circuit_breaker,
)

from .client import (
    StripeAPIWrapper,
    get_stripe_client,
)

from .idempotency import (
    StripeIdempotencyManager,
    stripe_idempotency_manager,
    generate_idempotency_key,
    generate_checkout_idempotency_key,
    generate_trial_idempotency_key,
    generate_credit_purchase_idempotency_key,
    generate_subscription_modify_idempotency_key,
    generate_subscription_cancel_idempotency_key,
    generate_refund_idempotency_key,
)

from .webhook_lock import WebhookLock

from .webhooks import (
    WebhookService,
    webhook_service,
)

from .handlers import (
    CheckoutHandler,
    SubscriptionHandler,
    InvoiceHandler,
    RefundHandler,
)

__all__ = [
    # Circuit Breaker
    'CircuitState',
    'StripeCircuitBreaker',
    'stripe_circuit_breaker',
    # API Client
    'StripeAPIWrapper',
    'get_stripe_client',
    # Idempotency
    'StripeIdempotencyManager',
    'stripe_idempotency_manager',
    'generate_idempotency_key',
    'generate_checkout_idempotency_key',
    'generate_trial_idempotency_key',
    'generate_credit_purchase_idempotency_key',
    'generate_subscription_modify_idempotency_key',
    'generate_subscription_cancel_idempotency_key',
    'generate_refund_idempotency_key',
    # Webhook Lock
    'WebhookLock',
    # Webhook Service
    'WebhookService',
    'webhook_service',
    # Handlers
    'CheckoutHandler',
    'SubscriptionHandler',
    'InvoiceHandler',
    'RefundHandler',
]
