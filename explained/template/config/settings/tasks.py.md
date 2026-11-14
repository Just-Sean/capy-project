# template/config/settings/tasks.py

**What it is:** where background jobs go, using Django's built-in Tasks API. Jobs are written with `@task` and started with `.enqueue(...)`.

| Environment | `TASKS` backend | What happens |
| --- | --- | --- |
| Production | `django_tasks_db.DatabaseBackend` | The job is stored in PostgreSQL. The `worker` service (`manage.py db_worker`) runs it, in its own process, so a slow job never holds up a request |
| Development and tests | Django's `ImmediateBackend` | The job runs straight away, inside the request or test that enqueued it, so there's no worker to start |

**Why the database, not Redis:** Redis here is a cache that saves nothing to disk, so jobs waiting in it would be lost on a restart.

The README's Background jobs section covers what differs between the two: delayed jobs, looking results up, JSON-only arguments, cleaning up old jobs, and keeping each job under 60 s.
