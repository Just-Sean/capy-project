"""Email: how it's sent, set by EMAIL_URL, and the address it comes from."""

from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

from .environment import IS_DEVELOPMENT, IS_PRODUCTION, IS_TEST, env

# EMAIL_URL is one of:
#   smtp+tls://user:password@smtp.example.com:587   a mail server, encrypted with STARTTLS
#   smtp+ssl://user:password@smtp.example.com:465   a mail server, encrypted from the start
#   smtp://localhost:1025                           unencrypted: development only
#   consolemail://                                  print emails (development's default)
#   memorymail://                                   keep them in mail.outbox (tests' default)
# Characters like @ or / in the user or password must be percent-encoded (@ is %40).
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
SMTP_SCHEMES = {"smtp": {}, "smtp+tls": {"use_tls": True}, "smtp+ssl": {"use_ssl": True}}
OTHER_BACKENDS = {
    "consolemail": "django.core.mail.backends.console.EmailBackend",
    "memorymail": "django.core.mail.backends.locmem.EmailBackend",
}
EMAIL_TIMEOUT_SECONDS = 10  # how long to wait for the mail server, so it can't hold a request

if IS_TEST:
    default_url = "memorymail://"
elif IS_DEVELOPMENT:
    default_url = "consolemail://"
else:
    default_url = ""  # production: optional, see below
email_url = env("EMAIL_URL", default="") or default_url
parts = urlsplit(email_url)

if not email_url:
    # No email set up: the app runs, but sending fails with a clear error instead of
    # the email being lost without a trace.
    mailer = {"BACKEND": "config.email_not_set_up.EmailNotSetUpBackend"}
elif IS_PRODUCTION and parts.scheme not in ("smtp+tls", "smtp+ssl"):
    # Plain SMTP would send the login and every email (password reset links included)
    # readable on the network; the other backends would print or drop them.
    raise ImproperlyConfigured("EMAIL_URL must start with smtp+tls:// or smtp+ssl://.")
elif parts.scheme in SMTP_SCHEMES:
    if not parts.hostname:
        raise ImproperlyConfigured("EMAIL_URL must include the mail server's address.")
    mailer = {
        "BACKEND": SMTP_BACKEND,
        "OPTIONS": {
            "host": parts.hostname,
            "port": parts.port,  # if left out: 587 with TLS, 465 with SSL, else 25
            "username": unquote(parts.username or ""),
            "password": unquote(parts.password or ""),
            "timeout": EMAIL_TIMEOUT_SECONDS,
            **SMTP_SCHEMES[parts.scheme],
        },
    }
elif parts.scheme in OTHER_BACKENDS:
    mailer = {"BACKEND": OTHER_BACKENDS[parts.scheme]}
else:
    raise ImproperlyConfigured(
        "EMAIL_URL must start with smtp+tls://, smtp+ssl://, smtp://, consolemail:// "
        "or memorymail://."
    )
MAILERS = {"default": mailer}

# The From: address. Production must set it when it sends email; the mail service
# usually only accepts addresses on a domain you've verified with it.
if IS_PRODUCTION and email_url:
    DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL")  # required
else:
    DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="webmaster@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL  # From: for Django's own messages
