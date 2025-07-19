# Gunicorn Configuration File
# Production configuration for DonAlert donation platform

import multiprocessing
import os

# Server socket
project_path = os.getenv('PROJECT_PATH', '/srv/www/donalert.invictamotus.com')
bind = f"unix:{project_path}/gunicorn.sock"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 30
keepalive = 2

# Restart workers after this many requests, to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = f"{project_path}/logs/gunicorn_access.log"
errorlog = f"{project_path}/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "donalert"

# Server mechanics
daemon = False
pidfile = f"{project_path}/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment
raw_env = [
    'FLASK_ENV=production',
]

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190