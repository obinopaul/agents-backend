"""
Billing Configuration

This module defines subscription tiers, credit packages, and billing constants.
Adapted from external_billing/shared/config.py for use with agents-backend.

Usage:
    from backend.src.billing.shared.config import TIERS, get_tier_by_name
    
    tier = get_tier_by_name('tier_2_20')
    print(tier.monthly_credits)  # Decimal('40.00')
"""

from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from backend.core.conf import settings


# =============================================================================
# TRIAL CONFIGURATION
# =============================================================================
TRIAL_ENABLED: bool = False  # Set to True to enable free trials
TRIAL_DURATION_DAYS: int = 7
TRIAL_TIER: str = "tier_2_20"
TRIAL_CREDITS: Decimal = Decimal("5.00")


# =============================================================================
# CREDIT CONSTANTS
# =============================================================================
# Token pricing multiplier (1.2 = 20% markup on raw costs)
TOKEN_PRICE_MULTIPLIER: Decimal = Decimal('1.2')

# Minimum credits required to start an agent run
MINIMUM_CREDIT_FOR_RUN: Decimal = Decimal('0.01')

# Default cost per token (fallback if model not in pricing table)
DEFAULT_TOKEN_COST: Decimal = Decimal('0.000002')

# How many credits equal $1 USD
# 100 credits = $1.00 (1 credit = $0.01)
CREDITS_PER_DOLLAR: int = 100

# Credits granted to new free tier users
FREE_TIER_INITIAL_CREDITS: Decimal = Decimal('0.00')

# "Unlimited" plan limits - using large integers for DB/JSON compatibility
UNLIMITED_THREAD_LIMIT: int = 100_000
UNLIMITED_PROJECT_LIMIT: int = UNLIMITED_THREAD_LIMIT * 2


# =============================================================================
# TIER DEFINITION
# =============================================================================
@dataclass
class Tier:
    """
    Subscription tier configuration.
    
    Attributes:
        name: Internal tier identifier (e.g., 'free', 'tier_2_20')
        price_ids: List of Stripe price IDs that map to this tier
        monthly_credits: Credits granted at each billing cycle (in dollars)
        display_name: Human-readable name shown in UI
        can_purchase_credits: Whether additional credits can be purchased
        models: List of allowed LLM models ('all' = unrestricted)
        project_limit: Maximum number of projects
        thread_limit: Maximum number of threads/chats
        concurrent_runs: Maximum simultaneous agent runs
        custom_workers_limit: Maximum custom AI workers
        scheduled_triggers_limit: Maximum scheduled triggers
        app_triggers_limit: Maximum app triggers
        memory_config: Optional memory/retrieval configuration
        daily_credit_config: Optional daily credit refresh configuration
        monthly_refill_enabled: Whether monthly credits are refilled
    """
    name: str
    price_ids: List[str]
    monthly_credits: Decimal
    display_name: str
    can_purchase_credits: bool
    models: List[str]
    project_limit: int
    thread_limit: int
    concurrent_runs: int
    custom_workers_limit: int = 0
    scheduled_triggers_limit: int = 0
    app_triggers_limit: int = 0
    memory_config: Optional[Dict] = None
    daily_credit_config: Optional[Dict] = None
    monthly_refill_enabled: bool = True


# =============================================================================
# TIER DEFINITIONS
# =============================================================================
# Helper to safely get Stripe price IDs from settings (may not exist yet)
def _get_stripe_id(attr_name: str, default: str = '') -> str:
    """Safely get a Stripe price ID from settings."""
    return getattr(settings, attr_name, default) or default


