"""
Scheduled Scripts System

This package provides a production-ready framework for running scheduled tasks.

Execution Modes:
1. APScheduler (in-process): Starts with FastAPI, good for Docker
2. OS Crontab: Uses python-crontab for production Linux VMs  
3. Standalone: Run individual scripts via `python -m`

Usage:
    # Run all active scripts once
    python -m backend.src.scripts --run-all
    
    # Install to system crontab (Linux only)
    python -m backend.src.scripts --install-cron
    
    # Run a specific script
    python -m backend.src.scripts.billing.refresh_monthly_credits
"""

from backend.src.scripts.base import ScriptDefinition, ScriptStatus

__all__ = [
    'ScriptDefinition',
    'ScriptStatus',
    'get_all_scripts',
    'get_active_scripts',
]


def get_all_scripts():
    """Get all registered scripts (imported lazily to avoid circular imports)."""
    from backend.src.scripts.registry import SCRIPTS
    return SCRIPTS


def get_active_scripts():
    """Get only active scripts."""
    return [s for s in get_all_scripts() if s.status == 'active']
