import os

# Environment-aware configuration
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/srv/www/donalert.invictamotus.com')
BIND_PORT = os.environ.get('GUNICORN_PORT', '5014')

bind = f"127.0.0.1:{BIND_PORT}"
workers = 1
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 60
max_requests = 1000
max_requests_jitter = 100
preload_app = True
daemon = False
pidfile = f"{PROJECT_PATH}/gunicorn.pid"
accesslog = f"{PROJECT_PATH}/logs/gunicorn_access.log"
errorlog = f"{PROJECT_PATH}/logs/gunicorn_error.log"
loglevel = "info"
capture_output = True