TIERS: Dict[str, Tier] = {
    # -------------------------------------------------------------------------
    # No Plan - Unsubscribed users
    # -------------------------------------------------------------------------
    'none': Tier(
        name='none',
        price_ids=[],
        monthly_credits=Decimal('0.00'),
        display_name='No Plan',
        can_purchase_credits=False,
        models=['haiku'],
        project_limit=0,
        thread_limit=0,
        concurrent_runs=0,
        custom_workers_limit=0,
        scheduled_triggers_limit=0,
        app_triggers_limit=0,
        memory_config={
            'enabled': False,
            'max_memories': 0,
            'retrieval_limit': 0
        },
    ),
    
    # -------------------------------------------------------------------------
    # Free Tier - Basic access with daily credit refresh
    # -------------------------------------------------------------------------
    'free': Tier(
        name='free',
        price_ids=[_get_stripe_id('STRIPE_FREE_TIER_ID')],
        monthly_credits=Decimal('0.00'),
        display_name='Basic',
        can_purchase_credits=False,
        models=['haiku'],  # Limited to basic models
        project_limit=20,
        thread_limit=10,
        concurrent_runs=1,
        custom_workers_limit=0,
        scheduled_triggers_limit=0,
        app_triggers_limit=0,
        memory_config={
            'enabled': True,
            'max_memories': 10,
            'retrieval_limit': 2
        },
        daily_credit_config={
            'enabled': True,
            'amount': Decimal('1.00'),  # $1/day in credits
            'refresh_interval_hours': 24
        },
        monthly_refill_enabled=False  # Free tier uses daily refresh instead
    ),
    
    # -------------------------------------------------------------------------
    # Plus Tier - Entry-level paid plan
    # ~$20/month = $40 monthly credits
    # -------------------------------------------------------------------------
    'tier_2_20': Tier(
        name='tier_2_20',
        price_ids=[
            _get_stripe_id('STRIPE_TIER_2_20_ID'),
            _get_stripe_id('STRIPE_TIER_2_20_YEARLY_ID'),
            _get_stripe_id('STRIPE_TIER_2_17_YEARLY_COMMITMENT_ID'),
        ],
        monthly_credits=Decimal('40.00'),
        display_name='Plus',
        can_purchase_credits=False,
        models=['all'],  # Full model access
        project_limit=UNLIMITED_PROJECT_LIMIT,
        thread_limit=UNLIMITED_THREAD_LIMIT,
        concurrent_runs=3,
        custom_workers_limit=5,
        scheduled_triggers_limit=5,
        app_triggers_limit=25,
        memory_config={
            'enabled': True,
            'max_memories': 100,
            'retrieval_limit': 15
        },
        daily_credit_config={
            'enabled': True,
            'amount': Decimal('2.00'),
            'refresh_interval_hours': 24
        },
        monthly_refill_enabled=True
    ),
    
    # -------------------------------------------------------------------------
    # Pro Tier - Professional plan
    # ~$50/month = $100 monthly credits
    # -------------------------------------------------------------------------
    'tier_6_50': Tier(
        name='tier_6_50',
        price_ids=[
            _get_stripe_id('STRIPE_TIER_6_50_ID'),
            _get_stripe_id('STRIPE_TIER_6_50_YEARLY_ID'),
            _get_stripe_id('STRIPE_TIER_6_42_YEARLY_COMMITMENT_ID'),
        ],
        monthly_credits=Decimal('100.00'),
        display_name='Pro',
        can_purchase_credits=False,
        models=['all'],
        project_limit=UNLIMITED_PROJECT_LIMIT,
        thread_limit=UNLIMITED_THREAD_LIMIT,
        concurrent_runs=5,
        custom_workers_limit=20,
        scheduled_triggers_limit=10,
        app_triggers_limit=50,
        memory_config={
            'enabled': True,
            'max_memories': 500,
            'retrieval_limit': 25
        },
        daily_credit_config={
            'enabled': True,
            'amount': Decimal('2.00'),
            'refresh_interval_hours': 24
        },
        monthly_refill_enabled=True
    ),
    
    # -------------------------------------------------------------------------
    # Ultra Tier - Power user plan
    # ~$200/month = $400 monthly credits + credit purchases allowed
    # -------------------------------------------------------------------------
    'tier_25_200': Tier(
        name='tier_25_200',
        price_ids=[
            _get_stripe_id('STRIPE_TIER_25_200_ID'),
            _get_stripe_id('STRIPE_TIER_25_200_YEARLY_ID'),
            _get_stripe_id('STRIPE_TIER_25_170_YEARLY_COMMITMENT_ID'),
        ],
        monthly_credits=Decimal('400.00'),
        display_name='Ultra',
        can_purchase_credits=True,  # Only this tier can buy extra credits
        models=['all'],
        project_limit=UNLIMITED_PROJECT_LIMIT,
        thread_limit=UNLIMITED_THREAD_LIMIT,
        concurrent_runs=20,
        custom_workers_limit=100,
        scheduled_triggers_limit=50,
        app_triggers_limit=200,
        memory_config={
            'enabled': True,
            'max_memories': 2000,
            'retrieval_limit': 40
        },
        daily_credit_config={
            'enabled': True,
            'amount': Decimal('2.00'),
            'refresh_interval_hours': 24
        },
        monthly_refill_enabled=True
    ),
}


