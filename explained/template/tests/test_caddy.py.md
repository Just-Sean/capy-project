# template/tests/test_caddy.py

**What it tests:** `deploy/Caddyfile`, **really running**. It builds production's Caddy image from `deploy/caddy.Dockerfile` and starts containers locked down as `compose.prod.yaml` runs them: no capabilities, read-only, the unprivileged-port sysctl, plus sample uploads. The containers answer over plain HTTP (`SITE_ADDRESS=:80`) on a local port. The config check uses a real domain, so HTTPS is part of what it checks. Docker must be installed, and the first run downloads the Caddy images.

**Containers it starts:**

- **Caddy with no app behind it** (`caddy_down`).
- **Caddy with a small stand-in app** on a shared Docker network (`caddy_with_app`). The stand-in is another Caddy, which answers every request the way the real app answers someone it allows: it names a private file in `X-Accel-Redirect` and renews the session cookie.
- **A fresh Caddy for each rate-limit test** (`fresh_caddy`), so the counters start at zero.

Every container is removed afterwards, with its volumes, and Caddy's logs are shown if it fails to start.

**What it proves:**

- **Caddy runs as its own user,** not root, and the config is valid.
- **Rate limits:**
  - Too many form posts get a 429, while pages still load.
  - CSP reports have their own limit and never use up a visitor's form posts.
  - A flood of requests gets a 429.
- **Health checks** (`/healthz`, `/readyz`) are a 404 from outside.
- **Public uploads** are downloads that can't run scripts, and folders are never listed or served by an `index.html`.
- **Private uploads:**
  - They're **never** served by their path.
  - Once the app names one in `X-Accel-Redirect`, it's sent as a download, with the app's cookies.
  - That handoff works **only for `/media/` addresses**.
- **Requests over 10 MB** get a 413.
- **With the app down,** visitors get the site's own page with the real status, and no header names Caddy.
