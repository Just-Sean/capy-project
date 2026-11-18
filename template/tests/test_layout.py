"""templates/layout.html, which the site's own pages and plugged-in apps extend: what a
page fills in, where Django's messages show, and that the error pages stay on the bare
base.html. This file is also the URL map for its tests: pages that extend the layout,
plus the project's own URLs, so a nav link ({% url %}) in the layout still works.

The checks hold for a project's own edited layout.html too (a nav, a theme's lines,
which read the database, a footer), so they keep checking what plugged-in apps rely on.
"""

import re
from html.parser import HTMLParser

import pytest
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.template import RequestContext, Template
from django.urls import include, path

from tests.test_error_pages import TEMPLATES_DIR

ERROR_PAGES = ["400.html", "403.html", "403_csrf.html", "404.html", "500.html"]
# Tags with no closing tag, so they never change how deep inside the region we are.
VOID_TAGS = {"area", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
FIRST_EXTENDS = re.compile(r"\{%\s*extends\s+(['\"])(?P<name>[^'\"]+)\1\s*%\}")

# A theme module's lines read the database, so these tests may use it.
pytestmark = pytest.mark.django_db

# A page as a plugged-in app writes it: only the title, head and content blocks.
APP_PAGE = (
    '{% extends "layout.html" %}{% block title %}Invoices{% endblock %}'
    '{% block head %}{{ block.super }}<script src="/invoices.js" defer></script>'
    "{% endblock %}{% block content %}<h1>Invoices</h1>{% endblock %}"
)


def app_page(request):
    # Adds a message for each ?m=..., as a view does after saving something.
    for text in request.GET.getlist("m"):
        messages.success(request, text)
    # Compiled on each request, so it uses the template settings of the moment (a test
    # can put a stand-in layout.html first).
    return HttpResponse(Template(APP_PAGE).render(RequestContext(request)))


def missing(request):
    messages.success(request, "Saved.")
    raise Http404


urlpatterns = [
    path("invoices/", app_page),
    path("missing/", missing),
    path("", include("config.urls")),
]


class StatusRegion(HTMLParser):
    """Collects the text inside the element with role="status", however deeply its
    messages are wrapped (a theme might put each in its own <div>), and whether that
    element is inside <header>."""

    def __init__(self):
        super().__init__()
        self.found = False
        self.in_header = False
        self.region_in_header = False
        self.depth = 0  # more than 0 while inside the region
        self.text = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            self.depth += tag not in VOID_TAGS
        elif ("role", "status") in attrs:
            self.found, self.depth = True, 1
            self.region_in_header = self.in_header
        elif tag == "header":
            self.in_header = True

    def handle_startendtag(self, tag, attrs):
        pass  # <img ... />: opens and closes at once, so the depth stays the same

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
        elif tag == "header":
            self.in_header = False

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)


def status_region(html):
    parser = StatusRegion()
    parser.feed(html)
    assert parser.found, 'no role="status" region: modules show their messages there'
    return parser


def region_text(html):
    return "".join(status_region(html).text)


@pytest.mark.urls(__name__)
def test_an_apps_page_fills_the_title_head_and_content(client):
    html = client.get("/invoices/").content.decode()
    head, body = html.split("</head>")
    assert "<title>Invoices</title>" in head
    assert '<script src="/invoices.js" defer></script>' in head
    main = body[body.index("<main") : body.index("</main>")]
    assert "<h1>Invoices</h1>" in main
    assert html.count("<main") == 1


@pytest.mark.urls(__name__)
def test_messages_show_in_the_status_region_in_the_header(client):
    html = client.get("/invoices/", {"m": "Saved."}).content.decode()
    assert "Saved." in region_text(html)
    assert status_region(html).region_in_header
    assert html.index("</header>") < html.index("<main")


@pytest.mark.urls(__name__)
def test_the_status_region_is_there_without_messages(client):
    # Always present, so a message added later without a page reload is announced.
    html = client.get("/invoices/").content.decode()
    assert region_text(html).strip() == ""


@pytest.mark.urls(__name__)
def test_a_message_is_shown_once(client):
    client.get("/invoices/", {"m": "Saved."})
    html = client.get("/invoices/").content.decode()
    assert "Saved." not in html


@pytest.mark.urls(__name__)
def test_every_message_shows_in_order_and_escaped(client):
    sent = ["First ✓ 🎉", "<b>x</b> & y", "Third"]
    html = client.get("/invoices/", {"m": sent}).content.decode()
    region = region_text(html)  # the text, with HTML entities decoded
    first, second, third = (region.index(text) for text in sent)
    assert first < second < third
    assert "<b>x</b>" not in html  # shown as text, never as markup


@pytest.mark.urls(__name__)
def test_a_message_waits_past_an_error_page_for_the_next_page(client):
    # Error pages use the bare base.html, so a pending message isn't lost on them.
    response = client.get("/missing/")
    assert response.status_code == 404
    assert "Saved." not in response.content.decode()
    html = client.get("/invoices/").content.decode()
    assert "Saved." in region_text(html)


# A layout as a project edits it: a nav link, a theme's line on <html> (starting with a
# space), its messages each in their own <div> with an icon, and a footer.
EDITED_LAYOUT = """{% extends "base.html" %}
{% block html_attrs %} data-theme="dark"{% endblock %}
{% block header %}<header>
  <nav aria-label="Primary"><a href="{% url "csp-report" %}">Link</a></nav>
  <div role="status">{% for message in messages %}
    <div class="alert"><img src="/i.svg" alt=""><br/><span>{{ message }}</span></div>
  {% endfor %}</div>
</header>{% endblock %}
{% block footer %}<footer>Contact</footer>{% endblock %}
"""


@pytest.mark.urls(__name__)
def test_the_checks_work_with_an_edited_layout(client, settings, tmp_path):
    (tmp_path / "layout.html").write_text(EDITED_LAYOUT)
    engine = settings.TEMPLATES[0]
    settings.TEMPLATES = [{**engine, "DIRS": [tmp_path, *engine["DIRS"]]}]

    html = client.get("/invoices/", {"m": ["First", "Second"]}).content.decode()
    assert '<html lang="en" data-theme="dark">' in html
    assert '<a href="/csp-report/">Link</a>' in html
    assert "First" in region_text(html) and "Second" in region_text(html)
    assert status_region(html).region_in_header
    assert "<footer>Contact</footer>" in html
    assert region_text(client.get("/invoices/").content.decode()).strip() == ""


@pytest.mark.parametrize("page", ERROR_PAGES)
def test_error_pages_stay_on_the_bare_base(page):
    # The 500 page must work with the database down, and the layout is where tags that
    # read it go: error pages never use the layout.
    match = FIRST_EXTENDS.search((TEMPLATES_DIR / page).read_text())
    assert match and match["name"] == "base.html", (
        f"{page} must extend base.html, not a layout (see the README's Error pages)"
    )
