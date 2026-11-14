"""The compose files: development stays on this machine, production keeps its secrets in
env files, migrates before the app starts, and shuts down gracefully.

`docker compose config` merges the files exactly as `docker compose up` would, without
starting anything or needing the Docker daemon.
"""

import json
import os
import re
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILES = ["compose.yaml", "compose.override.yaml", "compose.prod.yaml"]
PRODUCTION = ["-f", "compose.yaml", "-f", "compose.prod.yaml"]
SECRET_FILES = {".env.production": "DJANGO_SECRET_KEY=placeholder\n", ".env.postgres": ""}


@pytest.fixture
def project(tmp_path):
    """A copy of the compose files, with placeholder secret files (production needs them)."""
    for name in COMPOSE_FILES:
        shutil.copy(PROJECT_DIR / name, tmp_path / name)
    for name, text in SECRET_FILES.items():
        (tmp_path / name).write_text(text)
    return tmp_path


def config(project, *files):
    """The merged configuration, as Compose sees it."""
    docker = shutil.which("docker")
    assert docker, "Docker (with Compose) is needed to run this test"
    # Only these files count: not COMPOSE_* variables or a .env from this machine.
    environment = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    result = subprocess.run(
        [docker, "compose", *files, "config", "--format", "json"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def host_ips(service):
    return {port.get("host_ip") for port in service.get("ports", [])}


def seconds(duration):
    """Compose durations such as "35s" or "1m5s", in seconds."""
    units = {"h": 3600, "m": 60, "s": 1}
    parts = re.findall(r"(\d+)([hms])", duration)
    assert parts, f"not a duration: {duration!r}"
    return sum(int(number) * units[unit] for number, unit in parts)


def test_development_runs_only_postgres_reachable_from_this_machine(project):
    services = config(project)["services"]
    assert set(services) == {"db"}
    assert host_ips(services["db"]) == {"127.0.0.1"}


def test_production_runs_postgres_migrate_and_the_app(project):
    assert set(config(project, *PRODUCTION)["services"]) == {"db", "migrate", "web"}


def test_production_is_a_separate_project_from_development(project):
    assert config(project, *PRODUCTION)["name"] != config(project)["name"]


def test_production_database_has_no_open_port(project):
    assert "ports" not in config(project, *PRODUCTION)["services"]["db"]


def test_production_app_listens_on_this_machine_only(project):
    assert host_ips(config(project, *PRODUCTION)["services"]["web"]) == {"127.0.0.1"}


def test_production_migrates_before_the_app_starts(project):
    services = config(project, *PRODUCTION)["services"]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["web"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["migrate"]["command"][-2:] == ["migrate", "--noinput"]


def test_production_secrets_come_only_from_env_files():
    # Written in compose.prod.yaml, a secret would be committed to git.
    text = (PROJECT_DIR / "compose.prod.yaml").read_text()
    assert "environment:" not in text
    assert ".env.production" in text
    assert ".env.postgres" in text


def test_production_restarts_after_a_crash(project):
    services = config(project, *PRODUCTION)["services"]
    assert services["db"]["restart"] == services["web"]["restart"] == "unless-stopped"


def test_the_app_gets_longer_to_stop_than_gunicorn_needs(project):
    # Docker force-stops a container after stop_grace_period; Gunicorn needs up to
    # graceful_timeout to finish requests in progress.
    gunicorn = runpy.run_path(str(PROJECT_DIR / "gunicorn.conf.py"))
    web = config(project, *PRODUCTION)["services"]["web"]
    assert seconds(web["stop_grace_period"]) > gunicorn["graceful_timeout"]


@pytest.mark.parametrize(("duration", "expected"), [("35s", 35), ("1m5s", 65), ("2h", 7200)])
def test_seconds(duration, expected):
    assert seconds(duration) == expected
