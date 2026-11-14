"""The page for a form that failed Django's security check (CSRF), with the reason it
failed when debug is on.

Django's own page says why (e.g. "CSRF cookie not set"), but only when there's no
templates/403_csrf.html. This shows the site's page instead, and keeps the reason for
development, where it's the main clue; production never shows it.
"""

from django.conf import settings
from django.http import HttpResponseForbidden
from django.template.loader import render_to_string


def csrf_failure(request, reason=""):
    context = {"reason": reason} if settings.DEBUG else {}
    return HttpResponseForbidden(render_to_string("403_csrf.html", context))
