# Django starter (Copier template)

A minimal, production-ready Django starting point. Every project made from it
gets only what has to exist on day one:

- PostgreSQL 18 (pgvector image) in Docker
- A custom `User` model (`accounts.User`) with a unique, lowercase email and a public UUID
- One settings file driven by environment variables (django-environ), secure by default
- A production Dockerfile (uv, non-root, Gunicorn, WhiteNoise)
- pytest and Ruff

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
# django-starter
# django-starter
