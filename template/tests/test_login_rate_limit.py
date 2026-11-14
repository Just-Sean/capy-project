"""Login rate limiting (django-axes plus config/login_limits.py): repeated wrong
passwords lock that username out from that address, too many failures from one address
lock the address out whatever usernames it tries, nobody else is affected, and a faked
X-Forwarded-For header can't get around either limit."""

from datetime import timedelta

import pytest
from axes.models import AccessAttempt, AccessLog
from django.conf import settings
from django.test import RequestFactory, override_settings
from django.utils import timezone

from config.login_limits import client_ip
from tests.test_production_settings import run_manage

LOGIN = f"/{settings.ADMIN_URL}login/"
PASSWORD = "a-long-correct-password"
LIMIT = settings.AXES_FAILURE_LIMIT
LOCKED = 429  # Too Many Requests
LOGGED_IN = 302  # the admin redirects after a successful login
PRINT_LIMITS = (
    "from django.conf import settings as s; "
    "print(s.AXES_FAILURE_LIMIT, s.LOGIN_IP_FAILURE_LIMIT, s.AXES_COOLOFF_TIME)"
)


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


def last_line(result):
    return result.stdout.strip().splitlines()[-1]


# --- The limits and their settings -------------------------------------------------


def test_the_defaults_are_5_per_user_30_per_address_for_15_minutes():
    # Read without .env, so a developer's own values don't change the answer.
    result = run_manage("shell", "-c", PRINT_LIMITS)
    assert last_line(result) == "5 30 0:15:00", result.stderr


def test_the_limits_come_from_the_environment():
    result = run_manage(
        "shell",
        "-c",
        PRINT_LIMITS,
        DJANGO_LOGIN_FAILURE_LIMIT="3",
        DJANGO_LOGIN_IP_FAILURE_LIMIT="12",
        DJANGO_LOGIN_LOCKOUT_MINUTES="60",
    )
    assert last_line(result) == "3 12 1:00:00", result.stderr


@pytest.mark.parametrize(
    "variable",
    ["DJANGO_LOGIN_FAILURE_LIMIT", "DJANGO_LOGIN_IP_FAILURE_LIMIT", "DJANGO_LOGIN_LOCKOUT_MINUTES"],
)
def test_a_limit_below_one_is_refused(variable):
    # 0 minutes would mean "locked until someone resets it"; 0 attempts, never allowed.
    result = run_manage("check", **{variable: "0"})
    assert result.returncode != 0
    assert "must each be at least 1" in result.stderr


# --- Per username and address ------------------------------------------------------


@pytest.mark.django_db
def test_wrong_passwords_lock_the_user_out_even_with_the_right_one(client, staff):
    fail(client, LIMIT)
    response = log_in(client, PASSWORD)
    assert response.status_code == LOCKED
    assert int(response["Retry-After"]) > 0


@pytest.mark.django_db
def test_a_lockout_doesnt_block_other_users_or_other_addresses(client, staff, django_user_model):
    django_user_model.objects.create_user(
        username="other", email="other@example.com", password=PASSWORD, is_staff=True
    )
    fail(client, LIMIT)
    assert log_in(client, PASSWORD, username="other").status_code == LOGGED_IN
    client.logout()
    assert log_in(client, PASSWORD, ip="198.51.100.7").status_code == LOGGED_IN


@pytest.mark.django_db
def test_the_lockout_ends_after_its_time(client, staff):
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
def test_logged_in_users_stay_logged_in(client, staff):
    # The rate-limit backends must never be the one Django uses to load a session's user.
    client.force_login(staff)
    assert client.get(f"/{settings.ADMIN_URL}").status_code == 200


@pytest.mark.django_db
def test_successful_logins_arent_recorded(client, staff):
    assert log_in(client, PASSWORD).status_code == LOGGED_IN
    assert AccessLog.objects.count() == 0


# --- Per address, across usernames ---------------------------------------------------


@pytest.mark.django_db
@override_settings(LOGIN_IP_FAILURE_LIMIT=8)
def test_a_new_username_each_time_still_hits_the_address_limit(client, staff):
    for attempt in range(8):
        log_in(client, "wrong-password", username=f"guess-{attempt}")
    assert log_in(client, PASSWORD).status_code == LOCKED  # even the right login
    assert log_in(client, PASSWORD, ip="198.51.100.7").status_code == LOGGED_IN  # elsewhere


