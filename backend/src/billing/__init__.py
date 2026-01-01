"""
Billing Module

Comprehensive billing system for the agents-backend project.
Integrates with Stripe for payment processing and subscription management.

Submodules:
- shared: Configuration, exceptions, cache utilities
- domain: Core entities (CreditAccount, Subscription)
- external: Payment provider integrations (Stripe)
- credits: Credit management (manager, calculator, daily refresh, integration)
- subscriptions: Subscription management (service, handlers, trial, free tier)
- payments: One-time payments (Phase 5)
- endpoints: API routes (Phase 6)

Usage:
    # Configuration
    from backend.src.billing import (
        TIERS,
        get_tier_by_name,
        subscription_service,
    )
    
    # Credit operations
    from backend.src.billing.credits import (
        check_model_and_billing_access,
        deduct_usage,
    )
    
    # Subscription operations
    from backend.src.billing.subscriptions import (
        subscription_service,
        create_checkout_session,
    )
"""

# Shared configuration and utilities
from .shared import (
    # Tier configuration
    Tier,
    TIERS,
    get_tier_by_name,
    get_tier_by_price_id,
    get_monthly_credits,
    is_model_allowed,
    get_tier_limits,
    get_plan_type,
    is_commitment_price_id,
    # Credit packages
    CreditPackage,
    CREDIT_PACKAGES,
    get_credit_package,
    # Exceptions
    BillingError,
    InsufficientCreditsError,
    SubscriptionError,
    PaymentError,
    WebhookError,
    TierNotFoundError,
    TrialError,
    ReconciliationError,
    CircuitBreakerOpenError,
    # Cache utilities
    invalidate_account_state_cache,
    cache_account_state,
    get_cached_account_state,
)

# Domain entities
from .domain import (
    CreditAccount,
    Subscription,
    SubscriptionStatus,
    SubscriptionProvider,
)

# External integrations (Stripe)
from .external import (
    # API Client
    StripeAPIWrapper,
    get_stripe_client,
    # Circuit Breaker
    CircuitState,
    stripe_circuit_breaker,
    # Idempotency
    generate_idempotency_key,
    generate_checkout_idempotency_key,
    # Webhook
    webhook_service,
    WebhookService,
)

# Credits module
from .credits import (
    # Manager
    CreditManager,
    credit_manager,
    # Calculator
    CreditCalculator,
    credit_calculator,
    calculate_token_cost,
    calculate_cached_token_cost,
    calculate_cache_write_cost,
    # Daily Refresh
    DailyCreditRefreshService,
    daily_credit_service,
    check_and_refresh_daily_credits,
    # Integration
    BillingIntegration,
    billing_integration,
    check_model_and_billing_access,
    deduct_usage,
    get_credit_summary,
    add_credits,
    can_afford,
)

# Subscriptions module
from .subscriptions import (
    # Main service
    SubscriptionService,
    subscription_service,
    # Handlers
    CustomerHandler,
    CheckoutHandler,
    LifecycleHandler,
    TierHandler,
    PortalHandler,
    # Handler functions
    get_or_create_stripe_customer,
    create_checkout_session,
    cancel_subscription,
    reactivate_subscription,
    get_user_subscription_tier,
    get_allowed_models_for_user,
    check_model_access,
    create_portal_session,
    # Free tier
    FreeTierService,
    free_tier_service,
    ensure_free_tier_subscription,
    # Trial
    TrialService,
    trial_service,
    get_trial_status,
    start_trial,
    cancel_trial,
)

__all__ = [
    # Configuration
    'Tier',
    'TIERS',
    'get_tier_by_name',
    'get_tier_by_price_id',
    'get_monthly_credits',
    'is_model_allowed',
    'get_tier_limits',
    'get_plan_type',
    'is_commitment_price_id',
    'CreditPackage',
    'CREDIT_PACKAGES',
    'get_credit_package',
    # Exceptions
    'BillingError',
    'InsufficientCreditsError',
    'SubscriptionError',
    'PaymentError',
    'WebhookError',
    'TierNotFoundError',
    'TrialError',
    'ReconciliationError',
    'CircuitBreakerOpenError',
    # Cache
    'invalidate_account_state_cache',
    'cache_account_state',
    'get_cached_account_state',
    # Domain
    'CreditAccount',
    'Subscription',
    'SubscriptionStatus',
    'SubscriptionProvider',
    # Stripe
    'StripeAPIWrapper',
    'get_stripe_client',
    'CircuitState',
    'stripe_circuit_breaker',
    'generate_idempotency_key',
    'generate_checkout_idempotency_key',
    'webhook_service',
    'WebhookService',
    # Credits
    'CreditManager',
    'credit_manager',
    'CreditCalculator',
    'credit_calculator',
    'calculate_token_cost',
    'calculate_cached_token_cost',
    'calculate_cache_write_cost',
    'DailyCreditRefreshService',
    'daily_credit_service',
    'check_and_refresh_daily_credits',
    'BillingIntegration',
    'billing_integration',
    'check_model_and_billing_access',
    'deduct_usage',
    'get_credit_summary',
    'add_credits',
    'can_afford',
    # Subscriptions
    'SubscriptionService',
    'subscription_service',
    'CustomerHandler',
    'CheckoutHandler',
    'LifecycleHandler',
    'TierHandler',
    'PortalHandler',
    'get_or_create_stripe_customer',
    'create_checkout_session',
    'cancel_subscription',
    'reactivate_subscription',
    'get_user_subscription_tier',
    'get_allowed_models_for_user',
    'check_model_access',
    'create_portal_session',
    'FreeTierService',
    'free_tier_service',
    'ensure_free_tier_subscription',
    'TrialService',
    'trial_service',
    'get_trial_status',
    'start_trial',
    'cancel_trial',
    # Payments
    'PaymentService',
    'payment_service',
    'ReconciliationService',
    'reconciliation_service',
]

# Payments module
from .payments import (
    PaymentService,
    payment_service,
    ReconciliationService,
    reconciliation_service,
)
