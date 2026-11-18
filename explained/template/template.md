# template/

**What it is:** everything a new project gets. Copier copies this folder's contents into the new project's root folder (see `copier.yml`). Files ending in `.jinja` are filled in with the project's name and slug, then lose the `.jinja` ending.

**What's in it** (as named in a generated project):

| Folder / file | Purpose |
| --- | --- |
| `config/` | The Django project: settings (one file per topic), URLs, entry points and the project's own small modules |
| `accounts/` | The custom `User` model |
| `templates/` | `base.html`, `layout.html` (the site's layout, the project's own file), the error pages, and the page Caddy shows when the app is down |
| `static/` | The site's own static files: `site.css`, loaded on every page |
| `tests/` | The project-wide tests |
| `deploy/` | Caddy's config (`Caddyfile`) and its image (`caddy.Dockerfile`) |
| `manage.py` | Django's command runner |
| `gunicorn.conf.py` | The production server's settings |
| `Dockerfile` | The production image for the app, the migrate step and the worker |
| `compose.yaml` | What every environment shares: Postgres and Redis |
| `compose.override.yaml` | Development's additions, loaded automatically |
| `compose.prod.yaml` | Production: every service, locked down |
| `compose.local-http.yaml` | Runs production on your machine over plain HTTP, for checking it |
| `pyproject.toml` | Dependencies and tool settings |
| `.python-version` | The Python version uv installs |
| `README.md` | The project's own manual |
| `.env.example` | Every environment variable, documented |
| `.gitignore`, `.dockerignore` | What git, and the image, leave out |
| `.pre-commit-config.yaml` | The checks run on every commit |
| `.github/dependabot.yml` | Weekly dependency update pull requests |
| `.copier-answers.yml` | The answers given to Copier, for `copier update` |

**Made in a project, never in the template:** `uv.lock` (by `uv sync`), `.venv/`, `.env` and the production `.env.*` files, `media/`, `media-public/` and `staticfiles/`.

**A naming note for this folder:** the page for `.env.example.jinja` is called `env.example.jinja.md`, without the leading dot. The starter's `.gitignore` ignores every file whose name starts with `.env`, so a page with the dot in its name would never be committed.
