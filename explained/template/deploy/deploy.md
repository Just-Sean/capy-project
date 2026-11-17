# template/deploy/

**What it is:** production's server-side files: the reverse proxy's (Caddy runs in front of the app, the `caddy` service in `compose.prod.yaml`) and the database's first-start script.

| File | Purpose |
| --- | --- |
| `Caddyfile` | Caddy's settings: HTTPS, rate limits, forwarding to the app, uploads, the error page, hidden health checks, logs |
| `caddy.Dockerfile` | Caddy's image: the official one plus the rate-limit plugin, running as its own user |
| `postgres-app-user.sh` | Run once by Postgres when it first creates its data: makes the app's own login, not a superuser (`db` mounts it) |
| `postgres-app-user-upgrade.sql` | Run once by hand on a database made before v1.0.0: the same login, given everything the app made, and a new superuser password |

**Two ways this folder is used:**

- **Mounted into Caddy, read-only:** at `/etc/caddy`. The whole folder is mounted rather than the single file: a mounted single file stays the old copy in a running container after git or Copier replaces it.
- **As Caddy's build context:** `compose.prod.yaml` builds `caddy.Dockerfile` from here, so the image build sees only these few small files. (Caddy also sees the two Postgres files there, read-only; they hold no secrets and Caddy never runs them. `db` mounts `postgres-app-user.sh` as a single file, which is fine although a single mounted file isn't refreshed in a running container: Postgres reads it only once, when it first creates its data.)

**After changing the Caddyfile:**

1. Validate it with `caddy validate`.
2. Recreate Caddy (the README has both commands). A normal deploy doesn't reload it.
