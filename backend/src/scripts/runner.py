"""
APScheduler-based script runner for in-process execution.

This runner starts with the FastAPI application and executes scripts
on their defined schedules using APScheduler's async scheduler.

Best for: Docker deployments, development, single-server setups.

Usage:
    # Start with FastAPI (add to registrar.py lifespan):
    from backend.src.scripts.runner import start_runner, stop_runner
    start_runner()  # In startup
    stop_runner()   # In shutdown
    
    # Or run standalone:
    python -m backend.src.scripts.runner
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.src.scripts.base import ScriptDefinition, ScriptResult

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None
_is_running = False


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def run_script(script: ScriptDefinition) -> ScriptResult:
    """
    Execute a single script and return the result.
    
    Args:
        script: Script definition to run
        
    Returns:
        ScriptResult with execution details
    """
    started_at = datetime.now(timezone.utc)
    items_processed = 0
    error_msg = None
    success = False
    
    logger.info(f"[SCRIPT] Starting: {script.name}")
    
    try:
        # Run the script task
        result = script.task()
        if inspect.isawaitable(result):
            task_result = await result
        else:
            task_result = result
        
        # Try to extract items_processed from result if returned
        if isinstance(task_result, dict):
            items_processed = task_result.get('items_processed', 0)
        elif isinstance(task_result, int):
            items_processed = task_result
        
        success = True
        script.last_run = datetime.now(timezone.utc)
        
    except Exception as e:
        logger.exception(f"[SCRIPT] Failed: {script.name}")
        error_msg = str(e)
        success = False
    
    completed_at = datetime.now(timezone.utc)
    duration = (completed_at - started_at).total_seconds()
    
    result = ScriptResult(
        success=success,
        script_name=script.name,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration,
        items_processed=items_processed,
        error=error_msg,
    )
    
    logger.info(result.summary)
    
    return result


def _create_job_wrapper(script: ScriptDefinition):
    """Create a synchronous wrapper for async script execution."""
    async def wrapper():
        await run_script(script)
    return wrapper


def schedule_script(script: ScriptDefinition, scheduler: Optional[AsyncIOScheduler] = None) -> str:
    """
    Schedule a script with the APScheduler.
    
    Args:
        script: Script definition to schedule
        scheduler: Optional scheduler instance (uses global if not provided)
        
    Returns:
        Job ID
    """
    sched = scheduler or get_scheduler()
    
    # Parse cron schedule
    parts = script.schedule.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron schedule '{script.schedule}' for script '{script.name}'")
    
    minute, hour, day, month, day_of_week = parts
    
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
    
    job = sched.add_job(
        _create_job_wrapper(script),
        trigger=trigger,
        id=script.name,
        name=script.description,
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )
    
    logger.debug(f"Scheduled script '{script.name}' with schedule '{script.schedule}'")
    
    return job.id


def start_runner(scripts: Optional[list[ScriptDefinition]] = None) -> None:
    """
    Start the APScheduler with all active scripts.
    
    Args:
        scripts: Optional list of scripts to schedule (uses registry if not provided)
    """
    global _is_running
    
    if _is_running:
        logger.warning("[RUNNER] Already running, ignoring start request")
        return
    
    scheduler = get_scheduler()
    
    # Get scripts from registry if not provided
    if scripts is None:
        from backend.src.scripts import get_active_scripts
        scripts = get_active_scripts()
    
    # Schedule all active scripts
    scheduled_count = 0
    for script in scripts:
        if script.status == "active":
            schedule_script(script, scheduler)
            scheduled_count += 1
    
    # Get the current event loop (we're called from async context in FastAPI lifespan)
    try:
        loop = asyncio.get_running_loop()
        logger.debug("[RUNNER] Using existing event loop")
    except RuntimeError:
        # No running loop - create one (for standalone usage)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug("[RUNNER] Created new event loop")
    
    # Start the scheduler with the event loop
    scheduler.start()
    _is_running = True
    
    logger.info(
        f"[RUNNER] Started APScheduler with {scheduled_count} active scripts:\n" +
        "\n".join(f"  - {s.name}: {s.schedule}" for s in scripts if s.status == "active")
    )


def stop_runner() -> None:
    """Stop the APScheduler gracefully."""
    global _is_running, _scheduler
    
    if not _is_running:
        logger.debug("[RUNNER] Not running, ignoring stop request")
        return
    
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
    
    _is_running = False
    logger.info("[RUNNER] Stopped APScheduler")


def is_running() -> bool:
    """Check if the runner is currently active."""
    return _is_running


async def run_all_once(scripts: Optional[list[ScriptDefinition]] = None) -> Dict[str, ScriptResult]:
    """
    Run all active scripts once immediately.
    
    Args:
        scripts: Optional list of scripts (uses registry if not provided)
        
    Returns:
        Dict mapping script name to result
    """
    if scripts is None:
        from backend.src.scripts import get_active_scripts
        scripts = get_active_scripts()
    
    results = {}
    failures = []
    
    for script in scripts:
        if script.status != "active":
            logger.info(f"[RUNNER] Skipping inactive script: {script.name}")
            continue
        
        result = await run_script(script)
        results[script.name] = result
        
        if not result.success:
            failures.append(script.name)
    
    if failures:
        logger.warning(f"[RUNNER] {len(failures)} script(s) failed: {', '.join(failures)}")
    else:
        logger.info(f"[RUNNER] All {len(results)} script(s) completed successfully")
    
    return results


async def _main_async():
    """Main entry point for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run scheduled scripts")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run all active scripts once and exit"
    )
    parser.add_argument(
        "--script",
        type=str,
        help="Run a specific script by name"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Start the scheduler and run continuously"
    )
    
    args = parser.parse_args()
    
    from backend.src.scripts import get_active_scripts, get_all_scripts
    
    if args.script:
        # Run specific script
        all_scripts = get_all_scripts()
        script = next((s for s in all_scripts if s.name == args.script), None)
        if not script:
            logger.error(f"Script not found: {args.script}")
            return
        await run_script(script)
        
    elif args.run_once:
        # Run all active scripts once
        await run_all_once()
        
    elif args.daemon:
        # Start scheduler daemon
        start_runner()
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            stop_runner()
    else:
        # Default: list scripts
        scripts = get_all_scripts()
        print(f"\nRegistered scripts ({len(scripts)} total):\n")
        for script in scripts:
            status_icon = "✅" if script.status == "active" else "⏸️"
            print(f"  {status_icon} {script.name}")
            print(f"      Schedule: {script.schedule}")
            print(f"      {script.description}\n")


def main():
    """Entry point for command line."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
