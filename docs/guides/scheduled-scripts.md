# Scheduled Scripts System - Complete Guide

The Agents Backend includes a **production-grade scheduled scripts system** for running background tasks automatically. This system manages sandbox lifecycle, credit refreshes, and cleanup operations using APScheduler integrated with FastAPI.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Scheduled Scripts Architecture                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    ┌─────────────────────────────────────┐                  │
│                    │         FastAPI Lifespan           │                  │
│                    │   (Application Startup/Shutdown)    │                  │
│                    └─────────────────────────────────────┘                  │
│                                    │                                         │
│                                    ▼                                         │
│                    ┌─────────────────────────────────────┐                  │
│                    │        APScheduler Runner           │                  │
│                    │    (AsyncIOScheduler Instance)      │                  │
│                    └─────────────────────────────────────┘                  │
│                                    │                                         │
│              ┌─────────────────────┼─────────────────────┐                  │
│              ▼                     ▼                     ▼                  │
│     ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐        │
│     │  Billing        │   │   Sandbox       │   │   Cleanup       │        │
│     │  Scripts        │   │   Scripts       │   │   Scripts       │        │
│     └─────────────────┘   └─────────────────┘   └─────────────────┘        │
│              │                     │                     │                  │
│              └─────────────────────┼─────────────────────┘                  │
│                                    ▼                                         │
│                    ┌─────────────────────────────────────┐                  │
│                    │      Script Registry                │                  │
│                    │   (Central Script Definitions)      │                  │
│                    └─────────────────────────────────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Automatic Startup** | Scripts start automatically with FastAPI server |
| **Graceful Shutdown** | Clean scheduler shutdown on app termination |
| **Cron Scheduling** | Standard cron expressions for flexible timing |
| **In-Process Execution** | Runs within FastAPI's event loop (no external processes) |
| **Debug Endpoints** | HTTP endpoints to monitor scheduler status |
| **Registry Pattern** | Centralized script definitions for easy management |

---

## How It All Works Together

> [!IMPORTANT]
> **Zero Configuration Required.** The scheduler starts automatically when your app starts. You don't need to run any extra commands, set up cron jobs, or configure anything special.

### Automatic Startup - What Happens When You Deploy

When you deploy your app (Docker, cloud, or local), here's exactly what happens:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTOMATIC STARTUP FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. You run your app:                                                       │
│      • docker-compose up                                                     │
│      • python -m uvicorn backend.main:app                                   │
│      • Deploy to Railway/AWS/GCP                                            │
│                        │                                                     │
│                        ▼                                                     │
│   2. FastAPI starts → Lifespan context begins                               │
│                        │                                                     │
│                        ▼                                                     │
│   3. start_scripts() is called automatically                                │
│      • Creates APScheduler instance                                         │
│      • Loads 5 scripts from registry                                        │
│      • Schedules each with cron trigger                                     │
│      • Starts the scheduler                                                 │
│                        │                                                     │
│                        ▼                                                     │
│   4. Scheduler runs forever in background                                   │
│      • Every 30 min: extend_sandbox_timeouts                                │
│      • Every 40 min: cleanup_stale_tasks                                    │
│      • Every 1 hour: refresh_daily_credits                                  │
│      • Every 2 hours: sandbox_cleanup                                       │
│      • Every day: refresh_monthly_credits                                   │
│                        │                                                     │
│                        ▼                                                     │
│   5. On app shutdown → stop_scripts() gracefully stops scheduler            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Do I Need To Do Anything?

**No.** Just deploy your app normally:

| Deployment Method | What You Do | Scheduler Status |
|-------------------|-------------|------------------|
| `docker-compose up` | Nothing extra | ✅ Starts automatically |
| Push to Railway/Render | Just push code | ✅ Starts automatically |
| AWS ECS/Fargate | Deploy container | ✅ Starts automatically |
| Local uvicorn | Run uvicorn | ✅ Starts automatically |

