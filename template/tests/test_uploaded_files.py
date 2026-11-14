"""Uploaded files: local by default (development serves them), S3 if chosen, with safe
defaults, and misconfiguration refused at startup."""

import pytest
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from tests.test_production_settings import run_manage

PRINT_STORAGE = (
    "from django.conf import settings as s; d = s.STORAGES['default']; "
    "print(d['BACKEND'], d.get('OPTIONS', {}))"
)
# Fake keys, and boto3 told not to look for a server role, so nothing goes over the network.
S3 = {"DJANGO_MEDIA_STORAGE": "s3", "DJANGO_MEDIA_S3_BUCKET": "my-bucket"}
KEYS = {"AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "EXAMPLESECRET"}
OFFLINE = {"AWS_EC2_METADATA_DISABLED": "true"}
PRINT_URL = (
    "from django.core.files.storage import default_storage as d; print(d.url('reports/q1.pdf'))"
)
PRINT_CREDENTIALS = (
    "from django.core.files.storage import default_storage as d; "
    "print(repr(d.access_key), repr(d.secret_key))"
)
CAN_RESOLVE_MEDIA = (
    "from django.urls import resolve, Resolver404\n"
    "try:\n    resolve('/media/report.pdf'); print('served')\n"
    "except Resolver404:\n    print('not served')"
)


def last_line(result):
    return result.stdout.strip().splitlines()[-1]


def test_uploads_are_stored_locally_by_default():
    result = run_manage("shell", "-c", PRINT_STORAGE)
    assert last_line(result).startswith("django.core.files.storage.FileSystemStorage"), (
        result.stderr
    )


def test_a_local_upload_never_replaces_an_existing_file(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    first = default_storage.save("report.txt", ContentFile(b"first"))
    second = default_storage.save("report.txt", ContentFile(b"second"))
    assert first != second  # the second upload gets a new name
    assert (tmp_path / first).read_bytes() == b"first"


@pytest.mark.parametrize("name", ["../escape.txt", "a/../../escape.txt", "/etc/escape.txt"])
def test_local_uploads_cant_escape_the_media_folder(settings, tmp_path, name):
    settings.MEDIA_ROOT = tmp_path / "media"
    with pytest.raises(SuspiciousFileOperation):
        default_storage.save(name, ContentFile(b"x"))
    assert not (tmp_path / "escape.txt").exists()


def test_development_serves_uploads_and_production_doesnt():
    development = run_manage("shell", "-c", CAN_RESOLVE_MEDIA, DJANGO_ENV="development")
    production = run_manage("shell", "-c", CAN_RESOLVE_MEDIA)
    assert last_line(development) == "served", development.stderr
    assert last_line(production) == "not served", production.stderr


def test_s3_files_are_private_downloads_that_are_never_overwritten():
    result = run_manage("shell", "-c", PRINT_STORAGE, **S3)
    line = last_line(result)
    assert line.startswith("storages.backends.s3.S3Storage"), result.stderr
    assert "'location': 'media'" in line
    assert "'file_overwrite': False" in line
    assert "'object_parameters': {'ContentDisposition': 'attachment'}" in line
    assert "acl" not in line  # private like the bucket, with no ACL header to refuse


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"DJANGO_MEDIA_S3_REGION": "eu-west-1"},
        {"DJANGO_MEDIA_S3_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com"},
    ],
    ids=["aws, no region", "aws with region", "other service"],
)
def test_s3_links_are_signed_and_expire_after_an_hour(extra):
    result = run_manage("shell", "-c", PRINT_URL, **S3, **KEYS, **OFFLINE, **extra)
    url = last_line(result)
    assert "/media/reports/q1.pdf?" in url, result.stderr
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url  # SigV4, which every service accepts
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=3600" in url


def test_s3_keys_come_from_the_environment_and_stay_out_of_settings():
    credentials = run_manage("shell", "-c", PRINT_CREDENTIALS, **S3, **KEYS, **OFFLINE)
    assert last_line(credentials) == "'AKIAEXAMPLE' 'EXAMPLESECRET'", credentials.stderr
    settings_dump = run_manage("diffsettings", "--all", **S3, **KEYS)
    assert settings_dump.returncode == 0, settings_dump.stderr
    assert "AKIAEXAMPLE" not in settings_dump.stdout
    assert "EXAMPLESECRET" not in settings_dump.stdout


def test_without_keys_s3_uses_the_servers_role():
    result = run_manage("shell", "-c", PRINT_CREDENTIALS, **S3, **OFFLINE)
    assert last_line(result) == "None None", result.stderr


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"DJANGO_MEDIA_STORAGE": "dropbox"}, "DJANGO_MEDIA_STORAGE must be"),
        ({"DJANGO_MEDIA_STORAGE": "s3"}, "DJANGO_MEDIA_S3_BUCKET"),
        ({**S3, "DJANGO_MEDIA_S3_BUCKET": ""}, "DJANGO_MEDIA_S3_BUCKET"),
        ({**S3, "DJANGO_MEDIA_S3_BUCKET": " my-bucket "}, "DJANGO_MEDIA_S3_BUCKET"),
        ({**S3, "DJANGO_MEDIA_S3_ENDPOINT_URL": "http://s3.example.com"}, "must start with https"),
        ({**S3, "DJANGO_MEDIA_S3_ENDPOINT_URL": "s3.example.com"}, "DJANGO_MEDIA_S3_ENDPOINT_URL"),
        ({**S3, "DJANGO_MEDIA_S3_ENDPOINT_URL": "https://"}, "DJANGO_MEDIA_S3_ENDPOINT_URL"),
        ({**S3, "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE"}, "AWS_SECRET_ACCESS_KEY"),
        ({**S3, "AWS_SECRET_ACCESS_KEY": "secret"}, "AWS_ACCESS_KEY_ID"),
    ],
    ids=[
        "unknown storage",
        "no bucket",
        "empty bucket",
        "bucket with spaces",
        "plain http",
        "no scheme",
        "no host",
        "key without secret",
        "secret without key",
    ],
)
def test_misconfigured_uploads_are_refused(environment, message):
    result = run_manage("check", **environment)
    assert result.returncode != 0
    assert message in result.stderr


def test_an_https_endpoint_in_capitals_is_accepted_in_production():
    result = run_manage("check", DJANGO_MEDIA_S3_ENDPOINT_URL="HTTPS://s3.example.com", **S3)
    assert result.returncode == 0, result.stderr


def test_a_local_test_service_may_use_plain_http_outside_production():
    result = run_manage(
        "check",
        DJANGO_ENV="development",
        DJANGO_MEDIA_S3_ENDPOINT_URL="http://localhost:9000",
        **S3,
    )
    assert result.returncode == 0, result.stderr
