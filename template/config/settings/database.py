"""The database (PostgreSQL) and the cache (Redis)."""

from django.core.exceptions import ImproperlyConfigured

from .environment import IS_TEST, env

DATABASES = {"default": env.db("DATABASE_URL")}  # required, postgres://user:pass@host:port/name
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# 64-bit whole-number primary keys for every model (the public face is a UUID).
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
