"""Gunicorn settings for production. Gunicorn reads this file automatically.

Docker's CMD and a Linux server's service both run `gunicorn config.wsgi`, so these
settings apply to both. Gunicorn listens on 127.0.0.1:8000 unless told otherwise;
the Dockerfile tells it to listen on 0.0.0.0:8000 inside the container.
"""

import os

# Worker processes. Set WEB_CONCURRENCY on the server, about 2 x CPU cores + 1.
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))

# A worker that doesn't respond for this many seconds is replaced.
timeout = 30
# On shutdown or reload, workers get this many seconds to finish their requests.
graceful_timeout = 30

# Replace each worker after about this many requests, so a slow memory leak never
# builds up. The jitter spreads the restarts so workers don't all restart at once.
max_requests = 1000
max_requests_jitter = 100

# Workers' heartbeat files go in memory: on a container's disk they can stall workers
# (Gunicorn's docs recommend /dev/shm in containers). Ruff's S108 warns about shared
# temp folders; it doesn't apply: Gunicorn makes the files with random names, and only
# the app runs in the container.
worker_tmp_dir = "/dev/shm"  # noqa: S108

# Request and error logs go to stdout/stderr, for Docker, systemd or the platform.
accesslog = "-"
errorlog = "-"

# Gunicorn's local control socket isn't used: Docker or systemd restart the server.
# (It would also need a home folder, which the unprivileged app user doesn't have.)
control_socket_disable = True
