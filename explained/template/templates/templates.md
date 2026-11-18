# template/templates/

**What it is:** the project-wide templates. `TEMPLATES["DIRS"]` in `settings/core.py` checks this folder before any app's own templates, so a file here replaces an app's file with the same name. Each app keeps its own templates in `<app>/templates/<app>/`.

| File | Shown when |
| --- | --- |
| `base.html` | Never on its own: the bare page every other page extends |
| `layout.html` | Never on its own: the site's layout (nav, messages, shell modules' lines), which the site's pages and plugged-in apps extend. The project's own file: `copier update` never changes it once it exists |
| `400.html` | A request the site can't use, e.g. a host name not in `ALLOWED_HOSTS` |
| `403.html` | Access denied (`PermissionDenied`) |
| `403_csrf.html` | A form failed its security check (`config/csrf_failure.py`) |
| `404.html` | No page at that address |
| `500.html` | The site crashed (the error is logged with its stack trace) |
| `proxy_error.html` | **Not Django's:** Caddy shows it when the app doesn't answer (502, 503, 504) |

**Shared rules** (for the error pages, which extend the bare `base.html`, never `layout.html`):

- **Minimal and accessible:** a title, a heading, a sentence saying what to do, and a link home. Every page has a title.
- **Nothing inline** (`<script>`, `<style>`, `style=`, `onclick=`), so the Content Security Policy never blocks anything. `tests/test_error_pages.py` checks every page.
- **No internal details:** no stack traces, settings or error text, even when the error message holds them.
- With debug on, Django shows its own detailed pages for 400, 404 and 500 instead. The 403 pages show either way.

**Mounted into Caddy:** production mounts this folder read-only at `/srv/errors`, but Caddy serves only `proxy_error.html` from it.
