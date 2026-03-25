"""
Scripts System Main Entry Point

This module provides the CLI interface for managing scheduled scripts.

Usage:
    # List all scripts
    python -m backend.src.scripts
    
    # Run all active scripts once
    python -m backend.src.scripts --run-all
    
    # Run a specific script
    python -m backend.src.scripts --run agents-backend-refresh-monthly-credits
    
    # Install all active scripts to system crontab (Linux only)
    python -m backend.src.scripts --install-cron
    
    # Remove all installed cron jobs
    python -m backend.src.scripts --remove-cron
    
    # Start APScheduler daemon (for Docker/development)
    python -m backend.src.scripts --daemon
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="Agents Backend Scheduled Scripts Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.src.scripts                    # List all scripts
  python -m backend.src.scripts --run-all          # Run all active scripts once
  python -m backend.src.scripts --run SCRIPT_NAME  # Run specific script
  python -m backend.src.scripts --install-cron     # Install to system crontab
  python -m backend.src.scripts --daemon           # Start APScheduler daemon
"""
    )
    
    group = parser.add_mutually_exclusive_group()
    
    group.add_argument(
        "--run-all",
        action="store_true",
        help="Run all active scripts once and exit"
    )
    
    group.add_argument(
        "--run",
        type=str,
        metavar="SCRIPT_NAME",
        help="Run a specific script by name"
    )
    
    group.add_argument(
        "--install-cron",
        action="store_true",
        help="Install all active scripts to system crontab (Linux only)"
    )
    
    group.add_argument(
        "--remove-cron",
        action="store_true",
        help="Remove all installed cron jobs"
    )
    
    group.add_argument(
        "--daemon",
        action="store_true",
        help="Start APScheduler and run continuously"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser


async def run_all_scripts() -> int:
    """Run all active scripts once."""
    from backend.src.scripts.runner import run_all_once
    
    results = await run_all_once()
    failures = sum(1 for r in results.values() if not r.success)
    
    return 1 if failures else 0


async def run_script(name: str) -> int:
    """Run a specific script."""
    from backend.src.scripts.registry import get_script_by_name
    from backend.src.scripts.runner import run_script as execute_script
    
    script = get_script_by_name(name)
    if not script:
        logger.error(f"Script not found: {name}")
        return 1
    
    result = await execute_script(script)
    return 0 if result.success else 1


def install_cron_jobs(dry_run: bool = False) -> int:
    """Install all active scripts to system crontab."""
    from backend.src.scripts import get_active_scripts
    from backend.src.scripts.cron_manager import CronManager, CronJobDefinition, build_script_command
    
    manager = CronManager()
    scripts = get_active_scripts()
    
    jobs = [
        CronJobDefinition(
            name=script.name,
            schedule=script.schedule,
            command=build_script_command(script.module_path)
        )
        for script in scripts
    ]
    
    if dry_run:
        print(f"\n[DRY-RUN] Would install {len(jobs)} cron jobs:\n")
        for job in jobs:
            print(f"  {job.schedule}  {job.command}  # {job.name}")
        return 0
    
    manager.sync(jobs=jobs)
    print(f"✅ Installed {len(jobs)} cron jobs to system crontab")
    return 0


def remove_cron_jobs(dry_run: bool = False) -> int:
    """Remove all installed cron jobs."""
    from backend.src.scripts.cron_manager import CronManager
    
    manager = CronManager()
    removed = manager.remove_all_managed(prefix="agents-backend-", dry_run=dry_run)
    
    if not dry_run:
        print(f"✅ Removed {removed} cron jobs from system crontab")
    else:
        print(f"[DRY-RUN] Would remove {removed} cron jobs")
    
    return 0


async def run_daemon() -> None:
    """Start APScheduler and run continuously."""
    from backend.src.scripts.runner import start_runner, stop_runner
    
    print("Starting APScheduler daemon (Ctrl+C to stop)...")
    start_runner()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping daemon...")
        stop_runner()


def list_scripts() -> None:
    """List all registered scripts."""
    from backend.src.scripts.registry import list_scripts as show_scripts
    show_scripts()


async def async_main(args: argparse.Namespace) -> int:
    """Async main function."""
    if args.run_all:
        return await run_all_scripts()
    
    elif args.run:
        return await run_script(args.run)
    
    elif args.daemon:
        await run_daemon()
        return 0
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handle synchronous commands
    if args.install_cron:
        return install_cron_jobs(dry_run=args.dry_run)
    
    if args.remove_cron:
        return remove_cron_jobs(dry_run=args.dry_run)
    
    # Handle async commands
    if args.run_all or args.run or args.daemon:
        return asyncio.run(async_main(args))
    
    # Default: list scripts
    list_scripts()
    return 0


if __name__ == "__main__":
    sys.exit(main())
