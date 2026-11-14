"""The compose files: development stays on this machine, production keeps its secrets in
env files, migrates before the app starts, runs locked down, limits every container's
logs, and shuts down gracefully.
Redis is a cache only: nothing on disk, a memory limit, and internal in production.

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
COMPOSE_FILES = [
    "compose.yaml",
    "compose.override.yaml",
    "compose.prod.yaml",
    "compose.local-http.yaml",
]
PRODUCTION = ["-f", "compose.yaml", "-f", "compose.prod.yaml"]
LOCAL_HTTP = [*PRODUCTION, "-f", "compose.local-http.yaml"]
HTTPS_SETTINGS = {
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DJANGO_CSRF_COOKIE_SECURE",
    "DJANGO_SECURE_HSTS_SECONDS",
}
APP_SERVICES = ["migrate", "web", "worker"]


@pytest.fixture
def project(tmp_path):
    """A copy of the compose files, with empty secret files (production needs them)."""
    for name in COMPOSE_FILES:
        shutil.copy(PROJECT_DIR / name, tmp_path / name)
    for name in [".env.production", ".env.postgres", ".env.redis"]:
        (tmp_path / name).write_text("")
    return tmp_path


def config(project, *files, as_written=False):
    """The merged configuration. as_written keeps env files as env files instead of
    copying their contents into `environment` (Compose's normal, filled-in view)."""
    docker = shutil.which("docker")
    assert docker, "Docker (with Compose) is needed to run this test"
    # Only these files count: not COMPOSE_* variables or a .env from this machine.
    environment = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    command = [docker, "compose", *files, "config"]
    if as_written:
        command += ["--no-normalize", "--no-interpolate"]
    result = subprocess.run(
        [*command, "--format", "json"], cwd=project, env=environment, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def host_ips(service):
    return {port.get("host_ip") for port in service.get("ports", [])}


def env_files(service):
    return [Path(entry["path"]).name for entry in service.get("env_file", [])]


# --- Development -----------------------------------------------------------------


def test_development_runs_postgres_and_redis_reachable_from_this_machine(project):
    services = config(project)["services"]
    assert set(services) == {"db", "redis"}
    assert host_ips(services["db"]) == host_ips(services["redis"]) == {"127.0.0.1"}


def redis_start_script(project, *files):
    """The shell script the Redis service starts with (sh -c '...'), on one line."""
    command = config(project, *files, as_written=True)["services"]["redis"]["command"]
    assert command[:2] == ["sh", "-c"]
    return " ".join(command[2].split())


def last_value(script, option):
    """The value Redis uses for an option: the last one given, as Redis reads them."""
    values = re.findall(rf"{option} (\S+)", script)
    assert values, f"{option} is missing"
    return values[-1]


@pytest.mark.parametrize("files", [[], PRODUCTION], ids=["development", "production"])
def test_redis_is_a_cache_that_saves_nothing_and_stays_within_its_memory(project, files):
    script = redis_start_script(project, *files)
    assert last_value(script, "--save") == '""'
    assert last_value(script, "--appendonly") == "no"
    assert last_value(script, "--maxmemory-policy") == "allkeys-lru"
    assert re.fullmatch(r"[1-9]\d*mb", last_value(script, "--maxmemory"))  # 0 means no limit
    assert "volumes" not in config(project, *files)["services"]["redis"]


def test_redis_needs_a_login_and_keeps_the_password_out_of_its_arguments(project):
    script = redis_start_script(project)
    assert "user default off" in script  # no login-free access
    assert "-@dangerous" in script  # the app's login can't run admin commands
    assert "--aclfile" in script
    # The password goes into the users file, never onto redis-server's command line.
    assert "PASSWORD" not in script.split("exec redis-server", 1)[1]
    assert config(project)["services"]["redis"]["user"] == "redis"  # never root


def test_the_redis_health_check_uses_the_ping_only_login(project):
    test = config(project)["services"]["redis"]["healthcheck"]["test"]
    assert test[test.index("--user") + 1] == "healthcheck"


def test_the_database_is_ready_only_once_it_answers_over_tcp(project):
    # A new database first runs a setup server that only answers locally.
    test = config(project)["services"]["db"]["healthcheck"]["test"]
    assert "-h 127.0.0.1" in " ".join(test)


# --- Production ------------------------------------------------------------------


def test_production_runs_postgres_redis_migrate_the_app_and_the_worker(project):
    services = config(project, *PRODUCTION)["services"]
    assert set(services) == {"db", "redis", "migrate", "web", "worker"}


def test_production_is_a_separate_project_from_development(project):
    assert config(project, *PRODUCTION)["name"] != config(project)["name"]


def test_production_secrets_come_only_from_env_files(project):
    # Written in a compose file, a secret would be committed to git.
    services = config(project, *PRODUCTION, as_written=True)["services"]
    assert env_files(services["db"]) == [".env.postgres"]
    assert env_files(services["redis"]) == [".env.redis"]
    for name in APP_SERVICES:
        assert env_files(services[name]) == [".env.production"]
    assert [name for name, service in services.items() if "environment" in service] == []


def test_only_the_app_is_published_and_only_on_this_machine(project):
    services = config(project, *PRODUCTION)["services"]
    assert host_ips(services["web"]) == {"127.0.0.1"}
    unpublished = ["db", "redis", "migrate", "worker"]
    assert [name for name in unpublished if "ports" in services[name]] == []
    assert [name for name, service in services.items() if "network_mode" in service] == []


def test_the_database_and_redis_are_only_on_an_internal_network(project):
    production = config(project, *PRODUCTION)
    for name in ["db", "redis"]:
        assert list(production["services"][name]["networks"]) == ["backend"]
    assert production["networks"]["backend"]["internal"] is True


def test_production_migrates_before_the_app_and_worker_start(project):
    services = config(project, *PRODUCTION)["services"]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    for name in ["web", "worker"]:
        assert services[name]["depends_on"]["migrate"]["condition"] == (
            "service_completed_successfully"
        )
    assert services["migrate"]["command"][-2:] == ["migrate", "--noinput"]


def test_the_app_and_worker_start_once_redis_is_ready(project):
    services = config(project, *PRODUCTION)["services"]
    for name in ["web", "worker"]:
        assert services[name]["depends_on"]["redis"]["condition"] == "service_healthy"


def test_migrate_runs_once_and_has_no_health_check(project):
    migrate = config(project, *PRODUCTION)["services"]["migrate"]
    assert migrate.get("restart", "no") == "no"  # restarting would re-run it in a loop
    assert migrate["healthcheck"]["disable"] is True


def test_the_app_and_redis_run_locked_down(project):
    services = config(project, *PRODUCTION)["services"]
    for name in [*APP_SERVICES, "redis"]:
        assert services[name]["cap_drop"] == ["ALL"]
        assert services[name]["read_only"] is True
        assert "no-new-privileges:true" in services[name]["security_opt"]
    assert services["redis"]["user"] == "redis"  # never root
    # Its read-only filesystem leaves only /data, in memory, for the login file.
    assert services["redis"]["tmpfs"] == ["/data:uid=999,gid=999,mode=0700"]
    assert "no-new-privileges:true" in services["db"]["security_opt"]


def test_every_production_service_keeps_limited_logs(project):
    # Docker's default keeps logs without a limit, so they could fill the disk.
    services = config(project, *PRODUCTION)["services"]
    for name, service in services.items():
        options = service.get("logging", {}).get("options", {})
        assert {"max-size", "max-file"} <= set(options), f"{name} has no log limit"
        assert service["logging"] == services["web"]["logging"], f"{name} differs"


def test_production_restarts_after_a_crash(project):
    services = config(project, *PRODUCTION)["services"]
    restarts = {services[name]["restart"] for name in ["db", "redis", "web", "worker"]}
    assert restarts == {"unless-stopped"}


def test_the_app_gets_longer_to_stop_than_gunicorn_needs(project):
    # Docker force-stops a container after stop_grace_period; Gunicorn needs up to
    # graceful_timeout to finish requests in progress. Whole seconds keep it simple.
    gunicorn = runpy.run_path(str(PROJECT_DIR / "gunicorn.conf.py"))
    grace = config(project, *PRODUCTION)["services"]["web"]["stop_grace_period"]
    assert re.fullmatch(r"\d+s", grace), f"write stop_grace_period in whole seconds: {grace}"
    assert int(grace[:-1]) > gunicorn["graceful_timeout"]


def test_the_worker_runs_jobs_with_the_apps_files_and_no_web_health_check(project):
    services = config(project, *PRODUCTION)["services"]
    worker = services["worker"]
    assert worker["command"][-2:] == ["manage.py", "db_worker"]
    assert worker["image"] == services["web"]["image"]
    assert worker["healthcheck"]["disable"] is True  # the image's check calls /healthz
    assert worker["volumes"] == services["web"]["volumes"]  # the same uploaded files


def test_the_worker_gets_time_to_finish_its_job(project):
    # As written: Compose would show 60s as 1m0s.
    services = config(project, *PRODUCTION, as_written=True)["services"]
    grace = services["worker"]["stop_grace_period"]
    assert re.fullmatch(r"\d+s", grace), f"write stop_grace_period in whole seconds: {grace}"
    assert int(grace[:-1]) >= 60


# --- The local HTTP check --------------------------------------------------------


def test_only_the_local_http_file_turns_the_https_settings_off(project):
    services = config(project, *LOCAL_HTTP, as_written=True)["services"]
    assert set(services["web"]["environment"]) == HTTPS_SETTINGS
    others = ["db", "redis", "migrate", "worker"]
    assert [name for name in others if "environment" in services[name]] == []
