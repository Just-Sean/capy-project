"""Background jobs: they run straight away in development and tests, and production
stores them in the database for the worker (`manage.py db_worker`) to run."""

import pytest
from django.core.management import call_command
from django.tasks import TaskResultStatus, task

from tests.test_production_settings import run_manage

DATABASE_BACKEND = "django_tasks_db.DatabaseBackend"
IMMEDIATE_BACKEND = "django.tasks.backends.immediate.ImmediateBackend"
PRINT_BACKEND = "from django.conf import settings; print(settings.TASKS['default']['BACKEND'])"


@task
def add(a, b):
    return a + b


def last_line(result):
    return result.stdout.strip().splitlines()[-1]


def test_a_job_runs_straight_away_in_tests():
    result = add.enqueue(2, 3)
    assert result.status == TaskResultStatus.SUCCESSFUL
    assert result.return_value == 5


@pytest.mark.parametrize(
    ("environment", "backend"),
    [({}, DATABASE_BACKEND), ({"DJANGO_ENV": "development"}, IMMEDIATE_BACKEND)],
    ids=["production", "development"],
)
def test_production_stores_jobs_for_the_worker_and_development_runs_them(environment, backend):
    result = run_manage("shell", "-c", PRINT_BACKEND, **environment)
    assert last_line(result) == backend, result.stderr


@pytest.mark.django_db(transaction=True)  # the worker closes connections, as in production
def test_the_worker_runs_a_stored_job(settings):
    settings.TASKS = {"default": {"BACKEND": DATABASE_BACKEND}}
    result = add.enqueue(2, 3)
    assert result.status == TaskResultStatus.READY  # stored, waiting for the worker

    call_command("db_worker", "--batch", "--no-startup-delay")  # run every waiting job

    result.refresh()
    assert result.status == TaskResultStatus.SUCCESSFUL
    assert result.return_value == 5


@pytest.mark.django_db(transaction=True)  # the worker closes connections, as in production
def test_a_failing_job_is_recorded_as_failed(settings):
    settings.TASKS = {"default": {"BACKEND": DATABASE_BACKEND}}
    result = add.enqueue(2, "three")  # 2 + "three" raises TypeError

    call_command("db_worker", "--batch", "--no-startup-delay")

    result.refresh()
    assert result.status == TaskResultStatus.FAILED
    assert result.errors[0].exception_class is TypeError
