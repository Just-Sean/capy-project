# template/config/asgi.py

**What it is:** the entry point for an async server such as Uvicorn. Nothing uses it yet: production runs Gunicorn through `wsgi.py`. It's there, as in every new Django project, for a project that later needs WebSockets or long-lived connections.
