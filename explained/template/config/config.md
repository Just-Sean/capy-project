# template/config/

**What it is:** the Django project itself: the settings, the URL map, the server entry points, and the small project-wide modules that don't belong to any one app. Every app you plug in is wired up here, in `settings/core.py` (`INSTALLED_APPS`) and `urls.py`.

| File | Purpose |
| --- | --- |
| `settings/` | Every setting, one file per topic, read from the environment |
| `urls.py` | The root URL map |
| `wsgi.py` | Gunicorn's entry point |
| `asgi.py` | An async entry point, unused until a project needs one |
| `middleware.py` | Answers `/healthz` and `/readyz` before anything else runs |
| `health.py` | The checks behind `/readyz` and the worker's Docker health check |
| `uploads.py` | Private uploads: who may download, the download view, `random_folder`, `public_storage` |
| `login_limits.py` | The visitor's real address, and the per-address login limit |
| `logging.py` | The log formats: JSON lines and plain text |
| `csp_report.py` | Receives and logs reports of what the Content Security Policy blocked |
| `csrf_failure.py` | The page for a form that failed its security check |
| `email_not_set_up.py` | The email backend production uses without `EMAIL_URL` |
| `__init__.py` | Empty; makes the folder a Python package |

**Rule of thumb:** project-wide plumbing goes here. Anything with its own models, views or pages goes in its own app at the project's top level, as `accounts/` does.
