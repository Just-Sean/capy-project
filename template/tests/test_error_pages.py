"""Each error shows the site's own page, with no internal details, and the 500 page works
even with the database down. This file is also the URL map for its tests: views that
raise each kind of error."""

from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import HttpResponse
from django.template import Context, Engine, Template
from django.template.loader import render_to_string
from django.test import Client
from django.urls import path

from tests.test_production_settings import run_manage
from tests.test_security_headers import blocked_in, last_line

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

# A real crash in a request, through every middleware, in production, with nothing
# listening where the database and Redis should be. As in the image, `collectstatic` runs
# first (into a temporary folder), so the page uses production's compressed,
# cache-busting static files: it prints the status, whether the 500 page showed, and
# whether it linked the site's stylesheet by its hashed name.
CRASH_WITH_NOTHING_UP = (
    "import re, tempfile\n"
    "from django.core.management import call_command\n"
    "from django.test import Client, override_settings\n"
    "with tempfile.TemporaryDirectory() as static_root, override_settings(\n"
    "    ROOT_URLCONF='tests.test_error_pages', STATIC_ROOT=static_root\n"
    "):\n"
    "    call_command('collectstatic', interactive=False, verbosity=0)\n"
    "    response = Client(raise_request_exception=False).get('/crash/', secure=True,"
    " headers={'host': 'example.com'})\n"
    "html = response.content.decode()\n"
    "print(response.status_code, '<h1>Something went wrong</h1>' in html,"
    " bool(re.search(r'/static/site[.][0-9a-f]{12}[.]css', html)))\n"
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
@pytest.mark.parametrize("debug", [False, True], ids=["debug off", "debug on"])
def test_a_failed_form_security_check_explains_what_to_do(settings, debug):
    settings.DEBUG = debug
    browser = Client(enforce_csrf_checks=True)
    response = browser.post("/form/", {"name": "x"})  # no CSRF token
    assert response.status_code == 403
    html = response.content.decode()
    assert "<h1>Your form wasn't sent</h1>" in html
    # Django's reason is the main clue in development, and never shown in production.
    assert ("CSRF cookie not set" in html) is debug


def test_an_unknown_host_gets_the_400_page(visitor):
    response = visitor.get("/", headers={"host": "attacker.example"})
    assert response.status_code == 400
    assert "<h1>Bad request</h1>" in response.content.decode()


def test_the_500_page_works_with_the_database_and_redis_down():
    result = run_manage(
        "shell",
        "-c",
        CRASH_WITH_NOTHING_UP,
        DATABASE_URL="postgres://user:pass@127.0.0.1:1/db",
        CACHE_URL="redis://app:pass@127.0.0.1:1/0",
    )
    assert last_line(result) == "500 True True", result.stderr
    assert "hunter2" not in result.stdout


def test_a_page_without_a_title_still_gets_one():
    html = render_to_string("base.html")
    assert "<title>Untitled page</title>" in html


def test_a_page_can_add_to_the_head():
    # A page (or an app's layer) extending base.html adds stylesheets and meta tags
    # inside <head>, where browsers use them, without editing base.html.
    page = Template(
        '{% extends "base.html" %}{% block head %}<link rel="stylesheet" href="/x.css">'
        "{% endblock %}{% block content %}<p>body</p>{% endblock %}"
    )
    html = page.render(Context())
    head, body = html.split("</head>")
    assert '<link rel="stylesheet" href="/x.css">' in head
    assert "x.css" not in body and "<p>body</p>" in body


def test_a_page_adds_to_its_layouts_head_with_block_super(tmp_path):
    # The README's pattern: a layout fills the head (a theme's stylesheet), and a page
    # that extends it adds its own tags after {{ block.super }}, keeping the layout's.
    (tmp_path / "layout.html").write_text(
        '{% extends "base.html" %}{% block head %}<link rel="stylesheet" href="/theme.css">'
        "{% endblock %}"
    )
    (tmp_path / "page.html").write_text(
        '{% extends "layout.html" %}{% block title %}Map{% endblock %}'
        '{% block head %}{{ block.super }}<script src="/map.js" defer></script>{% endblock %}'
    )
    # The stand-in layout first, ahead of the project's own templates/layout.html.
    engine = Engine(
        dirs=[tmp_path, TEMPLATES_DIR], libraries={"static": "django.templatetags.static"}
    )
    head = engine.get_template("page.html").render(Context()).split("</head>")[0]
    assert head.index("/theme.css") < head.index("/map.js")
    assert "<title>Map</title>" in head


def test_a_themes_color_scheme_comes_before_the_default():
    # Browsers use the first color-scheme tag, so a light-only theme can set its own.
    page = Template(
        '{% extends "base.html" %}{% block head %}<meta name="color-scheme" content="light">'
        "{% endblock %}"
    )
    html = page.render(Context())
    assert html.index('content="light">') < html.index('content="light dark">')


LAYOUT = (
    '{% extends "base.html" %}'
    "{% block header %}<header><nav>Site menu</nav></header>{% endblock %}"
    "{% block content %}<h1>Page</h1>{% endblock %}"
    "{% block footer %}<footer>Contact</footer>{% endblock %}"
)


def test_header_and_footer_are_landmarks_of_their_own():
    # A layout's nav and footer stay outside <main>, so screen readers list a header,
    # the main content and a footer, rather than one <main> holding everything.
    html = Template(LAYOUT).render(Context())
    main = html[html.index("<main") : html.index("</main>")]
    assert "<h1>Page</h1>" in main
    assert "Site menu" not in main and "Contact" not in main
    assert html.index("Site menu") < html.index("<main") < html.index("</main>")
    assert html.index("</main>") < html.index("Contact")


def test_the_skip_link_comes_first_and_leads_to_the_main_content():
    html = Template(LAYOUT).render(Context())
    body = html[html.index("<body>") :]
    first_link = body[body.index("<a") : body.index("</a>")]
    assert 'href="#main"' in first_link and "Skip to the main content" in first_link
    assert body.index("Skip to the main content") < body.index("Site menu")
    assert '<main id="main" tabindex="-1">' in html


def test_every_page_loads_the_sites_stylesheet(visitor):
    # It hides the skip link until it's focused; without it the link would always show.
    html = render_to_string("404.html")
    assert '<link rel="stylesheet" href="/static/site.css">' in html
    response = visitor.get("/static/site.css")
    assert response.status_code == 200
    assert b".skip-link:focus" in b"".join(response.streaming_content)


@pytest.mark.urls(__name__)
@pytest.mark.parametrize("url", ["/bad/", "/forbidden/", "/no-such-page/", "/crash/"])
def test_every_error_page_has_the_page_structure(visitor, url):
    html = visitor.get(url).content.decode()
    assert html.count("<main") == 1 and '<main id="main" tabindex="-1">' in html
    assert html.index('href="#main"') < html.index("<main")
    assert '<link rel="stylesheet" href="/static/site.css">' in html


def test_a_page_without_header_or_footer_has_no_empty_landmarks():
    html = render_to_string("404.html")
    for landmark in ("<header", "<footer", "<nav"):
        assert landmark not in html


@pytest.mark.parametrize(
    "page", sorted(TEMPLATES_DIR.rglob("*.html")), ids=lambda p: str(p.relative_to(TEMPLATES_DIR))
)
def test_no_page_has_code_the_csp_would_block(page):
    assert blocked_in(page.read_text()) == {}


def test_the_proxys_page_stands_on_its_own():
    # The proxy shows it when Django is down, so it can't use Django or load anything.
    html = (TEMPLATES_DIR / "proxy_error.html").read_text()
    assert "{%" not in html and "{{" not in html
    for loads_something in ["<link", "<script", "<img", "src=", "@import"]:
        assert loads_something not in html
    assert "<h1>Temporarily unavailable</h1>" in html
