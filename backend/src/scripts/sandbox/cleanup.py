"""
Sandbox Cleanup Script

Pauses inactive sandboxes and deletes expired ones.

Schedule: Every 2 hours ("0 */2 * * *")
Purpose: Clean up sandboxes that are no longer actively used.

This script:
1. Pauses sandboxes inactive for > INACTIVITY_THRESHOLD_HOURS
2. Deletes paused sandboxes older than EXPIRED_THRESHOLD_DAYS
3. Logs all actions for audit

Usage:
    # Run manually
    python -m backend.src.scripts.sandbox.cleanup
    
    # Install to crontab
    python -m backend.src.scripts.sandbox.cleanup --install-cron
"""

from __future__ import annotations

import asyncio
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from sqlalchemy import select

from backend.src.scripts.base import ScriptDefinition
from backend.src.sandbox.sandbox_server.models.exceptions import SandboxNotFoundException

logger = logging.getLogger(__name__)

# Cron schedule: Every 2 hours
DEFAULT_SCHEDULE = "0 */2 * * *"

# Cleanup thresholds
INACTIVITY_THRESHOLD_HOURS = 2  # Pause after 2h inactive
EXPIRED_THRESHOLD_DAYS = 30     # Delete after 30 days paused
BATCH_SIZE = 50


