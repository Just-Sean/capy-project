# template/config/settings/core.py

**What it is:** the settings every Django project has.

**Debug and the required values:**

- `DEBUG` (`DJANGO_DEBUG`) is on in development and off elsewhere. **Production refuses to start with it on.**
- **In production, required, with no default:**
  - `SECRET_KEY` (`DJANGO_SECRET_KEY`)
  - `ALLOWED_HOSTS` (`DJANGO_ALLOWED_HOSTS`)
  - `ADMIN_URL` (`DJANGO_ADMIN_URL`), and **never `admin/`**, so bots don't find the admin at its usual address
- **Elsewhere, defaults:** a clearly fake secret key, local host names, and `admin/`.
- `CSRF_TRUSTED_ORIGINS` (`DJANGO_CSRF_TRUSTED_ORIGINS`) is empty by default.

**`INSTALLED_APPS`, the list a new app is added to** (step 2 of "Adding a reusable app" in the README):

- `accounts` comes first: your apps go at the top, so their templates override third-party ones.
- Django's admin, auth, contenttypes, sessions, messages and staticfiles.
- `axes`, for login rate limiting.
- `whitenoise.runserver_nostatic`, placed before staticfiles: WhiteNoise then serves static files in development too, with the same headers (and CSP) as production.
- `django_tasks_db`, for background jobs.

**`MIDDLEWARE`, in order:**

1. **`config.middleware.health_checks`:** first, so `/healthz` and `/readyz` skip host checks and redirects.
2. Security.
3. **The CSP:** sends `SECURE_CSP`.
4. **WhiteNoise:** right after the headers, so static files carry them.
5. Sessions, common, CSRF, auth, messages and clickjacking.
6. **`axes.middleware.AxesMiddleware`:** last; turns a lockout into the "too many attempts" page.

**`TEMPLATES`:**

- The root `templates/` folder (`BASE_DIR / "templates"`) is checked before apps' own templates, so `base.html` and the error pages there replace any app's file with the same name.
- The `csp` context processor gives every template `{{ csp_nonce }}`.

**Time and language:** `en-us`, `UTC`, and `USE_TZ = True`, so every datetime is stored in UTC.
