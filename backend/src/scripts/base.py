"""
Base classes and types for the scripts system.

Provides ScriptDefinition for registering scheduled tasks.
"""

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Optional
from datetime import datetime

# Script status type
ScriptStatus = Literal["active", "inactive"]

# Script runner function type
ScriptRunner = Callable[[], Awaitable[None]]


@dataclass
class ScriptDefinition:
    """
    Configuration for a scheduled script.
    
    Attributes:
        name: Unique identifier for the script (used in crontab comments)
        description: Human-readable description shown in logs
        schedule: Cron schedule in crontab format (e.g., "0 0 * * *" for daily at midnight)
        task: Async function that executes the script logic
        module_path: Full Python module path for standalone execution
        status: Whether the script is active or inactive
        last_run: Timestamp of last successful run (set at runtime)
        timeout_seconds: Maximum execution time before script is killed
        
    Schedule Examples:
        "0 0 * * *"    - Daily at midnight
        "0 0 1 * *"    - Monthly on the 1st at midnight
        "*/30 * * * *" - Every 30 minutes
        "0 */2 * * *"  - Every 2 hours
    """
    name: str
    description: str
    schedule: str
    task: ScriptRunner
    module_path: str
    status: ScriptStatus = "active"
    last_run: Optional[datetime] = field(default=None, repr=False)
    timeout_seconds: int = 3600  # 1 hour default
    
    def __hash__(self):
        """Allow scripts to be used in sets."""
        return hash(self.name)
    
    def __eq__(self, other):
        """Compare scripts by name."""
        if isinstance(other, ScriptDefinition):
            return self.name == other.name
        return False
    
    @property
    def cron_command(self) -> str:
        """Generate shell command for crontab entry."""
        import sys
        return f"{sys.executable} -m {self.module_path}"


@dataclass
class ScriptResult:
    """
    Result of running a script.
    
    Attributes:
        success: Whether the script completed successfully
        script_name: Name of the script that was run
        started_at: When the script started
        completed_at: When the script completed
        duration_seconds: How long the script took
        message: Optional message about the result
        error: Optional error message if failed
        items_processed: Number of items processed (for batch scripts)
    """
    success: bool
    script_name: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    message: Optional[str] = None
    error: Optional[str] = None
    items_processed: int = 0
    
    @property
    def summary(self) -> str:
        """Generate a one-line summary."""
        status = "✅" if self.success else "❌"
        msg = f"{status} {self.script_name}: "
        if self.success:
            msg += f"Processed {self.items_processed} items in {self.duration_seconds:.2f}s"
        else:
            msg += f"Failed - {self.error}"
        return msg
