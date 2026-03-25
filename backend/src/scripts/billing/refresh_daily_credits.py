"""
Daily Credit Refresh Script

Refreshes daily credits for free tier users.

Schedule: Hourly for responsive daily refresh ("0 * * * *")
Purpose: Check and refresh daily credits for free tier users whose 24-hour window has elapsed.

This script uses the existing billing infrastructure's check_and_refresh_daily_credits function,
but runs it for all free tier users proactively.

Usage:
    # Run manually
    python -m backend.src.scripts.billing.refresh_daily_credits
    
    # Install to crontab
    python -m backend.src.scripts.billing.refresh_daily_credits --install-cron
"""

from __future__ import annotations

import asyncio
import argparse
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import text

from backend.src.scripts.base import ScriptDefinition

logger = logging.getLogger(__name__)

# Cron schedule: Hourly (to catch users whose 24h window just expired)
DEFAULT_SCHEDULE = "0 * * * *"

# Batch processing size
BATCH_SIZE = 100


async def refresh_daily_credits() -> Dict[str, Any]:
    """
    Refresh daily credits for eligible free tier users.
    
    This script proactively refreshes daily credits for all free tier users
    whose last refresh was more than 24 hours ago.
    
    Returns:
        Dict with 'items_processed' and 'failed' counts
    """
    from backend.database.db import async_db_session
    from backend.src.billing.shared.config import TIERS
    
    now = datetime.now(timezone.utc)
    processed = 0
    failed = 0
    
    logger.info("[REFRESH DAILY] Starting daily credit refresh check")
    
    # Get free tier config
    free_tier = TIERS.get('free')
    if not free_tier or not free_tier.daily_credit_config:
        logger.info("[REFRESH DAILY] Free tier daily credits not configured, skipping")
        return {"items_processed": 0, "failed": 0, "message": "Daily credits not configured"}
    
    daily_config = free_tier.daily_credit_config
    if not daily_config.get('enabled', False):
        logger.info("[REFRESH DAILY] Daily credits disabled for free tier")
        return {"items_processed": 0, "failed": 0, "message": "Daily credits disabled"}
    
    refresh_hours = daily_config.get('refresh_interval_hours', 24)
    daily_amount = float(daily_config.get('amount', Decimal('1.00')))
    
    cutoff_time = now - timedelta(hours=refresh_hours)
    
    async with async_db_session() as session:
        # Find free tier accounts that need daily refresh
        result = await session.execute(
            text("""
                SELECT 
                    id,
                    account_id,
                    tier,
                    daily_credits_balance,
                    last_daily_refresh
                FROM credit_accounts
                WHERE tier = 'free'
                  AND (
                      last_daily_refresh IS NULL 
                      OR last_daily_refresh < :cutoff_time
                  )
                LIMIT :batch_size
            """),
            {"cutoff_time": cutoff_time, "batch_size": BATCH_SIZE}
        )
        accounts = result.fetchall()
        
        logger.info(f"[REFRESH DAILY] Found {len(accounts)} free tier accounts needing refresh")
        
        for account in accounts:
            try:
                account_id = str(account.account_id)
                
                # Update daily credits
                await session.execute(
                    text("""
                        UPDATE credit_accounts
                        SET daily_credits_balance = :amount,
                            last_daily_refresh = :now,
                            updated_at = :now
                        WHERE id = :account_id
                    """),
                    {
                        "account_id": account.id,
                        "amount": daily_amount,
                        "now": now
                    }
                )
                
                processed += 1
                logger.debug(f"[REFRESH DAILY] Refreshed account {account_id}: ${daily_amount:.2f}")
                
            except Exception as e:
                logger.error(f"[REFRESH DAILY] Failed for account {account.account_id}: {e}")
                failed += 1
        
        await session.commit()
    
    result = {
        "items_processed": processed,
        "failed": failed,
        "message": f"Refreshed {processed} free tier accounts, {failed} failed"
    }
    
    logger.info(f"[REFRESH DAILY] Completed: {result['message']}")
    
    return result


def build_cron_job_definition(schedule: str = DEFAULT_SCHEDULE):
    """Build cron job definition for system crontab installation."""
    from backend.src.scripts.cron_manager import CronJobDefinition, build_script_command
    
    return CronJobDefinition(
        name="agents-backend-refresh-daily-credits",
        schedule=schedule,
        command=build_script_command("backend.src.scripts.billing.refresh_daily_credits")
    )


def install_cron_job(schedule: str = DEFAULT_SCHEDULE, dry_run: bool = False) -> None:
    """Install cron job to system crontab."""
    from backend.src.scripts.cron_manager import CronManager
    
    manager = CronManager()
    job = build_cron_job_definition(schedule)
    manager.install(job=job, dry_run=dry_run)


# Script definition for registry
SCRIPT = ScriptDefinition(
    name="agents-backend-refresh-daily-credits",
    description="Refresh daily credits for free tier users",
    schedule=DEFAULT_SCHEDULE,
    task=refresh_daily_credits,
    module_path="backend.src.scripts.billing.refresh_daily_credits",
    status="active",
)


async def _main_async() -> None:
    """Async main entry point."""
    await refresh_daily_credits()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Refresh daily credits for free tier users"
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
