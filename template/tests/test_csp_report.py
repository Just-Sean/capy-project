"""The CSP report endpoint logs a short, safe summary of what the policy blocked."""

import json

import pytest
from django.test import Client

from config.csp_report import MAX_REPORT_BYTES, MAX_VALUE_LENGTH

URL = "/csp-report/"
REPORT = {
    "csp-report": {
        "document-uri": "https://example.com/account/?token=secret#part",
        "referrer": "https://example.com/private/",
        "violated-directive": "script-src-elem",
        "effective-directive": "script-src-elem",
        "blocked-uri": "https://evil.example/x.js?id=1",
        "script-sample": "alert(document.cookie)",
    }
}


def post(client, body, content_type="application/csp-report"):
    return client.post(URL, body, content_type=content_type)


def test_a_report_is_logged_without_query_strings_or_samples(client, caplog):
    with caplog.at_level("WARNING", logger="csp"):
        response = post(client, json.dumps(REPORT))
    assert response.status_code == 204
    [message] = [r.getMessage() for r in caplog.records if r.name == "csp"]
    logged = json.loads(message.removeprefix("CSP violation: "))
    assert logged == {
        "document-uri": "https://example.com/account/",
        "effective-directive": "script-src-elem",
        "violated-directive": "script-src-elem",
        "blocked-uri": "https://evil.example/x.js",
    }
    for private in ["secret", "private", "cookie", "id=1"]:
        assert private not in message


def test_long_values_are_cut_short(client, caplog):
    report = {"csp-report": {"violated-directive": "x" * 5000}}
    with caplog.at_level("WARNING", logger="csp"):
        post(client, json.dumps(report))
    [message] = [r.getMessage() for r in caplog.records if r.name == "csp"]
    assert len(json.loads(message.removeprefix("CSP violation: "))["violated-directive"]) == (
        MAX_VALUE_LENGTH
    )


def test_a_value_cant_add_a_fake_log_line(client, caplog):
    report = {"csp-report": {"violated-directive": "x\nERROR something else"}}
    with caplog.at_level("WARNING", logger="csp"):
        post(client, json.dumps(report))
    [message] = [r.getMessage() for r in caplog.records if r.name == "csp"]
    assert "\n" not in message


def test_a_huge_report_is_refused_unread(client, caplog):
    body = json.dumps({"csp-report": {"violated-directive": "x" * MAX_REPORT_BYTES}})
    with caplog.at_level("WARNING", logger="csp"):
        response = post(client, body)
    assert response.status_code == 413
    assert not [r for r in caplog.records if r.name == "csp"]


@pytest.mark.parametrize(
    "body",
    ["not json", "[]", json.dumps({"other": {}}), json.dumps({"csp-report": "text"})],
    ids=["not json", "a list", "no csp-report", "csp-report not an object"],
)
def test_something_that_isnt_a_report_is_refused(client, body):
    assert post(client, body).status_code == 400


@pytest.mark.parametrize(
    "url",
    ["http://[::1/", "http://[not-an-ip]/", "http://exa＃mple.com/"],
    ids=["unclosed IPv6 bracket", "bad IPv6 host", "host changed by normalizing"],
)
def test_a_url_python_cant_read_is_refused_not_a_server_error(url):
    client = Client(raise_request_exception=False)
    body = json.dumps({"csp-report": {"document-uri": url}})
    assert post(client, body).status_code == 400


def test_a_login_in_a_reported_url_isnt_logged(client, caplog):
    report = {"csp-report": {"blocked-uri": "https://user:hunter2@evil.example/x.js"}}
    with caplog.at_level("WARNING", logger="csp"):
        post(client, json.dumps(report))
    [message] = [r.getMessage() for r in caplog.records if r.name == "csp"]
    assert json.loads(message.removeprefix("CSP violation: ")) == {
        "blocked-uri": "https://evil.example/x.js"
    }


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/x-www-form-urlencoded", "application/json"],
)
def test_only_the_type_browsers_send_is_accepted(client, content_type):
    # Another site's page can make its visitors' browsers send plain text or forms.
    assert post(client, json.dumps(REPORT), content_type=content_type).status_code == 415


def test_only_post_is_accepted(client):
    assert client.get(URL).status_code == 405


def test_reports_need_no_csrf_token():
    strict = Client(enforce_csrf_checks=True)  # browsers send no token with reports
    assert post(strict, json.dumps(REPORT)).status_code == 204
