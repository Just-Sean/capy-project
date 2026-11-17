# README.md (the starter's own)

**What it is:** the starter repo's front page, for whoever maintains the starter or makes projects from it. Each generated project has its own README, which comes from `template/README.md.jinja`.

**What's in it:**

- **What every project gets:** a short list covering the database, cache, settings, security, uploads, email, jobs, error pages, health checks, logs, Docker and Caddy, and the checks.
- **Make a new project:** install Copier, then run `copier copy gh:Just-Sean/django-starter` (the newest release; `--vcs-ref=HEAD` is only for trying unreleased changes, see Working on the starter).
- **Update an existing project:** commit, then run `copier update` (it moves the project to the newest release). Then comes the long part: **one note per change that needs a hand step**, grouped by the release that brought it ("New in v1.0.0", "New in v0.4.0"), newest first. Examples:
  - adding `CACHE_URL` for Redis
  - running `migrate` for django-axes
  - making `.env.caddy`
  - handing Caddy's certificate volumes to its new non-root user
  - moving public uploads to `public_storage`
  - moving settings changes out of the old `config/settings.py`
  - turning on Dependabot

  `copier update` never touches a project's `.env` files, so those steps can't be automated.
- **Working on the starter:**
  - How `.jinja` files work.
  - Why the new projects' `.gitignore` is stored as `.gitignore.jinja`: a file named `.gitignore` inside `template/` would hide `template/.env.example.jinja` from git.
  - What the starter's own `.gitignore` covers.
  - Setting up its pre-commit hook.
  - The Docker commands that scan every file, and the whole history, with gitleaks.
  - Updating gitleaks: it's pinned in four places that must match. Those are the two hooks and the Docker commands in both READMEs.

**When to change it:** whenever a starter change needs a hand step in existing projects, add a note for it here, in the same pull request.
