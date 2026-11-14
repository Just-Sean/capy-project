# template/tests/test_compose.py

**What it tests:** the compose files. It copies them to a temporary folder with dummy `.env` files, then asks **Docker Compose itself** (`docker compose config`) for the final combined setup, so the checks see exactly what Compose would run. Docker must be installed, but nothing is started. `test_caddy.py` reuses its helpers.

**Development:**

- Postgres and Redis are reachable from this machine only (`127.0.0.1`).
- The database counts as ready only once it answers over TCP.

**Redis, in every environment:**

- It's a cache that saves nothing and stays within its memory.
- It needs a login, and keeps the password out of its command line.
- Its health check uses the `PING`-only login.

**Production:**

- It runs Postgres, Redis, `migrate`, the app, the worker and Caddy, as a separate project from development.
- **Secrets come only from the env files,** never written in the compose files.
- **Only Caddy is published,** and the app always runs behind it (`DJANGO_BEHIND_PROXY`).
- Caddy serves the uploads read-only and keeps its certificates in a volume.
- **Locked down:**
  - The app, Redis and Caddy have no capabilities and a read-only filesystem, and **nothing adds a capability back**.
  - Caddy has the unprivileged-port sysctl and is built from `deploy/caddy.Dockerfile`.
  - The app's in-memory `/tmp` has a size limit.
- **Networks:**
  - The database and Redis are only on the internal network.
  - Caddy's network has IPv6 on, so IPv6 visitors keep their own address.
- **Start order:** `migrate` runs once, with no health check, before the app and worker start. Those two wait for Redis too.
- **Every service:**
  - keeps limited logs
  - restarts after a crash
  - gets enough time to stop: the app longer than Gunicorn's 30 s, the worker 60 s to finish its job
- The worker has the app's files and its own health check.

**The local HTTP check:**

- Only `compose.local-http.yaml` turns the HTTPS settings off.
- It's reachable from this machine only.

Whether the Caddyfile itself is valid is checked in `test_caddy.py`.
