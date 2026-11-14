"""Login rate limiting (django-axes): repeated wrong passwords lock that username out
from that IP address for a while, without affecting anyone else, and a faked
X-Forwarded-For header can't get around it."""

from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.conf import settings
from django.test import RequestFactory, override_settings
from django.utils import timezone

from config.client_ip import client_ip

LOGIN = f"/{settings.ADMIN_URL}login/"
PASSWORD = "a-long-correct-password"
LIMIT = settings.AXES_FAILURE_LIMIT
LOCKED = 429  # Too Many Requests
LOGGED_IN = 302  # the admin redirects after a successful login


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(
        username="staff", email="staff@example.com", password=PASSWORD, is_staff=True
    )


def log_in(client, password, username="staff", ip="203.0.113.1", **headers):
    data = {"username": username, "password": password, "next": f"/{settings.ADMIN_URL}"}
    return client.post(LOGIN, data, REMOTE_ADDR=ip, **headers)


def fail(client, times, **kwargs):
    for _ in range(times):
        assert log_in(client, "wrong-password", **kwargs).status_code != LOGGED_IN


@pytest.mark.django_db
def test_the_defaults_are_five_attempts_and_fifteen_minutes():
    assert settings.AXES_FAILURE_LIMIT == 5
    assert settings.AXES_COOLOFF_TIME == timedelta(minutes=15)


@pytest.mark.django_db
def test_wrong_passwords_lock_the_user_out_even_with_the_right_one(client, staff):
    fail(client, LIMIT - 1)
    assert log_in(client, PASSWORD).status_code == LOGGED_IN  # still allowed before the limit
    client.logout()
    AccessAttempt.objects.all().delete()  # start counting again

    fail(client, LIMIT)
    response = log_in(client, PASSWORD)
    assert response.status_code == LOCKED
    assert int(response["Retry-After"]) > 0


@pytest.mark.django_db
def test_a_lockout_doesnt_block_other_users_or_other_addresses(client, staff, django_user_model):
    django_user_model.objects.create_user(username="other", email="o@example.com", password=PASSWORD)
    fail(client, LIMIT)
    assert log_in(client, PASSWORD, username="other").status_code == LOGGED_IN
    client.logout()
    assert log_in(client, PASSWORD, ip="198.51.100.7").status_code == LOGGED_IN


@pytest.mark.django_db
def test_the_lockout_ends_after_the_cool_off(client, staff):
    fail(client, LIMIT)
    assert log_in(client, PASSWORD).status_code == LOCKED
    earlier = timezone.now() - settings.AXES_COOLOFF_TIME - timedelta(minutes=1)
    AccessAttempt.objects.update(attempt_time=earlier)
    assert log_in(client, PASSWORD).status_code == LOGGED_IN


@pytest.mark.django_db
def test_a_successful_login_clears_the_count(client, staff):
    fail(client, LIMIT - 1)
    assert log_in(client, PASSWORD).status_code == LOGGED_IN
    client.logout()
    fail(client, LIMIT - 1)  # would be over the limit if the earlier failures still counted
    assert log_in(client, PASSWORD).status_code == LOGGED_IN


@pytest.mark.django_db
def test_a_faked_forwarded_header_doesnt_help_when_not_behind_a_proxy(client, staff):
    for attempt in range(LIMIT):
        log_in(client, "wrong-password", HTTP_X_FORWARDED_FOR=f"10.0.0.{attempt}")
    assert log_in(client, PASSWORD, HTTP_X_FORWARDED_FOR="10.0.0.99").status_code == LOCKED


@pytest.mark.django_db
@override_settings(BEHIND_PROXY=True)
def test_behind_a_proxy_only_the_address_it_adds_counts(client, staff):
    # The proxy adds the real address last; anything before it came from the visitor.
    for attempt in range(LIMIT):
        log_in(client, "wrong-password", ip="10.1.0.1", HTTP_X_FORWARDED_FOR=f"1.2.3.{attempt}, 203.0.113.5")
    locked = log_in(client, PASSWORD, ip="10.1.0.1", HTTP_X_FORWARDED_FOR="9.9.9.9, 203.0.113.5")
    assert locked.status_code == LOCKED
    other = log_in(client, PASSWORD, ip="10.1.0.1", HTTP_X_FORWARDED_FOR="203.0.113.6")
    assert other.status_code == LOGGED_IN


@pytest.mark.parametrize(
    ("behind_proxy", "headers", "expected"),
    [
        (False, {"HTTP_X_FORWARDED_FOR": "1.1.1.1"}, "10.0.0.1"),
        (True, {"HTTP_X_FORWARDED_FOR": "1.1.1.1, 2.2.2.2"}, "2.2.2.2"),
        (True, {"HTTP_X_FORWARDED_FOR": " 2.2.2.2 "}, "2.2.2.2"),
        (True, {}, "10.0.0.1"),  # no header: the connection's own address
    ],
)
def test_client_ip(behind_proxy, headers, expected):
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", **headers)
    with override_settings(BEHIND_PROXY=behind_proxy):
        assert client_ip(request) == expected
