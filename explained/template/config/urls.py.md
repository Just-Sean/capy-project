# template/config/urls.py

**What it is:** the root URL map. Every app you add plugs its own `urls.py` in here, e.g. `path("billing/", include("billing.urls"))`.

**What it maps:**

| Address | Goes to |
| --- | --- |
| `settings.ADMIN_URL` | Django's admin. The address comes from `DJANGO_ADMIN_URL`: `admin/` in development, and production refuses `admin/` |
| `csp-report/` | `config.csp_report.csp_report`: where browsers report what the CSP blocked |
| `media/<path:name>` | `config.uploads.download`: **private uploads**, checked on every request, in every environment |
| `/media-public/...` | Public uploads, **in development only**. Django's `static()` adds this route only when `DEBUG` is on. In production Caddy serves them (or S3 does) |

**There's no `/` view.** The error pages link to `/`, so a project should add a home page. Until it does, that link shows the 404 page.

`/healthz` and `/readyz` aren't here: `config/middleware.py` answers them before URL routing.
