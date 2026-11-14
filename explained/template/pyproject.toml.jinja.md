# template/pyproject.toml.jinja → pyproject.toml

**What it is:** the project's Python setup: its dependencies and every tool's settings. Copier fills in the name (the slug) and the description (the project's name).

**Dependencies** (installed in production too):

| Package | For |
| --- | --- |
| `django>=6.1.3,<6.2` | The framework, kept within 6.1 |
| `psycopg[binary]` | The PostgreSQL driver |
| `django-environ` | Reading settings from environment variables and `.env` |
| `gunicorn` | The production server |
| `whitenoise` | Serving static files, with the same security headers |
| `redis` | The client for Django's built-in Redis cache |
| `argon2-cffi` | Argon2 password hashing |
| `django-axes` | Login rate limiting |
| `django-storages[s3]` | Uploads in S3, when chosen |
| `django-tasks-db==0.13.0` | Background jobs stored in the database. **Pinned exactly**, because it's pre-1.0 and a new version could change its tables or worker |

**Dev tools** (`[dependency-groups] dev`, never in the image): pytest, pytest-django, pytest-env, pytest-cov, Ruff, pre-commit and pip-audit.

**Tool settings:**

- **`[tool.uv] package = false`:** an application, not a library to publish.
- **pytest:**
  - Uses `config.settings` and always sets `DJANGO_ENV=test` (pytest-env).
  - Finds both `tests.py` and `tests/test_*.py`.
  - **Turns every Django deprecation warning into an error** (`RemovedInNextVersionWarning`, `RemovedAfterNextVersionWarning`), so an upgrade never surprises you. Other libraries' deprecations don't fail.
- **Ruff:**
  - 100-character lines, Python 3.14, migrations excluded.
  - Rules: errors and style, import order, likely bugs (`B`), **security (`S`)**, Django (`DJ`) and modern syntax (`UP`).
  - Test files may use `assert`, dummy passwords and `subprocess`.
- **Coverage:**
  - Measures the project's code, not tests, migrations or `.venv`.
  - Measures both sides of every `if`, and the Django processes some tests start (`patch = ["subprocess"]`).
  - **Fails below 80%.**

**`uv.lock`**, made from this file by `uv sync`, pins every exact version and hash. It's committed in each project, and the image installs exactly what it lists.