# =============================================================================
# CREDIT PACKAGES (One-time purchases)
# =============================================================================
@dataclass
class CreditPackage:
    """
    Configuration for a one-time credit purchase package.
    
    Attributes:
        id: Internal identifier (e.g., 'credits_10')
        amount: Amount of credits (in USD)
        stripe_price_id: Stripe Price ID for checkout
        name: Display name
    """
    id: str
    amount: Decimal
    stripe_price_id: str
    name: str

    @property
    def price(self) -> Decimal:
        """Alias for amount (assuming 1:1 USD to Credit value)."""
        return self.amount


CREDIT_PACKAGES: List[CreditPackage] = [
    CreditPackage(id='credits_10', amount=Decimal('10.00'), stripe_price_id=_get_stripe_id('STRIPE_CREDITS_10_PRICE_ID'), name='$10 Credits'),
    CreditPackage(id='credits_25', amount=Decimal('25.00'), stripe_price_id=_get_stripe_id('STRIPE_CREDITS_25_PRICE_ID'), name='$25 Credits'),
    CreditPackage(id='credits_50', amount=Decimal('50.00'), stripe_price_id=_get_stripe_id('STRIPE_CREDITS_50_PRICE_ID'), name='$50 Credits'),
    CreditPackage(id='credits_100', amount=Decimal('100.00'), stripe_price_id=_get_stripe_id('STRIPE_CREDITS_100_PRICE_ID'), name='$100 Credits'),
    CreditPackage(id='credits_250', amount=Decimal('250.00'), stripe_price_id=_get_stripe_id('STRIPE_CREDITS_250_PRICE_ID'), name='$250 Credits'),
    CreditPackage(id='credits_500', amount=Decimal('500.00'), stripe_price_id=_get_stripe_id('STRIPE_CREDITS_500_PRICE_ID'), name='$500 Credits'),
]


def get_credit_package(package_id: str) -> Optional[CreditPackage]:
    """
    Get a credit package by its ID.
    
    Args:
        package_id: Package ID (e.g., 'credits_10') or Stripe Price ID
        
    Returns:
        CreditPackage or None
    """
    for pkg in CREDIT_PACKAGES:
        if pkg.id == package_id or pkg.stripe_price_id == package_id:
            return pkg
    return None


