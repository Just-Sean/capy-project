# template/templates/proxy_error.html

**What it is:** the "Temporarily unavailable" page. **It's not a Django template:** Caddy shows it itself when Django doesn't answer (502, 503 or 504), e.g. during a deploy's restart or when the app is down. The visitor gets the real status code (`handle_errors` in `deploy/Caddyfile`).

**Complete on its own:** a whole HTML page, loading nothing (no CSS, scripts or images), because the app it would load from isn't answering. It matches `base.html`'s light and dark look. Caddy sends it with a strict CSP and `Cache-Control: no-store`.

**After changing it,** restart Caddy so it serves the new version (see the README's Production section).

**With nginx instead of Caddy,** the README shows the two lines that serve the same page.
