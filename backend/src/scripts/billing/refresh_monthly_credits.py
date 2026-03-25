"""
Monthly Credit Refresh Script

Refreshes monthly credits for subscribers at the start of each billing period.

Schedule: Daily at midnight UTC ("0 0 * * *")
Purpose: Check for users whose monthly credits should be refreshed at billing cycle reset.

This script:
1. Finds credit accounts with monthly_refill_enabled for their tier
2. Checks if the billing period has reset
3. Resets credits to the tier's monthly allowance
4. Updates last_monthly_refresh timestamp

Usage:
    # Run manually
    python -m backend.src.scripts.billing.refresh_monthly_credits
    
    # Install to crontab
    python -m backend.src.scripts.billing.refresh_monthly_credits --install-cron
"""

from __future__ import annotations

import asyncio
import argparse
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import select, update, text

from backend.src.scripts.base import ScriptDefinition

logger = logging.getLogger(__name__)

# Cron schedule: Daily at midnight UTC
DEFAULT_SCHEDULE = "0 0 * * *"

# Batch processing size
BATCH_SIZE = 100


async def refresh_monthly_credits() -> Dict[str, Any]:
    """
    Refresh monthly credits for eligible subscribers.
    
    Returns:
        Dict with 'items_processed' and 'failed' counts
    """
    from backend.database.db import async_db_session
    from backend.src.billing.shared.config import TIERS, get_tier_by_name
    
    now = datetime.now(timezone.utc)
    processed = 0
    failed = 0
    
    logger.info("[REFRESH MONTHLY] Starting monthly credit refresh")
    
    async with async_db_session() as session:
        # Get all credit accounts with active subscriptions
        # Only process accounts that haven't been refreshed this month
        result = await session.execute(
            text("""
                SELECT 
                    id,
                    account_id,
                    tier,
                    balance,
                    stripe_subscription_id,
                    last_monthly_refresh,
                    subscription_current_period_start,
                    subscription_current_period_end
                FROM credit_accounts
                WHERE tier IS NOT NULL 
                  AND tier != 'none'
                  AND tier != 'free'
            """)
        )
        accounts = result.fetchall()
        
        logger.info(f"[REFRESH MONTHLY] Found {len(accounts)} non-free accounts to check")
        
        for account in accounts:
            try:
                account_id = str(account.account_id)
                tier_name = account.tier
                last_refresh = account.last_monthly_refresh
                period_start = account.subscription_current_period_start
                
                # Get tier configuration
                tier = get_tier_by_name(tier_name)
                if not tier:
                    logger.warning(f"[REFRESH MONTHLY] Unknown tier '{tier_name}' for account {account_id}")
                    continue
                
                if not tier.monthly_refill_enabled:
                    continue
                
                # Determine if refresh is needed
                should_refresh = False
                
                # If period_start is set, check if we're in a new period
                if period_start:
                    # Refresh if we haven't refreshed since the period started
                    if last_refresh is None or last_refresh < period_start:
                        should_refresh = True
                else:
                    # Fallback: refresh on the 1st of each month if not refreshed this month
                    if now.day == 1:
                        if last_refresh is None:
                            should_refresh = True
                        elif last_refresh.month != now.month or last_refresh.year != now.year:
                            should_refresh = True
                
                if not should_refresh:
                    continue
                
                # Perform the refresh
                monthly_credits = float(tier.monthly_credits)
                
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET balance = :new_balance,
                            last_monthly_refresh = :now,
                            updated_at = :now
                        WHERE id = :account_id
                    """),
                    {
                        "account_id": account.id,
                        "new_balance": monthly_credits,
                        "now": now
                    }
                )
                
                processed += 1
                logger.info(
                    f"[REFRESH MONTHLY] Refreshed {account_id}: "
                    f"tier={tier_name}, credits=${monthly_credits:.2f}"
                )
                
            except Exception as e:
                logger.error(f"[REFRESH MONTHLY] Failed for account {account.account_id}: {e}")
                failed += 1
        
        await session.commit()
    
    result = {
        "items_processed": processed,
        "failed": failed,
        "message": f"Refreshed {processed} accounts, {failed} failed"
    }
    
    logger.info(f"[REFRESH MONTHLY] Completed: {result['message']}")
    
    return result


def build_cron_job_definition(schedule: str = DEFAULT_SCHEDULE):
    """Build cron job definition for system crontab installation."""
    from backend.src.scripts.cron_manager import CronJobDefinition, build_script_command
    
    return CronJobDefinition(
        name="agents-backend-refresh-monthly-credits",
        schedule=schedule,
        command=build_script_command("backend.src.scripts.billing.refresh_monthly_credits")
    )


def install_cron_job(schedule: str = DEFAULT_SCHEDULE, dry_run: bool = False) -> None:
    """Install cron job to system crontab."""
    from backend.src.scripts.cron_manager import CronManager
    
    manager = CronManager()
    job = build_cron_job_definition(schedule)
    manager.install(job=job, dry_run=dry_run)


# Script definition for registry
SCRIPT = ScriptDefinition(
    name="agents-backend-refresh-monthly-credits",
    description="Refresh monthly credits for paid subscribers at billing cycle reset",
    schedule=DEFAULT_SCHEDULE,
    task=refresh_monthly_credits,
    module_path="backend.src.scripts.billing.refresh_monthly_credits",
    status="active",
)


async def _main_async() -> None:
    """Async main entry point."""
    await refresh_monthly_credits()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Refresh monthly credits for paid subscribers"
    )
    parser.add_argument(
        "--install-cron",
        action="store_true",
        help="Install cron job instead of running now"
    )
    parser.add_argument(
        "--schedule",
        default=DEFAULT_SCHEDULE,
        help=f"Cron schedule (default: '{DEFAULT_SCHEDULE}')"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show cron job without installing"
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.install_cron:
        install_cron_job(schedule=args.schedule, dry_run=args.dry_run)
    else:
        asyncio.run(_main_async())


if __name__ == "__main__":
    main()
