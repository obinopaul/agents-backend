"""
Agent Tasks Cleanup Script

Marks stale agent run tasks as system interrupted.

Schedule: Every 40 minutes ("*/40 * * * *")
Purpose: Clean up agent tasks that have been running for too long.

This script:
1. Finds tasks running longer than STALE_TASK_MINUTES
2. Marks them as SYSTEM_INTERRUPTED
3. Logs for monitoring

Usage:
    # Run manually
    python -m backend.src.scripts.cleanup.stale_tasks
    
    # Install to crontab
    python -m backend.src.scripts.cleanup.stale_tasks --install-cron
"""

from __future__ import annotations

import asyncio
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from sqlalchemy import select, update

from backend.src.scripts.base import ScriptDefinition

logger = logging.getLogger(__name__)

# Cron schedule: Every 40 minutes
DEFAULT_SCHEDULE = "*/40 * * * *"

# Tasks running longer than this are considered stale
STALE_TASK_MINUTES = 45
BATCH_SIZE = 50


async def cleanup_stale_tasks(
    stale_minutes: int = STALE_TASK_MINUTES
) -> Dict[str, Any]:
    """
    Clean up stale agent run tasks.
    
    Args:
        stale_minutes: Minutes before a task is considered stale
        
    Returns:
        Dict with 'items_processed' count
    """
    from backend.database.db import async_db_session
    
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(minutes=stale_minutes)
    processed = 0
    
    logger.info(f"[CLEANUP TASKS] Starting cleanup of tasks older than {stale_minutes} minutes")
    
    async with async_db_session() as session:
        # Try to import AgentRunTask - may not exist in all deployments
        try:
            from backend.app.agent.model.agent_models import AgentRunTask, RunStatus
        except ImportError:
            logger.info("[CLEANUP TASKS] AgentRunTask model not found, skipping")
            return {"items_processed": 0, "message": "AgentRunTask model not available"}
        
        # Find stale running tasks with row-level locking
        # skip_locked=True ensures we don't wait for locked rows 
        result = await session.execute(
            select(AgentRunTask).where(
                AgentRunTask.created_at < cutoff_time,
                AgentRunTask.status == RunStatus.RUNNING,
            ).order_by(AgentRunTask.created_at.desc())
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        tasks = result.scalars().all()
        
        logger.info(f"[CLEANUP TASKS] Found {len(tasks)} stale tasks")
        
        for task in tasks:
            task.status = RunStatus.SYSTEM_INTERRUPTED
            task.updated_at = now
            processed += 1
        
        await session.commit()
    
    result = {
        "items_processed": processed,
        "message": f"Marked {processed} stale tasks as system_interrupted"
    }
    
    logger.info(f"[CLEANUP TASKS] Completed: {result['message']}")
    
    return result


def build_cron_job_definition(schedule: str = DEFAULT_SCHEDULE):
    """Build cron job definition for system crontab installation."""
    from backend.src.scripts.cron_manager import CronJobDefinition, build_script_command
    
    return CronJobDefinition(
        name="agents-backend-cleanup-stale-tasks",
        schedule=schedule,
        command=build_script_command("backend.src.scripts.cleanup.stale_tasks")
    )


def install_cron_job(schedule: str = DEFAULT_SCHEDULE, dry_run: bool = False) -> None:
    """Install cron job to system crontab."""
    from backend.src.scripts.cron_manager import CronManager
    
    manager = CronManager()
    job = build_cron_job_definition(schedule)
    manager.install(job=job, dry_run=dry_run)


# Script definition for registry
SCRIPT = ScriptDefinition(
    name="agents-backend-cleanup-stale-tasks",
    description="Mark stale agent run tasks as system interrupted",
    schedule=DEFAULT_SCHEDULE,
    task=cleanup_stale_tasks,
    module_path="backend.src.scripts.cleanup.stale_tasks",
    status="active",
)


async def _main_async() -> None:
    """Async main entry point."""
    await cleanup_stale_tasks()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up stale agent run tasks"
    )
    parser.add_argument(
        "--stale-minutes",
        type=int,
        default=STALE_TASK_MINUTES,
        help=f"Minutes before task is stale (default: {STALE_TASK_MINUTES})"
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
    
    asyncio.run(cleanup_stale_tasks(stale_minutes=args.stale_minutes))


if __name__ == "__main__":
    main()