async def cleanup_sandboxes(
    inactivity_hours: int = INACTIVITY_THRESHOLD_HOURS,
    expired_days: int = EXPIRED_THRESHOLD_DAYS
) -> Dict[str, Any]:
    """
    Clean up inactive and expired sandboxes.
    
    Args:
        inactivity_hours: Hours of inactivity before pausing
        expired_days: Days paused before deletion
        
    Returns:
        Dict with 'paused', 'deleted', and 'failed' counts
    """
    from backend.src.sandbox.sandbox_server.db.manager import get_db, Sandboxes
    from backend.src.sandbox.sandbox_server.db.model import Sandbox
    from backend.src.services.sandbox_service import sandbox_service
    
    now = datetime.now(timezone.utc)
    inactive_cutoff = now - timedelta(hours=inactivity_hours)
    expired_cutoff = now - timedelta(days=expired_days)
    
    paused_count = 0
    deleted_count = 0
    cleaned_count = 0
    failed_count = 0
    
    logger.info("[CLEANUP] Starting sandbox cleanup")
    logger.info(f"[CLEANUP] Inactive cutoff: {inactive_cutoff} ({inactivity_hours}h ago)")
    logger.info(f"[CLEANUP] Expired cutoff: {expired_cutoff} ({expired_days}d ago)")
    
    # Initialize sandbox service if needed
    if sandbox_service._controller is None:
        try:
            await sandbox_service.initialize()
        except Exception as e:
            logger.error(f"[CLEANUP] Failed to initialize sandbox service: {e}")
            return {"paused": 0, "deleted": 0, "failed": 1, "message": f"Service init failed: {e}"}
    
    controller = sandbox_service.controller
    
    async with get_db() as db:
        # STEP 1: Find and pause inactive running sandboxes
        inactive_result = await db.execute(
            select(Sandbox).where(
                Sandbox.status == "running",
                Sandbox.last_activity_at < inactive_cutoff
            ).limit(BATCH_SIZE)
        )
        inactive_sandboxes = list(inactive_result.scalars().all())
        
        logger.info(f"[CLEANUP] Found {len(inactive_sandboxes)} inactive sandboxes to pause")
        
        for sandbox in inactive_sandboxes:
            try:
                await controller.pause_sandbox(sandbox.id, reason="inactivity")
                paused_count += 1
                logger.info(f"[CLEANUP] Paused sandbox {sandbox.id} (inactive since {sandbox.last_activity_at})")
            except SandboxNotFoundException:
                # Sandbox no longer exists on provider (404) — clean up stale DB record
                logger.warning(
                    f"[CLEANUP] Sandbox {sandbox.id} not found on provider (404). "
                    f"Marking as 'expired'."
                )
                try:
                    await Sandboxes.update_sandbox_status(
                        sandbox.id, status="expired",
                        stopped_at=True  # Sets current UTC timestamp
                    )
                    cleaned_count += 1
                except Exception as cleanup_err:
                    logger.error(f"[CLEANUP] Failed to clean up stale sandbox {sandbox.id}: {cleanup_err}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"[CLEANUP] Failed to pause sandbox {sandbox.id}: {e}")
                failed_count += 1
        
        # STEP 2: Find and delete expired paused sandboxes
        expired_result = await db.execute(
            select(Sandbox).where(
                Sandbox.status == "paused",
                Sandbox.stopped_at < expired_cutoff
            ).limit(BATCH_SIZE)
        )
        expired_sandboxes = list(expired_result.scalars().all())
        
        logger.info(f"[CLEANUP] Found {len(expired_sandboxes)} expired sandboxes to delete")
        
        for sandbox in expired_sandboxes:
            try:
                await controller.delete_sandbox(sandbox.id)
                deleted_count += 1
                logger.info(f"[CLEANUP] Deleted sandbox {sandbox.id} (paused since {sandbox.stopped_at})")
            except SandboxNotFoundException:
                # Already gone from provider — just delete the DB record
                logger.warning(
                    f"[CLEANUP] Expired sandbox {sandbox.id} not found on provider (404). "
                    f"Deleting stale DB record."
                )
                try:
                    await Sandboxes.delete_sandbox(sandbox.id)
                    cleaned_count += 1
                except Exception as cleanup_err:
                    logger.error(f"[CLEANUP] Failed to delete stale record {sandbox.id}: {cleanup_err}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"[CLEANUP] Failed to delete sandbox {sandbox.id}: {e}")
                failed_count += 1
    
    result = {
        "paused": paused_count,
        "deleted": deleted_count,
        "cleaned": cleaned_count,
        "failed": failed_count,
        "items_processed": paused_count + deleted_count + cleaned_count,
        "message": f"Paused {paused_count}, deleted {deleted_count}, cleaned {cleaned_count} stale, {failed_count} failed"
    }
    
    logger.info(f"[CLEANUP] Completed: {result['message']}")
    
    return result


def build_cron_job_definition(schedule: str = DEFAULT_SCHEDULE):
    """Build cron job definition for system crontab installation."""
    from backend.src.scripts.cron_manager import CronJobDefinition, build_script_command
    
    return CronJobDefinition(
        name="agents-backend-sandbox-cleanup",
        schedule=schedule,
        command=build_script_command("backend.src.scripts.sandbox.cleanup")
    )


def install_cron_job(schedule: str = DEFAULT_SCHEDULE, dry_run: bool = False) -> None:
    """Install cron job to system crontab."""
    from backend.src.scripts.cron_manager import CronManager
    
    manager = CronManager()
    job = build_cron_job_definition(schedule)
    manager.install(job=job, dry_run=dry_run)


# Script definition for registry
SCRIPT = ScriptDefinition(
    name="agents-backend-sandbox-cleanup",
    description="Pause inactive sandboxes and delete expired ones",
    schedule=DEFAULT_SCHEDULE,
    task=cleanup_sandboxes,
    module_path="backend.src.scripts.sandbox.cleanup",
    status="active",
)


async def _main_async() -> None:
    """Async main entry point."""
    await cleanup_sandboxes()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up inactive and expired sandboxes"
    )
    parser.add_argument(
        "--inactivity-hours",
        type=int,
        default=INACTIVITY_THRESHOLD_HOURS,
        help=f"Hours before pausing inactive sandboxes (default: {INACTIVITY_THRESHOLD_HOURS})"
    )
    parser.add_argument(
        "--expired-days",
        type=int,
        default=EXPIRED_THRESHOLD_DAYS,
        help=f"Days before deleting paused sandboxes (default: {EXPIRED_THRESHOLD_DAYS})"
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
        return
    
    asyncio.run(cleanup_sandboxes(
        inactivity_hours=args.inactivity_hours,
        expired_days=args.expired_days
    ))


if __name__ == "__main__":
    main()
