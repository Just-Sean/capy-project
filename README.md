# Django starter (Copier template)

A minimal, production-ready Django starting point. Every project made from it
gets only what has to exist on day one:

- PostgreSQL 18 (the official image) in Docker; extensions such as pgvector are added
  per project when one needs them
- Redis 8 as Django's cache (`CACHE_URL`), with a login: it saves nothing to disk, and in
  production only the app can reach it
- Docker Compose for development and production: a shared base, a development override,
  and a production file with secrets from env files and a separate migrate step
- A custom `User` model (`accounts.User`) with a unique, lowercase email and a public UUID
- Settings driven by environment variables (django-environ), one file per topic in
  `config/settings/`, secure by default:
  Argon2 passwords, login rate limiting (django-axes), a strict Content Security Policy
  with nonces, HSTS in production and the standard security headers
- Uploaded files on local disk by default, or in S3 (or any S3-compatible service) with
  private files, expiring signed links and no overwriting (django-storages)
- Email set by one `EMAIL_URL`: printed in development, captured in tests, optional in
  production and only over an encrypted connection there
- Background jobs with Django's Tasks API: run straight away in development and tests,
  stored in the database and run by a worker service in production (django-tasks-db)
- Health checks: `/healthz` (the app runs) for Docker, `/readyz` (the database and Redis
  answer) for load balancers, and one for the job worker
