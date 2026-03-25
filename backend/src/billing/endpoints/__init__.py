"""
Billing Endpoints Module

API routes for billing operations.

Routers:
- account_state: Unified account data endpoint
- subscriptions: Subscription management
- payments: Credit purchases and transactions
- webhooks: Stripe webhook processing

Usage:
    from backend.src.billing.endpoints import billing_router
    
    app.include_router(billing_router, prefix="/billing")
"""

from fastapi import APIRouter

from .account_state import router as account_state_router
from .subscriptions import router as subscriptions_router
from .payments import router as payments_router
from .webhooks import router as webhooks_router
from .dependencies import get_current_user_id, verify_billing_enabled

# Create main billing router
billing_router = APIRouter()

# Include all sub-routers
billing_router.include_router(account_state_router)
billing_router.include_router(subscriptions_router)
billing_router.include_router(payments_router)
billing_router.include_router(webhooks_router)

__all__ = [
    'billing_router',
    'account_state_router',
    'subscriptions_router',
    'payments_router',
    'webhooks_router',
    'get_current_user_id',
    'verify_billing_enabled',
]
