# django-starter (the repo root)

**What it is:** a [Copier](https://copier.readthedocs.io/) template that makes new Django projects. Each new project starts secure and ready for production, as a shell you plug small reusable Django apps into. The repo itself isn't a Django project: it holds the files a new project is made from.

**How a project gets made:** `copier copy gh:Just-Sean/django-starter my-client-app` (the newest release) asks two questions (the project's name and its slug, see `copier.yml`). It then copies everything under `template/` into the new folder:

- Files ending in `.jinja` are filled in with the answers and lose the `.jinja` ending. For example, `compose.yaml.jinja` becomes `compose.yaml`, with the slug as the Compose project name.
- Every other file is copied unchanged.

Later, `copier update` inside the project pulls in the starter's improvements.

**How the repo is laid out:**

| Folder / file | Purpose |
| --- | --- |
| `template/` | **What new projects get.** Everything in it becomes a project file. |
| `copier.yml` | Copier's settings: the two questions, and that only `template/` is copied. |
| `README.md` | How to make and update a project, the notes for each update, and how to work on the starter. |
| `.gitignore` | Files the starter repo itself never commits. |
| `.pre-commit-config.yaml` | The starter repo's own commit check (gitleaks). |
| `explained/` | This folder: a file-by-file explanation of the starter. It sits outside `template/`, so projects never get it. |

**Not in git:**

- `.git/`: git's own history database.
- `.ruff_cache/`: Ruff's cache, from running it here.

**What a generated project contains:**

- **The Django app:** `config/` (settings, URLs, health checks, logs, private uploads) and `accounts/` (the custom `User`).
- **Templates:** `templates/`, with `base.html`, the error pages and the proxy's error page.
- **Tests:** `tests/`.
- **Development:** Docker Compose runs PostgreSQL 18 and Redis 8, and Django runs on your machine with `runserver`.
- **Production:** Docker Compose runs Postgres, Redis, a migrate step, the app under Gunicorn, a background-job worker, and Caddy in front for HTTPS and rate limits.

**How the pieces connect:** a visitor reaches Caddy, which passes the request to Gunicorn. Gunicorn runs Django, which uses PostgreSQL for data and Redis as its cache. Background jobs wait in PostgreSQL until the worker runs them. Secrets and every value that differs between environments come from environment variables (`.env` files), never from the code; the rest of the settings are fixed in `config/settings/`.
