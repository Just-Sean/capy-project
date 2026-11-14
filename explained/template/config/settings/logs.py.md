# template/config/settings/logs.py

**What it is:** where logs go and in which format. The formats themselves are in `config/logging.py`.

- **Everything goes to the console,** where `runserver`, Docker, systemd or a hosting platform collects it.
- **JSON lines in production, readable text** in development and tests.
- **The level** comes from `DJANGO_LOG_LEVEL`, `INFO` by default. Set `WARNING` for less, or `DEBUG` for more, briefly: some libraries log request headers at `DEBUG`.
- **The `django` logger** gets the same single console handler. This replaces two Django defaults:
  - a second console handler in development, which printed each line twice
  - emailing request errors to `ADMINS`

  So **errors are never emailed**, even if `ADMINS` is set. They're logged with their stack trace instead.
- **In production, Python's warnings** (e.g. "received a naive datetime") are logged too, so they're JSON lines like everything else.

Gunicorn's own logging is set separately, in `gunicorn.conf.py`, with the same JSON format.
