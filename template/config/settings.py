"""Settings for every environment.

One file, secure by default. DJANGO_ENV picks the environment:
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
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Load .env if it exists. Real environment variables always win over the file.
# Set DJANGO_READ_DOT_ENV=false to ignore the file (the settings tests do this).
if env.bool("DJANGO_READ_DOT_ENV", default=True) and (BASE_DIR / ".env").exists():
    env.read_env(BASE_DIR / ".env")


# --- Environment ----------------------------------------------------------------

DJANGO_ENV = env("DJANGO_ENV", default="production")  # unset means production, the safest choice
if DJANGO_ENV not in ("development", "test", "production"):
    raise ImproperlyConfigured(
        f"DJANGO_ENV must be 'development', 'test' or 'production', not {DJANGO_ENV!r}."
    )
IS_DEVELOPMENT = DJANGO_ENV == "development"
IS_TEST = DJANGO_ENV == "test"
IS_PRODUCTION = DJANGO_ENV == "production"


# --- Core ---------------------------------------------------------------------

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
    "axes",  # login rate limiting: see "Login rate limiting" below
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # Before staticfiles: stops runserver serving static files itself, so WhiteNoise
    # serves them in development too, with the same headers (including the CSP).
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "config.middleware.healthz",  # first: answers /healthz before host checks or the database
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",  # sends SECURE_CSP below
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
        "DIRS": [],  # no root templates folder: each app keeps its own
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


# --- Database -----------------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}  # required, postgres://user:pass@host:port/name
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# 64-bit whole-number primary keys for every model (the public face is a UUID).
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Cache ----------------------------------------------------------------------

# Redis, set by CACHE_URL (e.g. redis://app:password@localhost:6379/0). Required outside
# tests; tests use an in-memory cache, so they don't need Redis running. Django's own
# Redis backend is named explicitly, so another installed package can't swap it.
# Connection and read timeout (not how long keys are kept): a slow or missing Redis
# fails fast instead of holding a request.
REDIS_SOCKET_TIMEOUT_SECONDS = 2
REDIS_URL_SCHEMES = ("redis://", "rediss://")
if IS_TEST:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    # Only Redis: a dummy cache stores nothing, and an in-memory one isn't shared
    # between server processes.
    if not env("CACHE_URL").startswith(REDIS_URL_SCHEMES):  # required
        raise ImproperlyConfigured("CACHE_URL must start with redis:// or rediss://.")
    CACHES = {"default": env.cache("CACHE_URL")}
    CACHES["default"]["BACKEND"] = "django.core.cache.backends.redis.RedisCache"
    # Added to any options given in CACHE_URL itself, e.g. TLS settings for rediss://.
    CACHES["default"].setdefault("OPTIONS", {}).update(
        socket_connect_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
    )


# --- Users and passwords --------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

# Argon2, the hasher Django recommends. The others only check existing passwords made
# with them, and those are re-hashed with Argon2 at the user's next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Login rate limiting (django-axes, plus config/login_limits.py). Two limits, each over
# DJANGO_LOGIN_LOCKOUT_MINUTES (each further try during a lockout restarts it):
#   - DJANGO_LOGIN_FAILURE_LIMIT failed logins for one username from one address lock
#     that pair out. Someone elsewhere can't lock a real user out this way.
#   - DJANGO_LOGIN_IP_FAILURE_LIMIT failed logins from one address, whatever usernames
#     were tried, lock that address out. Higher, so a shared office address is fine.
# A successful login clears its pair's count. Django's own login views (the admin,
# LoginView) are covered; custom code must call authenticate(request, ...) with the
# request, and tests should use client.force_login(user) instead of client.login(...).
# Failed attempts are kept in the database (not Redis, which can be emptied) until their
# lockout time has passed, and listed in the admin; `manage.py axes_reset` clears them.
AUTHENTICATION_BACKENDS = [
    "config.login_limits.IPLoginLimitBackend",  # refuses addresses over their limit
    "axes.backends.AxesStandaloneBackend",  # refuses locked-out username + address pairs
    "django.contrib.auth.backends.ModelBackend",  # the real login
]
AXES_FAILURE_LIMIT = env.int("DJANGO_LOGIN_FAILURE_LIMIT", default=5)
LOGIN_IP_FAILURE_LIMIT = env.int("DJANGO_LOGIN_IP_FAILURE_LIMIT", default=30)
LOGIN_LOCKOUT_MINUTES = env.int("DJANGO_LOGIN_LOCKOUT_MINUTES", default=15)
if min(AXES_FAILURE_LIMIT, LOGIN_IP_FAILURE_LIMIT, LOGIN_LOCKOUT_MINUTES) < 1:
    raise ImproperlyConfigured(
        "DJANGO_LOGIN_FAILURE_LIMIT, DJANGO_LOGIN_IP_FAILURE_LIMIT and "
        "DJANGO_LOGIN_LOCKOUT_MINUTES must each be at least 1."
    )
AXES_COOLOFF_TIME = timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]  # the pair, not either alone
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_RETRY_AFTER_HEADER = True  # tells clients when they may try again
AXES_CLIENT_IP_CALLABLE = "config.login_limits.client_ip"  # trusts a proxy only if declared
AXES_DISABLE_ACCESS_LOG = True  # don't keep a record of every successful login
# Shorter log lines. Failures and lockouts are still logged, with these hidden.
AXES_SENSITIVE_PARAMETERS = ["username", "ip_address"]
AXES_VERBOSE = False

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


# --- Security (HTTPS-only in production, plain HTTP elsewhere) --------------------

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=IS_PRODUCTION)
SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=IS_PRODUCTION)

# HSTS tells browsers to only ever use HTTPS for this domain. On a brand-new
# domain, start with DJANGO_SECURE_HSTS_SECONDS=3600 and raise it once HTTPS works.
SECURE_HSTS_SECONDS = env.int(
    "DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365 if IS_PRODUCTION else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = False  # preloading is hard to undo; opt in deliberately per project
SILENCED_SYSTEM_CHECKS = ["security.W021"]  # the "HSTS preload is off" warning, by design

# Only behind a proxy you control (nginx, Caddy, a load balancer) that sets these
# headers: then X-Forwarded-Proto says whether the visitor used HTTPS, and the last
# X-Forwarded-For entry is the visitor's address (see config/login_limits.py).
BEHIND_PROXY = env.bool("DJANGO_BEHIND_PROXY", default=False)
if BEHIND_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

X_FRAME_OPTIONS = "DENY"  # never allow this site inside a frame
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Content Security Policy (Django's built-in one, so there's no extra package to keep
# updated): the browser only loads what's listed below and blocks everything else, such
# as code injected into a page. Scripts and styles come from this site, plus inline ones
# that carry the page's nonce (<script nonce="{{ csp_nonce }}">). Anything not listed
# (frames, audio and video, workers, manifests) falls back to default-src: nothing, until
# a project allows it on purpose. A view that needs more can set its own policy with
# csp_override from django.views.decorators.csp; see the README's Security section.
SECURE_CSP = {
    "default-src": [CSP.NONE],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],  # the same as X_FRAME_OPTIONS, for newer browsers
}
if IS_DEVELOPMENT:
    # Report only: Django's yellow debug pages use inline styles without the nonce, so
    # an enforced policy would break them. Anything the policy would block still shows
    # as a warning in the browser console. Tests and production enforce it.
    SECURE_CSP_REPORT_ONLY = SECURE_CSP
    SECURE_CSP = {}


# --- Logging ----------------------------------------------------------------------

# Everything goes to the console, where Docker and hosting platforms collect it.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}


# --- Test-only adjustments ----------------------------------------------------------

if IS_TEST:
    # Hashing passwords properly is deliberately slow; tests don't need that.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Serve static files without needing `collectstatic` first.
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    # Serve static files straight from the apps during tests, like development,
    # so WhiteNoise doesn't look for the collectstatic folder.
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
