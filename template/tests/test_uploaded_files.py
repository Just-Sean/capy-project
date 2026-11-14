"""Uploaded files: local by default (development serves them), S3 if chosen, with safe
defaults, and misconfiguration refused at startup."""

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from tests.test_production_settings import run_manage

PRINT_STORAGE = (
    "from django.conf import settings as s; d = s.STORAGES['default']; "
    "o = d.get('OPTIONS', {}); "
    "print(d['BACKEND'], sorted(o), o.get('default_acl'), o.get('file_overwrite'), "
    "o.get('querystring_auth'), o.get('location'))"
)
S3 = {"DJANGO_MEDIA_STORAGE": "s3", "DJANGO_MEDIA_S3_BUCKET": "my-bucket"}
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


def test_development_serves_uploads_and_production_doesnt():
    development = run_manage("shell", "-c", CAN_RESOLVE_MEDIA, DJANGO_ENV="development")
    production = run_manage("shell", "-c", CAN_RESOLVE_MEDIA)
    assert last_line(development) == "served", development.stderr
    assert last_line(production) == "not served", production.stderr


def test_s3_is_private_signed_and_never_overwrites():
    result = run_manage("shell", "-c", PRINT_STORAGE, **S3)
    assert last_line(result) == (
        "storages.backends.s3.S3Storage ['bucket_name', 'default_acl', 'endpoint_url', "
        "'file_overwrite', 'location', 'querystring_auth', 'querystring_expire', "
        "'region_name'] private False True media"
    ), result.stderr


def test_s3_keys_are_used_only_when_given():
    # Without keys, boto3 uses the server's own role instead.
    keys = {"AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "x"}
    result = run_manage("shell", "-c", PRINT_STORAGE, **keys, **S3)
    assert "'access_key'" in last_line(result) and "'secret_key'" in last_line(result)


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"DJANGO_MEDIA_STORAGE": "dropbox"}, "DJANGO_MEDIA_STORAGE must be"),
        ({"DJANGO_MEDIA_STORAGE": "s3"}, "DJANGO_MEDIA_S3_BUCKET"),
        ({**S3, "DJANGO_MEDIA_S3_ENDPOINT_URL": "http://s3.example.com"}, "must start with https"),
        ({**S3, "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE"}, "AWS_SECRET_ACCESS_KEY"),
    ],
    ids=["unknown storage", "no bucket", "plain http", "key without secret"],
)
def test_misconfigured_uploads_are_refused(environment, message):
    result = run_manage("check", **environment)
    assert result.returncode != 0
    assert message in result.stderr


def test_a_local_test_service_may_use_plain_http_outside_production():
    result = run_manage(
        "check",
        DJANGO_ENV="development",
        DJANGO_MEDIA_S3_ENDPOINT_URL="http://localhost:9000",
        **S3,
    )
    assert result.returncode == 0, result.stderr
