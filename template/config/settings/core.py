"""Core: debug, the secret key, hosts, apps, middleware, templates, time and language."""

from django.core.exceptions import ImproperlyConfigured

from .environment import BASE_DIR, IS_DEVELOPMENT, IS_PRODUCTION, env

DEBUG = env.bool("DJANGO_DEBUG", default=IS_DEVELOPMENT)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must not be true in production.")

if IS_PRODUCTION:
    SECRET_KEY = env("DJANGO_SECRET_KEY")  # required
    ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # required
    ADMIN_URL = env("DJANGO_ADMIN_URL")  # required, e.g. "staff-k3v9q2/"
    if ADMIN_URL == "admin/":
        raise ImproperlyConfigured("Set DJANGO_ADMIN_URL to something other than 'admin/'.")
else:
    SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-key-for-development-and-tests-only")
    ALLOWED_HOSTS = env.list(
        "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )
    ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    # Your apps first, so their templates override third-party ones.
    "accounts",
    "django.contrib.admin",
    "django.contrib.auth",
    "axes",  # login rate limiting: see users.py
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # Before staticfiles: stops runserver serving static files itself, so WhiteNoise
    # serves them in development too, with the same headers (including the CSP).
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django_tasks_db",  # background jobs in production: see tasks.py
]

MIDDLEWARE = [
    "config.middleware.health_checks",  # first: /healthz and /readyz skip host checks
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",  # sends SECURE_CSP (security.py)
    # Static files, right after the security headers, so they carry them (and the CSP) too.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # last: turns a lockout into a "too many attempts" page
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-wide templates: base.html and the error pages. Apps keep their own too.
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",  # {{ csp_nonce }} in templates
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True  # store every datetime in UTC
