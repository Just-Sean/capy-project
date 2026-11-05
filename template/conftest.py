"""Test-only adjustments, applied automatically to every test."""

import pytest


@pytest.fixture(autouse=True)
def _test_settings(settings):
    # Hashing passwords properly is deliberately slow; tests don't need that.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Serve static files without needing `collectstatic` first.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
