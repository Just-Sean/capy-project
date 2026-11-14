"""Email: how it's sent, set by EMAIL_URL, and the address it comes from."""

from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

from .environment import IS_DEVELOPMENT, IS_PRODUCTION, IS_TEST, env

# EMAIL_URL is one of:
#   smtp+tls://user:password@smtp.example.com:587   a mail server, encrypted with STARTTLS
#   smtp+ssl://user:password@smtp.example.com:465   a mail server, encrypted from the start
#   smtp://localhost:1025                           unencrypted, no login: development only
#   consolemail://                                  print emails (development's default)
# Percent-encode every character in the user or password other than letters, digits
# and - . _ ~ (e.g. @ is %40, / is %2F, # is %23).
# Lowercase names below are helpers: only uppercase names become Django settings.
smtp_backend = "django.core.mail.backends.smtp.EmailBackend"
encrypted_schemes = {"smtp+tls": {"use_tls": True}, "smtp+ssl": {"use_ssl": True}}
smtp_schemes = {"smtp": {}, **encrypted_schemes}
console_backend = "django.core.mail.backends.console.EmailBackend"
timeout_seconds = 10  # how long to wait for the mail server, so it can't hold a request
url_help = "EMAIL_URL couldn't be read: percent-encode special characters in the password."

if IS_TEST:
    # Tests never send real email, whatever .env says (Django's test runner also keeps
    # every email in django.core.mail.outbox).
    email_url = "memorymail://"
else:
    default_url = "consolemail://" if IS_DEVELOPMENT else ""  # production: optional
    email_url = env("EMAIL_URL", default="") or default_url
parts = urlsplit(email_url)  # the scheme comes back lowercase, so SMTP+TLS:// works too
encrypted_scheme_names = " or ".join(f"{name}://" for name in encrypted_schemes)

if not email_url:
    # No email set up: the app runs, but sending fails with a clear error instead of
    # the email being lost without a trace.
    mailer = {"BACKEND": "config.email_not_set_up.EmailNotSetUpBackend"}
elif IS_PRODUCTION and parts.scheme not in encrypted_schemes:
    # Plain SMTP would send the login and every email (password reset links included)
    # readable on the network; the console backend would print them.
    raise ImproperlyConfigured(f"EMAIL_URL must start with {encrypted_scheme_names}.")
elif parts.scheme in smtp_schemes:
    # A path, ? or # means part of the password wasn't percent-encoded, so the address
    # was cut short. The port is read in a try, so its error can't quote the password.
    try:
        port = parts.port
    except ValueError:
        raise ImproperlyConfigured(url_help) from None
    if parts.path or parts.query or parts.fragment or port == 0:
        raise ImproperlyConfigured(url_help)
    if not parts.hostname:
        raise ImproperlyConfigured("EMAIL_URL must include the mail server's address.")
    if parts.scheme == "smtp" and (parts.username or parts.password):
        raise ImproperlyConfigured(
            f"EMAIL_URL with a login must start with {encrypted_scheme_names}: plain "
            "smtp:// is only for a local mail catcher."
        )
    mailer = {
        "BACKEND": smtp_backend,
        "OPTIONS": {
            "host": parts.hostname,
            "port": port,  # if left out: 587 with TLS, 465 with SSL, else 25
            "username": unquote(parts.username or ""),
            "password": unquote(parts.password or ""),
            "timeout": timeout_seconds,
            **smtp_schemes[parts.scheme],
        },
    }
elif email_url == "consolemail://":
    mailer = {"BACKEND": console_backend}
elif email_url == "memorymail://":
    mailer = {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
else:
    raise ImproperlyConfigured(
        "EMAIL_URL must start with smtp+tls://, smtp+ssl://, smtp:// or consolemail://."
    )
MAILERS = {"default": mailer}

# The From: address. Production must set it when it sends email; the mail service
# usually only accepts addresses on a domain you've verified with it.
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="")
if IS_PRODUCTION and email_url and not DEFAULT_FROM_EMAIL:
    raise ImproperlyConfigured("Set DJANGO_DEFAULT_FROM_EMAIL: EMAIL_URL is set.")
DEFAULT_FROM_EMAIL = DEFAULT_FROM_EMAIL or "webmaster@localhost"
# The From: of Django's own messages (error emails, if ADMINS is ever set).
SERVER_EMAIL = DEFAULT_FROM_EMAIL
