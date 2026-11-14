"""Logs: one JSON object per line in production, readable text in development and tests,
errors with their stack trace, and Gunicorn's logs in the same JSON form."""

import json
import logging
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from django.core import mail

from config.logging import JsonFormatter
from tests.test_production_settings import run_manage

PROJECT_DIR = Path(__file__).resolve().parent.parent
# Logs an error with a stack trace, the way Django logs a crashed request.
LOG_AN_ERROR = (
    "import logging\n"
    "try:\n"
    "    1 / 0\n"
    "except ZeroDivisionError:\n"
    "    logging.getLogger('django.request').exception('Internal Server Error: /page/')\n"
)


def record(message="hello %s", args=("world",), exc_info=None, **extra):
    entry = logging.LogRecord("app", logging.ERROR, __file__, 1, message, args, exc_info)
    entry.__dict__.update(extra)
    return entry


def test_a_line_is_one_json_object_with_the_basics():
    line = JsonFormatter().format(record())
    entry = json.loads(line)
    assert entry["level"] == "ERROR"
    assert entry["logger"] == "app"
    assert entry["message"] == "hello world"
    assert entry["time"].endswith("+00:00")  # UTC, with the zone written out


def test_an_error_keeps_its_stack_trace_on_one_line():
    try:
        raise ValueError("bad value")
    except ValueError:
        line = JsonFormatter().format(record(exc_info=sys.exc_info()))
    assert "\n" not in line
    exception = json.loads(line)["exception"]
    assert "Traceback" in exception and "ValueError: bad value" in exception


def test_a_stack_logged_on_purpose_is_kept():
    entry = json.loads(JsonFormatter().format(record(stack_info="Stack (most recent call)")))
    assert entry["stack"] == "Stack (most recent call)"


def test_a_message_with_line_breaks_cant_fake_another_line():
    line = JsonFormatter().format(record(message='x\n{"level": "INFO"}', args=()))
    assert "\n" not in line
    assert json.loads(line)["message"] == 'x\n{"level": "INFO"}'


def test_a_request_error_names_the_request_without_its_query(rf):
    request = rf.get("/reset/?token=secret")
    entry = json.loads(JsonFormatter().format(record(request=request, status_code=500)))
    assert entry["request"] == "GET /reset/"
    assert entry["status"] == 500
    assert "secret" not in json.dumps(entry)


def test_a_value_json_cant_hold_is_written_as_text():
    entry = json.loads(JsonFormatter().format(record(args=(object(),))))
    assert entry["message"].startswith("hello <object object")


@pytest.mark.parametrize(
    ("environment", "json_lines"),
    [({}, True), ({"DJANGO_ENV": "development"}, False)],
    ids=["production", "development"],
)
def test_errors_are_logged_with_their_stack_trace(environment, json_lines):
    result = run_manage("shell", "-c", LOG_AN_ERROR, **environment)
    lines = [line for line in result.stderr.splitlines() if "Internal Server Error" in line]
    assert len(lines) == 1, result.stderr  # exactly once: no second handler
    if json_lines:
        entry = json.loads(lines[0])
        assert entry["logger"] == "django.request"
        assert "ZeroDivisionError" in entry["exception"]
    else:
        assert "ERROR django.request: Internal Server Error" in lines[0]
        assert "ZeroDivisionError" in result.stderr


def test_errors_are_never_emailed_even_with_admins_set(settings):
    settings.ADMINS = ["admin@example.com"]
    logging.getLogger("django.request").error("Internal Server Error: /page/")
    assert mail.outbox == []


def test_a_lowercase_log_level_works():
    result = run_manage("check", DJANGO_LOG_LEVEL="debug")
    assert result.returncode == 0, result.stderr


def test_a_python_warning_in_production_is_a_json_line():
    code = "import warnings\nwarnings.warn('received a naive datetime', RuntimeWarning)\n"
    result = run_manage("shell", "-c", code)
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert len(lines) == 1, result.stderr
    entry = json.loads(lines[0])
    assert entry["logger"] == "py.warnings"
    assert "received a naive datetime" in entry["message"]


@pytest.mark.parametrize("separator", [" ", " ", "\x85", "\x9b"])
def test_unicode_line_breaks_and_control_codes_are_escaped(separator):
    line = JsonFormatter().format(record(message="a%sb", args=(separator,)))
    assert line.isascii()
    assert len(line.splitlines()) == 1


def gunicorn_settings():
    return runpy.run_path(str(PROJECT_DIR / "gunicorn.conf.py"))


def test_gunicorn_logs_json_too():
    config = gunicorn_settings()["logconfig_dict"]
    assert config["formatters"]["json"]["()"] == "config.logging.JsonFormatter"
    for name in ["gunicorn.access", "gunicorn.error"]:
        handlers = config["loggers"][name]["handlers"]
        assert all(config["handlers"][h]["formatter"] == "json" for h in handlers)


def test_gunicorn_can_set_up_its_logging():
    # Gunicorn's own logging setup, with this project's settings, in its own process so
    # this test process's logging stays as it was.
    script = (
        "import runpy\n"
        "from gunicorn.config import Config\n"
        "from gunicorn.glogging import Logger\n"
        "config = Config()\n"
        "for name, value in runpy.run_path('gunicorn.conf.py').items():\n"
        "    if name in config.settings:\n"
        "        config.set(name, value)\n"
        "Logger(config).error_log.info('started')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=PROJECT_DIR, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stderr)["message"] == "started"


@pytest.mark.parametrize(
    ("behind_proxy", "client"),
    [("false", "%(h)s"), ("true", "%({x-forwarded-for}i)s")],
    ids=["direct", "behind the proxy"],
)
def test_gunicorns_request_lines_leave_out_query_strings(monkeypatch, behind_proxy, client):
    monkeypatch.setenv("DJANGO_BEHIND_PROXY", behind_proxy)
    access_format = gunicorn_settings()["access_log_format"]
    assert access_format.startswith(client + " ")  # the visitor's address
    assert "%(U)s" in access_format  # the path only
    for with_query in ["%(r)s", "%(q)s", "%(f)s"]:  # request line, query, referrer
        assert with_query not in access_format
    # The only header logged is the address the proxy sets.
    assert access_format.count("%({") == (client != "%(h)s")
