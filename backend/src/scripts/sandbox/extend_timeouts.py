"""
Sandbox Timeout Extension Script

Extends timeouts for all running sandboxes to prevent premature termination.

Schedule: Every 30 minutes ("*/30 * * * *")
Purpose: Keep sandboxes alive for active sessions by extending their E2B timeout.

This script:
1. Finds all running sandboxes
2. Extends each sandbox's timeout by the configured amount
3. Updates last_activity_at timestamp

Usage:
    # Run manually
    python -m backend.src.scripts.sandbox.extend_timeouts
    
    # With specific session IDs
    python -m backend.src.scripts.sandbox.extend_timeouts --session-ids "id1,id2"
    
    # Install to crontab
    python -m backend.src.scripts.sandbox.extend_timeouts --install-cron
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.src.scripts.base import ScriptDefinition
from backend.src.sandbox.sandbox_server.models.exceptions import SandboxNotFoundException

logger = logging.getLogger(__name__)

# Cron schedule: Every 30 minutes
DEFAULT_SCHEDULE = "*/30 * * * *"

# Timeout extension settings
TIMEOUT_EXTENSION_SECONDS = 7200  # 2 hours
BATCH_SIZE = 20


async def extend_sandbox_timeouts(
    session_ids: Optional[List[str]] = None,
    timeout_seconds: int = TIMEOUT_EXTENSION_SECONDS
) -> Dict[str, Any]:
    """
    Extend timeouts for running sandboxes.
    
    Args:
        session_ids: Optional list of specific session IDs to extend
        timeout_seconds: Number of seconds to extend timeout
        
    Returns:
        Dict with 'items_processed', 'failed', and 'message'
    """
    from backend.src.sandbox.sandbox_server.db.manager import get_db, Sandboxes
    from backend.src.sandbox.sandbox_server.db.model import Sandbox
    from backend.src.services.sandbox_service import sandbox_service
    
    processed = 0
    failed = 0
    cleaned = 0
    
    logger.info("[EXTEND TIMEOUT] Starting sandbox timeout extension")
    
    # Initialize sandbox service if needed
    if sandbox_service._controller is None:
        try:
            await sandbox_service.initialize()
        except Exception as e:
            logger.error(f"[EXTEND TIMEOUT] Failed to initialize sandbox service: {e}")
            return {"items_processed": 0, "failed": 1, "message": f"Service init failed: {e}"}
    
    controller = sandbox_service.controller
    
    async with get_db() as db:
        # Get sandboxes to extend
        if session_ids:
            # Get sandboxes for specific sessions
            sandboxes = []
            for session_id in session_ids:
                sandbox = await Sandboxes.get_sandbox_for_session(session_id)
                if sandbox and sandbox.status == "running":
                    sandboxes.append(sandbox)
            logger.info(f"[EXTEND TIMEOUT] Found {len(sandboxes)} sandboxes for {len(session_ids)} sessions")
        else:
            # Get all running sandboxes
            result = await db.execute(
                select(Sandbox).where(
                    Sandbox.status == "running"
                ).limit(BATCH_SIZE)
            )
            sandboxes = list(result.scalars().all())
            logger.info(f"[EXTEND TIMEOUT] Found {len(sandboxes)} running sandboxes")
        
        for sandbox in sandboxes:
            try:
                # Schedule new timeout via controller
                await controller.schedule_timeout(sandbox.id, timeout_seconds)
                
                # Update last activity
                await Sandboxes.update_last_activity(sandbox.id)
                
                processed += 1
                logger.debug(f"[EXTEND TIMEOUT] Extended sandbox {sandbox.id} by {timeout_seconds}s")
                
            except SandboxNotFoundException:
                # Sandbox no longer exists on e2b (404) — clean up stale DB record
                logger.warning(
                    f"[EXTEND TIMEOUT] Sandbox {sandbox.id} not found on provider (404). "
                    f"Marking as 'expired' and cleaning up stale DB record."
                )
                try:
                    await Sandboxes.update_sandbox_status(
                        sandbox.id, status="expired",
                        stopped_at=True  # Sets current UTC timestamp
                    )
                    cleaned += 1
                    logger.info(
                        f"[EXTEND TIMEOUT] Cleaned up stale sandbox {sandbox.id} "
                        f"(provider_id: {sandbox.provider_sandbox_id})"
                    )
                except Exception as cleanup_err:
                    logger.error(
                        f"[EXTEND TIMEOUT] Failed to clean up stale sandbox {sandbox.id}: {cleanup_err}"
                    )
                    failed += 1
                
            except Exception as e:
                logger.error(f"[EXTEND TIMEOUT] Failed for sandbox {sandbox.id}: {e}")
                failed += 1
    
    result = {
        "items_processed": processed,
        "failed": failed,
        "cleaned": cleaned,
        "message": f"Extended {processed} sandboxes, {cleaned} stale records cleaned, {failed} failed"
    }
    
    logger.info(f"[EXTEND TIMEOUT] Completed: {result['message']}")
    
    return result


def build_cron_job_definition(schedule: str = DEFAULT_SCHEDULE):
    """Build cron job definition for system crontab installation."""
    from backend.src.scripts.cron_manager import CronJobDefinition, build_script_command
    
    return CronJobDefinition(
        name="agents-backend-extend-sandbox-timeouts",
        schedule=schedule,
        command=build_script_command("backend.src.scripts.sandbox.extend_timeouts")
    )


def install_cron_job(schedule: str = DEFAULT_SCHEDULE, dry_run: bool = False) -> None:
    """Install cron job to system crontab."""
    from backend.src.scripts.cron_manager import CronManager
    
    manager = CronManager()
    job = build_cron_job_definition(schedule)
    manager.install(job=job, dry_run=dry_run)


# Script definition for registry
SCRIPT = ScriptDefinition(
    name="agents-backend-extend-sandbox-timeouts",
    description="Extend timeouts for running sandboxes to prevent premature termination",
    schedule=DEFAULT_SCHEDULE,
    task=extend_sandbox_timeouts,
    module_path="backend.src.scripts.sandbox.extend_timeouts",
    status="active",
)


async def _main_async(session_ids: Optional[List[str]] = None) -> None:
    """Async main entry point."""
    await extend_sandbox_timeouts(session_ids=session_ids)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extend sandbox timeouts"
    )
    parser.add_argument(
        "--session-ids",
        type=str,
        help="Comma-separated list of session IDs"
    )
    parser.add_argument(
        "--session-ids-file",
        type=str,
        help="Path to JSON file with session_ids array"
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
    
    # Parse session IDs
    session_ids = None
    if args.session_ids:
        session_ids = [s.strip() for s in args.session_ids.split(",") if s.strip()]
    elif args.session_ids_file and os.path.exists(args.session_ids_file):
        with open(args.session_ids_file) as f:
            data = json.load(f)
            session_ids = data.get("session_ids", [])
    
    asyncio.run(_main_async(session_ids))


if __name__ == "__main__":
    main()
