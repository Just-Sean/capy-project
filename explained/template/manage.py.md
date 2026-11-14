# template/manage.py

**What it is:** Django's standard command runner: `uv run python manage.py runserver`, `migrate`, `createsuperuser`, `axes_reset`, `db_worker` and the rest.

It sets `DJANGO_SETTINGS_MODULE` to `config.settings` (unless it's already set), then hands the command to Django. The production image runs it too: the `migrate` step and the `worker` service both start with `python manage.py ...`.
