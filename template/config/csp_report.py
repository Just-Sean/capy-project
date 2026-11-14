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
# What browsers send for report-uri. Other sites' pages can make their visitors'
# browsers post plain text or forms here, but not this type (it needs CORS).
REPORT_CONTENT_TYPE = "application/csp-report"
# The fields worth logging; the rest (the page's referrer, a sample of the blocked
# code) can hold personal data or tokens.
FIELDS = ["document-uri", "effective-directive", "violated-directive", "blocked-uri"]
URL_FIELDS = {"document-uri", "blocked-uri"}


def without_secrets(url):
    """A URL without a login, query string or fragment, which can hold secrets. Raises
    ValueError for a URL Python can't read."""
    parts = urlsplit(url)
    host = parts.netloc.rpartition("@")[2]  # drops user:password@
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def summary(report):
    """The fields worth logging from one report, each shortened. Raises ValueError for
    a URL Python can't read."""
    found = {}
    for field in FIELDS:
        value = report.get(field)
        if isinstance(value, str) and value:
            value = without_secrets(value) if field in URL_FIELDS else value
            found[field] = value[:MAX_VALUE_LENGTH]
    return found


@csrf_exempt  # browsers send reports without a CSRF token; nothing here changes data
@require_POST
def csp_report(request):
    if request.content_type != REPORT_CONTENT_TYPE:
        return HttpResponse(status=415)
    body = request.read(MAX_REPORT_BYTES + 1)
    if len(body) > MAX_REPORT_BYTES:
        return HttpResponse(status=413)
    try:
        report = json.loads(body)["csp-report"]
        found = summary(report)
    except ValueError, KeyError, TypeError, AttributeError:
        # Not JSON, no report, a report that isn't an object (no .get), or a URL
        # Python can't read: refused, never a server error.
        return HttpResponse(status=400)
    # json.dumps keeps each report on one line: values can't add fake log lines.
    logger.warning("CSP violation: %s", json.dumps(found))
    return HttpResponse(status=204)
