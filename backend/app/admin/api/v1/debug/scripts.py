"""
Debug endpoints for monitoring script scheduler status.

This module provides endpoints to check the APScheduler state
from within the running FastAPI process.

These endpoints help debug whether the scheduler started correctly
in the lifespan context.
"""

from fastapi import APIRouter
from datetime import datetime, timezone
from typing import Any

router = APIRouter(prefix="/debug/scripts", tags=["Debug - Scripts"])


@router.get("/status")
async def get_scripts_status() -> dict[str, Any]:
    """
    Get the current status of the scripts scheduler.
    
    This endpoint queries the actual scheduler state from within
    the running FastAPI process, allowing us to verify if the
    scheduler started correctly in the lifespan.
    """
    try:
        from backend.src.scripts.runner import is_running, get_scheduler, _is_running, _scheduler
        
        scheduler = get_scheduler() if _scheduler else None
        
        response = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runner": {
                "_is_running_flag": _is_running,
                "is_running()": is_running(),
                "scheduler_exists": scheduler is not None,
            },
            "scheduler": None,
            "jobs": [],
        }
        
        if scheduler:
            response["scheduler"] = {
                "state": str(scheduler.state),
                "running": scheduler.running,
                "job_count": len(scheduler.get_jobs()),
            }
            
            for job in scheduler.get_jobs():
                response["jobs"].append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                })
        
        return response
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/start")
async def start_scripts_runner() -> dict[str, Any]:
    """
    Manually start the scripts runner.
    
    Use this to start the scheduler if it didn't start during lifespan.
    """
    try:
        from backend.src.scripts.runner import start_runner, is_running, get_scheduler
        
        was_running = is_running()
        
        if not was_running:
            start_runner()
        
        scheduler = get_scheduler()
        
        return {
            "success": True,
            "was_already_running": was_running,
            "is_now_running": is_running(),
            "job_count": len(scheduler.get_jobs()) if scheduler else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/jobs")
async def list_scheduled_jobs() -> dict[str, Any]:
    """
    List all scheduled jobs with their details.
    """
    try:
        from backend.src.scripts.runner import get_scheduler, is_running
        
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        
        return {
            "scheduler_running": is_running(),
            "job_count": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                    "max_instances": job.max_instances,
                }
                for job in jobs
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
