"""Every response (except /healthz) carries the security headers, passwords use Argon2,
and the strict Content Security Policy doesn't break the pages the project ships: the
admin and, in development, Django's debug pages."""

import re
import tomllib

import pytest
from django.conf import settings
from django.test import Client, override_settings

from tests.test_production_settings import PROJECT_DIR, run_manage

ADMIN = f"/{settings.ADMIN_URL}"
NONCE = "'nonce-…'"  # stands in for the per-response nonce when comparing policies

# The whole policy. Any change to SECURE_CSP has to be made here too, on purpose.
EXPECTED_POLICY = {
    "default-src": ["'none'"],
    "script-src": ["'self'", NONCE],
    "style-src": ["'self'", NONCE],
    "img-src": ["'self'"],
    "font-src": ["'self'"],
    "connect-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
}

# Inline code the CSP would block: <script> or <style> without a nonce (or a src),
# style="..." attributes, onclick=-style handlers and javascript: links.
BLOCKED = {
    "inline script": re.compile(r"<script(?![^>]*\b(?:src|nonce)=)[^>]*>", re.IGNORECASE),
    "inline style": re.compile(r"<style(?![^>]*\bnonce=)[^>]*>", re.IGNORECASE),
    "style attribute": re.compile(r"\sstyle\s*=", re.IGNORECASE),
    "event handler": re.compile(r"\son[a-z]+\s*=", re.IGNORECASE),
    "javascript: link": re.compile(r"javascript:", re.IGNORECASE),
    "empty nonce": re.compile(r"\snonce=(?:\"\"|'')", re.IGNORECASE),  # a nonce that went missing
}


def directives(header):
    """{"script-src": ["'self'", "'nonce-…'"], ...} from a Content-Security-Policy header."""
    parsed = {}
    for directive in header.split(";"):
        name, *sources = directive.split()
        parsed[name] = sources
    return parsed


def without_nonce(policy):
    nonce = re.compile(r"'nonce-[\w+/=-]+'")
    return {name: [NONCE if nonce.fullmatch(s) else s for s in v] for name, v in policy.items()}


def blocked_in(html):
    """What in this HTML the CSP would block, by kind; empty when nothing would be."""
    found = {name: pattern.findall(html) for name, pattern in BLOCKED.items()}
    return {name: matches for name, matches in found.items() if matches}


def last_line(result):
    return result.stdout.strip().splitlines()[-1]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "status"),
    [(f"{ADMIN}login/", 200), ("/no-such-page/", 404), ("/static/admin/css/base.css", 200)],
    ids=["page", "not found", "static file"],
)
def test_responses_send_the_security_headers(client, path, status):
    response = client.get(path)
    assert response.status_code == status
    if not path.startswith("/static/"):
        # WhiteNoise answers before it's added; a static file can't frame anything, and
        # the CSP's frame-ancestors covers framing anyway.
        assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "Content-Security-Policy" in response


