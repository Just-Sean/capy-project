# template/config/settings/environment.py

**What it is:** the first topic, which every other topic imports from.

- **`BASE_DIR`:** the project folder, three levels up from this file.
- **`env`:** the django-environ reader. It loads `.env` if one exists, but **real environment variables always win** over the file. `DJANGO_READ_DOT_ENV=false` skips the file, which the image build and the tests that start their own `manage.py` use.
- **`DJANGO_ENV`:** `development`, `test` or `production`.
  - **Unset means production,** the safest choice: a server with nothing set gets production's strict settings and required values.
  - Anything else, a typo like `prod` included, **refuses to start**.
- **`IS_DEVELOPMENT`, `IS_TEST`, `IS_PRODUCTION`:** the flags the other topics check.

Who sets it: `.env` sets `development` on your machine, pytest sets `test` (pytest-env, in `pyproject.toml`), and production leaves it unset.
