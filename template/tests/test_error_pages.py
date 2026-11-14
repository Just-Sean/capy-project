"""Each error shows the site's own page, with no internal details, and the 500 page works
even with the database down. This file is also the URL map for its tests: views that
raise each kind of error."""

from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import HttpResponse
from django.test import Client
from django.urls import path

from tests.test_production_settings import run_manage
from tests.test_security_headers import blocked_in

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
SECRET_DETAIL = "internal detail: db.internal password hunter2"


def bad_request(request):
    raise SuspiciousOperation(SECRET_DETAIL)


def forbidden(request):
    raise PermissionDenied(SECRET_DETAIL)


def crash(request):
    raise ValueError(SECRET_DETAIL)


def a_form(request):
    return HttpResponse("saved")


urlpatterns = [
    path("bad/", bad_request),
    path("forbidden/", forbidden),
    path("crash/", crash),
    path("form/", a_form),
]

# The 500 page as Django renders it on a crash, with nothing listening where the
# database and Redis should be.
SERVER_ERROR_WITH_NOTHING_UP = (
    "from django.test import RequestFactory\n"
    "from django.views.defaults import server_error\n"
    "response = server_error(RequestFactory().get('/'))\n"
    "print(response.status_code, '<h1>Something went wrong</h1>' in response.content.decode())\n"
)


@pytest.fixture
def visitor():
    """A browser: a crash gives the 500 page instead of an exception in the test."""
    return Client(raise_request_exception=False)


@pytest.mark.urls(__name__)
@pytest.mark.parametrize(
    ("url", "status", "heading"),
    [
        ("/bad/", 400, "Bad request"),
        ("/forbidden/", 403, "Access denied"),
        ("/no-such-page/", 404, "Page not found"),
        ("/crash/", 500, "Something went wrong"),
    ],
)
def test_each_error_shows_the_sites_page_without_details(visitor, url, status, heading):
    response = visitor.get(url)
    assert response.status_code == status
    html = response.content.decode()
    assert f"<h1>{heading}</h1>" in html
    assert '<html lang="en">' in html
    assert "hunter2" not in html and "Traceback" not in html


@pytest.mark.urls(__name__)
def test_a_failed_form_security_check_explains_what_to_do():
    browser = Client(enforce_csrf_checks=True)
    response = browser.post("/form/", {"name": "x"})  # no CSRF token
    assert response.status_code == 403
    assert "<h1>Please try again</h1>" in response.content.decode()


def test_an_unknown_host_gets_the_400_page(visitor):
    response = visitor.get("/", headers={"host": "attacker.example"})
    assert response.status_code == 400
    assert "<h1>Bad request</h1>" in response.content.decode()


def test_the_500_page_works_with_the_database_and_redis_down():
    result = run_manage(
        "shell",
        "-c",
        SERVER_ERROR_WITH_NOTHING_UP,
        DATABASE_URL="postgres://user:pass@127.0.0.1:1/db",
        CACHE_URL="redis://app:pass@127.0.0.1:1/0",
    )
    assert result.stdout.strip().splitlines()[-1] == "500 True", result.stderr


@pytest.mark.parametrize("page", sorted(TEMPLATES_DIR.glob("*.html")), ids=lambda p: p.name)
def test_no_page_has_code_the_csp_would_block(page):
    assert blocked_in(page.read_text()) == {}


def test_the_proxys_page_stands_on_its_own():
    # The proxy shows it when Django is down, so it can't use Django or load anything.
    html = (TEMPLATES_DIR / "proxy_error.html").read_text()
    assert "{%" not in html and "{{" not in html
    for loads_something in ["<link", "<script", "<img", "src=", "@import"]:
        assert loads_something not in html
    assert "<h1>Temporarily unavailable</h1>" in html
