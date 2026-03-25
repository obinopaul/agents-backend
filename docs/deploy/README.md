# Deployment Documentation

The `deploy/` directory contains deployment configurations for Docker, nginx, and supervisord.

---

## Directory Structure

```
deploy/
└── backend/
    ├── docker-compose/
    │   ├── .env.docker           # Docker environment variables
    │   └── .env.server           # Server environment variables
    │
    ├── nginx.conf                # Nginx reverse proxy config
    ├── supervisord.conf          # Supervisord process manager
    ├── fba_server.conf           # Server process config
    ├── fba_celery_worker.conf    # Celery worker config
    ├── fba_celery_beat.conf      # Celery beat config
    └── fba_celery_flower.conf    # Celery flower config
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION DEPLOYMENT                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           NGINX                                      │
│  ─────────────────────────────────────                              │
│  • Port 80/443                                                       │
│  • Reverse proxy                                                     │
│  • Static file serving                                               │
│  • Gzip compression                                                  │
│  • WebSocket support                                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  /            │      │  /flower/     │      │  /static      │
│  (API)        │      │  (Celery UI)  │      │  (Assets)     │
└───────┬───────┘      └───────┬───────┘      └───────────────┘
        │                      │
        ▼                      ▼
┌───────────────┐      ┌───────────────┐
│  fba_server   │      │ celery_flower │
│  (Uvicorn)    │      │ (Port 8555)   │
│  Port 8001    │      └───────────────┘
└───────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                         SUPERVISORD                                  │
│  ─────────────────────────────────────                              │
│  Process Manager - Controls all services                             │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├── fba_server           (FastAPI/Uvicorn)
        ├── fba_celery_worker    (Celery worker)
        ├── fba_celery_beat      (Celery scheduler)
        └── fba_celery_flower    (Celery monitoring UI)
```

---

## Nginx Configuration

**File:** `nginx.conf`

```nginx
server {
    listen 80 default_server;
    server_name 127.0.0.1;
    
    # Gzip compression
    gzip on;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/javascript application/json;
    
    # API proxy
    location / {
        proxy_pass http://fba_server:8001;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Celery Flower UI
    location /flower/ {
        proxy_pass http://fba_celery_flower:8555;
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Static files
    location /static {
        alias /var/www/fba_server/backend/static;
    }
}
```

---

## Supervisord Configuration

**File:** `supervisord.conf`

Manages all application processes:

| Program | Command | Description |
|---------|---------|-------------|
| `fba_server` | `gunicorn -c gunicorn.py backend.main:app` | FastAPI application |
| `fba_celery_worker` | `celery -A backend.app.task.celery worker` | Task worker |
| `fba_celery_beat` | `celery -A backend.app.task.celery beat` | Task scheduler |
| `fba_celery_flower` | `celery -A backend.app.task.celery flower` | Monitoring UI |

### Supervisord Commands

```bash
# Start all processes
supervisorctl start all

# Stop specific process
supervisorctl stop fba_server

# Restart specific process
supervisorctl restart fba_celery_worker

# View status
supervisorctl status

# View logs
supervisorctl tail -f fba_server
```

---

## Docker Compose

### Environment Files

**`.env.docker`** - Docker-specific settings:
```bash
COMPOSE_PROJECT_NAME=fba
```

**`.env.server`** - Application settings:
```bash
ENVIRONMENT=prod
DATABASE_HOST=db
REDIS_HOST=redis
# ... other settings
```

### Running with Docker

```bash
# Navigate to deploy directory
cd deploy/backend/docker-compose

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Process Configuration

### fba_server.conf

```ini
[program:fba_server]
command=/path/to/gunicorn -c gunicorn.py backend.main:app
directory=/var/www/fba_server
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/fba/server.log
stderr_logfile=/var/log/fba/server.error.log
```

### fba_celery_worker.conf

```ini
[program:fba_celery_worker]
command=/path/to/celery -A backend.app.task.celery worker -l info
directory=/var/www/fba_server
user=www-data
numprocs=1
autostart=true
autorestart=true
stdout_logfile=/var/log/fba/celery_worker.log
stderr_logfile=/var/log/fba/celery_worker.error.log
```

---

## Deployment Checklist

1. **Environment Setup**
   - [ ] Copy `.env.server` and configure all variables
   - [ ] Set up database (PostgreSQL/MySQL)
   - [ ] Set up Redis
   - [ ] Set up RabbitMQ (production)

2. **Nginx Setup**
   - [ ] Copy `nginx.conf` to `/etc/nginx/sites-available/`
   - [ ] Create symlink in `sites-enabled`
   - [ ] Configure SSL certificates (Let's Encrypt)
   - [ ] Test and reload nginx

3. **Supervisord Setup**
   - [ ] Copy `supervisord.conf` to `/etc/supervisor/conf.d/`
   - [ ] Copy individual `.conf` files
   - [ ] Create log directories
   - [ ] Start supervisord

4. **Application Setup**
   - [ ] Clone repository
   - [ ] Install dependencies: `pip install -r requirements.txt`
   - [ ] Run migrations: `alembic upgrade head`
   - [ ] Create superuser: `python cli.py create-superuser`
   - [ ] Collect static files

5. **Verification**
   - [ ] Check all processes: `supervisorctl status`
   - [ ] Test API endpoints
   - [ ] Test Celery tasks
   - [ ] Check logs for errors

---

*Last Updated: December 2024*
