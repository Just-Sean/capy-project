"""deploy/Caddyfile, run by the real Caddy image from compose.prod.yaml, locked down as in
production: the config is valid, the health URLs are hidden, uploads are downloads,
requests are capped in size, and with the app down visitors get the site's page with
the real status. Needs the Docker daemon running (it starts a container)."""

import http.client
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

from tests.test_compose import PRODUCTION, config, copy_compose_files

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = PROJECT_DIR / "deploy"
TEMPLATES_DIR = PROJECT_DIR / "templates"


def docker(*args, check=True):
    executable = shutil.which("docker")
    assert executable, "Docker is needed to run this test"
    return subprocess.run([executable, *args], capture_output=True, text=True, check=check)


@pytest.fixture(scope="module")
def production_caddy(tmp_path_factory):
    """compose.prod.yaml's caddy service, as Compose merges it."""
    project = copy_compose_files(tmp_path_factory.mktemp("compose"))
    return config(project, *PRODUCTION)["services"]["caddy"]


def test_the_caddyfile_is_valid(production_caddy):
    # Caddy's own check, with the production site address (HTTPS).
    result = docker(
        "run", "--rm", "--env", "SITE_ADDRESS=example.com",
        "--volume", f"{DEPLOY_DIR}:/etc/caddy:ro",
        production_caddy["image"], "caddy", "validate", "--config", "/etc/caddy/Caddyfile",
        check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr


def lockdown(service):
    """compose.prod.yaml's lockdown for a service, as `docker run` options: the same
    capabilities, read-only filesystem and in-memory folders."""
    options = ["--read-only"] if service.get("read_only") else []
    for capability in service.get("cap_drop", []):
        options += ["--cap-drop", capability]
    for capability in service.get("cap_add", []):
        options += ["--cap-add", capability]
    for option in service.get("security_opt", []):
        options += ["--security-opt", option]
    for folder in service.get("tmpfs", []):
        options += ["--tmpfs", folder]
    return options


# As random_folder() stores it, with characters that must be escaped in an address.
PRIVATE_FOLDER = "3f9a0c"
PRIVATE_FILE = f"{PRIVATE_FOLDER}/q1 report #2.pdf"
APP_COOKIE = "sessionid=renewed; HttpOnly; Secure"


@pytest.fixture(scope="module")
def uploads(tmp_path_factory):
    """The two upload folders: private (media) and public (media-public). Everything is
    readable by anyone, as uploads are: Caddy's root has no capability to read past file
    permissions."""
    private = tmp_path_factory.mktemp("media")
    (private / PRIVATE_FOLDER).mkdir()
    (private / PRIVATE_FILE).write_text("the private report")
    public = tmp_path_factory.mktemp("media-public")
    (public / "page.html").write_text("<script>alert(1)</script>")
    (public / "uploads").mkdir()
    (public / "uploads" / "index.html").write_text("someone's upload")
    for path in [private, private / PRIVATE_FOLDER, public, public / "uploads"]:
        path.chmod(0o755)
    for path in [private / PRIVATE_FILE, public / "page.html", public / "uploads" / "index.html"]:
        path.chmod(0o644)
    return private, public


def start_caddy(production_caddy, uploads, *network):
    """Caddy with the project's Caddyfile over plain HTTP, locked down as in
    compose.prod.yaml (its certificate folders in memory, not volumes). Returns its name
    and the local port it answers on."""
    private, public = uploads
    name = f"caddyfile-test-{uuid.uuid4().hex[:8]}"
    docker(
        "run", "--detach", "--name", name, "--env", "SITE_ADDRESS=:80", *network,
        *lockdown(production_caddy),
        "--tmpfs", "/data", "--tmpfs", "/config",
        "--volume", f"{DEPLOY_DIR}:/etc/caddy:ro",
        "--volume", f"{TEMPLATES_DIR}:/srv/errors:ro",
        "--volume", f"{private}:/srv/media:ro",
        "--volume", f"{public}:/srv/media-public:ro",
        "--publish", "127.0.0.1::80",
        production_caddy["image"],
    )  # fmt: skip
    port = int(docker("port", name, "80/tcp").stdout.strip().rsplit(":", 1)[1])
    deadline = time.monotonic() + 15
    while not answers(port):
        if time.monotonic() > deadline:
            logs = docker("logs", name, check=False).stderr
            docker("rm", "--force", name, check=False)
            pytest.fail("Caddy didn't start:\n" + logs)
        time.sleep(0.2)
    return name, port


@pytest.fixture(scope="module")
def caddy(production_caddy, uploads):
    """Caddy with no app behind it, as when the app is down. Yields its local port."""
    name, port = start_caddy(production_caddy, uploads)
    try:
        yield port
    finally:
        docker("rm", "--force", name, check=False)


@pytest.fixture(scope="module")
def caddy_with_app(production_caddy, uploads):
    """Caddy in front of a stand-in app that, like config/uploads.py for someone it
    allows, answers every request by naming a private file in X-Accel-Redirect, and
    renews the session cookie. Yields Caddy's local port."""
    suffix = uuid.uuid4().hex[:8]
    network, app = f"caddyfile-test-{suffix}", f"caddyfile-test-app-{suffix}"
    docker("network", "create", network)
    try:
        docker(
            "run", "--detach", "--name", app, "--network", network, "--network-alias", "web",
            production_caddy["image"], "caddy", "respond", "--listen", ":8000",
            "--header", f"X-Accel-Redirect: /{quote(PRIVATE_FILE)}",
            "--header", f"Set-Cookie: {APP_COOKIE}",
        )  # fmt: skip
        name, port = start_caddy(production_caddy, uploads, "--network", network)
        try:
            yield port
        finally:
            docker("rm", "--force", name, check=False)
    finally:
        docker("rm", "--force", app, check=False)
        docker("network", "rm", network, check=False)


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


def test_public_uploads_are_downloads_that_cant_run_scripts(caddy):
    status, headers, _ = request(caddy, "GET", "/media-public/page.html")
    assert status == 200
    assert headers["Content-Disposition"] == "attachment"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == "default-src 'none'; sandbox"


@pytest.mark.parametrize("path", ["/media-public/", "/media-public/uploads/"])
def test_a_folder_is_never_listed_or_served_by_an_index_file(caddy, path):
    status, _, body = request(caddy, "GET", path)
    assert status == 404
    assert "someone's upload" not in body


def test_caddy_never_serves_a_private_upload_by_its_path(caddy):
    # /media/ goes to the app (down here), never straight to the folder.
    status, _, body = request(caddy, "GET", f"/media/{quote(PRIVATE_FILE)}")
    assert status == 502
    assert "the private report" not in body


def test_once_the_app_allows_it_caddy_sends_the_private_file_as_a_download(caddy_with_app):
    status, headers, body = request(caddy_with_app, "GET", "/media/anything")
    assert status == 200
    assert body == "the private report"
    assert headers["Content-Disposition"] == "attachment"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert headers["Cache-Control"] == "private, no-store"
    assert headers["Set-Cookie"] == APP_COOKIE  # the app's renewed session still arrives
    assert "X-Accel-Redirect" not in headers  # the file's name inside stays hidden


def test_only_media_addresses_can_have_caddy_send_a_private_file(caddy_with_app):
    # Any other page of the app naming a file (by mistake, or a header copied from
    # elsewhere) gets nothing sent, and the header is dropped.
    status, headers, body = request(caddy_with_app, "GET", "/any/page/")
    assert status == 200
    assert "the private report" not in body
    assert "X-Accel-Redirect" not in headers


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
