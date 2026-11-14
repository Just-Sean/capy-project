"""Health checks: whether the database and Redis answer (/readyz), and whether the
background-job worker is keeping up (the worker container's Docker health check).

The worker's check runs as `python -m config.health worker`: exit code 0 means healthy.
"""

import logging
import os
import sys
from datetime import timedelta

import django
from django.core.cache import cache
from django.db import connections
from django.db.models import Q
from django.utils import timezone

# Named in full: run as `python -m config.health`, __name__ would be "__main__".
logger = logging.getLogger("config.health")

# The worker is unhealthy when a job has waited longer than this AND no job has started
# for this long: it's stuck or stopped. A busy worker catching up on a backlog keeps
# starting jobs, so it stays healthy. Jobs should take well under a minute (README).
MAX_JOB_WAIT = timedelta(minutes=5)
# The queue and backend `manage.py db_worker` serves by default.
WORKER_QUEUE = "default"


def database_answers():
    """A new connection each time, not the request's kept one: a database that stops
    answering a kept connection could hold the check for good, while a new one gives up
    after connect_timeout (config/settings/database.py)."""
    database = connections.create_connection("default")
    try:
        with database.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        database.close()


def cache_answers():
    cache.get("readyz")  # any read reaches Redis; a missing key is fine


CHECKS = {"database": database_answers, "cache": cache_answers}


def failing_checks(names=None):
    """The names of the checks that fail (all of them, or those named). Each failure is
    logged with the error's type only: its message can include connection details."""
    failing = []
    for name in names or CHECKS:
        try:
            CHECKS[name]()
        except Exception as error:  # any failure at all means "not ready"
            logger.warning("Not ready: %s failed (%s)", name, type(error).__name__)
            failing.append(name)
    return failing


def worker_is_stuck(now):
    """Whether a job has waited over MAX_JOB_WAIT while no job started in that time."""
    # Imported here: its models load only once Django is set up. get_date_max is the
    # value django-tasks-db 0.13 (pinned in pyproject.toml) stores in run_after for "run
    # as soon as possible"; the tests fail if a new version changes that.
    from django.tasks import TaskResultStatus
    from django_tasks_db.models import DBTaskResult, get_date_max

    cutoff = now - MAX_JOB_WAIT
    jobs = DBTaskResult.objects.filter(queue_name=WORKER_QUEUE, backend_name="default")
    # Waiting since it was enqueued, or since its run_after if that's later.
    waited_too_long = jobs.filter(
        Q(run_after=get_date_max()) | Q(run_after__lt=cutoff),
        status=TaskResultStatus.READY,
        enqueued_at__lt=cutoff,
    )
    started_recently = jobs.filter(started_at__gte=cutoff)
    return waited_too_long.exists() and not started_recently.exists()


def worker_is_healthy():
    # Only the database: the worker runs jobs without Redis.
    if failing_checks(["database"]):
        return False
    if worker_is_stuck(timezone.now()):
        logger.warning("Unhealthy: no job has started for %s while jobs wait", MAX_JOB_WAIT)
        return False
    return True


def main(argv):
    """The worker container's health check: `python -m config.health worker`."""
    if argv != ["worker"]:
        sys.exit("usage: python -m config.health worker")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    sys.exit(0 if worker_is_healthy() else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
