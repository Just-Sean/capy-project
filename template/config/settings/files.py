"""Static files (served by WhiteNoise) and uploaded files (local, or S3 if chosen)."""

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
MEDIA_STORAGE = env("DJANGO_MEDIA_STORAGE", default="filesystem")
if MEDIA_STORAGE == "filesystem":
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
elif MEDIA_STORAGE == "s3":
    S3_ENDPOINT_URL = env("DJANGO_MEDIA_S3_ENDPOINT_URL", default=None)  # not needed for AWS
    # Plain http only for a local test service (e.g. MinIO in Docker), never in production.
    if IS_PRODUCTION and S3_ENDPOINT_URL and not S3_ENDPOINT_URL.startswith("https://"):
        raise ImproperlyConfigured("DJANGO_MEDIA_S3_ENDPOINT_URL must start with https://.")
    S3_OPTIONS = {
        "bucket_name": env("DJANGO_MEDIA_S3_BUCKET"),  # required
        "region_name": env("DJANGO_MEDIA_S3_REGION", default=None),
        "endpoint_url": S3_ENDPOINT_URL,
        "location": "media",  # files go under media/ in the bucket
        "default_acl": "private",  # nobody can read them without a signed link
        "querystring_auth": True,  # links to them are signed ...
        "querystring_expire": 3600,  # ... and stop working after an hour
        "file_overwrite": False,  # an upload never replaces an existing file
    }
    # Keys only if given: without them boto3 uses the server's own role (e.g. an EC2 or
    # ECS role), which is safer than a long-lived key.
    S3_ACCESS_KEY = env("AWS_ACCESS_KEY_ID", default=None)
    if S3_ACCESS_KEY is not None:
        S3_OPTIONS["access_key"] = S3_ACCESS_KEY
        S3_OPTIONS["secret_key"] = env("AWS_SECRET_ACCESS_KEY")  # required with a key
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": S3_OPTIONS}
else:
    raise ImproperlyConfigured(
        f"DJANGO_MEDIA_STORAGE must be 'filesystem' or 's3', not {MEDIA_STORAGE!r}."
    )

if IS_TEST:
    # Serve static files without needing `collectstatic` first.
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    # Serve static files straight from the apps during tests, like development,
    # so WhiteNoise doesn't look for the collectstatic folder.
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
