"""Email goes where expected in each environment: the console in development, memory in
tests, and only an encrypted mail server in production, which may also have none."""

import pytest
from django.core import mail
from django.core.exceptions import ImproperlyConfigured

from config.email_not_set_up import EmailNotSetUpBackend
from tests.test_production_settings import run_manage

PRINT_EMAIL_SETTINGS = (
    "from django.conf import settings as s; "
    "print(s.MAILERS['default'], s.DEFAULT_FROM_EMAIL, s.SERVER_EMAIL)"
)
SMTP = "django.core.mail.backends.smtp.EmailBackend"
FROM = {"DJANGO_DEFAULT_FROM_EMAIL": "hello@example.com"}


def last_line(result):
    return result.stdout.strip().splitlines()[-1]


def smtp_mailer(port, username, password, **encryption):
    options = {"host": "smtp.example.com", "port": port, "username": username}
    options |= {"password": password, "timeout": 10, **encryption}
    return {"BACKEND": SMTP, "OPTIONS": options}


def test_tests_capture_emails_in_memory():
    mail.send_mail("Hello", "Body", None, ["someone@example.com"])
    assert len(mail.outbox) == 1
    assert mail.outbox[0].from_email == "webmaster@localhost"


def test_development_prints_emails_to_the_console():
    result = run_manage("sendtestemail", "someone@example.com", DJANGO_ENV="development")
    assert result.returncode == 0, result.stderr
    assert "To: someone@example.com" in result.stdout


def test_production_starts_without_email_but_refuses_to_send():
    assert run_manage("check", "--deploy").returncode == 0
    result = run_manage("sendtestemail", "someone@example.com")
    assert result.returncode != 0
    assert "Email isn't set up: set EMAIL_URL" in result.stderr


def test_without_email_sending_raises():
    with pytest.raises(ImproperlyConfigured, match="set EMAIL_URL"):
        EmailNotSetUpBackend().send_messages([mail.EmailMessage("Hi", "Body")])


@pytest.mark.parametrize(
    ("url", "mailer"),
    [
        (
            "smtp+tls://apikey:s3cret@smtp.example.com:587",
            smtp_mailer(587, "apikey", "s3cret", use_tls=True),
        ),
        (
            "smtp+ssl://apikey:s3cret@smtp.example.com:465",
            smtp_mailer(465, "apikey", "s3cret", use_ssl=True),
        ),
        (
            "smtp+tls://me%40example.com:p%40ss%2Fword@smtp.example.com",
            smtp_mailer(None, "me@example.com", "p@ss/word", use_tls=True),
        ),
    ],
    ids=["STARTTLS", "SSL", "percent-encoded login, default port"],
)
def test_production_sends_over_an_encrypted_connection(url, mailer):
    result = run_manage("shell", "-c", PRINT_EMAIL_SETTINGS, EMAIL_URL=url, **FROM)
    assert last_line(result) == f"{mailer} hello@example.com hello@example.com", result.stderr


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"EMAIL_URL": "smtp://apikey:s3cret@smtp.example.com:25", **FROM}, "smtp+tls://"),
        ({"EMAIL_URL": "smtps://apikey:s3cret@smtp.example.com:587", **FROM}, "smtp+tls://"),
        ({"EMAIL_URL": "consolemail://", **FROM}, "smtp+tls://"),
        ({"EMAIL_URL": "smtp+tls://", **FROM}, "mail server's address"),
        ({"EMAIL_URL": "smtp+tls://apikey:s3cret@smtp.example.com:587"}, "DJANGO_DEFAULT_FROM"),
    ],
    ids=["plain smtp", "ambiguous smtps", "console", "no host", "no From address"],
)
def test_production_refuses_unsafe_or_incomplete_email(environment, message):
    result = run_manage("check", **environment)
    assert result.returncode != 0
    assert message in result.stderr
    assert "s3cret" not in result.stderr  # the password never appears in the error


def test_an_unknown_kind_of_email_url_is_refused():
    result = run_manage("check", DJANGO_ENV="development", EMAIL_URL="sendgrid://key")
    assert result.returncode != 0
    assert "EMAIL_URL must start with" in result.stderr


def test_development_may_use_a_local_mail_catcher_over_plain_smtp():
    result = run_manage(
        "shell",
        "-c",
        PRINT_EMAIL_SETTINGS,
        DJANGO_ENV="development",
        EMAIL_URL="smtp://localhost:1025",
    )
    expected = {"host": "localhost", "port": 1025, "username": "", "password": "", "timeout": 10}
    assert last_line(result).startswith(str({"BACKEND": SMTP, "OPTIONS": expected})), result.stderr
