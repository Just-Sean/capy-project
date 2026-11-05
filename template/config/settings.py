"""Settings for every environment.

One file, secure by default. The environment decides the rest:
  - development: values from the .env file (see .env.example)
  - test:        pytest, using the same .env (Django adds a throwaway test database)
  - production:  real environment variables on the server; no .env file exists

Anything unset falls back to the safe production value. Required values have no
fallback, so a misconfigured server refuses to start instead of running insecurely.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Load .env if it exists. Real environment variables always win over the file.
# Set DJANGO_READ_DOT_ENV=false to ignore the file (the settings tests do this).
if env.bool("DJANGO_READ_DOT_ENV", default=True) and (BASE_DIR / ".env").exists():
    env.read_env(BASE_DIR / ".env")


# --- Core ---------------------------------------------------------------------

DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env("DJANGO_SECRET_KEY")  # required
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # required
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

ADMIN_URL = env("DJANGO_ADMIN_URL")  # required, e.g. "staff-k3v9q2/"
if not DEBUG and ADMIN_URL == "admin/":
    raise ImproperlyConfigured("Set DJANGO_ADMIN_URL to something other than 'admin/'.")

INSTALLED_APPS = [
    # Your apps first, so their templates override third-party ones.
    "accounts",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static files, right after security
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # no root templates folder: each app keeps its own
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# --- Database -----------------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}  # required, postgres://user:pass@host:port/name
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# 64-bit whole-number primary keys for every model (the public face is a UUID).
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Users and passwords --------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Time and language ------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True  # store every datetime in UTC


# --- Static and uploaded files --------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # where collectstatic gathers files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"  # user uploads

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Compressed, cache-busting file names (app.3f9a1c.css) in production.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}


# --- Security (secure unless the environment says otherwise) ----------------------

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=True)

# HSTS tells browsers to only ever use HTTPS for this domain. On a brand-new
# domain, start with DJANGO_SECURE_HSTS_SECONDS=3600 and raise it once HTTPS works.
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = False  # preloading is hard to undo; opt in deliberately per project
SILENCED_SYSTEM_CHECKS = ["security.W021"]  # the "HSTS preload is off" warning, by design

# Only behind a proxy you control (nginx, Caddy, a load balancer) that sets this header.
if env.bool("DJANGO_BEHIND_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

X_FRAME_OPTIONS = "DENY"  # never allow this site inside a frame
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"


# --- Logging ----------------------------------------------------------------------

# Everything goes to the console, where Docker and hosting platforms collect it.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
