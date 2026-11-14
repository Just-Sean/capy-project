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
from django.db import connection
from django.db.models import Q
from django.utils import timezone

# Named in full: run as `python -m config.health`, __name__ would be "__main__".
logger = logging.getLogger("config.health")

# A job waiting longer than this means the worker is stuck, stopped or can't keep up.
# Jobs should take well under a minute (see the README), so a healthy worker gets to
# each one long before this.
MAX_JOB_WAIT = timedelta(minutes=5)


def database_answers():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def cache_answers():
    cache.get("readyz")  # any read reaches Redis; a missing key is fine


CHECKS = {"database": database_answers, "cache": cache_answers}


def failing_checks():
    """The names of the checks that fail. Each failure is logged with the error's type
    only: its message can include connection details."""
    failing = []
    for name, check in CHECKS.items():
        try:
            check()
        except Exception as error:  # any failure at all means "not ready"
            logger.warning("Not ready: %s failed (%s)", name, type(error).__name__)
            failing.append(name)
    return failing


def a_job_has_waited_too_long(now):
    """Whether a job has been ready to run for longer than MAX_JOB_WAIT."""
    # Imported here: its models load only once Django is set up.
    from django.tasks import TaskResultStatus
    from django_tasks_db.models import DBTaskResult, get_date_max

    cutoff = now - MAX_JOB_WAIT
    # A job enqueued to run straight away has run_after set to the largest date there is;
    # one set to run later has waited since its run_after.
    waiting_since_enqueued = Q(run_after=get_date_max(), enqueued_at__lt=cutoff)
    waiting_since_run_after = Q(run_after__lt=cutoff)
    waiting = DBTaskResult.objects.filter(status=TaskResultStatus.READY).filter(
        waiting_since_enqueued | waiting_since_run_after
    )
    return waiting.exists()


def worker_is_healthy():
    if failing_checks():
        return False
    if a_job_has_waited_too_long(timezone.now()):
        logger.warning("Unhealthy: a job has waited over %s", MAX_JOB_WAIT)
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
