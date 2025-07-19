# Gunicorn Configuration File
# Production configuration for DonAlert donation platform

import multiprocessing
import os

# Server socket
bind = "unix:/srv/www/donalert.invictamotus.com/gunicorn.sock"
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
accesslog = "/srv/www/donalert.invictamotus.com/logs/gunicorn_access.log"
errorlog = "/srv/www/donalert.invictamotus.com/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "donalert"

# Server mechanics
daemon = False
pidfile = "/srv/www/donalert.invictamotus.com/gunicorn.pid"
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