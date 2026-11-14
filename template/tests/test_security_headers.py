"""Every response carries the security headers, passwords use Argon2, and the strict
Content Security Policy doesn't break the pages the project ships (the admin)."""

import re

import pytest
from django.conf import settings

from tests.test_production_settings import run_manage

ADMIN_LOGIN = f"/{settings.ADMIN_URL}login/"

# A <script> with neither src= nor nonce=: inline code the CSP would block.
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\b(?:src|nonce)=)[^>]*>", re.IGNORECASE)
# A style="..." attribute: blocked by the CSP (it has no nonce).
STYLE_ATTRIBUTE = re.compile(r"\sstyle\s*=", re.IGNORECASE)


@pytest.fixture
def login_page(client):
    response = client.get(ADMIN_LOGIN)
    assert response.status_code == 200
    return response


def directives(header):
    """{"script-src": ["'self'", "'nonce-…'"], ...} from a Content-Security-Policy header."""
    parsed = {}
    for directive in header.split(";"):
        name, *sources = directive.split()
        parsed[name] = sources
    return parsed


@pytest.mark.django_db
def test_every_page_sends_the_security_headers(login_page):
    assert login_page["X-Frame-Options"] == "DENY"
    assert login_page["X-Content-Type-Options"] == "nosniff"
    assert login_page["Referrer-Policy"] == "same-origin"
    assert login_page["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "Content-Security-Policy" in login_page


@pytest.mark.django_db
def test_the_csp_allows_only_this_site_and_nonced_inline_code(login_page):
    policy = directives(login_page["Content-Security-Policy"])
    assert policy["default-src"] == ["'self'"]
    for kind in ["script-src", "style-src"]:
        assert policy[kind][0] == "'self'"
        assert re.fullmatch(r"'nonce-[\w+/=-]+'", policy[kind][1])
        assert "'unsafe-inline'" not in policy[kind]
    assert policy["object-src"] == ["'none'"]
    assert policy["frame-ancestors"] == ["'none'"]


@pytest.mark.django_db
def test_each_response_gets_a_new_nonce(client):
    first = directives(client.get(ADMIN_LOGIN)["Content-Security-Policy"])
    second = directives(client.get(ADMIN_LOGIN)["Content-Security-Policy"])
    assert first["script-src"][1] != second["script-src"][1]


@pytest.mark.django_db
def test_the_admin_has_nothing_the_csp_would_block(admin_client, login_page):
    # admin_client is logged in as a superuser, so this covers the admin's main pages.
    pages = [login_page, admin_client.get(f"/{settings.ADMIN_URL}")]
    pages.append(admin_client.get(f"/{settings.ADMIN_URL}accounts/user/"))
    for page in pages:
        assert page.status_code == 200
        html = page.content.decode()
        assert INLINE_SCRIPT.findall(html) == []
        assert STYLE_ATTRIBUTE.findall(html) == []


def test_production_hashes_passwords_with_argon2():
    result = run_manage(
        "shell",
        "-c",
        "from django.contrib.auth.hashers import get_hasher, identify_hasher, make_password; "
        "print(get_hasher().algorithm, identify_hasher(make_password('x')).algorithm)",
    )
    assert result.stdout.strip().splitlines()[-1] == "argon2 argon2", result.stderr


def test_older_password_hashes_still_work_and_get_upgraded():
    # Django re-hashes with the first hasher whenever a password checks against another.
    hashers = run_manage("shell", "-c", "from django.conf import settings as s; print(s.PASSWORD_HASHERS)")
    listed = hashers.stdout.strip().splitlines()[-1]
    assert listed.startswith("['django.contrib.auth.hashers.Argon2PasswordHasher'"), hashers.stderr
    assert "PBKDF2PasswordHasher" in listed


def test_production_sends_hsts_for_a_year_without_preloading():
    result = run_manage(
        "shell",
        "-c",
        "from django.conf import settings as s; "
        "print(s.SECURE_HSTS_SECONDS, s.SECURE_HSTS_INCLUDE_SUBDOMAINS, s.SECURE_HSTS_PRELOAD)",
    )
    assert result.stdout.strip().splitlines()[-1] == "31536000 True False", result.stderr


def test_development_serves_static_files_like_production():
    # whitenoise.runserver_nostatic must come before staticfiles to replace runserver's.
    apps = settings.INSTALLED_APPS
    assert apps.index("whitenoise.runserver_nostatic") < apps.index("django.contrib.staticfiles")
