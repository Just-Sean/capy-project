"""Logging: everything goes to the console, where Docker and hosting platforms collect it.
One JSON object per line in production, readable text in development and tests (the
formats are in config/logging.py). Errors are always logged with their stack trace."""

from config.logging import TEXT_FORMAT

from .environment import IS_PRODUCTION, env

level = env("DJANGO_LOG_LEVEL", default="INFO")  # lowercase: a helper, not a setting

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "config.logging.JsonFormatter"},
        "text": {"format": TEXT_FORMAT, "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if IS_PRODUCTION else "text",
        },
    },
    "root": {"handlers": ["console"], "level": level},
    "loggers": {
        # Django's own messages (request errors included) go through the same handler.
        # This replaces Django's defaults: a second console handler in development
        # (each line twice) and emailing errors to ADMINS (off in this starter).
        "django": {"handlers": ["console"], "level": level, "propagate": False},
    },
}
