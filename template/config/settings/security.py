"""HTTPS (only in production), the proxy, security headers and the Content Security Policy."""

from django.utils.csp import CSP

from .environment import IS_DEVELOPMENT, IS_PRODUCTION, env

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=IS_PRODUCTION)
SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=IS_PRODUCTION)

# HSTS tells browsers to only ever use HTTPS for this domain. On a brand-new
# domain, start with DJANGO_SECURE_HSTS_SECONDS=3600 and raise it once HTTPS works.
SECURE_HSTS_SECONDS = env.int(
    "DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365 if IS_PRODUCTION else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = False  # preloading is hard to undo; opt in deliberately per project
SILENCED_SYSTEM_CHECKS = ["security.W021"]  # the "HSTS preload is off" warning, by design

# Only behind a proxy you control (nginx, Caddy, a load balancer) that sets these
# headers: then X-Forwarded-Proto says whether the visitor used HTTPS, and the last
# X-Forwarded-For entry is the visitor's address (see config/login_limits.py).
BEHIND_PROXY = env.bool("DJANGO_BEHIND_PROXY", default=False)
if BEHIND_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

X_FRAME_OPTIONS = "DENY"  # never allow this site inside a frame
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Content Security Policy (Django's built-in one, so there's no extra package to keep
# updated): the browser only loads what's listed below and blocks everything else, such
# as code injected into a page. Scripts and styles come from this site, plus inline ones
# that carry the page's nonce (<script nonce="{{ csp_nonce }}">). Anything not listed
# (frames, audio and video, workers, manifests) falls back to default-src: nothing, until
# a project allows it on purpose. A view that needs more can set its own policy with
# csp_override from django.views.decorators.csp; see the README's Security section.
SECURE_CSP = {
    "default-src": [CSP.NONE],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],  # the same as X_FRAME_OPTIONS, for newer browsers
    # Browsers report what the policy blocked to this view, which logs it
    # (config/csp_report.py).
    "report-uri": ["/csp-report/"],
}
if IS_DEVELOPMENT:
    # Report only: Django's yellow debug pages use inline styles without the nonce, so
    # an enforced policy would break them. Anything the policy would block still shows
    # as a warning in the browser console. Tests and production enforce it.
    SECURE_CSP_REPORT_ONLY = SECURE_CSP
    SECURE_CSP = {}
