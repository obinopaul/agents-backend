"""
Cron Manager - System crontab integration.

This module provides a wrapper around python-crontab for installing,
removing, and managing cron jobs at the operating system level.

Based on IIAgent's scripts/cron_manager.py.

Usage:
    from backend.src.scripts.cron_manager import CronManager, CronJobDefinition
    
    manager = CronManager()
    
    # Install a single job
    job = CronJobDefinition(
        name="my-job",
        schedule="0 0 * * *",
        command="python -m my_module"
    )
    manager.install(job)
    
    # List installed jobs
    for job in manager.list_jobs():
        print(job)
    
    # Remove a job
    manager.remove("my-job")
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Iterable, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CronJobDefinition:
    """
    Configuration container for a cron job.
    
    Attributes:
        name: Unique identifier (stored as crontab comment)
        schedule: Cron schedule (e.g., "0 0 * * *" for daily midnight)
        command: Shell command to execute
    """
    name: str
    schedule: str
    command: str

    def render_command(self) -> str:
        """Return the shell command for the cron entry."""
        return self.command


class CronManager:
    """
    Thin wrapper around python-crontab to manage scheduled scripts.
    
    Provides methods to install, remove, and list cron jobs.
    Jobs are identified by their name (stored as crontab comments).
    
    Example:
        manager = CronManager()
        manager.install(job=CronJobDefinition(...))
        manager.sync(jobs=[...])  # Replace all managed jobs
    """

    def __init__(self, *, user: bool = True, tab=None) -> None:
        """
        Initialize the cron manager.
        
        Args:
            user: If True, use current user's crontab
            tab: Optional CronTab instance (for testing)
        """
        self._cron = tab
        self._user = user
        self._initialized = False

    def _ensure_cron(self):
        """Lazy initialization of CronTab to handle import errors gracefully."""
        if self._initialized:
            return
        
        if self._cron is None:
            try:
                from crontab import CronTab
                self._cron = CronTab(user=self._user)
                self._initialized = True
            except ImportError:
                logger.error(
                    "python-crontab not installed. "
                    "Install with: pip install python-crontab"
                )
                raise RuntimeError(
                    "python-crontab required for OS crontab management. "
                    "Install with: pip install python-crontab"
                )
            except Exception as e:
                logger.error(f"Failed to initialize CronTab: {e}")
                raise

    def install(self, *, job: CronJobDefinition, dry_run: bool = False) -> None:
        """
        Create or update a cron job based on its name.
        
        If a job with the same name exists, it will be replaced.
        
        Args:
            job: CronJobDefinition to install
            dry_run: If True, log what would happen but don't write
        """
        self._ensure_cron()
        
        command = job.render_command()
        
        # Remove any existing jobs with the same name
        existing = [scheduled for scheduled in self._cron if scheduled.comment == job.name]
        for scheduled in existing:
            self._cron.remove(scheduled)

        # Create new job
        scheduled_job = self._cron.new(command=command, comment=job.name)
        scheduled_job.setall(job.schedule)

        if dry_run:
            logger.info(f"[DRY-RUN] Would install cron job: {scheduled_job}")
            return

        self._cron.write()
        logger.info(f"Installed cron job '{job.name}' with schedule '{job.schedule}'")

    def remove(self, *, name: str, dry_run: bool = False) -> bool:
        """
        Remove a cron job by name.
        
        Args:
            name: Name of the job to remove
            dry_run: If True, log what would happen but don't write
            
        Returns:
            True if a job was removed, False otherwise
        """
        self._ensure_cron()
        
        removed = False
        for scheduled in list(self._cron):
            if scheduled.comment == name:
                self._cron.remove(scheduled)
                removed = True

        if dry_run:
            if removed:
                logger.info(f"[DRY-RUN] Would remove cron job '{name}'")
            return removed

        if removed:
            self._cron.write()
            logger.info(f"Removed cron job '{name}'")
        else:
            logger.info(f"No cron job named '{name}' found")

        return removed

    def iter_jobs(self) -> Iterator[str]:
        """Yield cron job string representations."""
        self._ensure_cron()
        yield from (str(entry) for entry in self._cron)

    def list_jobs(self) -> list[str]:
        """Return cron job string representations."""
        return list(self.iter_jobs())

    def sync(self, *, jobs: Iterable[CronJobDefinition], dry_run: bool = False) -> None:
        """
        Replace managed cron jobs with provided definitions.
        
        This removes all jobs matching the provided names, then installs
        the new definitions.
        
        Args:
            jobs: Iterable of CronJobDefinition to install
            dry_run: If True, log what would happen but don't write
        """
        self._ensure_cron()
        
        jobs_list = list(jobs)
        managed_names = {job.name for job in jobs_list}
        
        # Remove existing managed jobs
        for existing in list(self._cron):
            if existing.comment in managed_names:
                self._cron.remove(existing)

        # Install new jobs
        for job in jobs_list:
            scheduled_job = self._cron.new(command=job.render_command(), comment=job.name)
            scheduled_job.setall(job.schedule)

        if dry_run:
            for entry in self._cron:
                logger.info(f"[DRY-RUN] Cron job: {entry}")
            return

        self._cron.write()
        logger.info(f"Synchronized {len(managed_names)} cron job(s)")

    def remove_all_managed(self, *, prefix: str = "agents-backend-", dry_run: bool = False) -> int:
        """
        Remove all cron jobs with names starting with prefix.
        
        Args:
            prefix: Name prefix to match
            dry_run: If True, log what would happen but don't write
            
        Returns:
            Number of jobs removed
        """
        self._ensure_cron()
        
        removed_count = 0
        for scheduled in list(self._cron):
            if scheduled.comment and scheduled.comment.startswith(prefix):
                self._cron.remove(scheduled)
                removed_count += 1
                if dry_run:
                    logger.info(f"[DRY-RUN] Would remove: {scheduled}")

        if not dry_run and removed_count:
            self._cron.write()
            logger.info(f"Removed {removed_count} cron job(s) with prefix '{prefix}'")

        return removed_count


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parents[3]


def build_script_command(module_path: str) -> str:
    """
    Build the shell command to run a script module.
    
    Args:
        module_path: Full Python module path (e.g., "backend.src.scripts.billing.refresh")
        
    Returns:
        Shell command string
    """
    python_executable = sys.executable
    repo_root = get_project_root()
    return f"cd {repo_root} && {python_executable} -m {module_path}"


__all__ = ["CronJobDefinition", "CronManager", "build_script_command"]
