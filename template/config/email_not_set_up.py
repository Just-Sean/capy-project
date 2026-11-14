"""The email backend production uses when EMAIL_URL isn't set."""

from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class EmailNotSetUpBackend(BaseEmailBackend):
    """Refuses to send, so a missing EMAIL_URL shows up as an error the first time the
    app tries to email someone (e.g. a password reset), instead of the email silently
    going nowhere."""

    def send_messages(self, email_messages):
        raise ImproperlyConfigured("Email isn't set up: set EMAIL_URL to send email.")
