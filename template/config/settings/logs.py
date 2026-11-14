"""Logging: everything goes to the console, where Docker and hosting platforms collect it.
One JSON object per line in production, readable text in development and tests (the
formats are in config/logging.py). Errors are always logged with their stack trace."""

import logging

from config import logging as log_formats

from .environment import IS_PRODUCTION, env

# Lowercase, so it doesn't become a setting (only UPPERCASE names are).
level = env("DJANGO_LOG_LEVEL", default="INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "config.logging.JsonFormatter"},
        "text": {"format": log_formats.TEXT_FORMAT, "style": "{"},
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
        # (each line twice) and emailing request errors to ADMINS, so they're never
        # emailed, even if ADMINS is set.
        "django": {"handlers": ["console"], "level": level, "propagate": False},
    },
}

if IS_PRODUCTION:
    # Python's warnings (e.g. "received a naive datetime") go through logging too, so
    # they're JSON lines like everything else instead of plain text.
    logging.captureWarnings(True)
