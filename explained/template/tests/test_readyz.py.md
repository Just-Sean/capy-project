# template/tests/test_readyz.py

**What it tests:** `/readyz` and the worker's health check, both in `config/health.py`.

**`/readyz`:**

- It's `ok` when the database and cache answer, and **503** when either doesn't. The failure is logged, without connection details.
- **With the database down, it says so quickly**, and `/healthz` still answers.
- It gives up on a database that **accepts the connection but never answers**. The test uses a fake server that does exactly that.
- Database connections time out after 5 s, and `DATABASE_URL` can set its own timeout.
- The database check uses its own new connection, not the request's.

**The worker's check:**

- It's **stuck** once a job has waited too long with none started.
- A worker catching up on a backlog isn't stuck.
- Finished jobs don't count.
- A job set to run later counts from when it may run, and one enqueued just now with a past `run_after` hasn't waited yet.
- Jobs in a queue the worker doesn't serve don't count.
- It's unhealthy when it's stuck, or when the database doesn't answer. **It doesn't need Redis.**
- **The real Docker command** (`python -m config.health worker`) fails when the database is down, and explains its usage when run wrong.
