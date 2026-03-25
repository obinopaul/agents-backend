"""
Sandbox Lifecycle Utilities

Provides utility functions for sandbox lifecycle management:
- get_sandbox_stats() - Get counts of running/paused/total
- extend_sandbox_timeout() - Extend single sandbox timeout
- pause_sandbox() - Pause a sandbox
- resume_sandbox() - Resume a paused sandbox
- delete_sandbox() - Delete a sandbox

These utilities can be called from:
- Scheduled scripts (cleanup.py, extend_timeouts.py)
- API endpoints
- Tests
- Interactive scripts

Architecture:
    User Request -> sandbox_service.get_or_create_sandbox()
                         |
                         v (creates with default timeout)
                    E2B Sandbox (running)
                         |
                         | (every 30 min)
                         v
                    extend_sandbox_timeout() 
                         |
                         | (after 2h inactivity)
                         v
                    pause_sandbox() -> (paused state preserved)
                         |
                         | (user returns)
                         v
                    resume_sandbox() -> (running again)
                         |
                         | (after 30 days paused)
                         v
                    delete_sandbox() -> (data deleted)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy import select

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT_EXTENSION = 7200  # 2 hours
INACTIVITY_THRESHOLD_HOURS = 2   # Pause after 2h inactivity 
EXPIRED_THRESHOLD_DAYS = 30      # Delete after 30 days paused


async def get_sandbox_stats() -> Dict[str, int]:
    """
    Get statistics about current sandbox states.
    
    Returns:
        Dict with counts: running, paused, other, total
    """
    from backend.src.sandbox.sandbox_server.db.manager import get_db
    from backend.src.sandbox.sandbox_server.db.model import Sandbox
    
    async with get_db() as db:
        # Count running
        running_result = await db.execute(
            select(Sandbox).where(Sandbox.status == "running")
        )
        running_count = len(running_result.scalars().all())
        
        # Count paused
        paused_result = await db.execute(
            select(Sandbox).where(Sandbox.status == "paused")
        )
        paused_count = len(paused_result.scalars().all())
        
        # Count total
        total_result = await db.execute(select(Sandbox))
        total_count = len(total_result.scalars().all())
    
    return {
        "running": running_count,
        "paused": paused_count,
        "other": total_count - running_count - paused_count,
        "total": total_count,
    }


async def extend_sandbox_timeout(
    sandbox_id: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_EXTENSION
) -> bool:
    """
    Extend timeout for a specific sandbox.
    
    Args:
        sandbox_id: The sandbox ID to extend
        timeout_seconds: How long to extend the timeout (default 2 hours)
        
    Returns:
        True if successful, False otherwise
    """
    from backend.src.sandbox.sandbox_server.db.manager import Sandboxes
    from backend.src.services.sandbox_service import sandbox_service
    
    try:
        if sandbox_service._controller is None:
            await sandbox_service.initialize()
        
        await sandbox_service.controller.schedule_timeout(sandbox_id, timeout_seconds)
        await Sandboxes.update_last_activity(sandbox_id)
        
        logger.info(f"Extended timeout for sandbox {sandbox_id} by {timeout_seconds}s")
        return True
    except Exception as e:
        logger.error(f"Failed to extend sandbox {sandbox_id}: {e}")
        return False


async def pause_sandbox(sandbox_id: str, reason: str = "inactivity") -> bool:
    """
    Pause a sandbox to preserve its state.
    
    Args:
        sandbox_id: The sandbox ID to pause
        reason: Reason for pausing (for logging)
        
    Returns:
        True if successful, False otherwise
    """
    from backend.src.services.sandbox_service import sandbox_service
    
    try:
        if sandbox_service._controller is None:
            await sandbox_service.initialize()
        
        await sandbox_service.controller.pause_sandbox(sandbox_id, reason)
        
        logger.info(f"Paused sandbox {sandbox_id} (reason: {reason})")
        return True
    except Exception as e:
        logger.error(f"Failed to pause sandbox {sandbox_id}: {e}")
        return False


async def resume_sandbox(sandbox_id: str) -> bool:
    """
    Resume a paused sandbox.
    
    Args:
        sandbox_id: The sandbox ID to resume
        
    Returns:
        True if successful, False otherwise
    """
    from backend.src.services.sandbox_service import sandbox_service
    
    try:
        if sandbox_service._controller is None:
            await sandbox_service.initialize()
        
        await sandbox_service.controller.connect(sandbox_id)
        
        logger.info(f"Resumed sandbox {sandbox_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to resume sandbox {sandbox_id}: {e}")
        return False


async def delete_sandbox(sandbox_id: str) -> bool:
    """
    Delete a sandbox and its data.
    
    Args:
        sandbox_id: The sandbox ID to delete
        
    Returns:
        True if successful, False otherwise
    """
    from backend.src.services.sandbox_service import sandbox_service
    
    try:
        if sandbox_service._controller is None:
            await sandbox_service.initialize()
        
        await sandbox_service.controller.delete_sandbox(sandbox_id)
        
        logger.info(f"Deleted sandbox {sandbox_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete sandbox {sandbox_id}: {e}")
        return False


async def get_inactive_sandboxes(
    hours_threshold: int = INACTIVITY_THRESHOLD_HOURS
) -> List[Any]:
    """
    Get sandboxes that have been inactive longer than threshold.
    
    Args:
        hours_threshold: Hours of inactivity to consider inactive
        
    Returns:
        List of inactive sandbox records
    """
    from backend.src.sandbox.sandbox_server.db.manager import get_db
    from backend.src.sandbox.sandbox_server.db.model import Sandbox
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
    
    async with get_db() as db:
        result = await db.execute(
            select(Sandbox).where(
                Sandbox.status == "running",
                Sandbox.last_activity_at < cutoff
            )
        )
        return list(result.scalars().all())


async def get_expired_sandboxes(
    days_threshold: int = EXPIRED_THRESHOLD_DAYS
) -> List[Any]:
    """
    Get paused sandboxes that have exceeded expiration threshold.
    
    Args:
        days_threshold: Days paused after which to consider expired
        
    Returns:
        List of expired sandbox records
    """
    from backend.src.sandbox.sandbox_server.db.manager import get_db
    from backend.src.sandbox.sandbox_server.db.model import Sandbox
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
    
    async with get_db() as db:
        result = await db.execute(
            select(Sandbox).where(
                Sandbox.status == "paused",
                Sandbox.stopped_at < cutoff
            )
        )
        return list(result.scalars().all())


async def extend_batch_with_concurrency(
    sandbox_ids: List[str],
    timeout_seconds: int = DEFAULT_TIMEOUT_EXTENSION,
    batch_size: int = 10,
    delay_between_batches: float = 1.0
) -> Tuple[int, int]:
    """
    Extend timeouts for multiple sandboxes with batched concurrency.
    
    This mirrors the cron/ implementation with asyncio.gather for efficiency.
    
    Args:
        sandbox_ids: List of sandbox IDs to extend
        timeout_seconds: Timeout extension in seconds
        batch_size: How many to process concurrently
        delay_between_batches: Seconds to wait between batches
        
    Returns:
        Tuple of (success_count, failure_count)
    """
    total_success = 0
    total_failure = 0
    
    for i in range(0, len(sandbox_ids), batch_size):
        batch = sandbox_ids[i:i + batch_size]
        
        # Process batch concurrently
        tasks = [
            extend_sandbox_timeout(sid, timeout_seconds)
            for sid in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        failure_count = len(results) - success_count
        
        total_success += success_count
        total_failure += failure_count
        
        logger.info(f"Batch {i // batch_size + 1}: Success: {success_count}, Failure: {failure_count}")
        
        # Delay between batches to avoid overwhelming the system
        if i + batch_size < len(sandbox_ids):
            await asyncio.sleep(delay_between_batches)
    
    return total_success, total_failure


async def run_lifecycle_cleanup() -> Tuple[int, int]:
    """
    Run complete lifecycle cleanup.
    
    Pauses inactive sandboxes and deletes expired ones.
    
    Returns:
        Tuple of (paused_count, deleted_count)
    """
    paused_count = 0
    deleted_count = 0
    
    # Pause inactive sandboxes
    inactive = await get_inactive_sandboxes()
    for sandbox in inactive:
        if await pause_sandbox(sandbox.id):
            paused_count += 1
    
    # Delete expired sandboxes
    expired = await get_expired_sandboxes()
    for sandbox in expired:
        if await delete_sandbox(sandbox.id):
            deleted_count += 1
    
    logger.info(f"Lifecycle cleanup: {paused_count} paused, {deleted_count} deleted")
    return paused_count, deleted_count


__all__ = [
    "get_sandbox_stats",
    "extend_sandbox_timeout",
    "pause_sandbox",
    "resume_sandbox",
    "delete_sandbox",
    "get_inactive_sandboxes",
    "get_expired_sandboxes",
    "extend_batch_with_concurrency",
    "run_lifecycle_cleanup",
    "DEFAULT_TIMEOUT_EXTENSION",
    "INACTIVITY_THRESHOLD_HOURS",
    "EXPIRED_THRESHOLD_DAYS",
]
