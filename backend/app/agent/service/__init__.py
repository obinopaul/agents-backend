"""Agent service package."""

from backend.app.agent.service.credit_service import (
    get_user_credits,
    has_sufficient_credits,
    deduct_user_credits,
    add_user_credits,
    set_user_credits,
    get_user_credit_history,
    CreditBalance,
    SessionCreditHistory,
    CreditHistory,
)

from backend.app.agent.service.metrics_service import (
    track_llm_usage,
    get_session_metrics,
    calculate_credits_from_tokens,
    get_model_pricing,
    MODEL_PRICING,
    ModelPricing,
)

__all__ = [
    # Credit service
    'get_user_credits',
    'has_sufficient_credits',
    'deduct_user_credits',
    'add_user_credits',
    'set_user_credits',
    'get_user_credit_history',
    'CreditBalance',
    'SessionCreditHistory',
    'CreditHistory',
    # Metrics service
    'track_llm_usage',
    'get_session_metrics',
    'calculate_credits_from_tokens',
    'get_model_pricing',
    'MODEL_PRICING',
    'ModelPricing',
]

