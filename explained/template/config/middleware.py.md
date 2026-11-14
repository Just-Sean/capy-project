# template/config/middleware.py

**What it is:** `health_checks`, the first middleware in `MIDDLEWARE`. It answers two addresses before any other code runs:

| Path | Answers |
| --- | --- |
| `/healthz` | Always `ok`, while the process is up. **It never touches the database or Redis**, so a database outage doesn't mark every app container unhealthy. Docker's `HEALTHCHECK` uses it |
| `/readyz` | `ok` only when the database and Redis answer (`config.health.failing_checks()`), else **503 `not ready`**. For a load balancer in front of several app servers |

**Why first in the list:** it runs before Django's host check, the HTTPS redirect and sessions. Load balancers and Docker call by IP address, often over plain HTTP, and those checks would refuse them. Every other request passes straight through.

Both answers are plain text with `Cache-Control: no-store`, so nothing caches a stale answer. Neither gets the security headers, which the README notes. Caddy hides both from the public with a 404 (`deploy/Caddyfile`).
