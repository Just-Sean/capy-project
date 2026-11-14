"""The email backend production uses when EMAIL_URL isn't set."""

from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class EmailNotSetUpBackend(BaseEmailBackend):
    """Refuses to send, so a missing EMAIL_URL shows up as an error the first time the
    app tries to email someone (e.g. a password reset), instead of the email silently
    going nowhere. It raises even when asked to fail silently (an option Django 6.1
    deprecates).

    Not Django's own `MAILERS = {}`: that also warns (mail.W001) on every `check`, which
    would make `check --deploy --fail-level WARNING` fail."""

    def send_messages(self, email_messages):
        raise ImproperlyConfigured("Email isn't set up: set EMAIL_URL to send email.")
