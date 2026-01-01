"""
External Integrations Module

Integration with external payment providers:
- Stripe (primary payment provider)
- RevenueCat (mobile payments, optional - future)

Usage:
    from backend.src.billing.external.stripe import (
        StripeAPIWrapper,
        webhook_service,
    )
"""

# Re-export Stripe module
from .stripe import (
    # Circuit Breaker
    CircuitState,
    StripeCircuitBreaker,
    stripe_circuit_breaker,
    # API Client
    StripeAPIWrapper,
    get_stripe_client,
    # Idempotency
    StripeIdempotencyManager,
    stripe_idempotency_manager,
    generate_idempotency_key,
    generate_checkout_idempotency_key,
    generate_trial_idempotency_key,
    generate_credit_purchase_idempotency_key,
    generate_subscription_modify_idempotency_key,
    generate_subscription_cancel_idempotency_key,
    generate_refund_idempotency_key,
    # Webhook
    WebhookLock,
    WebhookService,
    webhook_service,
    # Handlers
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
    # Webhook
    'WebhookLock',
    'WebhookService',
    'webhook_service',
    # Handlers
    'CheckoutHandler',
    'SubscriptionHandler',
    'InvoiceHandler',
    'RefundHandler',
]
