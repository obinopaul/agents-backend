# Scheduled Scripts API Contract

## Overview

The scheduled scripts system provides **debug endpoints** for monitoring the APScheduler state and background script execution. These endpoints are essential for production monitoring and troubleshooting.

**Last Verified:** 2026-01-08 | **Scheduler Running: ✅**

---

## Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/debug/scripts/status` | Get scheduler status and all jobs |
| `POST` | `/debug/scripts/start` | Manually start the scheduler |

---

## Scheduler Status

### Request

```http
GET /debug/scripts/status HTTP/1.1
Host: 127.0.0.1:8000
```

No authentication required for debug endpoints (internal use).

### Response

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
      "name": "Extend timeouts for running sandboxes to prevent premature termination",
      "next_run_time": "2026-01-08T00:30:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='*', minute='*/30']"
    },
    {
      "id": "agents-backend-cleanup-stale-tasks",
      "name": "Mark stale agent run tasks as system interrupted",
      "next_run_time": "2026-01-08T00:40:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='*', minute='*/40']"
    },
    {
      "id": "agents-backend-refresh-daily-credits",
      "name": "Refresh daily credits for free tier users",
      "next_run_time": "2026-01-08T01:00:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='*', minute='0']"
    },
    {
      "id": "agents-backend-sandbox-cleanup",
      "name": "Pause inactive sandboxes and delete expired ones",
      "next_run_time": "2026-01-08T02:00:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='*/2', minute='0']"
    },
    {
      "id": "agents-backend-refresh-monthly-credits",
      "name": "Refresh monthly credits for paid subscribers at billing cycle reset",
      "next_run_time": "2026-01-09T00:00:00+00:00",
      "trigger": "cron[month='*', day='*', day_of_week='*', hour='0', minute='0']"
    }
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `string` | ISO 8601 UTC timestamp |
| `runner._is_running_flag` | `boolean` | Internal running flag |
| `runner.is_running()` | `boolean` | Runner function result |
| `runner.scheduler_exists` | `boolean` | Whether scheduler instance exists |
| `scheduler.state` | `string` | APScheduler state code ("1" = running) |
| `scheduler.running` | `boolean` | Scheduler running property |
| `scheduler.job_count` | `integer` | Number of scheduled jobs |
| `jobs` | `array` | List of scheduled job details |

### Job Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique script identifier |
| `name` | `string` | Human-readable description |
| `next_run_time` | `string` | ISO 8601 timestamp of next scheduled run |
| `trigger` | `string` | Cron trigger specification |

### Error Response

```json
{
  "error": "Error message",
  "traceback": "Full Python traceback...",
  "timestamp": "2026-01-08T00:14:02.672893+00:00"
}
```

---

## Start Scheduler

### Request

```http
POST /debug/scripts/start HTTP/1.1
Host: 127.0.0.1:8000
```

### Response (Success)

```json
{
  "success": true,
  "was_already_running": false,
  "is_now_running": true,
  "job_count": 5,
  "timestamp": "2026-01-08T00:15:00.000000+00:00"
}
```

### Response (Already Running)

```json
{
  "success": true,
  "was_already_running": true,
  "is_now_running": true,
  "job_count": 5,
  "timestamp": "2026-01-08T00:15:00.000000+00:00"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | Whether operation succeeded |
| `was_already_running` | `boolean` | Was scheduler running before this call |
| `is_now_running` | `boolean` | Is scheduler running after this call |
| `job_count` | `integer` | Number of jobs scheduled |
| `timestamp` | `string` | ISO 8601 UTC timestamp |

### Error Response

```json
{
  "success": false,
  "error": "Error message",
  "traceback": "Full Python traceback...",
  "timestamp": "2026-01-08T00:15:00.000000+00:00"
}
```

---

## Usage Examples

### cURL

```bash
# Check scheduler status
curl http://127.0.0.1:8000/debug/scripts/status

# Pretty print with jq
curl -s http://127.0.0.1:8000/debug/scripts/status | jq .

# Check if running
curl -s http://127.0.0.1:8000/debug/scripts/status | jq '.scheduler.running'

# List next run times
curl -s http://127.0.0.1:8000/debug/scripts/status | jq '.jobs[] | {id, next_run_time}'

# Manually start scheduler
curl -X POST http://127.0.0.1:8000/debug/scripts/start
```

### Python

```python
import httpx

BASE_URL = "http://127.0.0.1:8000"

def check_scheduler_health():
    """Check if scheduler is healthy."""
    response = httpx.get(f"{BASE_URL}/debug/scripts/status")
    data = response.json()
    
    if data.get("error"):
        print(f"❌ Error: {data['error']}")
        return False
    
    running = data.get("scheduler", {}).get("running", False)
    job_count = data.get("scheduler", {}).get("job_count", 0)
    
    if running and job_count > 0:
        print(f"✅ Scheduler running with {job_count} jobs")
        return True
    else:
        print(f"⚠️ Scheduler status: running={running}, jobs={job_count}")
        return False

def get_next_run_times():
    """Get next scheduled run times for all jobs."""
    response = httpx.get(f"{BASE_URL}/debug/scripts/status")
    data = response.json()
    
    for job in data.get("jobs", []):
        print(f"{job['id']}: {job['next_run_time']}")

# Usage
check_scheduler_health()
get_next_run_times()
```

---

## Health Check Integration

Include scheduler status in your health monitoring:

```python
@app.get("/health")
async def health_check():
    from backend.src.scripts.runner import is_running, get_scheduler
    
    scheduler_healthy = is_running()
    job_count = len(get_scheduler().get_jobs()) if get_scheduler() else 0
    
    return {
        "status": "healthy" if scheduler_healthy else "degraded",
        "scheduler": {
            "running": scheduler_healthy,
            "job_count": job_count,
        }
    }
```

---

## Scheduler States

| State Code | Meaning | Description |
|------------|---------|-------------|
| `0` | Stopped | Scheduler is not running |
| `1` | Running | Scheduler is active and processing jobs |
| `2` | Paused | Scheduler exists but paused |

---

## Troubleshooting

### Scheduler Shows Not Running

| Symptom | Solution |
|---------|----------|
| `running: false` | Call `POST /debug/scripts/start` |
| `scheduler_exists: false` | Restart FastAPI server |
| `error` in response | Check error message and traceback |

### No Jobs Scheduled

| Symptom | Solution |
|---------|----------|
| `job_count: 0` | Check script registry imports |
| Jobs exist but `next_run_time: null` | Invalid cron expression |

---

## Related Documentation

- [Scheduled Scripts Guide](../guides/scheduled-scripts.md) - Full system documentation
- [Sandbox Server API](sandbox-server.md) - Sandbox endpoints
- [Health Check](../README.md) - Application health
