"""
Subscription Domain Entity

Represents a user's subscription with status tracking.
Based on external_billing/domain/entities/subscription.py.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict
from enum import Enum


class SubscriptionStatus(Enum):
    """Possible subscription statuses."""
    ACTIVE = "active"
    CANCELED = "canceled"  
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    PAUSED = "paused"


class SubscriptionProvider(Enum):
    """Payment providers for subscriptions."""
    STRIPE = "stripe"
    REVENUECAT = "revenuecat"  # For mobile apps


@dataclass
class Subscription:
    """
    Represents a user's subscription.
    
    Attributes:
        id: Internal subscription ID
        account_id: User/account ID this subscription belongs to
        provider: Payment provider (Stripe, RevenueCat)
        provider_subscription_id: External subscription ID from provider
        tier_name: Internal tier name (e.g., 'tier_2_20')
        status: Current subscription status
        current_period_start: Start of current billing period
        current_period_end: End of current billing period
        monthly_credits: Credits granted per billing cycle
        created_at: When subscription was created
        updated_at: Last update timestamp
        cancel_at_period_end: Whether subscription is set to cancel
        canceled_at: When subscription was canceled (if applicable)
        metadata: Additional metadata from provider
    """
    id: str
    account_id: str
    provider: SubscriptionProvider
    provider_subscription_id: str
    tier_name: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    monthly_credits: Decimal
    created_at: datetime
    updated_at: datetime
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    scheduled_change: Optional[Dict] = None
    metadata: Optional[Dict] = None
    
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
    
    def is_canceled(self) -> bool:
        """Check if subscription has been canceled."""
        return self.status == SubscriptionStatus.CANCELED or self.cancel_at_period_end
    
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == SubscriptionStatus.TRIALING
    
    def is_past_due(self) -> bool:
        """Check if subscription payment is past due (grace period)."""
        return self.status == SubscriptionStatus.PAST_DUE
    
    def is_expired(self) -> bool:
        """Check if the current period has ended."""
        return datetime.utcnow() > self.current_period_end
    
    def days_until_renewal(self) -> int:
        """Calculate days until subscription renews."""
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    def days_in_period(self) -> int:
        """Calculate total days in current billing period."""
        delta = self.current_period_end - self.current_period_start
        return max(1, delta.days)
    
    def period_progress_percent(self) -> float:
        """Calculate what percentage of the billing period has elapsed."""
        total_days = self.days_in_period()
        elapsed = (datetime.utcnow() - self.current_period_start).days
        return min(100.0, (elapsed / total_days) * 100)
    
    def has_scheduled_change(self) -> bool:
        """Check if there's a scheduled tier change."""
        return self.scheduled_change is not None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Subscription':
        """
        Create a Subscription from a dictionary.
        
        Args:
            data: Dictionary with subscription fields
            
        Returns:
            Subscription instance
        """
        def parse_datetime(value) -> Optional[datetime]:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, int):  # Unix timestamp
                return datetime.fromtimestamp(value)
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return None
        
        def parse_status(value) -> SubscriptionStatus:
            if isinstance(value, SubscriptionStatus):
                return value
            try:
                return SubscriptionStatus(value)
            except ValueError:
                return SubscriptionStatus.INCOMPLETE
        
        def parse_provider(value) -> SubscriptionProvider:
            if isinstance(value, SubscriptionProvider):
                return value
            try:
                return SubscriptionProvider(value)
            except ValueError:
                return SubscriptionProvider.STRIPE
        
        return cls(
            id=data.get('id', ''),
            account_id=data.get('account_id', ''),
            provider=parse_provider(data.get('provider', 'stripe')),
            provider_subscription_id=data.get('provider_subscription_id', data.get('stripe_subscription_id', '')),
            tier_name=data.get('tier_name', data.get('tier', 'none')),
            status=parse_status(data.get('status', 'incomplete')),
            current_period_start=parse_datetime(data.get('current_period_start')) or datetime.utcnow(),
            current_period_end=parse_datetime(data.get('current_period_end')) or datetime.utcnow(),
            monthly_credits=Decimal(str(data.get('monthly_credits', 0))),
            created_at=parse_datetime(data.get('created_at')) or datetime.utcnow(),
            updated_at=parse_datetime(data.get('updated_at')) or datetime.utcnow(),
            cancel_at_period_end=data.get('cancel_at_period_end', False),
            canceled_at=parse_datetime(data.get('canceled_at')),
            scheduled_change=data.get('scheduled_change'),
            metadata=data.get('metadata'),
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'provider': self.provider.value,
            'provider_subscription_id': self.provider_subscription_id,
            'tier_name': self.tier_name,
            'status': self.status.value,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'monthly_credits': float(self.monthly_credits),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'cancel_at_period_end': self.cancel_at_period_end,
            'canceled_at': self.canceled_at.isoformat() if self.canceled_at else None,
            'scheduled_change': self.scheduled_change,
            'metadata': self.metadata,
            # Computed fields
            'is_active': self.is_active(),
            'is_trialing': self.is_trialing(),
            'days_until_renewal': self.days_until_renewal(),
        }
