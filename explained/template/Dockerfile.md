# template/Dockerfile

**What it is:** the production image, used for three services in `compose.prod.yaml`:

- the `migrate` step
- the app (`web`)
- the background-job `worker`

Development doesn't use it: there Django runs on your machine.

**Stage 1, `build`** (`python:3.14-slim-trixie` plus uv 0.11.32):

1. Copies `pyproject.toml` and `uv.lock` first, then installs exactly the locked packages without the dev tools (`uv sync --locked --no-dev`). This slow layer is cached until `uv.lock` changes.
2. Copies the code, apart from what `.dockerignore` leaves out, and runs `collectstatic`. Placeholder settings (`build-only` secret key and so on) let the settings load for that one command. They never reach the running container.

**Stage 2, `runtime`** (the same slim Python, without uv or build leftovers):

- Creates an unprivileged user `app` (uid **10001**).
- Copies `/app` from the build stage. The code and static files stay owned by root, so the app can't change them.
- `media/` and `media-public/` are the only folders the app owns. With `compose.prod.yaml`'s read-only filesystem and in-memory `/tmp`, they're the only places it can write (the image on its own still allows `/tmp`).
- Runs as `app`, on port 8000.
- `HEALTHCHECK` calls `/healthz` every 30 seconds with Python's `urllib`, because curl isn't in the slim image.
- `CMD`: `gunicorn config.wsgi --bind 0.0.0.0:8000`. Every other Gunicorn setting comes from `gunicorn.conf.py`.

**Why uid 10001 matters:** the README's backup restore hands restored uploads to `10001:10001`, so the app can still change and delete them.

**Kept up to date by:** Dependabot's `docker` check (`.github/dependabot.yml`), which watches the base images.
