"""Which environment this is (DJANGO_ENV), and the env reader every topic uses."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # the project folder

env = environ.Env()
# Load .env if it exists. Real environment variables always win over the file.
# Set DJANGO_READ_DOT_ENV=false to ignore the file (the settings tests do this).
if env.bool("DJANGO_READ_DOT_ENV", default=True) and (BASE_DIR / ".env").exists():
    env.read_env(BASE_DIR / ".env")

DJANGO_ENV = env("DJANGO_ENV", default="production")  # unset means production, the safest choice
if DJANGO_ENV not in ("development", "test", "production"):
    raise ImproperlyConfigured(
        f"DJANGO_ENV must be 'development', 'test' or 'production', not {DJANGO_ENV!r}."
    )
IS_DEVELOPMENT = DJANGO_ENV == "development"
IS_TEST = DJANGO_ENV == "test"
IS_PRODUCTION = DJANGO_ENV == "production"
