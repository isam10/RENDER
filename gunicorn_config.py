"""
Gunicorn configuration file for production deployment
Optimized for Render.com free tier
"""

import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
backlog = 2048

# Worker processes
# Use 1 worker for free tier to minimize memory usage
workers = 1
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # Increased timeout for image processing
keepalive = 5

# Preload app to load model once for all workers
preload_app = True

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

def on_starting(server):
    """Called just before the master process is initialized."""
    print("=" * 60)
    print("Starting Background Removal API Server")
    print("=" * 60)

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("Reloading server...")

def when_ready(server):
    """Called just after the server is started."""
    print(f"Server is ready. Listening on {bind}")
    print(f"Workers: {workers}")
    print(f"Timeout: {timeout}s")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    print(f"Worker {worker.pid} is being forked...")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker {worker.pid} spawned")

def pre_exec(server):
    """Called just before a new master process is forked."""
    print("Forking new master process...")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    print(f"Worker {worker.pid} exited")
