# Production image. Build and run it, with its migrate step and Postgres, using:
#   docker compose -f compose.yaml -f compose.prod.yaml up --build
# Development doesn't use this: Django runs on your machine, only Postgres runs in Docker.

# ---- Stage 1: install dependencies with uv -----------------------------------
FROM python:3.14-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# Dependencies first, so this slow layer is cached until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Then the code, and collect static files. The placeholder values only let
# settings load during the build; they never reach the running container.
COPY . .
RUN DJANGO_SECRET_KEY=build-only DJANGO_ALLOWED_HOSTS=build DJANGO_ADMIN_URL=build-only/ \
    DATABASE_URL=postgres://build@localhost/build DJANGO_READ_DOT_ENV=false \
    /app/.venv/bin/python manage.py collectstatic --noinput

# ---- Stage 2: the small runtime image ------------------------------------------
FROM python:3.14-slim-trixie AS runtime
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# An unprivileged user. Code and static files stay owned by root (read-only to
# the app); the uploads folder is the only place it can write.
RUN groupadd --system app && useradd --system --gid app --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build /app /app
RUN mkdir -p /app/media && chown app:app /app/media

USER app
EXPOSE 8000

# Docker marks the container unhealthy if /healthz stops answering. Python's
# urllib does the request because curl isn't in the slim image.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

# Gunicorn's settings (workers, timeouts, logs) are in gunicorn.conf.py. Inside the
# container it listens on all interfaces, so Docker can forward port 8000 to it.
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000"]