# =============================================================================
# ADMIN LIMITS
# =============================================================================
ADMIN_LIMITS: Dict[str, Decimal] = {
    'max_credit_adjustment': Decimal('1000.00'),
    'max_bulk_grant': Decimal('10000.00'),
    'require_super_admin_above': Decimal('500.00'),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tier_by_price_id(price_id: str) -> Optional[Tier]:
    """
    Look up a tier by its Stripe price ID.
    
    Args:
        price_id: Stripe price ID (e.g., 'price_xxx')
        
    Returns:
        Tier object if found, None otherwise
    """
    if not price_id:
        return None
    for tier in TIERS.values():
        if price_id in tier.price_ids:
            return tier
    return None


def get_tier_by_name(tier_name: str) -> Optional[Tier]:
    """
    Look up a tier by its internal name.
    
    Args:
        tier_name: Internal tier name (e.g., 'free', 'tier_2_20')
        
    Returns:
        Tier object if found, None otherwise
    """
    return TIERS.get(tier_name)


def get_monthly_credits(tier_name: str) -> Decimal:
    """Get the monthly credits for a tier."""
    tier = TIERS.get(tier_name)
    return tier.monthly_credits if tier else TIERS['none'].monthly_credits


def can_purchase_credits(tier_name: str) -> bool:
    """Check if a tier allows credit purchases."""
    tier = TIERS.get(tier_name)
    return tier.can_purchase_credits if tier else False


def is_model_allowed(tier_name: str, model: str) -> bool:
    """
    Check if a model is allowed for a given tier.
    
    Args:
        tier_name: Internal tier name
        model: Model identifier to check
        
    Returns:
        True if model is allowed, False otherwise
    """
    tier = TIERS.get(tier_name, TIERS['none'])
    
    # 'all' means unrestricted model access
    if 'all' in tier.models:
        return True
    
    # Check if model matches any allowed patterns
    model_lower = model.lower()
    for allowed_pattern in tier.models:
        if allowed_pattern.lower() in model_lower:
            return True
    
    return False


def get_project_limit(tier_name: str) -> int:
    """Get the project limit for a tier."""
    tier = TIERS.get(tier_name)
    return tier.project_limit if tier else 20


def get_thread_limit(tier_name: str) -> int:
    """Get the thread limit for a tier."""
    tier = TIERS.get(tier_name)
    return tier.thread_limit if tier else TIERS['free'].thread_limit


def get_concurrent_runs_limit(tier_name: str) -> int:
    """Get the concurrent runs limit for a tier."""
    tier = TIERS.get(tier_name)
    return tier.concurrent_runs if tier else TIERS['free'].concurrent_runs


def get_tier_limits(tier_name: str) -> Dict:
    """
    Get all limits for a tier as a dictionary.
    
    Args:
        tier_name: Internal tier name
        
    Returns:
        Dictionary with all tier limits
    """
    tier = TIERS.get(tier_name, TIERS['free'])
    return {
        'project_limit': tier.project_limit,
        'thread_limit': tier.thread_limit,
        'concurrent_runs': tier.concurrent_runs,
        'custom_workers_limit': tier.custom_workers_limit,
        'scheduled_triggers_limit': tier.scheduled_triggers_limit,
        'app_triggers_limit': tier.app_triggers_limit,
        'agent_limit': tier.custom_workers_limit,
        'can_purchase_credits': tier.can_purchase_credits,
        'models': tier.models,
        'memory_config': tier.memory_config or {'enabled': False, 'max_memories': 0, 'retrieval_limit': 0}
    }


def is_commitment_price_id(price_id: str) -> bool:
    """Check if a price ID is for a yearly commitment plan."""
    commitment_price_ids = [
        _get_stripe_id('STRIPE_TIER_2_17_YEARLY_COMMITMENT_ID'),
        _get_stripe_id('STRIPE_TIER_6_42_YEARLY_COMMITMENT_ID'),
        _get_stripe_id('STRIPE_TIER_25_170_YEARLY_COMMITMENT_ID'),
    ]
    return price_id in commitment_price_ids


def get_commitment_duration_months(price_id: str) -> int:
    """Get the commitment duration in months for a price ID."""
    if is_commitment_price_id(price_id):
        return 12
    return 0


def get_price_type(price_id: str) -> str:
    """
    Determine the billing type for a price ID.
    
    Returns:
        'yearly_commitment', 'yearly', or 'monthly'
    """
    if is_commitment_price_id(price_id):
        return 'yearly_commitment'
    
    yearly_price_ids = [
        _get_stripe_id('STRIPE_TIER_2_20_YEARLY_ID'),
        _get_stripe_id('STRIPE_TIER_6_50_YEARLY_ID'),
        _get_stripe_id('STRIPE_TIER_25_200_YEARLY_ID'),
    ]
    
    if price_id in yearly_price_ids:
        return 'yearly'
    
    return 'monthly'


def get_plan_type(price_id: str) -> str:
    """Alias for get_price_type."""
    return get_price_type(price_id)


def get_memory_config(tier_name: str) -> Dict:
    """Get memory configuration for a tier."""
    tier = TIERS.get(tier_name, TIERS['free'])
    if tier.memory_config:
        return tier.memory_config
    return {'enabled': False, 'max_memories': 0, 'retrieval_limit': 0}


def is_memory_enabled(tier_name: str) -> bool:
    """Check if memory is enabled for a tier."""
    config = get_memory_config(tier_name)
    return config.get('enabled', False)


def get_max_memories(tier_name: str) -> int:
    """Get the maximum number of memories for a tier."""
    config = get_memory_config(tier_name)
    return config.get('max_memories', 0)


def get_memory_retrieval_limit(tier_name: str) -> int:
    """Get the memory retrieval limit for a tier."""
    config = get_memory_config(tier_name)
    return config.get('retrieval_limit', 0)
