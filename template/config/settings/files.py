"""Static files (served by WhiteNoise) and uploaded files (local, or S3 if chosen)."""

from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .environment import BASE_DIR, IS_PRODUCTION, IS_TEST, env

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # where collectstatic gathers files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"  # uploads, when they're stored locally

STORAGES = {
    # Compressed, cache-busting file names (app.3f9a1c.css) in production.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Uploaded files: on this machine's disk (in production, the `media` Docker volume), or
# in S3 or any S3-compatible service (Cloudflare R2, Backblaze B2, MinIO, ...).
# Lowercase names below are helpers: only uppercase names become Django settings.
media_storage = env("DJANGO_MEDIA_STORAGE", default="filesystem")
if media_storage == "filesystem":
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
elif media_storage == "s3":
    bucket = env("DJANGO_MEDIA_S3_BUCKET", default="")  # required
    if not bucket or bucket != bucket.strip():
        raise ImproperlyConfigured("DJANGO_MEDIA_S3_BUCKET must be a bucket name.")
    endpoint = env("DJANGO_MEDIA_S3_ENDPOINT_URL", default="") or None  # not needed for AWS
    if endpoint and not urlsplit(endpoint).hostname:
        raise ImproperlyConfigured("DJANGO_MEDIA_S3_ENDPOINT_URL must be a full address.")
    # Plain http only for a local test service (e.g. MinIO in Docker), never in production.
    if IS_PRODUCTION and endpoint and urlsplit(endpoint).scheme.lower() != "https":
        raise ImproperlyConfigured("DJANGO_MEDIA_S3_ENDPOINT_URL must start with https://.")
    # The keys stay out of Django's settings: django-storages reads AWS_ACCESS_KEY_ID and
    # AWS_SECRET_ACCESS_KEY from the environment itself, and without them boto3 uses the
    # server's own role (e.g. an EC2 or ECS role), which is safer than a long-lived key.
    # Half a key pair would silently break that, so it's refused.
    has_key = bool(env("AWS_ACCESS_KEY_ID", default=""))
    has_secret = bool(env("AWS_SECRET_ACCESS_KEY", default=""))
    if has_key != has_secret:
        raise ImproperlyConfigured("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither.")
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": bucket,
            "region_name": env("DJANGO_MEDIA_S3_REGION", default="") or None,
            "endpoint_url": endpoint,
            "location": "media",  # files go under media/ in the bucket
            # No ACL header: files are private like the bucket (some services refuse one).
            "querystring_auth": True,  # links to them are signed ...
            "querystring_expire": 3600,  # ... and stop working after an hour
            "signature_version": "s3v4",  # the signing every service accepts
            "file_overwrite": False,  # an upload doesn't replace an existing file
            # Opening a file downloads it instead of showing it, so an uploaded HTML or
            # SVG file can't run scripts in the browser.
            "object_parameters": {"ContentDisposition": "attachment"},
        },
    }
else:
    raise ImproperlyConfigured(
        f"DJANGO_MEDIA_STORAGE must be 'filesystem' or 's3', not {media_storage!r}."
    )

if IS_TEST:
    # Serve static files without needing `collectstatic` first.
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    # Serve static files straight from the apps during tests, like development,
    # so WhiteNoise doesn't look for the collectstatic folder.
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
