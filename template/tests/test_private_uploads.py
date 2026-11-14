"""Private uploads (config/uploads.py): only those can_download() allows get a file, as a
download; everyone else gets a 404, whether or not the file exists."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from config.uploads import public_storage, random_folder

PASSWORD = "a-long-test-password"


@pytest.fixture
def uploads(settings, tmp_path):
    """A private uploads folder for the test, with one file in it."""
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_SENT_BY_PROXY = False
    name = default_storage.save("reports/q1 #2.pdf", ContentFile(b"%PDF secret"))
    return name


def user(**fields):
    User = get_user_model()
    username = fields.pop("username", "someone")
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, **fields
    )


def address(name):
    return default_storage.url(name)


@pytest.mark.django_db
def test_staff_get_a_private_file_as_a_download(client, uploads):
    client.force_login(user(is_staff=True))
    response = client.get(address(uploads))
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"%PDF secret"
    assert response["Content-Disposition"] == "attachment"
    assert response["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert response["Cache-Control"] == "private"
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "who", ["nobody logged in", "a user who isn't staff", "staff whose account is off"]
)
def test_anyone_else_gets_a_404(client, uploads, who):
    if who == "a user who isn't staff":
        client.force_login(user())
    elif who == "staff whose account is off":
        client.force_login(user(is_staff=True, is_active=False))
    response = client.get(address(uploads))
    assert response.status_code == 404
    assert b"secret" not in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/media/no-such-file.pdf", "/media/../config/settings/core.py"])
def test_a_missing_file_or_one_outside_the_folder_is_a_404_even_for_staff(client, uploads, path):
    client.force_login(user(is_staff=True))
    assert client.get(path).status_code == 404


@pytest.mark.django_db
def test_behind_caddy_the_app_names_the_file_and_caddy_sends_it(client, settings, uploads):
    settings.MEDIA_SENT_BY_PROXY = True
    client.force_login(user(is_staff=True))
    response = client.get(address(uploads))
    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == "/reports/q1%20%232.pdf"  # escaped for a path
    assert response.content == b""  # Caddy sends the file
    assert response["Content-Disposition"] == "attachment"


@pytest.mark.django_db
def test_behind_caddy_others_still_get_a_404(client, settings, uploads):
    settings.MEDIA_SENT_BY_PROXY = True
    response = client.get(address(uploads))
    assert response.status_code == 404
    assert "X-Accel-Redirect" not in response


def test_random_folder_puts_each_file_in_its_own_unguessable_folder():
    first = random_folder(None, "invoice.pdf")
    second = random_folder(None, "invoice.pdf")
    assert re.fullmatch(r"[0-9a-f]{32}/invoice\.pdf", first)
    assert first != second


def test_public_storage_saves_to_the_public_folder_not_the_private_one(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "public": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": tmp_path / "public", "base_url": "/media-public/"},
        },
    }
    name = public_storage().save("photo.png", ContentFile(b"png"))
    assert (tmp_path / "public" / name).read_bytes() == b"png"
    assert public_storage().url(name) == "/media-public/photo.png"
