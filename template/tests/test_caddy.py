"""deploy/Caddyfile, run by the real Caddy image from compose.prod.yaml, locked down as in
production: the config is valid, the health URLs are hidden, uploads are downloads,
requests are capped in size, and with the app down visitors get the site's page with
the real status. Needs the Docker daemon running (it starts a container)."""

import http.client
import re
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_DIR / "compose.prod.yaml"
DEPLOY_DIR = PROJECT_DIR / "deploy"
TEMPLATES_DIR = PROJECT_DIR / "templates"


def docker(*args, check=True):
    executable = shutil.which("docker")
    assert executable, "Docker is needed to run this test"
    return subprocess.run([executable, *args], capture_output=True, text=True, check=check)


def caddy_image():
    match = re.search(r"image: (caddy:\S+)", COMPOSE_FILE.read_text())
    assert match, "compose.prod.yaml has no caddy image"
    return match.group(1)


def test_the_caddyfile_is_valid():
    # Caddy's own check, with the production site address (HTTPS).
    result = docker(
        "run", "--rm", "--env", "SITE_ADDRESS=example.com",
        "--volume", f"{DEPLOY_DIR}:/etc/caddy:ro",
        caddy_image(), "caddy", "validate", "--config", "/etc/caddy/Caddyfile",
        check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="module")
def caddy(tmp_path_factory):
    """Caddy with the project's Caddyfile over plain HTTP, locked down as in
    compose.prod.yaml, with uploads in its media folder and no app behind it (as when
    the app is down). Yields the local port it answers on."""
    media = tmp_path_factory.mktemp("media")
    (media / "page.html").write_text("<script>alert(1)</script>")
    (media / "uploads").mkdir()
    (media / "uploads" / "index.html").write_text("someone's upload")
    # Readable by anyone, as uploads are: Caddy's root has no capability to read past
    # file permissions.
    for path in [media, media / "uploads"]:
        path.chmod(0o755)
    for path in [media / "page.html", media / "uploads" / "index.html"]:
        path.chmod(0o644)
    name = f"caddyfile-test-{uuid.uuid4().hex[:8]}"
    docker(
        "run", "--detach", "--name", name, "--env", "SITE_ADDRESS=:80",
        "--cap-drop", "ALL", "--cap-add", "NET_BIND_SERVICE",
        "--security-opt", "no-new-privileges:true", "--read-only",
        "--tmpfs", "/tmp", "--tmpfs", "/data", "--tmpfs", "/config",
        "--volume", f"{DEPLOY_DIR}:/etc/caddy:ro",
        "--volume", f"{TEMPLATES_DIR}:/srv/errors:ro",
        "--volume", f"{media}:/srv/media:ro",
        "--publish", "127.0.0.1::80",
        caddy_image(),
    )  # fmt: skip
    try:
        port = int(docker("port", name, "80/tcp").stdout.strip().rsplit(":", 1)[1])
        deadline = time.monotonic() + 15
        while not answers(port):
            if time.monotonic() > deadline:
                pytest.fail("Caddy didn't start:\n" + docker("logs", name, check=False).stderr)
            time.sleep(0.2)
        yield port
    finally:
        docker("rm", "--force", name, check=False)


def answers(port):
    try:
        request(port, "GET", "/healthz")
    except OSError:
        return False
    return True


def request(port, method, path, body=None):
    """The response to a request, read in full, as (status, headers, body)."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        connection.request(method, path, body=body, headers={"Host": "example.com"})
        response = connection.getresponse()
        return response.status, response.headers, response.read().decode(errors="replace")
    finally:
        connection.close()


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_the_health_checks_are_hidden_from_the_public(caddy, path):
    status, _, _ = request(caddy, "GET", path)
    assert status == 404


def test_uploads_are_downloads_that_cant_run_scripts(caddy):
    status, headers, _ = request(caddy, "GET", "/media/page.html")
    assert status == 200
    assert headers["Content-Disposition"] == "attachment"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == "default-src 'none'; sandbox"


@pytest.mark.parametrize("path", ["/media/", "/media/uploads/"])
def test_a_folder_is_never_listed_or_served_by_an_index_file(caddy, path):
    status, _, body = request(caddy, "GET", path)
    assert status == 404
    assert "someone's upload" not in body


def test_a_request_over_the_size_limit_is_refused(caddy):
    # Sent over a plain socket: Caddy answers 413 and closes the connection while the
    # body is still being sent, which http.client can't read past.
    size = 11 * 1024 * 1024
    with socket.create_connection(("127.0.0.1", caddy), timeout=15) as sock:
        head = f"POST /any/page/ HTTP/1.1\r\nHost: example.com\r\nContent-Length: {size}\r\n\r\n"
        try:
            sock.sendall(head.encode() + b"x" * size)
        except OSError:
            pass  # Caddy closed the connection once it saw too much: the answer is sent
        answer = sock.recv(200).decode(errors="replace")
    assert answer.startswith("HTTP/1.1 413"), answer


def test_with_the_app_down_visitors_get_the_sites_page_with_the_real_status(caddy):
    status, headers, body = request(caddy, "GET", "/any/page/")
    assert status == 502
    assert "<h1>Temporarily unavailable</h1>" in body
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Server" not in headers  # Caddy isn't named
    assert "Via" not in headers
