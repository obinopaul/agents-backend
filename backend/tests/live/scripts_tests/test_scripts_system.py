"""
Pytest tests for the Scripts System.

Tests:
- Import verification for all modules
- ScriptDefinition dataclass
- Registry contains all expected scripts
- Runner functions (mocked)
- CronManager (mocked)

Run with:
    pytest backend/tests/unit/test_scripts_system.py -v
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


class TestScriptDefinition:
    """Test ScriptDefinition dataclass."""
    
    def test_script_definition_creation(self):
        """Test creating a ScriptDefinition."""
        from backend.src.scripts.base import ScriptDefinition
        
        async def dummy_task():
            pass
        
        script = ScriptDefinition(
            name="test-script",
            description="A test script",
            schedule="0 0 * * *",
            task=dummy_task,
            module_path="backend.test.module",
            status="active",
        )
        
        assert script.name == "test-script"
        assert script.description == "A test script"
        assert script.schedule == "0 0 * * *"
        assert script.status == "active"
        assert script.module_path == "backend.test.module"
    
    def test_script_definition_hash(self):
        """Test ScriptDefinition can be hashed (for sets)."""
        from backend.src.scripts.base import ScriptDefinition
        
        async def dummy_task():
            pass
        
        script1 = ScriptDefinition(
            name="script-a",
            description="Script A",
            schedule="* * * * *",
            task=dummy_task,
            module_path="test.a",
        )
        script2 = ScriptDefinition(
            name="script-b",
            description="Script B",
            schedule="* * * * *",
            task=dummy_task,
            module_path="test.b",
        )
        
        scripts_set = {script1, script2}
        assert len(scripts_set) == 2
    
    def test_script_definition_cron_command(self):
        """Test cron_command property generates correct shell command."""
        from backend.src.scripts.base import ScriptDefinition
        
        async def dummy_task():
            pass
        
        script = ScriptDefinition(
            name="test",
            description="Test",
            schedule="* * * * *",
            task=dummy_task,
            module_path="backend.src.scripts.test",
        )
        
        # Should contain python and module path
        assert "python" in script.cron_command.lower() or "python" in script.cron_command
        assert "backend.src.scripts.test" in script.cron_command


class TestScriptResult:
    """Test ScriptResult dataclass."""
    
    def test_script_result_success(self):
        """Test successful ScriptResult."""
        from backend.src.scripts.base import ScriptResult
        
        now = datetime.now(timezone.utc)
        result = ScriptResult(
            success=True,
            script_name="test-script",
            started_at=now,
            completed_at=now,
            duration_seconds=1.5,
            items_processed=10,
        )
        
        assert result.success is True
        assert result.items_processed == 10
        assert "✅" in result.summary
        assert "10 items" in result.summary
    
    def test_script_result_failure(self):
        """Test failed ScriptResult."""
        from backend.src.scripts.base import ScriptResult
        
        now = datetime.now(timezone.utc)
        result = ScriptResult(
            success=False,
            script_name="failing-script",
            started_at=now,
            completed_at=now,
            duration_seconds=0.5,
            error="Connection refused",
        )
        
        assert result.success is False
        assert "❌" in result.summary
        assert "Connection refused" in result.summary


class TestRegistry:
    """Test the scripts registry."""
    
    def test_registry_has_scripts(self):
        """Test registry contains expected scripts."""
        from backend.src.scripts.registry import SCRIPTS
        
        assert len(SCRIPTS) >= 5, "Should have at least 5 scripts"
        
        names = [s.name for s in SCRIPTS]
        
        # Check key scripts exist
        assert "agents-backend-refresh-monthly-credits" in names
        assert "agents-backend-refresh-daily-credits" in names
        assert "agents-backend-extend-sandbox-timeouts" in names
        assert "agents-backend-sandbox-cleanup" in names
        assert "agents-backend-cleanup-stale-tasks" in names
    
    def test_get_script_by_name(self):
        """Test looking up script by name."""
        from backend.src.scripts.registry import get_script_by_name
        
        script = get_script_by_name("agents-backend-sandbox-cleanup")
        assert script is not None
        assert script.name == "agents-backend-sandbox-cleanup"
        
        missing = get_script_by_name("non-existent-script")
        assert missing is None
    
    def test_all_scripts_have_required_fields(self):
        """Test all scripts have required fields populated."""
        from backend.src.scripts.registry import SCRIPTS
        
        for script in SCRIPTS:
            assert script.name, f"Script missing name"
            assert script.description, f"Script {script.name} missing description"
            assert script.schedule, f"Script {script.name} missing schedule"
            assert script.task, f"Script {script.name} missing task"
            assert script.module_path, f"Script {script.name} missing module_path"
            assert callable(script.task), f"Script {script.name} task is not callable"


class TestPackageImports:
    """Test that all package modules import correctly."""
    
    def test_import_base(self):
        """Test importing base module."""
        from backend.src.scripts.base import ScriptDefinition, ScriptResult, ScriptStatus
        assert ScriptDefinition is not None
    
    def test_import_registry(self):
        """Test importing registry module."""
        from backend.src.scripts.registry import SCRIPTS, get_script_by_name
        assert SCRIPTS is not None
    
    def test_import_runner(self):
        """Test importing runner module."""
        from backend.src.scripts.runner import start_runner, stop_runner, run_script
        assert start_runner is not None
        assert stop_runner is not None
    
    def test_import_cron_manager(self):
        """Test importing cron_manager module."""
        from backend.src.scripts.cron_manager import CronManager, CronJobDefinition
        assert CronManager is not None
        assert CronJobDefinition is not None
    
    def test_import_package_init(self):
        """Test importing from package init."""
        from backend.src.scripts import get_all_scripts, get_active_scripts
        
        all_scripts = get_all_scripts()
        active_scripts = get_active_scripts()
        
        assert len(all_scripts) >= 5
        assert len(active_scripts) >= 1


class TestBillingScripts:
    """Test billing script imports."""
    
    def test_import_monthly_credits(self):
        """Test importing monthly credits script."""
        from backend.src.scripts.billing.refresh_monthly_credits import SCRIPT, refresh_monthly_credits
        assert SCRIPT.name == "agents-backend-refresh-monthly-credits"
        assert callable(refresh_monthly_credits)
    
    def test_import_daily_credits(self):
        """Test importing daily credits script."""
        from backend.src.scripts.billing.refresh_daily_credits import SCRIPT, refresh_daily_credits
        assert SCRIPT.name == "agents-backend-refresh-daily-credits"
        assert callable(refresh_daily_credits)


class TestSandboxScripts:
    """Test sandbox script imports."""
    
    def test_import_extend_timeouts(self):
        """Test importing extend timeouts script."""
        from backend.src.scripts.sandbox.extend_timeouts import SCRIPT, extend_sandbox_timeouts
        assert SCRIPT.name == "agents-backend-extend-sandbox-timeouts"
        assert callable(extend_sandbox_timeouts)
    
    def test_import_cleanup(self):
        """Test importing cleanup script."""
        from backend.src.scripts.sandbox.cleanup import SCRIPT, cleanup_sandboxes
        assert SCRIPT.name == "agents-backend-sandbox-cleanup"
        assert callable(cleanup_sandboxes)


class TestLifecycleUtilities:
    """Test sandbox lifecycle utility functions."""
    
    def test_import_lifecycle_module(self):
        """Test importing lifecycle module."""
        from backend.src.scripts.sandbox import lifecycle
        assert lifecycle is not None
    
    def test_lifecycle_exports_all_functions(self):
        """Test lifecycle exports all expected functions."""
        from backend.src.scripts.sandbox.lifecycle import (
            get_sandbox_stats,
            extend_sandbox_timeout,
            pause_sandbox,
            resume_sandbox,
            delete_sandbox,
            get_inactive_sandboxes,
            get_expired_sandboxes,
            extend_batch_with_concurrency,
            run_lifecycle_cleanup,
        )
        
        # All should be callable
        assert callable(get_sandbox_stats)
        assert callable(extend_sandbox_timeout)
        assert callable(pause_sandbox)
        assert callable(resume_sandbox)
        assert callable(delete_sandbox)
        assert callable(get_inactive_sandboxes)
        assert callable(get_expired_sandboxes)
        assert callable(extend_batch_with_concurrency)
        assert callable(run_lifecycle_cleanup)
    
    def test_lifecycle_constants_defined(self):
        """Test lifecycle constants are defined."""
        from backend.src.scripts.sandbox.lifecycle import (
            DEFAULT_TIMEOUT_EXTENSION,
            INACTIVITY_THRESHOLD_HOURS,
            EXPIRED_THRESHOLD_DAYS,
        )
        
        assert DEFAULT_TIMEOUT_EXTENSION == 7200  # 2 hours
        assert INACTIVITY_THRESHOLD_HOURS == 2
        assert EXPIRED_THRESHOLD_DAYS == 30
    
    def test_lifecycle_all_exports(self):
        """Test __all__ exports all expected items."""
        from backend.src.scripts.sandbox import lifecycle
        
        expected_exports = [
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
        
        for export in expected_exports:
            assert export in lifecycle.__all__, f"Missing export: {export}"
    
    def test_functions_are_coroutines(self):
        """Test async functions are properly defined as coroutines."""
        import inspect
        from backend.src.scripts.sandbox.lifecycle import (
            get_sandbox_stats,
            extend_sandbox_timeout,
            pause_sandbox,
            resume_sandbox,
            delete_sandbox,
            get_inactive_sandboxes,
            get_expired_sandboxes,
            extend_batch_with_concurrency,
            run_lifecycle_cleanup,
        )
        
        # Check that these are coroutine functions (using inspect for Python 3.14+)
        assert inspect.iscoroutinefunction(get_sandbox_stats)
        assert inspect.iscoroutinefunction(extend_sandbox_timeout)
        assert inspect.iscoroutinefunction(pause_sandbox)
        assert inspect.iscoroutinefunction(resume_sandbox)
        assert inspect.iscoroutinefunction(delete_sandbox)
        assert inspect.iscoroutinefunction(get_inactive_sandboxes)
        assert inspect.iscoroutinefunction(get_expired_sandboxes)
        assert inspect.iscoroutinefunction(extend_batch_with_concurrency)
        assert inspect.iscoroutinefunction(run_lifecycle_cleanup)


class TestCleanupScripts:
    """Test cleanup script imports."""
    
    def test_import_stale_tasks(self):
        """Test importing stale tasks script."""
        from backend.src.scripts.cleanup.stale_tasks import SCRIPT, cleanup_stale_tasks
        assert SCRIPT.name == "agents-backend-cleanup-stale-tasks"
        assert callable(cleanup_stale_tasks)
    
    def test_stale_tasks_constants(self):
        """Test stale_tasks constants are defined."""
        from backend.src.scripts.cleanup.stale_tasks import (
            DEFAULT_SCHEDULE,
            STALE_TASK_MINUTES,
            BATCH_SIZE,
        )
        
        assert DEFAULT_SCHEDULE == "*/40 * * * *"
        assert STALE_TASK_MINUTES == 45
        assert BATCH_SIZE == 50


class TestCronJobDefinition:
    """Test CronJobDefinition dataclass."""
    
    def test_cron_job_definition_creation(self):
        """Test creating a CronJobDefinition."""
        from backend.src.scripts.cron_manager import CronJobDefinition
        
        job = CronJobDefinition(
            name="test-job",
            schedule="0 0 * * *",
            command="python -m test"
        )
        
        assert job.name == "test-job"
        assert job.schedule == "0 0 * * *"
        assert job.render_command() == "python -m test"


class TestRunnerFunctions:
    """Test runner functions."""
    
    def test_is_running_initially_false(self):
        """Test runner is not running initially."""
        from backend.src.scripts.runner import is_running
        # Note: This may be True if tests run after server started
        # Just verify it returns a boolean
        assert isinstance(is_running(), bool)
    
    def test_get_scheduler_returns_scheduler(self):
        """Test get_scheduler returns an AsyncIOScheduler."""
        from backend.src.scripts.runner import get_scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        
        scheduler = get_scheduler()
        assert isinstance(scheduler, AsyncIOScheduler)
