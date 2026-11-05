import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_email_is_stored_lowercase():
    user = User.objects.create_user(username="bob", email="  Bob@Example.COM ", password="x")
    assert user.email == "bob@example.com"


def test_email_unique_regardless_of_case():
    User.objects.create_user(username="bob", email="bob@example.com", password="x")
    other = User.objects.create_user(username="rob", email="rob@example.com", password="x")
    # .update() skips save(), so this proves the database constraint itself works.
    with pytest.raises(IntegrityError):
        User.objects.filter(pk=other.pk).update(email="BOB@example.com")


def test_email_is_required():
    user = User(username="nobody", email="")
    with pytest.raises(Exception, match="email"):
        user.full_clean()


def test_every_user_gets_a_unique_public_id():
    a = User.objects.create_user(username="a", email="a@example.com", password="x")
    b = User.objects.create_user(username="b", email="b@example.com", password="x")
    assert a.public_id and b.public_id and a.public_id != b.public_id


def test_create_superuser():
    admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="x")
    assert admin.is_staff and admin.is_superuser
