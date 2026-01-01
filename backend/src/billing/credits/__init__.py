"""
Credits Module

Comprehensive credit management for the billing system.

Components:
- CreditManager: Core credit operations (add, deduct, query)
- CreditCalculator: Token cost calculation
- DailyCreditRefreshService: Daily credit grants
- BillingIntegration: High-level interface for application layer

Usage:
    from backend.src.billing.credits import (
        credit_manager,
        billing_integration,
        check_model_and_billing_access,
        deduct_usage,
    )
    
    # Pre-flight check
    can_run, message, info = await check_model_and_billing_access(
        account_id, model_name="gpt-4"
    )
    
    # After operation
    result = await deduct_usage(
        account_id,
        prompt_tokens=1000,
        completion_tokens=500,
        model="gpt-4"
    )
"""

from .manager import (
    CreditManager,
    credit_manager,
)

from .calculator import (
    CreditCalculator,
    credit_calculator,
    calculate_token_cost,
    calculate_cached_token_cost,
    calculate_cache_write_cost,
    estimate_cost,
    TOKEN_PRICE_MULTIPLIER,
)

from .daily_refresh import (
    DailyCreditRefreshService,
    daily_credit_service,
    check_and_refresh_daily_credits,
    get_daily_credit_status,
)

from .integration import (
    BillingIntegration,
    billing_integration,
    check_and_reserve_credits,
    check_model_and_billing_access,
    deduct_usage,
    get_credit_summary,
    add_credits,
    can_afford,
)

__all__ = [
    # Manager
    'CreditManager',
    'credit_manager',
    # Calculator
    'CreditCalculator',
    'credit_calculator',
    'calculate_token_cost',
    'calculate_cached_token_cost',
    'calculate_cache_write_cost',
    'estimate_cost',
    'TOKEN_PRICE_MULTIPLIER',
    # Daily Refresh
    'DailyCreditRefreshService',
    'daily_credit_service',
    'check_and_refresh_daily_credits',
    'get_daily_credit_status',
    # Integration
    'BillingIntegration',
    'billing_integration',
    'check_and_reserve_credits',
    'check_model_and_billing_access',
    'deduct_usage',
    'get_credit_summary',
    'add_credits',
    'can_afford',
]
