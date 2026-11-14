# template/config/health.py

**What it is:** the health checks themselves. They're used by `/readyz` (through `middleware.py`) and by the job worker's Docker health check.

**The two checks (`CHECKS`):**

- **`database_answers`:** runs `SELECT 1` over a **new connection** each time, not the request's kept one. A database that stops answering a kept connection could hold the check forever; a new one gives up after `connect_timeout` (5 s, see `settings/database.py`).
- **`cache_answers`:** reads a key from Redis. A missing key is fine, since any read proves Redis answered.

**`failing_checks(names=None)`:** runs the checks and returns the names of those that failed. Each failure is logged as `Not ready: database failed (OperationalError)`, with **the error's type only**, because its message can contain connection details.

**The worker's check:** `python -m config.health worker`, every 60 s, set in `compose.prod.yaml`. It exits 0 when healthy, 1 when not:

- **Unhealthy when the database doesn't answer.** Redis isn't checked, because the worker doesn't need it.
- **Unhealthy when it's stuck:** a job has waited longer than `MAX_JOB_WAIT` (5 minutes) **and** no job has started in that time. A busy worker catching up on a backlog keeps starting jobs, so it stays healthy.
  - "Waited" counts from when the job was enqueued, or from its `run_after` if that's later.
  - Only the `default` queue and backend count, the ones `db_worker` serves.

**Tied to django-tasks-db's internals:** `get_date_max()` is the value that package stores for "run as soon as possible". It's pinned to 0.13.0 for this reason, and `tests/test_readyz.py` fails if a new version changes it.

**Why `logging.getLogger("config.health")` is named in full:** run as `python -m config.health`, the module's `__name__` would be `__main__`.
