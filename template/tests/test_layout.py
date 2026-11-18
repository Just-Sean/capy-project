"""templates/layout.html, which the site's own pages and plugged-in apps extend: what a
page fills in, where Django's messages show, and that the error pages stay on the bare
base.html. This file is also the URL map for its tests: a page that extends the layout."""

import re
from pathlib import Path

import pytest
from django.contrib import messages
from django.http import HttpResponse
from django.template import RequestContext, Template
from django.test import Client
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
    if "saved" in request.GET:
        messages.success(request, "Saved.")
    return HttpResponse(APP_PAGE.render(RequestContext(request)))


urlpatterns = [path("invoices/", app_page)]


def status_region(html):
    # The element with role="status" (any tag, any other attributes) and what's in it.
    match = re.search(r'<(\w+)[^>]*\brole="status"[^>]*>(.*?)</\1>', html, re.DOTALL)
    assert match, "no role=status region: modules show their messages there"
    return match


@pytest.fixture
def browser():
    return Client()


@pytest.mark.urls(__name__)
def test_an_apps_page_fills_the_title_head_and_content(browser):
    html = browser.get("/invoices/").content.decode()
    head, body = html.split("</head>")
    assert "<title>Invoices</title>" in head
    assert '<script src="/invoices.js" defer></script>' in head
    main = body[body.index("<main") : body.index("</main>")]
    assert "<h1>Invoices</h1>" in main
    assert html.count("<main") == 1


@pytest.mark.urls(__name__)
def test_messages_show_in_the_status_region_in_the_header(browser):
    html = browser.get("/invoices/?saved").content.decode()
    region = status_region(html)
    assert "Saved." in region.group(2)
    header = html[html.index("<header") : html.index("</header>")]
    assert region.group(0) in header
    assert html.index("</header>") < html.index("<main")


@pytest.mark.urls(__name__)
def test_the_status_region_is_there_without_messages(browser):
    # Always present, so a message added later without a page reload is announced.
    html = browser.get("/invoices/").content.decode()
    assert status_region(html).group(2).strip() == ""


@pytest.mark.urls(__name__)
def test_a_message_is_shown_once(browser):
    browser.get("/invoices/?saved")
    html = browser.get("/invoices/").content.decode()
    assert "Saved." not in html


@pytest.mark.parametrize("page", ERROR_PAGES)
def test_error_pages_stay_on_the_bare_base(page):
    # The 500 page must work with the database down, and the layout is where tags that
    # read it go: error pages never use the layout.
    first_tag = (TEMPLATES_DIR / page).read_text().split("%}")[0]
    assert '{% extends "base.html"' in first_tag + "%}"
