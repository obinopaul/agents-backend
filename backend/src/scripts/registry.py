"""
Central Script Registry

This module collects all ScriptDefinition objects from the scripts package.
It's imported by __init__.py, runner.py, and the CLI entry point.

Adding a new script:
1. Create your script in the appropriate subdirectory (billing/, sandbox/, cleanup/)
2. Define a SCRIPT = ScriptDefinition(...) in the script file
3. Import and add it to the SCRIPTS list below
"""

from __future__ import annotations

from backend.src.scripts.base import ScriptDefinition

# Import all script definitions
from backend.src.scripts.billing.refresh_monthly_credits import SCRIPT as REFRESH_MONTHLY_CREDITS
from backend.src.scripts.billing.refresh_daily_credits import SCRIPT as REFRESH_DAILY_CREDITS
from backend.src.scripts.sandbox.extend_timeouts import SCRIPT as EXTEND_SANDBOX_TIMEOUTS
from backend.src.scripts.sandbox.cleanup import SCRIPT as SANDBOX_CLEANUP
from backend.src.scripts.cleanup.stale_tasks import SCRIPT as CLEANUP_STALE_TASKS

# Central registry of all scheduled scripts
SCRIPTS: list[ScriptDefinition] = [
    # ==========================================================================
    # Billing Scripts
    # ==========================================================================
    REFRESH_MONTHLY_CREDITS,   # Daily check for monthly credit refresh
    REFRESH_DAILY_CREDITS,     # Hourly check for free tier daily credits
    
    # ==========================================================================
    # Sandbox Scripts
    # ==========================================================================
    EXTEND_SANDBOX_TIMEOUTS,   # Every 30 min - extend active sandbox timeouts
    SANDBOX_CLEANUP,           # Every 2h - pause inactive, delete expired
    
    # ==========================================================================
    # Cleanup Scripts
    # ==========================================================================
    CLEANUP_STALE_TASKS,       # Every 40 min - mark stale agent tasks
]


def get_script_by_name(name: str) -> ScriptDefinition | None:
    """Look up a script by its name."""
    return next((s for s in SCRIPTS if s.name == name), None)


def list_scripts() -> None:
    """Print all registered scripts to stdout."""
    print(f"\n{'='*70}")
    print("REGISTERED SCRIPTS")
    print(f"{'='*70}\n")
    
    for script in SCRIPTS:
        status_icon = "✅ ACTIVE" if script.status == "active" else "⏸️  INACTIVE"
        print(f"{status_icon}: {script.name}")
        print(f"  Schedule:    {script.schedule}")
        print(f"  Description: {script.description}")
        print(f"  Module:      {script.module_path}")
        print()


__all__ = [
    "SCRIPTS",
    "get_script_by_name",
    "list_scripts",
]
