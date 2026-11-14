# template/tests/test_tasks.py

**What it tests:** background jobs.

- In tests (as in development), **a job runs straight away** when it's enqueued.
- Production's settings store jobs in the database for the worker. Development's run them at once.
- **The worker:**
  - It runs a stored job to completion.
  - It records a failing job as failed, with its error.
  - Running it inside a test gives Ctrl+C and the stop signals back afterwards. The worker takes them over, and otherwise Ctrl+C would stop later tests wrongly.

It uses a tiny `add(a, b)` job, with the database backend switched on for the worker tests. The worker runs in batch mode (`db_worker --batch`): it runs every waiting job, then stops.
