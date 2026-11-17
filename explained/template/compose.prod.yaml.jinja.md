# template/compose.prod.yaml.jinja → compose.prod.yaml

**What it is:** production. Run it with `docker compose -f compose.yaml -f compose.prod.yaml up --build -d --wait`. It's a separate Compose project, `<slug>-production`, with its own volumes, so it never touches development's data, even on the same machine.

**Settings and secrets** come from four files next to it, never from this file or the image:

| File | Read by |
| --- | --- |
| `.env.production` | The app, the worker and `migrate` |
| `.env.postgres` | Postgres |
| `.env.redis` | Redis |
| `.env.caddy` | Caddy |

**Shared blocks (YAML anchors):**

- **`x-logging`:** every service keeps at most 50 MB of logs: 10 MB files, 5 of them, the full ones compressed. Without a limit, a busy or attacked site could fill the disk and stop the database.
- **`x-app`:** the app image as `migrate`, `web` and `worker` all run it:
  - built from `.`, named `<slug>-web`, reading `.env.production`
  - **locked down:** no Linux capabilities (`cap_drop: [ALL]`), `no-new-privileges`, and a **read-only filesystem**
  - `/tmp` in memory, capped at 64 MB (uploads are received there)

**The services, in start order:**

| Service | What it does |
| --- | --- |
| `db` | Postgres. On the internal `backend` network only, with no published port. Keeps `pgdata`. Mounts `deploy/postgres-app-user.sh`, which makes the app's own login (not a superuser) when the database is first created; `.env.postgres` holds both logins. Not capability-dropped, because its entrypoint starts as root to set up its data folder |
| `redis` | The cache, locked down like the app. `/data` is in memory, owned by the redis user, and holds only the login file |
| `migrate` | Applies migrations, then exits. Waits for a healthy `db`. Has no health check |
| `web` | The app (Gunicorn). Starts **only if `migrate` succeeded** and Redis is healthy |
| `worker` | Runs background jobs (`manage.py db_worker`). Starts like `web`, with the same uploads |
| `caddy` | The reverse proxy, and the only service the internet reaches |

**`web` in more detail:**

- It's on `backend`, to reach the database and Redis, and on `default`, where Caddy reaches it and it can reach the internet (mail, S3).
- **It has no published port.**
- It sets `DJANGO_BEHIND_PROXY=true` and `DJANGO_MEDIA_SENT_BY_PROXY=true`: Caddy is always in front, and sends private files once the app allows them.
- Its uploads are the `media` (private) and `media_public` volumes.
- `stop_grace_period: 35s`, longer than Gunicorn's 30, so requests in progress finish.

**`worker` in more detail:**

- Its own health check, `python -m config.health worker`, every 60 s (see `config/health.py`).
- `stop_grace_period: 60s`, so the job in progress can finish.

**`caddy` in more detail:**

- Built from `deploy/caddy.Dockerfile` as `<slug>-caddy`. Its config comes from `deploy/Caddyfile`, and `SITE_ADDRESS` from `.env.caddy`.
- Locked down: its own non-root user, no capabilities, `no-new-privileges`, and a read-only filesystem.
- `net.ipv4.ip_unprivileged_port_start: 0` lets that user listen on ports 80 and 443 inside its container, with no capability.
- It starts once `web` has **started**, not once it's healthy. If the app can't start, visitors still get the error page instead of nothing.
- Its health check calls Caddy's admin API inside the container.
- Publishes 80, 443 and 443/udp (HTTP/3).
- Its mounts are all read-only, apart from its own volumes:
  - `deploy/`
  - `templates/`, for `proxy_error.html`
  - both upload volumes
  - its own `caddy_data` (certificates: keep it) and `caddy_config`

**Networks:**

- **`backend`** is `internal`: the database and Redis can't reach the internet.
- **`default`** has `enable_ipv6: true`. Docker then passes IPv6 visitors' own addresses to Caddy. Otherwise they'd all arrive from one address and share one rate limit. Docker Engine 27 or later picks the IPv6 address range by itself; older engines need one set by hand.

**Volumes:** `pgdata`, `media`, `media_public`, `caddy_data` and `caddy_config`. Back up the first three (see the README's Backups section).

**Checked by:** `tests/test_compose.py`.
