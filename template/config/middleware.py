"""Project-wide middleware."""

from django.http import HttpResponse

from config.health import failing_checks


def health_checks(get_response):
    """Answer /healthz and /readyz before anything else runs.

    It's first in MIDDLEWARE, so they skip the ALLOWED_HOSTS check (load balancers
    call them by IP), the HTTPS redirect and sessions.
      /healthz  "ok" while the process is up and serving requests. It never touches the
                database, so Docker doesn't restart the app over a database outage.
      /readyz   "ok" only if the database and Redis answer too, else 503 "not ready":
                for load balancers and proxies, to stop sending traffic it can't serve.
    """

    def middleware(request):
        if request.path == "/healthz":
            return plain_text("ok")
        if request.path == "/readyz":
            return plain_text("not ready", status=503) if failing_checks() else plain_text("ok")
        return get_response(request)

    return middleware


def plain_text(text, status=200):
    response = HttpResponse(text, content_type="text/plain", status=status)
    response["Cache-Control"] = "no-store"  # always a fresh answer, never a cached one
    return response
