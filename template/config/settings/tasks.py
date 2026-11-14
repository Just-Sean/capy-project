"""Background jobs, with Django's Tasks API: where enqueued jobs go."""

from .environment import IS_PRODUCTION

if IS_PRODUCTION:
    # Stored in the database and run by the worker (`manage.py db_worker`), a separate
    # process, so a slow job never holds up a request.
    TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
else:
    # Development and tests: each job runs straight away, inside the request or test
    # that enqueued it, so there's no worker to start.
    TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}