@pytest.mark.django_db
@override_settings(LOGIN_IP_FAILURE_LIMIT=8)
def test_the_address_limit_counts_only_recent_failures(client, staff):
    for attempt in range(8):
        log_in(client, "wrong-password", username=f"guess-{attempt}")
    earlier = timezone.now() - settings.AXES_COOLOFF_TIME - timedelta(minutes=1)
    AccessAttempt.objects.update(attempt_time=earlier)
    assert log_in(client, PASSWORD).status_code == LOGGED_IN


# --- Which address counts ----------------------------------------------------------


@pytest.mark.django_db
def test_a_faked_forwarded_header_doesnt_help_when_not_behind_a_proxy(client, staff):
    for attempt in range(LIMIT):
        log_in(client, "wrong-password", HTTP_X_FORWARDED_FOR=f"10.0.0.{attempt}")
    assert log_in(client, PASSWORD, HTTP_X_FORWARDED_FOR="10.0.0.99").status_code == LOCKED


@pytest.mark.django_db
@override_settings(BEHIND_PROXY=True)
def test_behind_a_proxy_only_the_address_it_adds_counts(client, staff):
    # The proxy adds the real address last; anything before it came from the visitor.
    proxy = "10.1.0.1"
    for attempt in range(LIMIT):
        faked = f"1.2.3.{attempt}, 203.0.113.5"
        log_in(client, "wrong-password", ip=proxy, HTTP_X_FORWARDED_FOR=faked)
    locked = log_in(client, PASSWORD, ip=proxy, HTTP_X_FORWARDED_FOR="9.9.9.9, 203.0.113.5")
    assert locked.status_code == LOCKED
    other = log_in(client, PASSWORD, ip=proxy, HTTP_X_FORWARDED_FOR="203.0.113.6")
    assert other.status_code == LOGGED_IN


@pytest.mark.django_db
@override_settings(BEHIND_PROXY=True)
def test_a_new_port_each_time_doesnt_get_around_the_lockout(client, staff):
    for port in range(50000, 50000 + LIMIT):
        faked = f"203.0.113.5:{port}"
        log_in(client, "wrong-password", ip="10.1.0.1", HTTP_X_FORWARDED_FOR=faked)
    locked = log_in(client, PASSWORD, ip="10.1.0.1", HTTP_X_FORWARDED_FOR="203.0.113.5:50099")
    assert locked.status_code == LOCKED


@pytest.mark.django_db
def test_a_try_during_the_lockout_restarts_it(client, staff):
    fail(client, LIMIT)
    nearly_over = timezone.now() - settings.AXES_COOLOFF_TIME + timedelta(minutes=1)
    AccessAttempt.objects.update(attempt_time=nearly_over)
    assert log_in(client, "wrong-password").status_code == LOCKED  # restarts the time
    assert log_in(client, PASSWORD).status_code == LOCKED  # still locked a minute later


@pytest.mark.parametrize(
    ("behind_proxy", "remote", "forwarded", "expected"),
    [
        (False, "10.0.0.1", "1.1.1.1", "10.0.0.1"),  # the header is ignored
        (True, "10.0.0.1", "1.1.1.1, 2.2.2.2", "2.2.2.2"),  # only the proxy's entry
        (True, "10.0.0.1", " 2.2.2.2 ", "2.2.2.2"),
        (True, "10.0.0.1", "", "10.0.0.1"),  # no header: the connection's own address
        (True, "10.0.0.1", "1.1.1.1,", "10.0.0.1"),  # empty last entry
        (True, "10.0.0.1", "not-an-address", "10.0.0.1"),  # junk: the connection's own
        (True, "10.0.0.1", "203.0.113.5:50123", "203.0.113.5"),  # a port some proxies add
        (True, "10.0.0.1", "[2001:db8:1:2::9]:443", "2001:db8:1:2::"),
        (True, "10.0.0.1", "1.1.1.1,\t2.2.2.2\t", "2.2.2.2"),
        (False, "2001:db8:1:2:aaaa::1", "", "2001:db8:1:2::"),  # IPv6 counts per /64
        (False, "2001:db8:1:2:bbbb::9", "", "2001:db8:1:2::"),  # same /64, same address
    ],
)
def test_client_ip(behind_proxy, remote, forwarded, expected):
    headers = {"HTTP_X_FORWARDED_FOR": forwarded} if forwarded else {}
    request = RequestFactory().get("/", REMOTE_ADDR=remote, **headers)
    with override_settings(BEHIND_PROXY=behind_proxy):
        assert client_ip(request) == expected
