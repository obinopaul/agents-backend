"""Metrics service for tracking session token usage and costs.

Provides:
- Model pricing database for cost calculation
- Token usage tracking per session
- Automatic credit deduction based on LLM usage
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.model.agent_models import SessionMetrics
from backend.app.agent.service.credit_service import deduct_user_credits

logger = logging.getLogger(__name__)


# =============================================================================
# Model Pricing
# =============================================================================

class ModelPricing(BaseModel):
    """Pricing information for LLM models (per million tokens)."""
    
    model_name: str
    input_price_per_million: float = Field(description="Price per million input tokens in USD")
    output_price_per_million: float = Field(description="Price per million output tokens in USD")
    cache_read_price_per_million: float = Field(default=0.0)
    cache_write_price_per_million: float = Field(default=0.0)


# Pricing database (prices in USD per million tokens)
MODEL_PRICING: Dict[str, ModelPricing] = {
    # Anthropic Claude
    "claude-sonnet-4-20250514": ModelPricing(
        model_name="claude-sonnet-4-20250514",
        input_price_per_million=3.00,
        output_price_per_million=15.00,
        cache_read_price_per_million=0.30,
        cache_write_price_per_million=3.75,
    ),
    "claude-3-5-sonnet": ModelPricing(
        model_name="claude-3-5-sonnet",
        input_price_per_million=3.00,
        output_price_per_million=15.00,
        cache_read_price_per_million=0.30,
    ),
    "claude-3-opus": ModelPricing(
        model_name="claude-3-opus",
        input_price_per_million=15.00,
        output_price_per_million=75.00,
        cache_read_price_per_million=1.50,
    ),
    # OpenAI
    "gpt-4o": ModelPricing(
        model_name="gpt-4o",
        input_price_per_million=2.50,
        output_price_per_million=10.00,
        cache_read_price_per_million=1.25,
    ),
    "gpt-4o-mini": ModelPricing(
        model_name="gpt-4o-mini",
        input_price_per_million=0.15,
        output_price_per_million=0.60,
        cache_read_price_per_million=0.075,
    ),
    "gpt-4-turbo": ModelPricing(
        model_name="gpt-4-turbo",
        input_price_per_million=10.00,
        output_price_per_million=30.00,
    ),
    # Google Gemini
    "gemini-2.0-flash": ModelPricing(
        model_name="gemini-2.0-flash",
        input_price_per_million=0.10,
        output_price_per_million=0.40,
    ),
    "gemini-1.5-pro": ModelPricing(
        model_name="gemini-1.5-pro",
        input_price_per_million=1.25,
        output_price_per_million=5.00,
    ),
    # DeepSeek
    "deepseek-chat": ModelPricing(
        model_name="deepseek-chat",
        input_price_per_million=0.14,
        output_price_per_million=0.28,
        cache_read_price_per_million=0.014,
    ),
    "deepseek-reasoner": ModelPricing(
        model_name="deepseek-reasoner",
        input_price_per_million=0.55,
        output_price_per_million=2.19,
        cache_read_price_per_million=0.14,
    ),
}

# Default pricing for unknown models
DEFAULT_PRICING = ModelPricing(
    model_name="default",
    input_price_per_million=1.00,
    output_price_per_million=3.00,
)


def get_model_pricing(model_name: str) -> ModelPricing:
    """Get pricing for a model, with fallback to partial matching."""
    # Exact match
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]
    
    # Partial match (e.g., "gpt-4o-2024-05-13" matches "gpt-4o")
    for key, pricing in MODEL_PRICING.items():
        if model_name.startswith(key) or key in model_name:
            return pricing
    
    logger.warning(f"Unknown model '{model_name}', using default pricing")
    return DEFAULT_PRICING


def calculate_credits_from_tokens(
    prompt_tokens: int,
    completion_tokens: int,
    model_name: str,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Calculate credits (USD cost) from token usage.
    
    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model_name: Name of the LLM model used
        cache_read_tokens: Tokens read from cache (cheaper)
        cache_write_tokens: Tokens written to cache
        
    Returns:
        Cost in USD (credits)
    """
    pricing = get_model_pricing(model_name)
    
    # Calculate cost per component
    # Prompt tokens minus cached tokens
    non_cached_prompt = max(0, prompt_tokens - cache_read_tokens)
    prompt_cost = (non_cached_prompt / 1_000_000) * pricing.input_price_per_million
    completion_cost = (completion_tokens / 1_000_000) * pricing.output_price_per_million
    cache_read_cost = (cache_read_tokens / 1_000_000) * pricing.cache_read_price_per_million
    cache_write_cost = (cache_write_tokens / 1_000_000) * pricing.cache_write_price_per_million
    
    total_cost = prompt_cost + completion_cost + cache_read_cost + cache_write_cost
    return round(total_cost, 6)


