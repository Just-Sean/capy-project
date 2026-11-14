"""Login rate limiting, on top of django-axes (see "Login rate limiting" in settings.py).

django-axes locks out a username + address pair after a few failed logins. This module
adds what it needs from the project:
  - client_ip: the visitor's address, as axes sees it
  - IPLoginLimitBackend: a looser limit per address across all usernames, so trying a
    new username each time can't get around the lockout (or run unlimited password
    checks, each of which costs Argon2's memory)
"""

import ipaddress

from axes.models import AccessAttempt
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.utils import timezone

IPV6_BLOCK = 64  # one IPv6 user usually controls a whole /64, so it counts as one address


def client_ip(request):
    """The address the request really came from.

    Directly on the internet, that's the connection's address (REMOTE_ADDR); visitors
    can't change it. Behind one reverse proxy you control (DJANGO_BEHIND_PROXY), every
    request comes from the proxy, so use the address the proxy adds as the last entry
    of X-Forwarded-For. Earlier entries are whatever the visitor sent, so they're never
    used: otherwise anyone could pick a new address for each attempt. This expects
    exactly one proxy, which must add that entry (Caddy does; nginx needs
    `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`). A port some
    proxies add (203.0.113.5:50123) is dropped, so a new connection isn't a new address,
    and anything that isn't an IP address falls back to the connection's own.
    """
    connection = parse_ip(request.META.get("REMOTE_ADDR", ""))
    if settings.BEHIND_PROXY:
        added_by_proxy = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1]
        ip = parse_ip(added_by_proxy) or connection
    else:
        ip = connection
    if ip is not None and ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/{IPV6_BLOCK}", strict=False).network_address)
    return None if ip is None else str(ip)


def parse_ip(value):
    """An IP address from "203.0.113.5", "203.0.113.5:50123", "[2001:db8::1]:443" or
    "2001:db8::1"; None if it isn't one."""
    value = value.strip()
    if value.startswith("["):  # [IPv6]:port
        value = value[1:].split("]", 1)[0]
    elif value.count(":") == 1:  # IPv4:port (a bare IPv6 address has several colons)
        value = value.split(":", 1)[0]
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


class IPLoginLimitBackend:
    """Refuses logins from an address with too many recent failures, whatever username
    they used. First in AUTHENTICATION_BACKENDS; it never logs anyone in itself.

    The limit (DJANGO_LOGIN_IP_FAILURE_LIMIT) is higher than the per-user one, so an
    office or school sharing one address doesn't lock itself out by accident.
    """

    def authenticate(self, request, **credentials):
        if request is None:
            return None  # django-axes (next) refuses logins without a request
        since = timezone.now() - settings.AXES_COOLOFF_TIME
        failures = AccessAttempt.objects.filter(
            ip_address=client_ip(request), attempt_time__gte=since
        ).aggregate(total=Sum("failures_since_start"))["total"]
        if (failures or 0) >= settings.LOGIN_IP_FAILURE_LIMIT:
            request.axes_locked_out = True  # axes' middleware shows its lockout page
            raise PermissionDenied("Too many failed logins from this address.")
        return None

    # No get_user(): Django would then use this backend to load logged-in users (it
    # picks the first backend that has one), and every session would be logged out.
