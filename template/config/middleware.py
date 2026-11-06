"""Project-wide middleware."""

from django.http import HttpResponse


def healthz(get_response):
    """Answer /healthz with "ok" before anything else runs.

    It's first in MIDDLEWARE, so it skips the ALLOWED_HOSTS check (load balancers
    call it by IP), the HTTPS redirect, sessions and the database. A 200 means the
    process is up and serving requests.
    """

    def middleware(request):
        if request.path == "/healthz":
            return HttpResponse("ok", content_type="text/plain")
        return get_response(request)

    return middleware
