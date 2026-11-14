"""deploy/Caddyfile, run by the real Caddy image from compose.prod.yaml: the health URLs
are hidden, uploads are downloads, and with the app down visitors get the site's page
with the real status. Needs Docker, like tests/test_compose.py."""

import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_DIR / "compose.prod.yaml"


def docker(*args, check=True):
    executable = shutil.which("docker")
    assert executable, "Docker is needed to run this test"
    return subprocess.run([executable, *args], capture_output=True, text=True, check=check)


def caddy_image():
    match = re.search(r"image: (caddy:\S+)", COMPOSE_FILE.read_text())
    assert match, "compose.prod.yaml has no caddy image"
    return match.group(1)


@pytest.fixture(scope="module")
def caddy(tmp_path_factory):
    """Caddy with the project's Caddyfile, over plain HTTP, with an upload in its media
    folder and no app behind it (as when the app is down)."""
    media = tmp_path_factory.mktemp("media")
    (media / "page.html").write_text("<script>alert(1)</script>")
    media.chmod(0o755)
    (media / "page.html").chmod(0o644)
    name = f"caddyfile-test-{uuid.uuid4().hex[:8]}"
    caddyfile = PROJECT_DIR / "deploy" / "Caddyfile"
    error_page = PROJECT_DIR / "templates" / "proxy_error.html"
    docker(
        "run", "--detach", "--name", name, "--env", "SITE_ADDRESS=:80",
        "--volume", f"{caddyfile}:/etc/caddy/Caddyfile:ro",
        "--volume", f"{error_page}:/srv/errors/proxy_error.html:ro",
        "--volume", f"{media}:/srv/media:ro",
        caddy_image(),
    )  # fmt: skip
    try:
        for _ in range(50):  # wait up to 10 s for it to answer
            if "HTTP/" in get(name, "/healthz"):
                break
            time.sleep(0.2)
        yield name
    finally:
        docker("rm", "--force", name, check=False)


def get(container, path):
    """The raw response (status line, headers and body) to a GET, from inside the
    container, with BusyBox's nc. The sleep keeps the connection open for the answer:
    closed early, Caddy stops waiting for the app (499, "client closed")."""
    send = f"printf 'GET {path} HTTP/1.0\\r\\nHost: example.com\\r\\n\\r\\n'"
    request = f"({send}; sleep 2) | nc -w 3 127.0.0.1 80"
    return docker("exec", container, "sh", "-c", request, check=False).stdout


def status(response):
    return int(response.split()[1])


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_the_health_checks_are_hidden_from_the_public(caddy, path):
    assert status(get(caddy, path)) == 404


def test_uploads_are_downloads_that_cant_run_scripts(caddy):
    response = get(caddy, "/media/page.html")
    assert status(response) == 200
    assert "Content-Disposition: attachment" in response
    assert "X-Content-Type-Options: nosniff" in response
    assert "Content-Security-Policy: default-src 'none'; sandbox" in response


def test_with_the_app_down_visitors_get_the_sites_page_with_the_real_status(caddy):
    response = get(caddy, "/any/page/")
    assert status(response) == 502
    assert "<h1>Temporarily unavailable</h1>" in response
    assert "Cache-Control: no-store" in response
    assert "X-Frame-Options: DENY" in response
    assert "Server:" not in response  # no "Server: Caddy"
