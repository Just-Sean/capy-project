"""Settings for every environment, one module per topic.

Secure by default. DJANGO_ENV picks the environment (see environment.py):
  - development: set in your .env. Debug on, plain HTTP allowed, and safe local
                 defaults for the secret key, allowed hosts and admin URL.
  - test:        set automatically by pytest (pytest-env). Debug off, fast password
                 hashing, plain static files storage, and an in-memory cache, so Redis
                 isn't needed. Django adds a throwaway test database.
  - production:  the default when DJANGO_ENV is unset. Real environment variables on the
                 server; no .env file exists. HTTPS-only, and debug can't be turned on.

Every setting can still be overridden by its own environment variable. In production,
required values have no fallback, so a misconfigured server refuses to start instead of
running insecurely.

Each topic module keeps its own test-only adjustments next to the settings they change.
This file only combines them: Django reads every UPPERCASE name defined here.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from . import core, database, email, environment, files, logs, security, tasks, users

# A config/settings.py left over from before the split (e.g. after `copier update`) would
# be silently ignored, so anything still in it would stop working without a sign.
if (Path(__file__).resolve().parent.parent / "settings.py").exists():
    raise ImproperlyConfigured(
        "config/settings.py is no longer used: move your changes into the matching file "
        "in config/settings/, then delete config/settings.py."
    )

for _topic in (environment, core, database, users, files, email, tasks, security, logs):
    globals().update({name: value for name, value in vars(_topic).items() if name.isupper()})
