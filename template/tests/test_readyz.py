"""/readyz (the database and Redis answer) and the job worker's health check."""

import os
import socket
import subprocess
import sys
import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.tasks import TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config import health
from tests.test_production_settings import PRODUCTION_ENV, PROJECT_DIR, run_manage
from tests.test_tasks import DATABASE_BACKEND, add

# Production, with nothing listening where the database and Redis should be.
NOTHING_THERE = {
    "DATABASE_URL": "postgres://user:pass@127.0.0.1:1/db",
    "CACHE_URL": "redis://app:pass@127.0.0.1:1/0",
}
ASK_BOTH = (
    "import time\n"
    "from django.test import Client\n"
    "client = Client()\n"
    "start = time.monotonic()\n"
    "ready = client.get('/readyz')\n"
    "print(ready.status_code, round(time.monotonic() - start))\n"
    "print(client.get('/healthz').status_code)\n"
)


def fail():
    raise ConnectionError("connection refused by db.internal:5432 for user app")


@pytest.mark.django_db
def test_readyz_is_ok_when_the_database_and_cache_answer(client):
    response = client.get("/readyz", headers={"host": "10.0.0.7"})  # any host
    assert response.status_code == 200
    assert response.content == b"ok"
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("name", ["database", "cache"])
def test_readyz_is_503_when_one_doesnt_answer(client, monkeypatch, caplog, name):
    monkeypatch.setitem(health.CHECKS, "database", lambda: None)
    monkeypatch.setitem(health.CHECKS, "cache", lambda: None)
    monkeypatch.setitem(health.CHECKS, name, fail)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.content == b"not ready"
    assert f"Not ready: {name} failed (ConnectionError)" in caplog.text
    assert "db.internal" not in caplog.text  # the error's message isn't logged


def test_with_the_database_down_readyz_says_so_quickly_and_healthz_still_answers():
    result = run_manage("shell", "-c", ASK_BOTH, **NOTHING_THERE)
    ready, healthz = result.stdout.strip().splitlines()[-2:]
    status, seconds = ready.split()
    assert status == "503", result.stderr
    assert int(seconds) <= 5  # a refused connection gives a quick answer
    assert healthz == "200"  # the app stays healthy through a database outage


def test_readyz_gives_up_on_a_database_that_accepts_but_never_answers():
    # The connection is taken but nothing comes back: connect_timeout gives up.
    silent = socket.create_server(("127.0.0.1", 0))
    taken = []
    threading.Thread(target=lambda: taken.append(silent.accept()), daemon=True).start()
    url = f"postgres://user:pass@127.0.0.1:{silent.getsockname()[1]}/db"
    try:
        result = run_manage("shell", "-c", ASK_BOTH, DATABASE_URL=url)
    finally:
        silent.close()
    status, seconds = result.stdout.strip().splitlines()[-2].split()
    assert status == "503", result.stderr
    assert int(seconds) <= 8


def test_database_connections_time_out(settings):
    assert settings.DATABASES["default"]["OPTIONS"]["connect_timeout"] == 5


def test_database_url_can_set_its_own_timeout():
    code = "from django.conf import settings; print(settings.DATABASES['default']['OPTIONS'])"
    url = "postgres://user:pass@localhost:5432/db?connect_timeout=10"
    result = run_manage("shell", "-c", code, DATABASE_URL=url)
    assert "'connect_timeout': 10" in result.stdout, result.stderr


@pytest.fixture
def stored_jobs(settings):
    """Jobs stored in the database, as in production (tests otherwise run them at once)."""
    settings.TASKS = {"default": {"BACKEND": DATABASE_BACKEND}}


def past_the_wait(moment):
    return moment + health.MAX_JOB_WAIT + timedelta(seconds=1)


