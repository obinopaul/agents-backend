"""
Daily Credit Refresh Service

Handles daily credit refresh for free tier and eligible subscription tiers.
Features:
- Automatic daily credit grant
- Timezone-aware refresh windows
- Distributed locking to prevent duplicates
- Redis caching for performance

Based on external_billing credit refresh patterns.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Tuple, Optional, Dict

from backend.src.billing.shared.config import get_tier_by_name, TIERS
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache

logger = logging.getLogger(__name__)


class DailyCreditRefreshService:
    """
    Manages daily credit refresh for users.
    
    Free tier users get a small daily credit allocation.
    Some paid tiers may also have daily refresh enabled.
    
    The daily credits:
    - Reset every 24 hours (based on last refresh time)
    - Do not accumulate - unused credits are lost
    - Are used first before other credit types
    
    Usage:
        service = DailyCreditRefreshService()
        refreshed, amount = await service.check_and_refresh_daily_credits(account_id)
    """
    
    # Default daily credit amount for free tier (can be overridden in tier config)
    DEFAULT_FREE_TIER_DAILY_CREDITS = Decimal('0.05')  # $0.05/day
    
    # Refresh window - minimum hours between refreshes
    REFRESH_WINDOW_HOURS = 20  # Allow refresh if last refresh was 20+ hours ago
    
    async def check_and_refresh_daily_credits(
        self,
        account_id: str,
        force_refresh: bool = False
    ) -> Tuple[bool, Decimal]:
        """
        Check if daily credits should be refreshed and do so if needed.
        
        Args:
            account_id: User account UUID
            force_refresh: If True, refresh regardless of time
            
        Returns:
            Tuple of (was_refreshed: bool, amount_granted: Decimal)
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Get account info
                result = await session.execute(
                    text("""
                        SELECT tier, last_daily_refresh, daily_credits_balance
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                        FOR UPDATE
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    logger.warning(f"[DAILY REFRESH] No account found for {account_id}")
                    return False, Decimal('0')
                
                tier_name = row.tier or 'none'
                last_refresh = row.last_daily_refresh
                current_daily_balance = Decimal(str(row.daily_credits_balance or 0))
                
                # Get tier configuration
                tier_info = get_tier_by_name(tier_name)
                
                # Check if tier has daily credits enabled
                daily_config = None
                if tier_info and tier_info.daily_credit_config:
                    daily_config = tier_info.daily_credit_config
                elif tier_name == 'free':
                    # Default config for free tier
                    daily_config = {
                        'enabled': True,
                        'amount': float(self.DEFAULT_FREE_TIER_DAILY_CREDITS),
                        'max_balance': float(self.DEFAULT_FREE_TIER_DAILY_CREDITS)
                    }
                
                if not daily_config or not daily_config.get('enabled'):
                    logger.debug(f"[DAILY REFRESH] Daily credits not enabled for tier '{tier_name}'")
                    return False, Decimal('0')
                
                # Check if refresh is due
                now = datetime.now(timezone.utc)
                
                if not force_refresh:
                    if last_refresh:
                        hours_since_refresh = (now - last_refresh).total_seconds() / 3600
                        if hours_since_refresh < self.REFRESH_WINDOW_HOURS:
                            logger.debug(f"[DAILY REFRESH] Not due yet for {account_id} "
                                       f"(last refresh {hours_since_refresh:.1f}h ago)")
                            return False, Decimal('0')
                
                # Calculate refresh amount
                daily_amount = Decimal(str(daily_config.get('amount', self.DEFAULT_FREE_TIER_DAILY_CREDITS)))
                max_balance = Decimal(str(daily_config.get('max_balance', daily_amount)))
                
                # Don't exceed max balance (prevents accumulation)
                new_daily_balance = min(daily_amount, max_balance)
                
                # Perform the refresh
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET daily_credits_balance = :new_daily,
                            balance = balance - daily_credits_balance + :new_daily,
                            last_daily_refresh = :now,
                            updated_at = :now
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {
                        "account_id": account_id,
                        "new_daily": float(new_daily_balance),
                        "now": now
                    }
                )
                
                # Record in ledger
                await session.execute(
                    text("""
                        INSERT INTO credit_ledger (
                            account_id, amount, type, description, is_expiring, metadata
                        ) VALUES (
                            CAST(:account_id AS UUID), :amount, 'daily_refresh', 'Daily credit refresh',
                            true, :metadata::jsonb
                        )
                    """),
                    {
                        "account_id": account_id,
                        "amount": float(new_daily_balance),
                        "metadata": str({
                            "tier": tier_name,
                            "previous_balance": float(current_daily_balance),
                            "is_reset": True
                        })
                    }
                )
                
                await session.commit()
            
            # Invalidate cache
            await invalidate_account_state_cache(account_id)
            
            logger.info(f"[DAILY REFRESH] ✅ Refreshed daily credits for {account_id}: ${new_daily_balance}")
            
            return True, new_daily_balance
            
        except Exception as e:
            logger.error(f"[DAILY REFRESH] Error refreshing daily credits for {account_id}: {e}")
            return False, Decimal('0')
    
    async def get_daily_credit_status(self, account_id: str) -> Dict:
        """
        Get detailed status of daily credits for an account.
        
        Returns:
            Dict with enabled, current_balance, max_balance, last_refresh, next_refresh
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT tier, daily_credits_balance, last_daily_refresh
                        FROM credit_accounts
                        WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    return {'enabled': False, 'error': 'Account not found'}
                
                tier_name = row.tier or 'none'
                tier_info = get_tier_by_name(tier_name)
                
                daily_config = None
                if tier_info and tier_info.daily_credit_config:
                    daily_config = tier_info.daily_credit_config
                elif tier_name == 'free':
                    daily_config = {
                        'enabled': True,
                        'amount': float(self.DEFAULT_FREE_TIER_DAILY_CREDITS),
                        'max_balance': float(self.DEFAULT_FREE_TIER_DAILY_CREDITS)
                    }
                
                if not daily_config or not daily_config.get('enabled'):
                    return {
                        'enabled': False,
                        'tier': tier_name,
                        'current_balance': 0
                    }
                
                last_refresh = row.last_daily_refresh
                now = datetime.now(timezone.utc)
                
                # Calculate next refresh time
                if last_refresh:
                    next_refresh = last_refresh + timedelta(hours=self.REFRESH_WINDOW_HOURS)
                    hours_until_refresh = max(0, (next_refresh - now).total_seconds() / 3600)
                else:
                    next_refresh = now
                    hours_until_refresh = 0
                
                return {
                    'enabled': True,
                    'tier': tier_name,
                    'current_balance': float(row.daily_credits_balance or 0),
                    'daily_amount': daily_config.get('amount', float(self.DEFAULT_FREE_TIER_DAILY_CREDITS)),
                    'max_balance': daily_config.get('max_balance', daily_config.get('amount', float(self.DEFAULT_FREE_TIER_DAILY_CREDITS))),
                    'last_refresh': last_refresh.isoformat() if last_refresh else None,
                    'next_refresh': next_refresh.isoformat() if next_refresh else None,
                    'hours_until_refresh': round(hours_until_refresh, 1),
                    'can_refresh': hours_until_refresh <= 0
                }
                
        except Exception as e:
            logger.error(f"[DAILY REFRESH] Error getting status for {account_id}: {e}")
            return {'enabled': False, 'error': str(e)}
    
    async def batch_refresh_due_accounts(self, limit: int = 100) -> int:
        """
        Find and refresh all accounts due for daily credit refresh.
        
        This is intended for use in a scheduled job/cron.
        
        Args:
            limit: Maximum accounts to process in one batch
            
        Returns:
            Number of accounts refreshed
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.REFRESH_WINDOW_HOURS)
            
            async with async_db_session() as session:
                # Find accounts due for refresh
                result = await session.execute(
                    text("""
                        SELECT account_id::text
                        FROM credit_accounts
                        WHERE tier IN ('free', 'tier_2_20', 'tier_6_50', 'tier_25_200')
                        AND (
                            last_daily_refresh IS NULL
                            OR last_daily_refresh < :cutoff
                        )
                        LIMIT :limit
                    """),
                    {"cutoff": cutoff, "limit": limit}
                )
                accounts = [row.account_id for row in result.fetchall()]
            
            refreshed_count = 0
            for account_id in accounts:
                try:
                    was_refreshed, _ = await self.check_and_refresh_daily_credits(account_id)
                    if was_refreshed:
                        refreshed_count += 1
                except Exception as e:
                    logger.error(f"[DAILY REFRESH] Failed to refresh {account_id}: {e}")
            
            if refreshed_count > 0:
                logger.info(f"[DAILY REFRESH] Batch refreshed {refreshed_count} accounts")
            
            return refreshed_count
            
        except Exception as e:
            logger.error(f"[DAILY REFRESH] Batch refresh error: {e}")
            return 0


# Global instance
daily_credit_service = DailyCreditRefreshService()


# Convenience functions
async def check_and_refresh_daily_credits(account_id: str, force_refresh: bool = False) -> Tuple[bool, Decimal]:
    """Check and refresh daily credits for an account."""
    return await daily_credit_service.check_and_refresh_daily_credits(account_id, force_refresh=force_refresh)


async def get_daily_credit_status(account_id: str) -> Dict:
    """Get daily credit status for an account."""
    return await daily_credit_service.get_daily_credit_status(account_id)
