"""templates/layout.html, which the site's own pages and plugged-in apps extend: what a
page fills in, where Django's messages show, and that the error pages stay on the bare
base.html. This file is also the URL map for its tests: pages that extend the layout.

The checks hold for a project's own edited layout.html too (a theme's lines, a nav, a
footer), so they keep checking what plugged-in apps rely on."""

import re
from pathlib import Path

import pytest
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.template import RequestContext, Template
from django.urls import path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
ERROR_PAGES = ["400.html", "403.html", "403_csrf.html", "404.html", "500.html"]

# A page as a plugged-in app writes it: only the title, head and content blocks.
APP_PAGE = Template(
    '{% extends "layout.html" %}{% block title %}Invoices{% endblock %}'
    '{% block head %}{{ block.super }}<script src="/invoices.js" defer></script>'
    "{% endblock %}{% block content %}<h1>Invoices</h1>{% endblock %}"
)


def app_page(request):
    # Adds a message for each ?m=..., as a view does after saving something.
    for text in request.GET.getlist("m"):
        messages.success(request, text)
    return HttpResponse(APP_PAGE.render(RequestContext(request)))


# A page whose html_attrs line is a theme module's: it starts with a space.
THEMED_PAGE = Template(
    '{% extends "layout.html" %}{% block html_attrs %} data-theme="dark"{% endblock %}'
)


def themed_page(request):
    return HttpResponse(THEMED_PAGE.render(RequestContext(request)))


def missing(request):
    messages.success(request, "Saved.")
    raise Http404


urlpatterns = [
    path("invoices/", app_page),
    path("themed/", themed_page),
    path("missing/", missing),
]


def status_region(html):
    # The element with role="status" (any tag, any other attributes) and what's in it.
    match = re.search(r'<(\w+)[^>]*\brole="status"[^>]*>(.*?)</\1>', html, re.DOTALL)
    assert match, "no role=status region: modules show their messages there"
    return match


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
    region = status_region(html)
    assert "Saved." in region.group(2)
    header = html[html.index("<header") : html.index("</header>")]
    assert region.group(0) in header
    assert html.index("</header>") < html.index("<main")


@pytest.mark.urls(__name__)
def test_the_status_region_is_there_without_messages(client):
    # Always present, so a message added later without a page reload is announced.
    html = client.get("/invoices/").content.decode()
    assert status_region(html).group(2).strip() == ""


@pytest.mark.urls(__name__)
def test_a_message_is_shown_once(client):
    client.get("/invoices/", {"m": "Saved."})
    html = client.get("/invoices/").content.decode()
    assert "Saved." not in html


@pytest.mark.urls(__name__)
def test_every_message_shows_in_order_and_escaped(client):
    sent = ["First ✓ 🎉", "<b>x</b> & y", "Third"]
    html = client.get("/invoices/", {"m": sent}).content.decode()
    region = status_region(html).group(2)
    assert region.index("First ✓ 🎉") < region.index("&lt;b&gt;x&lt;/b&gt; &amp; y")
    assert region.index("&amp; y") < region.index("Third")
    assert "<b>x</b>" not in html


@pytest.mark.urls(__name__)
def test_a_message_waits_past_an_error_page_for_the_next_page(client):
    # Error pages use the bare base.html, so a pending message isn't lost on them.
    response = client.get("/missing/")
    assert response.status_code == 404
    assert "Saved." not in response.content.decode()
    html = client.get("/invoices/").content.decode()
    assert "Saved." in status_region(html).group(2)


@pytest.mark.urls(__name__)
def test_a_themes_html_attrs_land_on_the_html_element(client):
    html = client.get("/themed/").content.decode()
    assert '<html lang="en" data-theme="dark">' in html


@pytest.mark.parametrize("page", ERROR_PAGES)
def test_error_pages_stay_on_the_bare_base(page):
    # The 500 page must work with the database down, and the layout is where tags that
    # read it go: error pages never use the layout.
    assert (TEMPLATES_DIR / page).read_text().startswith('{% extends "base.html" %}')
