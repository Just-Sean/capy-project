# template/config/wsgi.py

**What it is:** the entry point Gunicorn starts the app from (`gunicorn config.wsgi`, the `Dockerfile`'s `CMD`). It points Django at `config.settings` and creates the `application` object Gunicorn calls for each request. `WSGI_APPLICATION` in `settings/core.py` names it too, for `runserver`.
