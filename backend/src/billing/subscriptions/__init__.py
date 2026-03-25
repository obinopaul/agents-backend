"""
Subscriptions Module

Complete subscription management for the billing system.

Components:
- SubscriptionService: Main orchestrator
- Handlers: Customer, Checkout, Lifecycle, Tier, Portal
- FreeTierService: Auto-enrollment for new users
- TrialService: Trial signup and management

Usage:
    from backend.src.billing.subscriptions import subscription_service
    
    # Create checkout
    result = await subscription_service.create_checkout_session(
        account_id, price_id, success_url, cancel_url
    )
    
    # Cancel subscription
    result = await subscription_service.cancel_subscription(account_id)
"""

from .service import (
    SubscriptionService,
    subscription_service,
)

from .handlers import (
    CustomerHandler,
    CheckoutHandler,
    LifecycleHandler,
    TierHandler,
    PortalHandler,
    get_or_create_stripe_customer,
    create_checkout_session,
    cancel_subscription,
    reactivate_subscription,
    handle_subscription_change,
    get_user_subscription_tier,
    get_allowed_models_for_user,
    check_model_access,
    get_tier_limits,
    create_portal_session,
)

from .free_tier_service import (
    FreeTierService,
    free_tier_service,
    ensure_free_tier_subscription,
)

from .trial_service import (
    TrialService,
    trial_service,
    get_trial_status,
    start_trial,
    cancel_trial,
)

__all__ = [
    # Main service
    'SubscriptionService',
    'subscription_service',
    # Handlers
    'CustomerHandler',
    'CheckoutHandler',
    'LifecycleHandler',
    'TierHandler',
    'PortalHandler',
    # Convenience functions
    'get_or_create_stripe_customer',
    'create_checkout_session',
    'cancel_subscription',
    'reactivate_subscription',
    'handle_subscription_change',
    'get_user_subscription_tier',
    'get_allowed_models_for_user',
    'check_model_access',
    'get_tier_limits',
    'create_portal_session',
    # Free tier
    'FreeTierService',
    'free_tier_service',
    'ensure_free_tier_subscription',
    # Trial
    'TrialService',
    'trial_service',
    'get_trial_status',
    'start_trial',
    'cancel_trial',
]
