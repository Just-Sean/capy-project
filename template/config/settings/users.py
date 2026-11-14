"""Users, passwords and login rate limiting."""

from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured

from .environment import IS_TEST, env

AUTH_USER_MODEL = "accounts.User"

# Argon2, the hasher Django recommends. The others only check existing passwords made
# with them, and those are re-hashed with Argon2 at the user's next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
if IS_TEST:
    # Hashing passwords properly is deliberately slow; tests don't need that.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
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