# =============================================================================
# Session Metrics Functions
# =============================================================================

async def track_llm_usage(
    *,
    db_session: AsyncSession,
    user_id: int,
    session_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    model_name: str,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Optional[float]:
    """Track LLM usage for a session and deduct credits from user.
    
    This is the main function to call after each LLM API call.
    It calculates the cost, updates session metrics, and deducts from user credits.
    
    Args:
        db_session: Database session
        user_id: User ID to charge
        session_id: Session ID for tracking
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model_name: Name of the LLM model
        cache_read_tokens: Tokens from cache
        cache_write_tokens: Tokens written to cache
        
    Returns:
        Credits deducted, or None on error
    """
    try:
        # Calculate cost
        credits_used = calculate_credits_from_tokens(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_name=model_name,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )
        
        # Update or create session metrics
        metrics_record = (
            await db_session.execute(
                select(SessionMetrics).where(SessionMetrics.session_id == session_id)
            )
        ).scalar_one_or_none()
        
        if metrics_record:
            metrics_record.total_prompt_tokens += prompt_tokens
            metrics_record.total_completion_tokens += completion_tokens
            metrics_record.credits += credits_used
            metrics_record.model_name = model_name
            metrics_record.updated_at = datetime.now(timezone.utc)
        else:
            metrics_record = SessionMetrics(
                user_id=user_id,
                session_id=session_id,
                model_name=model_name,
                credits=credits_used,
                total_prompt_tokens=prompt_tokens,
                total_completion_tokens=completion_tokens,
            )
            db_session.add(metrics_record)
        
        # Deduct credits from user
        if credits_used > 0:
            await deduct_user_credits(
                db_session=db_session,
                user_id=user_id,
                amount=credits_used,
                description=f"LLM usage: {model_name}",
            )
        
        logger.info(
            f"Tracked LLM usage: session={session_id}, model={model_name}, "
            f"tokens={prompt_tokens}+{completion_tokens}, credits={credits_used:.6f}"
        )
        
        return credits_used
        
    except Exception as e:
        logger.error(f"Error tracking LLM usage: {e}", exc_info=True)
        return None


async def get_session_metrics(
    *, db_session: AsyncSession, session_id: str
) -> Optional[Dict[str, Any]]:
    """Get metrics for a specific session."""
    try:
        metrics = (
            await db_session.execute(
                select(SessionMetrics).where(SessionMetrics.session_id == session_id)
            )
        ).scalar_one_or_none()

        if metrics:
            return {
                "session_id": metrics.session_id,
                "user_id": metrics.user_id,
                "model_name": metrics.model_name,
                "credits": metrics.credits,
                "total_prompt_tokens": metrics.total_prompt_tokens,
                "total_completion_tokens": metrics.total_completion_tokens,
                "created_at": metrics.created_at,
                "updated_at": metrics.updated_at,
            }

        return None

    except Exception as e:
        logger.error(f"Error getting metrics for session {session_id}: {e}", exc_info=True)
        return None


async def accumulate_session_metrics(
    *, db_session: AsyncSession, session_id: str, user_id: int, credits: float
) -> Optional[SessionMetrics]:
    """Accumulate credits for a session (for manual adjustments)."""
    try:
        metrics_record = (
            await db_session.execute(
                select(SessionMetrics).where(SessionMetrics.session_id == session_id)
            )
        ).scalar_one_or_none()

        if metrics_record:
            metrics_record.credits += credits
            metrics_record.updated_at = datetime.now(timezone.utc)
        else:
            metrics_record = SessionMetrics(
                user_id=user_id,
                session_id=session_id,
                credits=credits,
            )
            db_session.add(metrics_record)
            await db_session.flush()
            await db_session.refresh(metrics_record)

        return metrics_record
        
    except Exception as e:
        logger.error(f"Error accumulating metrics: {e}", exc_info=True)
        return None
