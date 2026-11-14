# template/tests/

**The project-wide tests**, run with `uv run pytest` (pytest and pytest-django). Every project starts with them, and they should keep passing as it grows. `accounts/tests.py` holds the `User` model's own tests.

**How they run:**

- **As the test environment:** pytest sets `DJANGO_ENV=test` itself, which means fast password hashing, an in-memory cache and email kept in memory.
- **On PostgreSQL:** start it with `docker compose up -d db`. pytest makes and deletes its own throwaway database. Redis isn't needed.
- **Some tests need Docker:**
  - `test_compose.py` asks Docker Compose to read the compose files.
  - `test_caddy.py` builds and runs production's Caddy image. The first run downloads it.
- **Some start real `manage.py` processes,** with other environment variables, to prove what production does at start-up. Settings are read once per process, so changing them needs a fresh one.
- **Strictly:**
  - Any Django deprecation fails the tests.
  - `uv run pytest --cov` fails below 80% coverage.
  - A model changed without its migration fails `test_migrations.py`.

| File | Covers |
| --- | --- |
| `test_production_settings.py` | Production is secure and refuses bad config |
| `test_settings_package.py` | The settings topic files combine correctly |
| `test_env_example.py` | `.env.example` lists exactly the variables the project reads |
| `test_ignore_files.py` | Secrets stay out of git and the image |
| `test_compose.py` | The compose files: dev stays local, production locked down |
| `test_caddy.py` | Caddy, really running: rate limits, uploads, hidden health checks, the error page |
| `test_gunicorn_config.py` | `gunicorn.conf.py` is valid |
| `test_security_headers.py` | Headers, the CSP and its nonce, Argon2, HSTS |
| `test_login_rate_limit.py` | Login lockouts per user and per address |
| `test_private_uploads.py` | The private download view |
| `test_uploaded_files.py` | Upload storage: local, public, S3 |
| `test_email.py` | Email in each environment |
| `test_tasks.py` | Background jobs |
| `test_healthz.py` | `/healthz` |
| `test_readyz.py` | `/readyz` and the worker's health check |
| `test_logs.py` | Log formats, for Django and Gunicorn |
| `test_csp_report.py` | The CSP report view |
| `test_error_pages.py` | The error pages |
| `test_deprecation_warnings.py` | Deprecations fail the tests |
| `test_migrations.py` | No missing migrations |

`__init__.py` is empty and makes the folder a package.

**A shared helper:** several files define the same small `last_line()` helper, which reads the last line a `manage.py` process printed. Moving it into one shared place is on the backlog.