@pytest.mark.django_db
def test_a_refused_form_sends_the_security_headers():
    # A CSRF failure is answered by Django itself, before any view.
    client = Client(enforce_csrf_checks=True)
    response = client.post(f"{ADMIN}login/", {"username": "x", "password": "y"})
    assert response.status_code == 403
    assert response["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response
    assert blocked_in(response.content.decode()) == {}


@pytest.mark.django_db
def test_the_csp_is_exactly_the_strict_policy(client):
    policy = directives(client.get(f"{ADMIN}login/")["Content-Security-Policy"])
    assert without_nonce(policy) == EXPECTED_POLICY


@pytest.mark.django_db
def test_each_response_gets_a_new_nonce(client):
    first = directives(client.get(f"{ADMIN}login/")["Content-Security-Policy"])
    second = directives(client.get(f"{ADMIN}login/")["Content-Security-Policy"])
    assert first["script-src"][1] != second["script-src"][1]


@pytest.mark.django_db
def test_the_admin_has_nothing_the_csp_would_block(client, admin_client, admin_user):
    pages = {
        "login": client.get(f"{ADMIN}login/"),
        "index": admin_client.get(ADMIN),
        "user list": admin_client.get(f"{ADMIN}accounts/user/"),
        "add user": admin_client.get(f"{ADMIN}accounts/user/add/"),
        "change user": admin_client.get(f"{ADMIN}accounts/user/{admin_user.pk}/change/"),
        "change password": admin_client.get(f"{ADMIN}password_change/"),
    }
    for name, page in pages.items():
        assert page.status_code == 200, name
        assert blocked_in(page.content.decode()) == {}, name


def test_development_reports_the_csp_instead_of_enforcing_it():
    # Django's yellow debug pages use inline styles; development only reports what the
    # policy would block, so they keep working. Tests and production enforce it.
    result = run_manage(
        "shell",
        "-c",
        "from django.conf import settings as s; "
        "print(s.SECURE_CSP == {}, [str(v) for v in s.SECURE_CSP_REPORT_ONLY['default-src']])",
        DJANGO_ENV="development",
    )
    assert last_line(result) == "True [\"'none'\"]", result.stderr


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_the_debug_page_is_what_development_has_to_allow(client):
    # Proves why development is report-only: this would be blocked if enforced.
    page = client.get("/no-such-page/")
    assert "inline style" in blocked_in(page.content.decode())


@pytest.mark.django_db
@override_settings(SECURE_HSTS_SECONDS=31536000, SECURE_HSTS_INCLUDE_SUBDOMAINS=True)
def test_hsts_is_sent_over_https_only(client):
    assert client.get(f"{ADMIN}login/", secure=True)["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert "Strict-Transport-Security" not in client.get(f"{ADMIN}login/")


def test_production_sends_hsts_for_a_year_without_preloading():
    # Preloading is a per-project opt-in (see the README), so its warning stays silenced.
    assert "security.W021" in settings.SILENCED_SYSTEM_CHECKS
    result = run_manage(
        "shell",
        "-c",
        "from django.conf import settings as s; "
        "print(s.SECURE_HSTS_SECONDS, s.SECURE_HSTS_INCLUDE_SUBDOMAINS, s.SECURE_HSTS_PRELOAD)",
    )
    assert last_line(result) == "31536000 True False", result.stderr


def test_production_hashes_passwords_with_argon2():
    result = run_manage(
        "shell",
        "-c",
        "from django.contrib.auth.hashers import get_hasher, identify_hasher, make_password; "
        "print(get_hasher().algorithm, identify_hasher(make_password('x')).algorithm)",
    )
    assert last_line(result) == "argon2 argon2", result.stderr


def test_an_older_password_hash_still_works_and_gets_upgraded():
    # check_password calls the setter (which saves a new hash) when the stored hash
    # wasn't made with the first hasher, Argon2.
    result = run_manage(
        "shell",
        "-c",
        "from django.contrib.auth.hashers import check_password, make_password; "
        "old = make_password('secret-1', hasher='pbkdf2_sha256'); upgraded = []; "
        "print(check_password('secret-1', old, setter=upgraded.append), upgraded == ['secret-1'])",
    )
    assert last_line(result) == "True True", result.stderr


def test_argon2_is_installed_in_production_not_just_for_development():
    # In the dev group only, tests would still pass but every production login would fail.
    pyproject = tomllib.loads((PROJECT_DIR / "pyproject.toml").read_text())
    dependencies = pyproject["project"]["dependencies"]
    assert any(dependency.startswith("argon2-cffi") for dependency in dependencies)


def test_development_serves_static_files_like_production():
    # whitenoise.runserver_nostatic must come before staticfiles to replace runserver's.
    apps = settings.INSTALLED_APPS
    assert apps.index("whitenoise.runserver_nostatic") < apps.index("django.contrib.staticfiles")
