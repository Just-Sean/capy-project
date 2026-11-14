"""/readyz (the database and Redis answer) and the job worker's health check."""

import os
import subprocess
import sys
from datetime import timedelta

import pytest
from django.utils import timezone

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
    assert int(seconds) <= 10  # the connect timeouts, not a hang
    assert healthz == "200"  # Docker doesn't restart the app over a database outage


def test_database_connections_time_out(settings):
    assert settings.DATABASES["default"]["OPTIONS"]["connect_timeout"] == 5


def test_database_url_can_set_its_own_timeout():
    code = "from django.conf import settings; print(settings.DATABASES['default']['OPTIONS'])"
    url = "postgres://user:pass@localhost:5432/db?connect_timeout=10"
    result = run_manage("shell", "-c", code, DATABASE_URL=url)
    assert "'connect_timeout': 10" in result.stdout, result.stderr


@pytest.mark.django_db
def test_the_worker_is_unhealthy_once_a_job_has_waited_too_long(settings):
    settings.TASKS = {"default": {"BACKEND": DATABASE_BACKEND}}
    assert health.worker_is_healthy()  # nothing waiting
    add.enqueue(2, 3)
    now = timezone.now()
    assert not health.a_job_has_waited_too_long(now)
    later = now + health.MAX_JOB_WAIT + timedelta(seconds=1)
    assert health.a_job_has_waited_too_long(later)


@pytest.mark.django_db
def test_a_job_set_to_run_later_counts_from_when_it_may_run(settings):
    settings.TASKS = {"default": {"BACKEND": DATABASE_BACKEND}}
    run_after = timezone.now() + timedelta(hours=1)
    add.using(run_after=run_after).enqueue(2, 3)
    assert not health.a_job_has_waited_too_long(run_after)
    late = run_after + health.MAX_JOB_WAIT + timedelta(seconds=1)
    assert health.a_job_has_waited_too_long(late)


def test_a_job_waiting_too_long_makes_the_worker_unhealthy(monkeypatch, caplog):
    monkeypatch.setitem(health.CHECKS, "database", lambda: None)
    monkeypatch.setitem(health.CHECKS, "cache", lambda: None)
    monkeypatch.setattr(health, "a_job_has_waited_too_long", lambda now: True)
    assert not health.worker_is_healthy()
    assert "Unhealthy: a job has waited over 0:05:00" in caplog.text


def test_the_worker_is_unhealthy_when_the_database_doesnt_answer(monkeypatch):
    monkeypatch.setitem(health.CHECKS, "database", fail)
    assert not health.worker_is_healthy()


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
