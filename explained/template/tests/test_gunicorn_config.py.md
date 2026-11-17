# template/tests/test_gunicorn_config.py

**What it tests:** `gunicorn.conf.py`, loaded the way Gunicorn loads it.

- **Every name in the file is a real Gunicorn setting,** so a typo can't be silently ignored.
- **Gunicorn accepts every value.**
- The production values are as intended: 2 workers by default, timeouts, worker recycling, logs and the control socket.
- **It listens only on `127.0.0.1:8000`,** even when a host sets `PORT`.
- The number of workers comes from `WEB_CONCURRENCY`, and a value that isn't a number fails loudly.
