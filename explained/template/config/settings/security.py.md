# template/config/settings/security.py

**What it is:** HTTPS, the reverse proxy, security headers and the Content Security Policy (CSP).

**HTTPS, on by default in production only.** Each setting except preload can be changed with its own variable (`DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`):

- **Redirect** plain HTTP to HTTPS.
- **HTTPS-only** session and CSRF cookies.
- **HSTS** for one year, subdomains included, which tells browsers to use only HTTPS. On a brand-new domain, start with `DJANGO_SECURE_HSTS_SECONDS=3600`.
- **HSTS preload is off on purpose:** getting off browsers' preload list takes months. Django's warning about it (`security.W021`) is silenced for that reason, and the README lists the steps to opt in.

**Behind a proxy (`DJANGO_BEHIND_PROXY`):**

- Django trusts `X-Forwarded-Proto` to tell whether the visitor used HTTPS.
- `config/login_limits.py` uses the last `X-Forwarded-For` entry as the visitor's address.
- Production always sets it in `compose.prod.yaml`, because Caddy is always in front.
- Turn it on only behind a proxy you control that sets those headers.

**Headers on every response:**

- `X-Frame-Options: DENY`: never inside a frame.
- `Referrer-Policy: same-origin`.
- `Cross-Origin-Opener-Policy: same-origin`.
- `nosniff`, which Django sends by default.

`CSRF_FAILURE_VIEW` points to `config/csrf_failure.py`.

**The Content Security Policy (`SECURE_CSP`, Django's built-in one).** The browser loads only what's listed and blocks the rest, so code injected into a page doesn't run:

| Directive | Allows |
| --- | --- |
| `default-src` | Nothing. Anything not listed (frames, audio and video, workers, manifests) is blocked until a project allows it |
| `script-src`, `style-src` | This site, plus inline code carrying the page's **nonce** (`<script nonce="{{ csp_nonce }}">`) |
| `img-src` | This site, plus `data:` images: CSS frameworks such as daisyUI and Tailwind draw checkbox ticks and select arrows that way. An image can't run code |
| `font-src`, `connect-src` | This site |
| `object-src`, `frame-ancestors` | Nothing |
| `base-uri`, `form-action` | This site |
| `report-uri` | `/csp-report/`, where browsers report what was blocked (`config/csp_report.py`) |

- **`style="..."` attributes, `onclick=` handlers and files from other sites are blocked.** Put them in static CSS and JS files.
- A view that needs something from another site can set its own policy with `csp_override`. It replaces the whole policy, so build on `settings.SECURE_CSP`.
- **In development the policy only reports**, because Django's yellow debug pages use inline styles. The browser console still shows what it would block. Tests and production enforce it.