@pytest.mark.django_db
def test_the_worker_is_stuck_once_a_job_has_waited_too_long(stored_jobs):
    assert health.worker_is_healthy()  # nothing waiting
    add.enqueue(2, 3)
    now = timezone.now()
    assert not health.worker_is_stuck(now)
    assert health.worker_is_stuck(past_the_wait(now))


@pytest.mark.django_db
def test_a_worker_catching_up_on_a_backlog_isnt_stuck(stored_jobs):
    # After an outage, old jobs wait while a new worker works through them.
    add.enqueue(2, 3)
    later = past_the_wait(timezone.now())
    DBTaskResult.objects.filter(pk=add.enqueue(1, 1).id).update(
        status=TaskResultStatus.RUNNING, started_at=later
    )
    assert not health.worker_is_stuck(later)


@pytest.mark.django_db
@pytest.mark.parametrize("status", [TaskResultStatus.SUCCESSFUL, TaskResultStatus.FAILED])
def test_finished_jobs_dont_count(stored_jobs, status):
    add.enqueue(2, 3)
    DBTaskResult.objects.update(status=status)
    assert not health.worker_is_stuck(timezone.now() + timedelta(days=3))


@pytest.mark.django_db
def test_a_job_set_to_run_later_counts_from_when_it_may_run(stored_jobs):
    run_after = timezone.now() + timedelta(hours=1)
    add.using(run_after=run_after).enqueue(2, 3)
    assert not health.worker_is_stuck(run_after)
    assert health.worker_is_stuck(past_the_wait(run_after))


@pytest.mark.django_db
def test_a_job_enqueued_just_now_with_a_past_run_after_hasnt_waited(stored_jobs):
    add.using(run_after=timezone.now() - timedelta(hours=1)).enqueue(2, 3)
    assert not health.worker_is_stuck(timezone.now() + timedelta(seconds=1))


@pytest.mark.django_db
def test_jobs_in_a_queue_the_worker_doesnt_serve_dont_count(stored_jobs):
    add.enqueue(2, 3)
    DBTaskResult.objects.update(queue_name="emails")
    assert not health.worker_is_stuck(past_the_wait(timezone.now()))


def test_a_stuck_worker_is_unhealthy(monkeypatch, caplog):
    monkeypatch.setitem(health.CHECKS, "database", lambda: None)
    monkeypatch.setattr(health, "worker_is_stuck", lambda now: True)
    assert not health.worker_is_healthy()
    assert "Unhealthy: no job has started for 0:05:00 while jobs wait" in caplog.text


def test_the_worker_is_unhealthy_when_the_database_doesnt_answer(monkeypatch):
    monkeypatch.setitem(health.CHECKS, "database", fail)
    assert not health.worker_is_healthy()


@pytest.mark.django_db
def test_the_worker_doesnt_need_redis(monkeypatch):
    monkeypatch.setitem(health.CHECKS, "cache", fail)
    assert health.worker_is_healthy()


@pytest.mark.django_db
def test_the_database_check_uses_its_own_connection():
    # A kept connection to a database that stops answering could hold the check for good;
    # a new one gives up after connect_timeout.
    before = connection.connection
    health.database_answers()
    assert connection.connection is before


def run_worker_check(*args):
    """The worker container's health check, as Docker runs it, in production. Coverage's
    own variables are passed on, so `pytest --cov` measures it too."""
    coverage = {k: v for k, v in os.environ.items() if k.startswith("COVERAGE_")}
    environment = {"PATH": os.environ["PATH"], **coverage, **PRODUCTION_ENV, **NOTHING_THERE}
    return subprocess.run(
        [sys.executable, "-m", "config.health", *args],
        cwd=PROJECT_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_workers_docker_check_fails_when_the_database_is_down():
    result = run_worker_check("worker")
    assert result.returncode == 1, result.stderr
    assert "Not ready: database failed" in result.stderr


def test_the_workers_docker_check_explains_its_usage():
    result = run_worker_check("web")
    assert result.returncode == 1
    assert "usage: python -m config.health worker" in result.stderr
