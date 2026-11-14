# template/deploy/Caddyfile

**What it is:** Caddy's configuration: everything the proxy in front of the app does. `{$SITE_ADDRESS}` comes from `.env.caddy`. Caddy gets and renews the HTTPS certificate for that domain from Let's Encrypt by itself, and redirects plain HTTP to HTTPS.

**Global options (the top block):**

- `admin 127.0.0.1:2019`: Caddy's admin API, which can change its config, answers only inside the container. The health check uses it.
- The admin API's own log lines are left out, so there's no line per health check.
- `order rate_limit before basic_auth`: rate limits run first, before anything else answers.

**Reusable snippets:**

| Snippet | What it does |
| --- | --- |
| `(security_headers)` | `nosniff`, `X-Frame-Options DENY` and `Referrer-Policy same-origin` on what Caddy serves itself, each only if the app hasn't set it (`?`). Removes `Server` and `Via`, so nothing names Caddy. HSTS is left to the app's setting, so there's one place to change it |
| `(download_headers)` | Every upload is sent as a download (`Content-Disposition: attachment`) with `nosniff` and a sandboxing CSP, so an uploaded HTML or SVG file can't run scripts on the site. Must match `DOWNLOAD_HEADERS` in `config/uploads.py` |
| `(app_proxy)` | How Caddy talks to the app (below) |

**How Caddy talks to the app (`app_proxy`):**

- It takes in the first 1 MB of each request and response at once, so a slow visitor ties up Caddy, which handles many at a time, not one of Gunicorn's few workers.
- During a restart, it retries the app for up to 10 s.

**The site block, in order:**

1. **Access log:** one JSON line on stdout per request Caddy answers itself. Query strings and headers are removed. Requests the app answers are skipped (`log_skip`), because Gunicorn logs those.
2. **Rate limits,** per visitor address (`{remote_host}`), each over one minute. Over a limit, the visitor gets a **429 with `Retry-After`**:

   | Zone | Limit | Counts |
   | --- | --- | --- |
   | `per_visitor` | 600 | Every request |
   | `form_posts` | 30 | `POST`s, except CSP reports: against password guessing |
   | `csp_reports` | 120 | `/csp-report/`, apart from the rest, so the reports browsers send by themselves never use up a visitor's form posts |

3. **`request_body max_size 10MB`:** bigger requests get a 413 before reaching the app. Raise it together with the app's `/tmp` size in `compose.prod.yaml`.
4. **`/healthz` and `/readyz`:** a 404 from outside. Otherwise anyone could see when the database is down, and each call costs a database and Redis query.
5. **`/media-public/*`:** public uploads, straight from the `media_public` volume, as downloads. Folders are never listed, and no `index.html` is served for one.
6. **`/media/*`:** private uploads go **to the app**, which checks who's asking (`config/uploads.py`). If the app allows the request, it answers with the file's name in `X-Accel-Redirect`. Caddy then sends that file from the `media` volume itself, adding:
   - the download headers
   - `Cache-Control: private, no-store`
   - the app's `Set-Cookie` and HSTS headers

   Only the app's response can name a file, and only on this route.
7. **Everything else:** forwarded to the app (`web:8000`). Any `X-Accel-Redirect` the app sends here is dropped, so no other page can make Caddy send a file.
8. **`handle_errors 502 503 504`:** when the app doesn't answer, visitors get `templates/proxy_error.html` with the real status. It's sent with the security headers, a strict CSP and `no-store`.

**Checked by:** `tests/test_caddy.py`, which validates it with `caddy validate` and then runs it and tests each behavior above.
