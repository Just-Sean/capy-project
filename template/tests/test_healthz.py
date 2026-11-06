"""The /healthz endpoint that Docker and load balancers poll."""

import pytest


def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"
    assert response["Content-Type"] == "text/plain"


def test_healthz_ignores_unknown_host(client):
    # Load balancers call it by IP, which isn't in ALLOWED_HOSTS.
    response = client.get("/healthz", headers={"host": "10.0.0.7"})
    assert response.status_code == 200
    assert response.content == b"ok"


# The mark only lets the fixture count queries; the assertion is that there are none.
@pytest.mark.django_db
def test_healthz_makes_no_database_queries(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = client.get("/healthz")
    assert response.status_code == 200
