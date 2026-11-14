# template/compose.local-http.yaml

**What it is:** a third Compose file, **only for trying production on your own machine**. A laptop has no domain or certificate, so this runs production over plain HTTP at <http://localhost:8000>:

```bash
docker compose -f compose.yaml -f compose.prod.yaml -f compose.local-http.yaml up --build
```

**What it changes:**

- **`web`:** turns off the HTTPS redirect, the HTTPS-only cookies and HSTS. They're set here rather than in `.env.production`, so that file stays exactly as a server would have it.
- **`caddy`:** `SITE_ADDRESS` becomes `:80`, plain HTTP for any host name. The ports are replaced (`!override`) with `127.0.0.1:8000:80`, so only this machine reaches it. `!override` needs Docker Compose 2.24.4 or later.

**Never use it on a server:** it switches off HTTPS and its protections. `tests/test_compose.py` checks that only this file turns them off, and that the local check is only reachable from this machine.

It has no `.jinja` ending because it needs nothing from Copier.
