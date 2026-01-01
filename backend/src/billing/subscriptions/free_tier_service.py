"""
Free Tier Service

Handles automatic free tier subscription setup for new users.
Features:
- Auto-subscribe new users to free tier
- Create Stripe customer and subscription
- Grant initial daily credits
- Distributed locking to prevent race conditions

Based on external_billing/subscriptions/free_tier_service.py.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple

from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.config import TIERS, get_tier_by_name
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
from backend.src.billing.shared.exceptions import BillingError
from backend.src.billing.credits import credit_manager, check_and_refresh_daily_credits
from .handlers.customer import CustomerHandler

logger = logging.getLogger(__name__)


class FreeTierService:
    """
    Manages automatic free tier enrollment for new users.
    
    When a new user signs up:
    1. Create Stripe customer
    2. Create free tier subscription (no payment required)
    3. Set up credit account with daily refresh
    4. Grant initial daily credits
    
    Uses distributed locking to prevent duplicate enrollments.
    """
    
    # Free tier configuration
    FREE_TIER_NAME = 'free'
    FREE_TIER_DAILY_CREDITS = Decimal('0.05')
    
    @classmethod
    async def ensure_free_tier_subscription(
        cls,
        account_id: str,
        email: Optional[str] = None
    ) -> Dict:
        """
        Ensure user has at least free tier subscription.
        
        If user already has subscription, no action taken.
        If user has no subscription, creates free tier.
        
        Args:
            account_id: User account UUID
            email: User's email (for Stripe customer)
            
        Returns:
            Dict with success, tier, and details
        """
        service = cls()
        return await service._ensure_free_tier_subscription(account_id, email)
    
    async def _ensure_free_tier_subscription(
        self,
        account_id: str,
        email: Optional[str] = None
    ) -> Dict:
        """Internal implementation."""
        logger.info(f"[FREE TIER] Checking subscription for {account_id}")
        
        # Check if already has subscription
        existing = await self._check_existing_subscription(account_id)
        if existing.get('has_subscription'):
            logger.debug(f"[FREE TIER] {account_id} already has subscription: {existing.get('tier')}")
            return {
                'success': True,
                'already_subscribed': True,
                'tier': existing.get('tier'),
                'subscription_id': existing.get('subscription_id')
            }
        
        # Use distributed lock to prevent race conditions
        lock_acquired = await self._acquire_setup_lock(account_id)
        if not lock_acquired:
            logger.warning(f"[FREE TIER] Could not acquire setup lock for {account_id}")
            return {
                'success': False,
                'reason': 'Setup already in progress'
            }
        
        try:
            # Create Stripe customer
            customer_id = await CustomerHandler.get_or_create_stripe_customer(account_id)
            
            # Get free tier price ID
            free_tier = get_tier_by_name(self.FREE_TIER_NAME)
            if not free_tier or not free_tier.price_ids:
                # Create without Stripe subscription if no price configured
                await self._setup_free_tier_without_stripe(account_id, customer_id)
                return {
                    'success': True,
                    'tier': self.FREE_TIER_NAME,
                    'stripe_subscription': False
                }
            
            price_id = free_tier.price_ids[0]
            
            # Create free tier subscription in Stripe
            subscription = await self._create_free_subscription(
                customer_id, price_id, account_id
            )
            
            # Update credit account
            await self._setup_credit_account(
                account_id=account_id,
                tier=self.FREE_TIER_NAME,
                subscription_id=subscription.id,
                customer_id=customer_id
            )
            
            # Grant initial daily credits
            await check_and_refresh_daily_credits(account_id, force_refresh=True)
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[FREE TIER] ✅ Setup complete for {account_id}")
            
            return {
                'success': True,
                'tier': self.FREE_TIER_NAME,
                'subscription_id': subscription.id,
                'customer_id': customer_id
            }
            
        except Exception as e:
            logger.error(f"[FREE TIER] Setup failed for {account_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            await self._release_setup_lock(account_id)
    
    async def _check_existing_subscription(self, account_id: str) -> Dict:
        """Check if account already has a subscription."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT tier, stripe_subscription_id
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if row and row.stripe_subscription_id:
                    return {
                        'has_subscription': True,
                        'tier': row.tier,
                        'subscription_id': row.stripe_subscription_id
                    }
                elif row and row.tier and row.tier != 'none':
                    return {
                        'has_subscription': True,
                        'tier': row.tier
                    }
                
                return {'has_subscription': False}
                
        except Exception as e:
            logger.warning(f"[FREE TIER] Error checking subscription: {e}")
            return {'has_subscription': False}
    
    async def _acquire_setup_lock(self, account_id: str) -> bool:
        """Acquire distributed lock for setup."""
        try:
            from core.utils.distributed_lock import DistributedLock
            lock = DistributedLock(f"free_tier_setup:{account_id}", ttl=30)
            return await lock.acquire()
        except ImportError:
            # If distributed lock not available, proceed without it
            return True
        except Exception as e:
            logger.warning(f"[FREE TIER] Lock acquisition error: {e}")
            return True
    
    async def _release_setup_lock(self, account_id: str) -> None:
        """Release distributed lock."""
        try:
            from core.utils.distributed_lock import DistributedLock
            lock = DistributedLock(f"free_tier_setup:{account_id}")
            await lock.release()
        except Exception:
            pass
    
    async def _create_free_subscription(
        self,
        customer_id: str,
        price_id: str,
        account_id: str
    ):
        """Create free tier subscription in Stripe."""
        logger.info(f"[FREE TIER] Creating subscription for {account_id}")
        
        subscription = await StripeAPIWrapper.create_subscription(
            customer=customer_id,
            items=[{'price': price_id}],
            metadata={
                'account_id': account_id,
                'tier': self.FREE_TIER_NAME,
                'setup_type': 'auto_free_tier'
            }
        )
        
        logger.info(f"[FREE TIER] Created subscription {subscription.id}")
        
        return subscription
    
    async def _setup_free_tier_without_stripe(
        self,
        account_id: str,
        customer_id: str
    ) -> None:
        """Set up free tier without Stripe subscription."""
        await self._setup_credit_account(
            account_id=account_id,
            tier=self.FREE_TIER_NAME,
            subscription_id=None,
            customer_id=customer_id
        )
        
        await check_and_refresh_daily_credits(account_id, force_refresh=True)
    
    async def _setup_credit_account(
        self,
        account_id: str,
        tier: str,
        subscription_id: Optional[str],
        customer_id: str
    ) -> None:
        """Create or update credit account for free tier."""
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        now = datetime.now(timezone.utc)
        
        async with async_db_session() as session:
            # Check if account exists
            result = await session.execute(
                text("SELECT id FROM credit_accounts WHERE account_id = CAST(:account_id AS UUID)"),
                {"account_id": account_id}
            )
            exists = result.fetchone() is not None
            
            if exists:
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET tier = :tier,
                            stripe_subscription_id = :subscription_id,
                            stripe_customer_id = :customer_id,
                            updated_at = :now
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {
                        "account_id": account_id,
                        "tier": tier,
                        "subscription_id": subscription_id,
                        "customer_id": customer_id,
                        "now": now
                    }
                )
            else:
                await session.execute(
                    text("""
                        INSERT INTO credit_accounts (
                            account_id, tier, stripe_subscription_id, stripe_customer_id,
                            balance, expiring_credits, non_expiring_credits, daily_credits_balance,
                            created_at, updated_at
                        ) VALUES (
                            CAST(:account_id AS UUID), :tier, :subscription_id, :customer_id,
                            0, 0, 0, 0, :now, :now
                        )
                    """),
                    {
                        "account_id": account_id,
                        "tier": tier,
                        "subscription_id": subscription_id,
                        "customer_id": customer_id,
                        "now": now
                    }
                )
            
            await session.commit()


# Global instance
free_tier_service = FreeTierService()


# Convenience function
async def ensure_free_tier_subscription(account_id: str, email: Optional[str] = None) -> Dict:
    """Ensure user has at least free tier subscription."""
    return await FreeTierService.ensure_free_tier_subscription(account_id, email)