- Logs as one JSON object per line in production (Gunicorn's too, without query strings),
  readable text in development, and reports of what the Content Security Policy blocked
- A production Dockerfile (uv, non-root, Gunicorn, WhiteNoise)
- pytest (with an 80% coverage minimum and a missing-migrations check) and Ruff
- pre-commit (gitleaks and Ruff on every commit) and pip-audit
- Gunicorn settings in `gunicorn.conf.py`

Everything else (APIs, login pages, front end) is added per project.

## Make a new project

```bash
uv tool install copier          # once
copier copy --vcs-ref=HEAD /path/to/django-starter my-client-app
```

## Update an existing project when the starter improves

Commit your project first, then inside it:

```bash
copier update
```

Copier re-applies the starter's changes and asks about any conflicts.
Tag starter releases (`git tag v0.2.0`) so projects update to a known version.

`copier update` never touches a project's own secret files (`.env`, `.env.production`
and the like: they're git-ignored). When an update adds a required setting, add it by
hand. Changes so far that need this:

- **Redis cache:** add `CACHE_URL=redis://app:app@localhost:6379/0` to `.env`, and start
  development with `docker compose up -d` (it now starts Redis too). For production,
  make `.env.redis` and add `CACHE_URL` to `.env.production`, as the project README's
  Production section shows.
- **New packages (Redis cache, login rate limiting, S3 uploads, background jobs):** run `uv sync`, which installs
  them and updates `uv.lock`, and commit `uv.lock`: the production image installs
  exactly what it lists.
- **Login rate limiting:** run `uv run python manage.py migrate` (django-axes adds its
  tables; production's `migrate` step does this by itself). Behind a reverse proxy,
  set `DJANGO_BEHIND_PROXY=true` and check the proxy adds the visitor's address to
  `X-Forwarded-For` (see the project README), or every visitor shares the proxy's
  address. Tests that use `client.login(...)` must switch to
  `client.force_login(user)`.
- **Uploaded files:** nothing to add; uploads stay on local disk unless you set
  `DJANGO_MEDIA_STORAGE=s3` (see the project README's Uploaded files section).
  `config/urls.py` now serves `/media/` in development: if your project already added
  its own `static(settings.MEDIA_URL, ...)` line, remove yours. If you changed
  `STORAGES["default"]` in `config/settings/files.py`, keep your change in the new
  `if media_storage == ...` block.
- **Readiness check:** `/readyz` is new (the database and Redis answer); point a load
  balancer or proxy at it. The `worker` now has a Docker health check, and database
  connections give up after 5 seconds. The health middleware is now
  `config.middleware.health_checks` (it was `healthz`): if your project changed
  `MIDDLEWARE`, keep the new name first in the list. If your project has its own
  `/readyz` URL, it's now answered by the middleware instead.
- **Log limits:** each production container now keeps up to 50 MB of logs, with Docker's
  `json-file` driver. Your next deploy
  (`docker compose -f compose.yaml -f compose.prod.yaml up --build -d --wait`)
  recreates the containers with the limit, which deletes the logs kept so far: save
  any you need first (`docker compose -f compose.yaml -f compose.prod.yaml logs --no-color > old-logs.txt`,
  and keep that file private: it holds addresses). This setting replaces any log
  driver set in `/etc/docker/daemon.json` for these containers: if you forward logs
  that way (journald, syslog, a log service), put your driver in `x-logging` in
  `compose.prod.yaml` instead. If your project added its own services to
  `compose.prod.yaml`, give each `logging: *logging` (services using `<<: *app` already
  have it), or `tests/test_compose.py` fails.
- **Logs:** production now writes one JSON object per line (Gunicorn's request lines
  too, without query strings). If something reads your production logs as text,
  switch it to JSON. If your project set `ADMINS`, Django no longer emails it errors:
  they're only logged. If your project changed `LOGGING` in `config/settings/logs.py`,
  or logging in `gunicorn.conf.py`, keep your change alongside the new setup. The
  Content Security Policy now reports to `/csp-report/` (if your project has its own
  URL at that path, move one of them), so in development the `runserver` terminal now
  also shows what the policy would block.
- **Background jobs:** run `uv sync` (commit the updated `uv.lock`) and
  `uv run python manage.py migrate` (django-tasks-db adds its tables; production's
  `migrate` step does this by itself). In production, enqueued jobs no longer run inside
  the request: they wait in the database for the new `worker` service, which
  `compose.prod.yaml` now starts. If you run production another way (e.g. systemd),
  also run `python manage.py db_worker` as its own always-running service. Schedule the
  daily clean-up of old jobs (see the project README's Background jobs section). If
  your project already set `TASKS`, keep your change in `config/settings/tasks.py`.
- **Email:** nothing to add for development (emails are printed). Email settings now
  come from `EMAIL_URL` through Django's `MAILERS` setting; if your project set
  `EMAIL_BACKEND`, `EMAIL_HOST` or other `EMAIL_*` settings, remove them and set
  `EMAIL_URL` instead (see the project README's Email section). In production, add
  `EMAIL_URL` (`smtp+tls://` or `smtp+ssl://`) and `DJANGO_DEFAULT_FROM_EMAIL` to
  `.env.production` if the project sends email. Production now refuses to start if
  `EMAIL_URL` is plain `smtp://` or `smtps://`, or is set without
  `DJANGO_DEFAULT_FROM_EMAIL`.
- **Tests fail on every Django deprecation:** tests now fail on every Django deprecation
  warning, for features removed in the next version and in the one after (e.g.
  `RemovedInDjango2028Warning`), wherever the warning comes from, including the
  `manage.py` processes tests start. Before, only warnings raised inside Django's own
  code failed, and those included non-Django deprecations that Django code triggered,
  which no longer fail. After updating, run `uv run pytest`: each failure names the
  deprecated feature in use (in your code or an installed package) and what replaces it.
- **Content Security Policy:** inline scripts and styles without
  `nonce="{{ csp_nonce }}"`, `style=` attributes, `onclick=`-style handlers and files
  from other sites (CDNs, web fonts, analytics) are now blocked in tests and production.
  Before updating, search your templates for `<script`, `<style`, `style=` and `on…=`,
  and see the project README's Security section.
- **Settings split by topic:** `config/settings.py` became the `config/settings/`
  package (one file per topic). **`copier update` deletes `config/settings.py` even if
  your project changed it, with no conflict and no warning**, so your own settings
  changes are lost unless you move them. They're still in git until you commit the
  update:
  1. Run `copier update`. `git status` shows `config/settings.py` as deleted.
  2. Before committing, see what your project had changed:
     `git log -p -- config/settings.py` (every change since the project was made), or
     `git diff HEAD -- config/settings.py` (the whole old file).
  3. Copy each of your changes into the topic file it belongs in: `environment.py`
     (`DJANGO_ENV`), `core.py` (debug, keys, hosts, apps, middleware, templates, time
     and language), `database.py` (and the cache), `users.py` (passwords, login limits),
     `files.py` (static and uploaded files), `email.py`, `tasks.py`, `security.py` (HTTPS, headers, CSP),
     `logs.py`.
  4. Don't restore `config/settings.py`: Django would ignore it, so the settings refuse
     to start while it exists.
  5. Run `uv run pytest`, then commit.

  `DJANGO_SETTINGS_MODULE` is still `config.settings`, and the starter's own settings
  keep their values.
  Code that imported `env` from `config.settings` must now import it from
  `config.settings.environment`.
- **Postgres image:** projects made before the compose split used the pgvector image.
  The official Postgres image doesn't include pgvector, so a project that uses it must
  switch its image back in `compose.yaml`.

## Working on the starter

- Files under `template/` ending in `.jinja` are filled in by Copier and lose the
  `.jinja` ending in the new project. Other files are copied unchanged.
- New projects' `.gitignore` is stored as `template/.gitignore.jinja`. Keep the
  `.jinja` ending: git reads any file named `.gitignore`, even inside `template/`, and
  its `.env*` rule would stop git tracking `template/.env.example.jinja`.
  (`.dockerignore` doesn't need this, because git doesn't read it.)
- The starter has its own `.gitignore`: every file whose name starts with `.env` except
  files named `.env.example.jinja`, plus Python, pytest, Ruff and coverage output and
  Django's `media/` and `staticfiles/`. This matters beyond the starter's own history:
  `copier copy --vcs-ref=HEAD` from a local checkout includes uncommitted changes, so
  any file git doesn't ignore can end up in new projects.
- It also has its own `.pre-commit-config.yaml`, which runs gitleaks on every commit.

Set up the commit check once, after cloning:

```bash
uv tool install pre-commit      # once per machine
pre-commit install              # once per clone
```

The first commit afterwards is slow and needs the internet: pre-commit downloads and
builds gitleaks once. The hook only checks what's staged, so `pre-commit run
--all-files` is not a full scan; use the Docker commands below for that. If gitleaks
blocks a commit, remove the secret instead of skipping the check (never
`git commit --no-verify`).

To scan every file and the whole history, from the starter's root folder (needs
Docker). The every-file scan also reads files git ignores (like a local `.env`), so a
finding there may never have been committed; the history scan shows only what was:

```bash
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f dir /repo --redact   # every file
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f git /repo --redact   # the whole history
```

**Updating gitleaks:** it's pinned in four places, all to the same version: the two
hooks (here and in the template) and the Docker commands in both READMEs. From the
starter's root folder:

```bash
pre-commit autoupdate --freeze                                           # this repo's hook
pre-commit autoupdate --freeze --config template/.pre-commit-config.yaml # the template's hook
```

Check that both `# frozen:` comments show the same version. Then update the Docker
image's version and digest in this README and in `template/README.md.jinja`; its
"Updating gitleaks" paragraph shows how to find the digest.
