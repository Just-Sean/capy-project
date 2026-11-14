"""The visitor's IP address, as login rate limiting (django-axes) sees it."""

from django.conf import settings


def client_ip(request):
    """The address the request really came from.

    Directly on the internet, that's the connection's address (REMOTE_ADDR); visitors
    can't change it. Behind a reverse proxy you control (DJANGO_BEHIND_PROXY), every
    request comes from the proxy, so use the address the proxy adds as the last entry
    of X-Forwarded-For. Earlier entries are whatever the visitor sent, so they're never
    used: otherwise anyone could pick a new address for each attempt and never be
    locked out.
    """
    if settings.BEHIND_PROXY:
        added_by_proxy = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
        if added_by_proxy:
            return added_by_proxy
    return request.META.get("REMOTE_ADDR")
