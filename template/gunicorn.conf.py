"""Gunicorn settings for production.

Gunicorn reads this file automatically when it's started from the project folder
(Docker's WORKDIR is /app). Started from anywhere else, it silently skips the file,
so a Linux server's service must set its working directory to the project folder or
pass `-c /path/to/gunicorn.conf.py`.

Change timeouts and worker recycling here. Change the number of workers with the
WEB_CONCURRENCY environment variable instead (see the README).
"""

import os

# Listen only on this machine. On a Linux server a reverse proxy (e.g. Caddy or nginx)
# on the same machine forwards requests here. Set explicitly so a PORT environment
# variable, which some hosts set, can't make Gunicorn listen on every interface. In
# Docker the Dockerfile overrides it with --bind 0.0.0.0:8000.
bind = "127.0.0.1:8000"

# Worker processes. Set WEB_CONCURRENCY on the server, about 2 x CPU cores + 1. The
# default is 2, so one slow request (a login's password check, a slow email server)
# never holds up every other visitor, and a worker being replaced (max_requests below)
# never leaves the site with none. Each worker checking a login uses about 100 MB.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))

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
# the app runs in the container. (/dev/shm is Linux-only; development uses runserver.)
worker_tmp_dir = "/dev/shm"  # noqa: S108

# Request and error logs go to stdout/stderr, for Docker, systemd or the platform.
accesslog = "-"
errorlog = "-"
# One request per line: address, method, path, status, bytes, milliseconds, browser.
# The path leaves out the query string (%(U)s, not %(r)s): query strings often carry
# tokens (signed links, API keys) that shouldn't sit in logs. Behind the reverse proxy
# (DJANGO_BEHIND_PROXY), the visitor's address is the X-Forwarded-For the proxy sets;
# otherwise it's the connection's.
# Requests that don't come through the proxy (Docker's health check) show "-". The true
# values are the ones Django's settings accept (django-environ's), so the two always
# agree. (Written as one expression: every name in this file must be a Gunicorn setting.)
access_log_format = (
    "%({x-forwarded-for}i)s"
    if os.environ.get("DJANGO_BEHIND_PROXY", "").lower() in {"true", "on", "ok", "y", "yes", "1"}
    else "%(h)s"
) + ' "%(m)s %(U)s" %(s)s %(B)s %(M)sms "%(a)s"'
# Both logs as one JSON object per line, like the app's own (config/logging.py). The
# levels are set here: Gunicorn applies --log-level first, so this overrides it.
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stderr",
        },
    },
    # Gunicorn adds this to its own defaults, whose root logger needs a handler from here.
    "root": {"handlers": ["stderr"], "level": "INFO"},
    "loggers": {
        "gunicorn.access": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "gunicorn.error": {"handlers": ["stderr"], "level": "INFO", "propagate": False},
    },
}

# Gunicorn's local control socket isn't used: Docker or systemd restart the server,
# so the `gunicornc` tool can't connect. (The socket would also need a home folder,
# which the unprivileged app user doesn't have.)
control_socket_disable = True
