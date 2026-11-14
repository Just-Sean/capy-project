# template/deploy/

**What it is:** the reverse proxy's files. Production runs Caddy in front of the app (the `caddy` service in `compose.prod.yaml`).

| File | Purpose |
| --- | --- |
| `Caddyfile` | Caddy's settings: HTTPS, rate limits, forwarding to the app, uploads, the error page, hidden health checks, logs |
| `caddy.Dockerfile` | Caddy's image: the official one plus the rate-limit plugin, running as its own user |

**Two ways this folder is used:**

- **Mounted into Caddy, read-only:** at `/etc/caddy`. The whole folder is mounted rather than the single file: a mounted single file stays the old copy in a running container after git or Copier replaces it.
- **As Caddy's build context:** `compose.prod.yaml` builds `caddy.Dockerfile` from here, so the image build sees only these two small files.

**After changing the Caddyfile:**

1. Validate it with `caddy validate`.
2. Recreate Caddy (the README has both commands). A normal deploy doesn't reload it.
