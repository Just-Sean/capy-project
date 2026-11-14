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
- One settings file driven by environment variables (django-environ), secure by default:
  Argon2 passwords, login rate limiting (django-axes), a strict Content Security Policy
  with nonces, HSTS in production and the standard security headers
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
- **New packages (Redis cache, login rate limiting):** run `uv sync`, which installs
  them and updates `uv.lock`, and commit `uv.lock`: the production image installs
  exactly what it lists.
- **Login rate limiting:** run `uv run python manage.py migrate` (django-axes adds its
  tables; production's `migrate` step does this by itself). Behind a reverse proxy,
  set `DJANGO_BEHIND_PROXY=true` and check the proxy adds the visitor's address to
  `X-Forwarded-For` (see the project README), or every visitor shares the proxy's
  address. Tests that use `client.login(...)` must switch to
  `client.force_login(user)`.
- **Content Security Policy:** inline scripts and styles without
  `nonce="{{ csp_nonce }}"`, `style=` attributes, `onclick=`-style handlers and files
  from other sites (CDNs, web fonts, analytics) are now blocked in tests and production.
  Before updating, search your templates for `<script`, `<style`, `style=` and `on…=`,
  and see the project README's Security section.
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
