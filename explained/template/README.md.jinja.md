# template/README.md.jinja → README.md

**What it is:** each project's own manual: about 1,000 lines covering every command and setting, and the reason for each one. Copier fills in the project's name and slug, so commands such as `docker volume rm <slug>-production_pgdata` are ready to paste.

**Its sections:**

| Section | Covers |
| --- | --- |
| First-time setup | `git init` → `.env` → `uv sync` → pre-commit → first commit → Postgres and Redis → `migrate` → `createsuperuser` → `runserver` |
| Everyday commands | One table of the commands used most |
| Environments | `DJANGO_ENV` (development, test, production), what each defaults to, and what production refuses |
| Running each environment | **Development** (ports, Redis), **Test**, **Production**. Production covers the four `.env` files, Caddy's jobs, rate limits, the local HTTP check, the real-server steps, deploying a new version (with a tag per deploy) and rolling back, health checks, the worker's check and Gunicorn |
| Uploaded files | Private by default, `can_download()`, `random_folder`, `public_storage`, S3 |
| Email | `EMAIL_URL` in each environment, percent-encoding, testing it |
| Background jobs | `@task`, enqueueing, what differs in production, the worker, cleaning up old jobs |
| Error pages | Which page shows when, `base.html` rules, the proxy's page |
| Logs | Formats, what's in them (and what's left out), log levels, disk limits |
| Backups | The database and both upload volumes: backing up (files only the owner can read, and a ready-made nightly cron line that also deletes backups older than 14 days) and restoring (as one transaction), kept outside the project in `/var/backups/<slug>` |
| Checking what's running | `ps`, `down`, `down -v` and what each deletes |
| Security | Argon2, login rate limiting, headers, the CSP and its nonce, HSTS preload |
| Checks | pre-commit, gitleaks scans, and before every pull request: `pytest --cov` and pip-audit |
| Architecture | The main parts, a request's path, why each choice was made, and **Adding a reusable app** in five steps |
| What's in the project | A table of every file and what each test proves |
| Conventions | Templates, `public_id`, business logic in plain functions |

**Two Jinja details:** the file escapes the places where Django or Docker template syntax must survive as written. Examples are `{{ csp_nonce }}` and the `docker inspect --format` and `{{index .RepoDigests 0}}` commands. They use `{% raw %}` or `{{ '{{' }}` so Copier doesn't try to fill them in.
