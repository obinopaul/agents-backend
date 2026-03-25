# Authentication & Backend Crash Debugging Summary

## 1. The Problem: Authentication System Failure

**Symptoms:**
*   Users are unable to log in via the Frontend Web UI.
*   The UI displays a generic "Login failed" error.
*   Check of Network Inspect tools (or direct API testing) reveals a **502 Bad Gateway** error from Nginx.
*   Initial attempts to view logs showed them as "empty" or irrelevant because the backend server process (`granian`) was falling into a **Crash Loop** immediately upon startup.

**Root Cause Identified:**
The backend server fails to start due to a Python coding error in `backend/app/agent/api/v1/slides.py`.
*   **Error:** `AssertionError: Cannot specify 'Depends' in 'Annotated' and default value together`
*   **Location:** `download_slides_stream_alias` function key argument `db`.
*   **Impact:** This syntax error prevents the FastAPI application entry point (`register_app`) from initializing valid routes. Supervisord attempts to restart the process repeatedly, but it crashes every time, leading to Nginx returning 502s.

---

## 2. Troubleshooting Steps Attempted

*   **Log Instrumentation:** Added `[DEBUG AUTH]` print statements to `auth_service.py` to trace the login flow. (Verified these generate output only when the server successfully starts).
*   **Docker Analysis:**
    *   Verified container status is "Up" (misleading, as the internal process was crashing).
    *   Checked Nginx logs to confirm requests were reaching the proxy but failing upstream (502).
    *   Checked internal Supervisor logs to find the "Traceback" revealing the `AssertionError`.
*   **Code Fixes:**
    *   Identified the duplicate Dependency injection in `slides.py`.
    *   Attempted to "Hot Patch" the running container using `docker cp` to overwrite the faulty file.
*   **Build Management:**
    *   Attempted standard rebuilds (failed to pick up changes due to cache).
    *   Attempted data-busting rebuilds (`--no-cache`) to force code updates.

---

## 3. Essential Debugging Commands

Here are the specific commands developed and used during this session to diagnose and fix the issue.

### A. Force Rebuild (Crucial for Code Changes)
Since the source code is copied into the image (not mounted), you **must** run this to apply any Python code fixes:
```powershell
# 1. Rebuild the image from scratch (ignoring bad cache)
docker compose build --no-cache agents_backend_server

# 2. Force recreation of the container to use the new image
docker compose up -d --force-recreate agents_backend_server
```

### B. Precision Log Retrieval
Standard `docker logs` was often truncated or flooded. Use these to find the exact needle in the haystack:

**1. Find Authentication Debug Logs:**
```powershell
# Search for our custom instrumentation tags inside the log file
docker exec agents_backend_server grep "DEBUG AUTH" /var/log/agents_backend/agents_backend_server.log
```

**2. Find Crash Tracebacks:**
```powershell
# detailed tail of the internal log file where Python dumps its crash report
docker exec agents_backend_server tail -n 50 /var/log/agents_backend/agents_backend_server.log
```

**3. Check Nginx Proxy Status:**
```powershell
# See if requests are hitting the server and what code they return (e.g., 502)
docker logs agents_backend_nginx --tail 20
```

### C. Direct API Testing
Bypass the Frontend to check if the Backend is alive and reachable:
```powershell
curl -v -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"123456\"}"
```

### D. Hot-Patching (Advanced)
Used to try fixes without a full rebuild (note: requires restart):
```powershell
# Copy local fixed file into container
docker cp backend/app/agent/api/v1/slides.py agents_backend_server:/agents_backend/backend/app/agent/api/v1/slides.py

# Restart container to load new file
docker restart agents_backend_server
```
