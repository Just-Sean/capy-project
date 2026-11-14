# template/compose.yaml.jinja → compose.yaml

**What it is:** the Docker Compose services every environment shares. Compose always combines it with a second file:

- **Development:** `docker compose up -d` loads `compose.override.yaml` on top, by itself.
- **Production:** `docker compose -f compose.yaml -f compose.prod.yaml ...` loads the production file instead.

`name: <slug>` names the development Compose project. Production overrides it with `<slug>-production`.

**`db`, PostgreSQL 18** (`postgres:18-trixie`, the official image):

- Its health check is `pg_isready` **over TCP** (`-h 127.0.0.1`), the way the app connects. On a brand-new database, Postgres first runs a setup server that only answers locally, so a local check would report ready too early.
- It's checked every 2 s while starting, so `up` is quick, then every 10 s.
- Extensions such as pgvector aren't included: a project that needs one changes the image.

**`redis`, Redis 8** (`redis:8-trixie`), Django's cache:

- **A cache only:** nothing is saved to disk (`--save ""`, `--appendonly no`). Memory is capped at 256 MB, and when it's full the least recently used keys are dropped (`allkeys-lru`).
- **Runs as the `redis` user**, never root.
- **Needs a login.** Django unpickles what it reads from the cache, so anyone who could write to an open Redis could run code in the app. At start, a small shell script writes an ACL file with three users:
  - `default` (no login): switched off.
  - `app`: Django's login (`CACHE_URL`), with every command except Redis's dangerous admin ones. `flushdb` is added back, because Django's `cache.clear()` uses it.
  - `healthcheck`: no password, and allowed only `PING`, for the health check.
- **The password stays hidden:** it comes from `REDIS_PASSWORD` and goes into that file, never onto the command line, so it never shows in the process list. The script stops at once if `REDIS_PASSWORD` is missing.
- **`$$`** passes `$` through to the container's shell instead of letting Compose fill the variable in.

Development's override and production's file add the logins, ports, networks and lockdown.
