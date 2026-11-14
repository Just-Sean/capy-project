"""Static files (served by WhiteNoise) and uploaded files."""

from .environment import BASE_DIR, IS_TEST

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # where collectstatic gathers files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"  # user uploads

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Compressed, cache-busting file names (app.3f9a1c.css) in production.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

if IS_TEST:
    # Serve static files without needing `collectstatic` first.
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    # Serve static files straight from the apps during tests, like development,
    # so WhiteNoise doesn't look for the collectstatic folder.
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
