"""
Credit Account Domain Entity

Represents a user's credit account with balance tracking.
Based on external_billing/domain/entities/credit_account.py.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class CreditAccount:
    """
    Represents a user's credit account.
    
    Credit Structure:
    - balance: Total available credits (expiring + non_expiring)
    - expiring_credits: Credits from subscription that expire at billing cycle
    - non_expiring_credits: Credits from purchases that never expire
    - daily_credits_balance: Daily credits (for free tier)
    
    Expiring credits are consumed first, then non-expiring credits.
    
    Attributes:
        id: Unique identifier for the credit account
        account_id: Foreign key to user/account
        balance: Total current balance
        expiring_credits: Monthly subscription credits
        non_expiring_credits: Purchased credits
        daily_credits_balance: Daily refresh credits (free tier)
        tier: Current subscription tier name
        trial_status: Trial status ('none', 'active', 'expired', 'converted')
        created_at: When the account was created
        updated_at: Last modification time
        next_credit_grant: Next scheduled credit grant
        billing_cycle_anchor: Billing cycle start date
        stripe_subscription_id: Stripe subscription reference
        stripe_customer_id: Stripe customer reference
    """
    id: str
    account_id: str
    balance: Decimal
    expiring_credits: Decimal
    non_expiring_credits: Decimal
    tier: str
    created_at: datetime
    updated_at: datetime
    daily_credits_balance: Decimal = Decimal('0.00')
    trial_status: str = 'none'
    trial_ends_at: Optional[datetime] = None
    next_credit_grant: Optional[datetime] = None
    billing_cycle_anchor: Optional[datetime] = None
    last_grant_date: Optional[datetime] = None
    last_daily_refresh: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    plan_type: Optional[str] = None  # 'monthly', 'yearly', 'yearly_commitment'
    provider: str = 'stripe'  # 'stripe' or 'revenuecat'
    
    def total_credits(self) -> Decimal:
        """Calculate total available credits."""
        return self.expiring_credits + self.non_expiring_credits + self.daily_credits_balance
    
    def can_run_with_cost(self, cost: Decimal) -> bool:
        """Check if there are enough credits for an operation."""
        return self.balance >= cost
    
    def is_free_tier(self) -> bool:
        """Check if the account is on free tier."""
        return self.tier == 'free'
    
    def is_paid_tier(self) -> bool:
        """Check if the account is on a paid tier."""
        return self.tier not in ('none', 'free')
    
    def has_active_trial(self) -> bool:
        """Check if the account has an active trial."""
        return self.trial_status == 'active'
    
    def has_subscription(self) -> bool:
        """Check if the account has an active subscription."""
        return bool(self.stripe_subscription_id)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CreditAccount':
        """
        Create a CreditAccount from a dictionary (e.g., from database).
        
        Args:
            data: Dictionary with credit account fields
            
        Returns:
            CreditAccount instance
        """
        # Handle datetime fields
        def parse_datetime(value) -> Optional[datetime]:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return None
        
        # Handle Decimal fields
        def parse_decimal(value) -> Decimal:
            if value is None:
                return Decimal('0.00')
            return Decimal(str(value))
        
        return cls(
            id=data.get('id', ''),
            account_id=data.get('account_id', ''),
            balance=parse_decimal(data.get('balance')),
            expiring_credits=parse_decimal(data.get('expiring_credits')),
            non_expiring_credits=parse_decimal(data.get('non_expiring_credits')),
            daily_credits_balance=parse_decimal(data.get('daily_credits_balance')),
            tier=data.get('tier', 'none'),
            trial_status=data.get('trial_status', 'none'),
            trial_ends_at=parse_datetime(data.get('trial_ends_at')),
            created_at=parse_datetime(data.get('created_at')) or datetime.utcnow(),
            updated_at=parse_datetime(data.get('updated_at')) or datetime.utcnow(),
            next_credit_grant=parse_datetime(data.get('next_credit_grant')),
            billing_cycle_anchor=parse_datetime(data.get('billing_cycle_anchor')),
            last_grant_date=parse_datetime(data.get('last_grant_date')),
            last_daily_refresh=parse_datetime(data.get('last_daily_refresh')),
            stripe_subscription_id=data.get('stripe_subscription_id'),
            stripe_customer_id=data.get('stripe_customer_id'),
            plan_type=data.get('plan_type'),
            provider=data.get('provider', 'stripe'),
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'balance': float(self.balance),
            'expiring_credits': float(self.expiring_credits),
            'non_expiring_credits': float(self.non_expiring_credits),
            'daily_credits_balance': float(self.daily_credits_balance),
            'tier': self.tier,
            'trial_status': self.trial_status,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'next_credit_grant': self.next_credit_grant.isoformat() if self.next_credit_grant else None,
            'billing_cycle_anchor': self.billing_cycle_anchor.isoformat() if self.billing_cycle_anchor else None,
            'last_grant_date': self.last_grant_date.isoformat() if self.last_grant_date else None,
            'last_daily_refresh': self.last_daily_refresh.isoformat() if self.last_daily_refresh else None,
            'stripe_subscription_id': self.stripe_subscription_id,
            'stripe_customer_id': self.stripe_customer_id,
            'plan_type': self.plan_type,
            'provider': self.provider,
        }
