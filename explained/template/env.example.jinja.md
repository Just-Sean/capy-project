# template/.env.example.jinja → .env.example

**What it is:** the documented list of every environment variable the project reads, with a comment explaining each one. In a new project it becomes `.env.example`, the only `.env` file git keeps. (This page drops the leading dot from its own name: see `template.md`.)

**How it's used:**

- **Development:** `cp .env.example .env` is the first setup step. Its active lines set `DJANGO_ENV=development`, plus a `DATABASE_URL` and a `CACHE_URL` that match the development login in `compose.override.yaml` (`app`/`app`). Every other variable is a commented-out example.
- **Production:** never copied as a whole, because it sets `DJANGO_ENV=development`. You copy the lines you need into `.env.production` (see the project README's Production section).

**What it covers,** grouped as the code reads them:

- **Environment:** `DJANGO_ENV`, `DJANGO_READ_DOT_ENV` and `DJANGO_DEBUG`.
- **Core:** `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL` and `DJANGO_CSRF_TRUSTED_ORIGINS`.
- **Database and cache:** `DATABASE_URL`, `DJANGO_CONN_MAX_AGE` and `CACHE_URL`, plus `POSTGRES_PORT` and `REDIS_PORT`, which development's Compose file reads if the default port is taken.
- **Security and proxy:**
  - `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE` and `DJANGO_CSRF_COOKIE_SECURE`
  - `DJANGO_SECURE_HSTS_SECONDS` and `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
  - `DJANGO_BEHIND_PROXY`
- **Login limits:** `DJANGO_LOGIN_FAILURE_LIMIT`, `DJANGO_LOGIN_IP_FAILURE_LIMIT` and `DJANGO_LOGIN_LOCKOUT_MINUTES`.
- **Uploads:**
  - `DJANGO_MEDIA_STORAGE` and `DJANGO_MEDIA_SENT_BY_PROXY`
  - the `DJANGO_MEDIA_S3_*` settings
  - `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- **Email:** `EMAIL_URL` and `DJANGO_DEFAULT_FROM_EMAIL`.
- **Logs and server:** `DJANGO_LOG_LEVEL` and `WEB_CONCURRENCY`.

**Kept honest by a test:** `tests/test_env_example.py` fails if:

- a variable read anywhere in the project's Python or Compose files is missing
- a listed variable is read nowhere
- a variable is listed twice
- a line is something django-environ would misread
- a true/false value isn't a word django-environ knows

**Not in it:** the production-only Docker files' variables (`POSTGRES_*`, `REDIS_PASSWORD` and `SITE_ADDRESS`). Those live in `.env.postgres`, `.env.redis` and `.env.caddy`, which the README explains.