### How to Verify It's Working

After deployment, call the debug endpoint:

```bash
# Replace with your production URL
curl https://your-api.example.com/debug/scripts/status
```

A healthy response looks like:

```json
{
  "scheduler": {
    "running": true,
    "job_count": 5
  },
  "jobs": [
    {"id": "extend-sandbox-timeouts", "next_run_time": "2026-01-08T00:30:00+00:00"},
    {"id": "cleanup-stale-tasks", "next_run_time": "2026-01-08T00:40:00+00:00"},
    ...
  ]
}
```

If `running: false`, something went wrong - see [Troubleshooting](#12-troubleshooting).

---

## How Sandbox Monitoring Works at Scale

> [!TIP]
> The scheduler can manage **thousands of sandboxes** because it uses database queries, not in-memory tracking.

### The Database is the Source of Truth

Every sandbox created by any user is stored in PostgreSQL:

```sql
-- Sandbox table structure (simplified)
CREATE TABLE sandbox (
    id UUID PRIMARY KEY,
    user_id VARCHAR,
    provider_sandbox_id VARCHAR,    -- E2B's internal ID
    status VARCHAR,                  -- 'running', 'paused', 'deleted'
    last_activity_at TIMESTAMP,      -- When user last interacted
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### How Scripts Query and Process Sandboxes

**Extend Sandbox Timeouts (Every 30 Minutes):**

```python
# Step 1: Query ALL running sandboxes from database
sandboxes = await db.execute(
    select(Sandbox).where(Sandbox.status == 'running')
)
# Could return 1, 100, or 5000 sandboxes

# Step 2: Process in batches with concurrency
for batch in chunks(sandboxes, size=50):
    results = await asyncio.gather(*[
        e2b_api.extend_timeout(s.provider_sandbox_id, 7200)
        for s in batch
    ])
    
# Step 3: Log results
logger.info(f"Extended {success_count} sandboxes, {fail_count} failures")
```

**Sandbox Cleanup (Every 2 Hours):**

```python
# Find inactive sandboxes (no activity for 2+ hours)
inactive = await db.execute(
    select(Sandbox).where(
        Sandbox.status == 'running',
        Sandbox.last_activity_at < now() - timedelta(hours=2)
    )
)
# Pause each one

# Find expired sandboxes (paused for 30+ days)
expired = await db.execute(
    select(Sandbox).where(
        Sandbox.status == 'paused',
        Sandbox.updated_at < now() - timedelta(days=30)
    )
)
# Delete each one
```

### Scale Example

| Sandboxes | Processing Time | Notes |
|-----------|-----------------|-------|
| 100 | ~5 seconds | 2 batches of 50 |
| 1,000 | ~30 seconds | 20 batches, async concurrency |
| 10,000 | ~5 minutes | 200 batches, rate limiting kicks in |

---

## What Are "Stale Agent Tasks"?

### Understanding Agent Tasks

When a user sends a message to the AI agent, your backend creates a **task record** in the database:

```python
# AgentRunTask model (stored in PostgreSQL)
class AgentRunTask:
    id: UUID
    user_id: str
    thread_id: str
    status: str           # "RUNNING", "COMPLETED", "FAILED", "SYSTEM_INTERRUPTED"
    input_message: str
    created_at: datetime
    completed_at: datetime  # NULL while running
```

**Normal flow:**
1. User sends message → Task created with `status = RUNNING`
2. Agent processes message → Takes 10-60 seconds
3. Agent finishes → Task updated to `status = COMPLETED`

### What Makes a Task "Stale"?

A task becomes **stale** when something goes wrong:

| Scenario | What Happens | Task Status |
|----------|--------------|-------------|
| Normal completion | Agent finishes processing | ✅ COMPLETED |
| User closes browser mid-request | Connection drops | ⚠️ Still RUNNING |
| Server crashes | Process dies | ⚠️ Still RUNNING |
| Agent hits timeout | Never completes | ⚠️ Still RUNNING |
| Network error | Request fails silently | ⚠️ Still RUNNING |

**The problem:** The task is stuck at `RUNNING` forever, even though nothing is happening.

### Why Clean Up Stale Tasks?

1. **User Experience:** Dashboard might show "Task running..." forever
2. **Database Hygiene:** Accumulation of orphaned records
3. **Analytics:** Inflated "active task" counts
4. **Resource Tracking:** Can't tell what's really happening

### How the Cleanup Script Works

```python
# Every 40 minutes, the script:

# 1. Find tasks that have been "RUNNING" for too long (45+ minutes)
stale_tasks = await db.execute(
    select(AgentRunTask)
    .where(
        AgentRunTask.status == 'RUNNING',
        AgentRunTask.created_at < now() - timedelta(minutes=45)
    )
    .with_for_update(skip_locked=True)  # Prevents conflicts
)

# 2. Mark them as interrupted
for task in stale_tasks:
    task.status = 'SYSTEM_INTERRUPTED'
    task.completed_at = now()

# 3. Commit changes
await db.commit()
```

> [!NOTE]
> 45 minutes is the threshold because normal agent tasks complete in under 5 minutes. If something has been "running" for 45 minutes, it's definitely stuck.

---

## Using Debug Endpoints in Production

### When to Use Debug Endpoints

| Situation | Endpoint | What It Tells You |
|-----------|----------|-------------------|
| "Is scheduler running?" | `GET /debug/scripts/status` | Yes/no + job count |
| "When is next sandbox extension?" | `GET /debug/scripts/status` | `next_run_time` for each job |
| "Scheduler stopped unexpectedly" | `POST /debug/scripts/start` | Manually restart it |
| "Why are sandboxes dying?" | `GET /debug/scripts/status` | Check if extend_timeouts job exists |

### Production Monitoring Setup

**Add to your health check script:**

```bash
#!/bin/bash
# health_check.sh

# Check if scheduler is running
SCHEDULER_RUNNING=$(curl -s https://your-api.com/debug/scripts/status | jq -r '.scheduler.running')

if [ "$SCHEDULER_RUNNING" != "true" ]; then
    echo "ALERT: Scheduler not running!"
    # Send alert to Slack/PagerDuty/etc
fi
```

**Add to Docker health check:**

```yaml
# docker-compose.yml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/debug/scripts/status"]
      interval: 5m
      timeout: 10s
      retries: 3
```

### Quick Reference

```bash
# Check scheduler health
curl https://your-api.com/debug/scripts/status | jq '.scheduler'

# List all scheduled jobs
curl https://your-api.com/debug/scripts/status | jq '.jobs[] | {id, next_run_time}'

# Manual restart if needed
curl -X POST https://your-api.com/debug/scripts/start
```

---

## 1. Scheduled Scripts

### Script Overview

| Script ID | Schedule | Purpose |
|-----------|----------|---------|
| `agents-backend-extend-sandbox-timeouts` | Every 30 min (`*/30 * * * *`) | Extends timeouts for active sandboxes |
| `agents-backend-cleanup-stale-tasks` | Every 40 min (`*/40 * * * *`) | Marks stale agent tasks as interrupted |
| `agents-backend-refresh-daily-credits` | Hourly (`0 * * * *`) | Refreshes daily credits for free users |
| `agents-backend-sandbox-cleanup` | Every 2 hours (`0 */2 * * *`) | Pauses inactive, deletes expired sandboxes |
| `agents-backend-refresh-monthly-credits` | Daily at midnight (`0 0 * * *`) | Refreshes monthly credits for paid users |

---

### Extend Sandbox Timeouts

**Purpose:** Prevents sandbox timeouts by extending the E2B timeout for all running sandboxes.

**Schedule:** Every 30 minutes

**How it works:**
1. Queries database for all sandboxes with status `running`
2. Calls E2B API to extend timeout by 2 hours (7200 seconds)
3. Uses batch processing with concurrency control
4. Logs success/failure counts

**Code Location:** `backend/src/scripts/sandbox/extend_timeouts.py`

---

### Cleanup Stale Tasks

**Purpose:** Marks agent tasks that have been running too long as system-interrupted.

**Schedule:** Every 40 minutes

**How it works:**
1. Finds `AgentRunTask` records with status `RUNNING` older than 45 minutes
2. Uses row-level locking (`with_for_update(skip_locked=True)`) for safety
3. Updates status to `SYSTEM_INTERRUPTED`
4. Processes in batches of 50

**Code Location:** `backend/src/scripts/cleanup/stale_tasks.py`

---

### Refresh Daily Credits

**Purpose:** Refreshes daily credits for free-tier users.

**Schedule:** Hourly (at minute 0)

**How it works:**
1. Finds users eligible for daily credit refresh
2. Based on `last_daily_credit_refresh` timestamp
3. Adds configured daily credit amount
4. Updates refresh timestamp

**Code Location:** `backend/src/scripts/billing/refresh_daily_credits.py`

---

### Sandbox Cleanup

**Purpose:** Manages sandbox lifecycle by pausing inactive and deleting expired sandboxes.

**Schedule:** Every 2 hours

**How it works:**
1. **Pause Inactive:** Sandboxes idle > 2 hours are paused
2. **Delete Expired:** Sandboxes paused > 30 days are deleted
3. Uses batch processing with concurrency control
4. Logs statistics: paused count, deleted count

**Code Location:** `backend/src/scripts/sandbox/cleanup.py`

---

### Refresh Monthly Credits

**Purpose:** Refreshes monthly credits for paid subscribers at their billing cycle reset.

**Schedule:** Daily at midnight

**How it works:**
1. Finds users with `subscription_status=active`
2. Checks if billing cycle has reset (based on `subscription_current_period_end`)
3. Resets credits to plan's monthly allowance
4. Supports different plan tiers

**Code Location:** `backend/src/scripts/billing/refresh_monthly_credits.py`

---

## 2. Directory Structure

```
backend/src/scripts/
├── __init__.py           # Package exports (get_all_scripts, get_active_scripts)
├── __main__.py           # CLI interface for standalone usage
├── base.py               # ScriptDefinition, ScriptResult dataclasses
├── cron_manager.py       # OS crontab wrapper (python-crontab)
├── runner.py             # APScheduler integration (main runner)
├── registry.py           # Central registry of all scripts
├── billing/
│   ├── __init__.py
│   ├── refresh_monthly_credits.py
│   └── refresh_daily_credits.py
├── sandbox/
│   ├── __init__.py
│   ├── extend_timeouts.py
│   ├── cleanup.py
│   └── lifecycle.py      # Utility functions for sandbox management
└── cleanup/
    ├── __init__.py
    └── stale_tasks.py
```

---

## 3. Core Components

### ScriptDefinition

Defines a scheduled script with its metadata and task function.

```python
from backend.src.scripts.base import ScriptDefinition

SCRIPT = ScriptDefinition(
    name="my-custom-script",
    description="What this script does",
    schedule="*/15 * * * *",  # Every 15 minutes
    task=my_async_function,
    module_path="backend.src.scripts.my_module",
    status="active",  # or "inactive" to disable
)
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique identifier for the script |
| `description` | `str` | Human-readable description |
| `schedule` | `str` | Cron expression (5 fields) |
| `task` | `Callable` | Async or sync function to execute |
| `module_path` | `str` | Python module path for CLI usage |
| `status` | `str` | "active" or "inactive" |

### ScriptResult

Result of a script execution.

```python
from backend.src.scripts.base import ScriptResult

result = ScriptResult(
    success=True,
    script_name="my-script",
    started_at=datetime.now(timezone.utc),
    completed_at=datetime.now(timezone.utc),
    duration_seconds=1.5,
    items_processed=42,
    error=None,
)

print(result.summary)  # "✅ my-script: 42 items in 1.5s"
```

---

## 4. FastAPI Integration

### How It Works

The scripts system is integrated into FastAPI's lifespan context manager in `backend/core/registrar.py`:

```python
from backend.src.scripts.runner import start_runner as start_scripts, stop_runner as stop_scripts

@asynccontextmanager
async def register_init(app: FastAPI) -> AsyncGenerator[None, None]:
    # ... other initialization ...
    
    # Start Scheduled Scripts Runner (APScheduler)
    try:
        start_scripts()
        log.info("Scheduled Scripts Runner started successfully")
    except Exception as e:
        log.warning(f"Scheduled Scripts Runner failed to start: {e}")

    yield  # Application runs here
    
    # Stop Scheduled Scripts Runner
    try:
        stop_scripts()
        log.info("Scheduled Scripts Runner stopped")
    except Exception as e:
        log.warning(f"Scheduled Scripts Runner shutdown error: {e}")
```

### Startup Flow

1. FastAPI app starts
2. `register_init` lifespan context begins
3. `start_scripts()` is called:
   - Creates `AsyncIOScheduler` instance
   - Gets active scripts from registry
   - Schedules each script with cron trigger
   - Starts the scheduler
4. Scheduler runs jobs in background
5. On shutdown, `stop_scripts()` gracefully stops scheduler

---

## 5. Debug Endpoints

### Check Scheduler Status

**Endpoint:** `GET /debug/scripts/status`

**Purpose:** Query the actual scheduler state from within the running FastAPI process.

**Example Request:**
```bash
curl http://127.0.0.1:8000/debug/scripts/status
```

**Example Response:**
```json
{
  "timestamp": "2026-01-08T00:14:02.672893+00:00",
  "runner": {
    "_is_running_flag": true,
    "is_running()": true,
    "scheduler_exists": true
  },
  "scheduler": {
    "state": "1",
    "running": true,
    "job_count": 5
  },
  "jobs": [
    {
      "id": "agents-backend-extend-sandbox-timeouts",
      "name": "Extend timeouts for running sandboxes...",
      "next_run_time": "2026-01-08T00:30:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='*', minute='*/30']"
    },
    {
      "id": "agents-backend-cleanup-stale-tasks",
      "name": "Mark stale agent run tasks as system interrupted",
      "next_run_time": "2026-01-08T00:40:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='*', minute='*/40']"
    }
  ]
}
```

### Manually Start Scheduler

**Endpoint:** `POST /debug/scripts/start`

**Purpose:** Manually start the scheduler if it didn't start during lifespan.

**Example Request:**
```bash
curl -X POST http://127.0.0.1:8000/debug/scripts/start
```

**Example Response:**
```json
{
  "success": true,
  "was_already_running": true,
  "is_now_running": true,
  "job_count": 5,
  "timestamp": "2026-01-08T00:15:00.000000+00:00"
}
```

---

## 6. Lifecycle Utilities

Additional utility functions for sandbox management are available in `backend/src/scripts/sandbox/lifecycle.py`:

| Function | Description |
|----------|-------------|
| `get_sandbox_stats()` | Returns counts: running, paused, total sandboxes |
| `extend_sandbox_timeout(sandbox_id, timeout_seconds)` | Extend single sandbox timeout |
| `pause_sandbox(sandbox_id)` | Pause a sandbox |
| `resume_sandbox(sandbox_id)` | Resume a paused sandbox |
| `delete_sandbox(sandbox_id)` | Delete a sandbox |
| `get_inactive_sandboxes(hours)` | Find sandboxes inactive for N hours |
| `get_expired_sandboxes(days)` | Find sandboxes paused for N days |
| `extend_batch_with_concurrency(sandboxes, timeout)` | Batch extend with asyncio.gather |
| `run_lifecycle_cleanup()` | Combined pause inactive + delete expired |

### Example Usage

```python
from backend.src.scripts.sandbox.lifecycle import (
    get_sandbox_stats,
    resume_sandbox,
    run_lifecycle_cleanup,
)

# Get current sandbox statistics
stats = await get_sandbox_stats()
print(f"Running: {stats['running']}, Paused: {stats['paused']}, Total: {stats['total']}")

# Resume a paused sandbox
success = await resume_sandbox("sandbox-uuid-here")

# Run full lifecycle cleanup
result = await run_lifecycle_cleanup()
print(f"Paused: {result['paused_count']}, Deleted: {result['deleted_count']}")
```

---

## 7. Configuration

### Environment Variables

No additional environment variables are required. The scripts system uses existing configuration:

| Variable | Used By | Description |
|----------|---------|-------------|
| `DATABASE_URL` | All scripts | Database connection for queries |
| `REDIS_HOST` | Sandbox scripts | Redis for sandbox queue |
| `E2B_API_KEY` | Sandbox scripts | E2B API for timeout extension |

### Constants

Located in individual script files:

| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| `STALE_TASK_MINUTES` | 45 | `stale_tasks.py` | Age threshold for stale tasks |
| `BATCH_SIZE` | 50 | `stale_tasks.py` | Batch size for processing |
| `DEFAULT_TIMEOUT_EXTENSION` | 7200 | `lifecycle.py` | 2 hours in seconds |
| `INACTIVITY_THRESHOLD_HOURS` | 2 | `lifecycle.py` | Hours before sandbox is "inactive" |
| `EXPIRED_THRESHOLD_DAYS` | 30 | `lifecycle.py` | Days before sandbox is "expired" |

---

## 8. CLI Interface

Run scripts standalone from command line:

### List All Scripts

```bash
python -m backend.src.scripts
```

Output:
```
Registered scripts (5 total):

  ✅ agents-backend-refresh-monthly-credits
      Schedule: 0 0 * * *
      Refresh monthly credits for paid subscribers...

  ✅ agents-backend-refresh-daily-credits
      Schedule: 0 * * * *
      Refresh daily credits for free tier users
  ...
```

### Run All Scripts Once

```bash
python -m backend.src.scripts --run-once
```

### Run Specific Script

```bash
python -m backend.src.scripts --script agents-backend-extend-sandbox-timeouts
```

### Start Daemon Mode

```bash
python -m backend.src.scripts --daemon
```

---

## 9. Testing

### Unit Tests

```bash
pytest backend/tests/unit/test_scripts_system.py -v
```

**Tests include:**
- ScriptDefinition creation and hashing
- ScriptResult success/failure formatting
- Registry contents verification
- Runner function imports
- Lifecycle utility imports and coroutine verification
- Cron manager functionality

### Live Integration Test

```bash
python backend/tests/live/scripts_tests/test_scripts_live.py
```

**Tests include:**
- Authentication with backend
- Script import verification
- Scheduler status check
- Registry contents validation
- Lifecycle utilities (get_sandbox_stats)
- Cron manager dry-run
- Sandbox creation via agent (optional)

---

## 10. Production Deployment

### Docker Deployment

When deploying via Docker, the scheduler starts automatically with FastAPI:

```yaml
# docker-compose.yml
services:
  agents_backend_server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_HOST=redis
      - E2B_API_KEY=...
```

On startup, you'll see in logs:
```
Scheduled Scripts Runner started successfully
```

### Verifying Production Health

Use the debug endpoint to verify scheduler is running:

```bash
curl https://your-production-url.com/debug/scripts/status
```

Expected response should show:
- `runner.is_running()`: `true`
- `scheduler.running`: `true`
- `scheduler.job_count`: `5`
- `jobs`: Array with next_run_time for each job

### Monitoring Recommendations

1. **Health Check Integration:**
   Include scheduler status in your health monitoring:
   ```bash
   # Verify scheduler is running
   curl -s http://localhost:8000/debug/scripts/status | jq '.scheduler.running'
   ```

2. **Log Monitoring:**
   Watch for script execution logs:
   ```
   [SCRIPT] Starting: agents-backend-extend-sandbox-timeouts
   ✅ agents-backend-extend-sandbox-timeouts: 15 items in 2.3s
   ```

3. **Alert on Failures:**
   Monitor for error patterns:
   ```
   ❌ agents-backend-extend-sandbox-timeouts: Connection timeout
   ```

### Scaling Considerations

| Concern | Solution |
|---------|----------|
| **Multiple Instances** | Each FastAPI instance runs its own scheduler. Scripts are idempotent so duplicate runs are safe. |
| **Database Locks** | `with_for_update(skip_locked=True)` prevents conflicts |
| **Long-Running Scripts** | `max_instances=1` prevents overlapping executions |
| **Missed Runs** | APScheduler handles catch-up if server was down |

---

## 11. Adding New Scripts

### Step 1: Create Script File

```python
# backend/src/scripts/mymodule/my_script.py

import logging
from backend.src.scripts.base import ScriptDefinition

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = "0 */4 * * *"  # Every 4 hours

async def my_task() -> dict:
    """
    Your task logic here.
    
    Returns:
        Dict with 'items_processed' for logging
    """
    logger.info("[MY_SCRIPT] Starting...")
    
    # Your logic...
    items = 42
    
    logger.info(f"[MY_SCRIPT] Processed {items} items")
    return {"items_processed": items}


SCRIPT = ScriptDefinition(
    name="agents-backend-my-script",
    description="Description of what this script does",
    schedule=DEFAULT_SCHEDULE,
    task=my_task,
    module_path="backend.src.scripts.mymodule.my_script",
    status="active",
)
```

### Step 2: Add to Registry

```python
# backend/src/scripts/registry.py

from backend.src.scripts.mymodule.my_script import SCRIPT as MY_SCRIPT

SCRIPTS = [
    # ... existing scripts ...
    MY_SCRIPT,
]
```

### Step 3: Test

```bash
# Run once to test
python -m backend.src.scripts --script agents-backend-my-script

# Verify in registry
python -m backend.src.scripts
```

---

## 12. Troubleshooting

### Scheduler Not Running

**Symptom:** `/debug/scripts/status` shows `is_running: false`

**Possible Causes:**
1. Server just started, scheduler initializing
2. Import error in scripts module
3. Exception during `start_scripts()`

**Solution:**
1. Check server logs for errors
2. Try manual start: `POST /debug/scripts/start`
3. Verify script imports: `python -c "from backend.src.scripts import get_all_scripts; print(len(get_all_scripts()))"`

### Scripts Not Executing

**Symptom:** Jobs scheduled but never run

**Possible Causes:**
1. Cron schedule is incorrect
2. Script function throws exception
3. Event loop blocked

**Solution:**
1. Check cron syntax: [crontab.guru](https://crontab.guru/)
2. Run script manually: `python -m backend.src.scripts --script <name>`
3. Check APScheduler logs

### Sandbox Timeouts Still Happening

**Symptom:** Sandboxes dying even with extend_timeouts script

**Possible Causes:**
1. Script failing silently
2. E2B API key invalid
3. Sandbox not in database

**Solution:**
1. Check script logs for errors
2. Verify E2B_API_KEY is set
3. Check sandbox exists in database

---

## Related Documentation

- [Sandbox Server Guide](sandbox-guide.md) - Sandbox management
- [Billing Credits Guide](billing-credits.md) - Credit system details
- [FastAPI Backend Guide](fastapi-backend.md) - Backend architecture
- [Environment Variables](environment-variables.md) - Configuration reference
