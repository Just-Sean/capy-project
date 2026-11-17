# template/tests/test_production_settings.py

**What it tests:** production is secure, and refuses to start when it's misconfigured. Each check runs `manage.py` in its own process, with production's environment variables (`PRODUCTION_ENV`) changed one at a time:

- **Passes Django's deployment checklist:** `check --deploy` gives no warnings.
- **Debug** is off by default, and turning it on refuses to start.
- **Refuses to start without:** a secret key, allowed hosts or a cache. Development also needs the cache.
- **Refuses** the default `admin/` URL, and a misspelled `DJANGO_ENV`.
- **The cache:**
  - Production caches in Redis and gives up after 2 s.
  - Options in `CACHE_URL` are kept.
  - Anything that isn't Redis is refused.
- **Development** starts with only `DATABASE_URL` and `CACHE_URL` set.
- **pytest** runs as the test environment, and caches in memory without Redis.
- **Static files:** development, with debug on or off, renders `{% static %}` and serves the file without `collectstatic`; production keeps the compressed, cache-busting storage.
- **The CSP's images:** production (also with `DJANGO_ENV` set explicitly) enforces `img-src 'self' data:`; development only reports the same policy.

The processes it starts use the same deprecation rules as pytest (`MANAGE_WITH_WARNINGS_AS_ERRORS`), which `test_deprecation_warnings.py` checks.
