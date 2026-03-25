# Docker Helpful Commands for Agents Backend

This document contains essential Docker commands to help you debug and manage the Agents Backend project.

## 🔍 Log Retrieval

### 1. Read Internal Log File (Most Reliable)
Use this when logs are written to a file inside the container (like in this project) instead of standard output.
```powershell
docker exec agents_backend_server grep "DEBUG AUTH" /var/log/agents_backend/agents_backend_server.log
```
*   `grep "text"`: Filters for lines containing "text".
*   `tail -n 100`: Shows the last 100 lines instead.

### 2. Read Standard Output Logs
Use this for containers that print directly to the console (like Nginx).
```powershell
docker logs agents_backend_server
```
*   Add `--tail 100` to see only the last 100 lines.
*   Add `-f` to follow the logs in real-time (Ctrl+C to stop).

## 🛠️ Management & Debugging

### 3. Rebuild a Single Service
Required when you change code that is copied into the image (not mounted).
```powershell
docker compose up --build -d agents_backend_server
```
*   `-d`: Detached mode (runs in background).
*   `--build`: Forces a rebuild of the image.

### 4. Restart a Service
Use this to simply restart a running container (only picks up changes if volumes are mounted).
```powershell
docker restart agents_backend_server
```

### 5. Check Container Status
See which containers are running and if they are healthy.
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 6. Execute Command Inside Container
Open a bash shell inside the running container to explore files manually.
```powershell
docker exec -it agents_backend_server bash
```
Once inside, you can use `ls`, `cat`, or `nano` to inspect files. type `exit` to leave.

## ⚠️ Important Paths
*   **Backend Log File**: `/var/log/agents_backend/agents_backend_server.log`
*   **Source Code**: `/agents_backend/backend`
