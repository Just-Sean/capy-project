"""Receives the browser's reports of what the Content Security Policy blocked, and logs a
short summary of each, so a policy that breaks a page (or an attack it stopped) shows
up in the logs. The policy names this view in report-uri (config/settings/security.py).
"""

import json
import logging
from urllib.parse import urlsplit, urlunsplit

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger("csp")

# A real report is well under 2 KB. Anything bigger is refused unread, and each value
# logged is cut short, so nobody can fill the logs with one request.
MAX_REPORT_BYTES = 10_000
MAX_VALUE_LENGTH = 200
# The fields worth logging; the rest (the page's referrer, a sample of the blocked
# code) can hold personal data or tokens.
FIELDS = ["document-uri", "effective-directive", "violated-directive", "blocked-uri"]
URL_FIELDS = {"document-uri", "blocked-uri"}


def without_query(value):
    """A URL without its query string or fragment, which can hold tokens."""
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def summary(report):
    """The fields worth logging from one report, each shortened."""
    found = {}
    for field in FIELDS:
        value = report.get(field)
        if isinstance(value, str) and value:
            value = without_query(value) if field in URL_FIELDS else value
            found[field] = value[:MAX_VALUE_LENGTH]
    return found


@csrf_exempt  # browsers send reports without a CSRF token; nothing here changes data
@require_POST
def csp_report(request):
    body = request.read(MAX_REPORT_BYTES + 1)
    if len(body) > MAX_REPORT_BYTES:
        return HttpResponse(status=413)
    try:
        report = json.loads(body)["csp-report"]
    except ValueError, KeyError, TypeError:
        return HttpResponse(status=400)
    if not isinstance(report, dict):
        return HttpResponse(status=400)
    # json.dumps keeps each report on one line: values can't add fake log lines.
    logger.warning("CSP violation: %s", json.dumps(summary(report)))
    return HttpResponse(status=204)
