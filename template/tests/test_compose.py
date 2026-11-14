"""The compose files: development stays on this machine, production keeps its secrets in
env files, migrates before the app starts, runs locked down behind Caddy, limits every
container's logs, and shuts down gracefully.
Redis is a cache only: nothing on disk, a memory limit, and internal in production.

`docker compose config` merges the files exactly as `docker compose up` would, without
starting anything or needing the Docker daemon. (tests/test_caddy.py runs Caddy itself.)
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


def copy_compose_files(directory):
    """The compose files in this folder, with empty secret files (production needs
    them), so `config` can merge them without this machine's own files."""
    for name in COMPOSE_FILES:
        shutil.copy(PROJECT_DIR / name, directory / name)
    for name in [".env.production", ".env.postgres", ".env.redis", ".env.caddy"]:
        (directory / name).write_text("")
    return directory


@pytest.fixture
def project(tmp_path):
    return copy_compose_files(tmp_path)


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


def test_production_runs_postgres_redis_migrate_the_app_the_worker_and_caddy(project):
    services = config(project, *PRODUCTION)["services"]
    assert set(services) == {"db", "redis", "migrate", "web", "worker", "caddy"}


def test_production_is_a_separate_project_from_development(project):
    assert config(project, *PRODUCTION)["name"] != config(project)["name"]


def test_production_secrets_come_only_from_env_files(project):
    # Written in a compose file, a secret would be committed to git.
    services = config(project, *PRODUCTION, as_written=True)["services"]
    assert env_files(services["db"]) == [".env.postgres"]
    assert env_files(services["redis"]) == [".env.redis"]
    for name in APP_SERVICES:
        assert env_files(services[name]) == [".env.production"]
    assert env_files(services["caddy"]) == [".env.caddy"]
    # The only settings written here: the app is always behind Caddy, which sends private
    # uploads for it. Not secrets.
    written = {name: set(s["environment"]) for name, s in services.items() if "environment" in s}
    assert written == {"web": {"DJANGO_BEHIND_PROXY", "DJANGO_MEDIA_SENT_BY_PROXY"}}


def test_only_caddy_is_published_and_the_app_is_always_behind_it(project):
    services = config(project, *PRODUCTION)["services"]
    published = {name for name, service in services.items() if "ports" in service}
    assert published == {"caddy"}
    ports = {(p["target"], p.get("protocol", "tcp")) for p in services["caddy"]["ports"]}
    assert ports == {(80, "tcp"), (443, "tcp"), (443, "udp")}
    assert services["web"]["environment"]["DJANGO_BEHIND_PROXY"] == "true"
    assert services["web"]["environment"]["DJANGO_MEDIA_SENT_BY_PROXY"] == "true"
    assert [name for name, service in services.items() if "network_mode" in service] == []


def test_caddy_serves_the_uploads_read_only_and_keeps_its_certificates(project):
    caddy = config(project, *PRODUCTION)["services"]["caddy"]
    mounts = {volume["target"]: volume for volume in caddy["volumes"]}
    for target, volume in [("/srv/media", "media"), ("/srv/media-public", "media_public")]:
        assert mounts[target]["source"] == volume and mounts[target]["read_only"]
    assert mounts["/data"]["type"] == "volume"  # certificates survive a restart
    # Folders, not single files: a mounted file stays the old copy after git replaces it.
    for target in ["/etc/caddy", "/srv/errors"]:
        assert mounts[target]["type"] == "bind" and mounts[target]["read_only"]
    # Not waiting for a healthy app: the error page shows even if the app can't start.
    assert caddy["depends_on"]["web"]["condition"] == "service_started"
    assert "127.0.0.1:2019" in " ".join(caddy["healthcheck"]["test"])


def test_the_apps_tmp_in_memory_has_a_size_limit(project):
    # Django keeps an upload being received in /tmp, which is in memory.
    services = config(project, *PRODUCTION)["services"]
    for name in APP_SERVICES:
        [memory_folder] = services[name]["tmpfs"]
        assert ":size=" in memory_folder


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


def test_the_app_redis_and_caddy_run_locked_down(project):
    services = config(project, *PRODUCTION)["services"]
    for name in [*APP_SERVICES, "redis", "caddy"]:
        assert services[name]["cap_drop"] == ["ALL"]
        assert services[name]["read_only"] is True
        assert "no-new-privileges:true" in services[name]["security_opt"]
    # No service gets a capability back: Caddy's own user may listen on ports 80 and 443
    # in its network namespace instead (tests/test_caddy.py checks it isn't root).
    assert [name for name in services if "cap_add" in services[name]] == []
    assert services["caddy"]["sysctls"] == {"net.ipv4.ip_unprivileged_port_start": "0"}
    # Built with the rate-limit plugin, not the official image.
    assert services["caddy"]["build"]["dockerfile"] == "caddy.Dockerfile"
    assert services["redis"]["user"] == "redis"  # never root
    # Its read-only filesystem leaves only /data, in memory, for the login file.
    assert services["redis"]["tmpfs"] == ["/data:uid=999,gid=999,mode=0700"]
    assert "no-new-privileges:true" in services["db"]["security_opt"]


def test_ipv6_visitors_reach_caddy_with_their_own_address(project):
    # Without IPv6 on Caddy's network, Docker relays IPv6 connections itself, and every
    # IPv6 visitor shares one address, and one rate limit.
    production = config(project, *PRODUCTION)
    assert production["networks"]["default"]["enable_ipv6"] is True
    assert "default" in production["services"]["caddy"].get("networks", {"default": None})


def test_every_production_service_keeps_limited_logs(project):
    # Docker's default keeps logs without a limit, so they could fill the disk.
    services = config(project, *PRODUCTION)["services"]
    for name, service in services.items():
        options = service.get("logging", {}).get("options", {})
        assert {"max-size", "max-file"} <= set(options), f"{name} has no log limit"
        assert service["logging"] == services["web"]["logging"], f"{name} differs"


def test_production_restarts_after_a_crash(project):
    services = config(project, *PRODUCTION)["services"]
    restarts = {services[name]["restart"] for name in ["db", "redis", "web", "worker", "caddy"]}
    assert restarts == {"unless-stopped"}


def test_the_app_gets_longer_to_stop_than_gunicorn_needs(project):
    # Docker force-stops a container after stop_grace_period; Gunicorn needs up to
    # graceful_timeout to finish requests in progress. Whole seconds keep it simple.
    gunicorn = runpy.run_path(str(PROJECT_DIR / "gunicorn.conf.py"))
    grace = config(project, *PRODUCTION)["services"]["web"]["stop_grace_period"]
    assert re.fullmatch(r"\d+s", grace), f"write stop_grace_period in whole seconds: {grace}"
    assert int(grace[:-1]) > gunicorn["graceful_timeout"]


def test_the_worker_runs_jobs_with_the_apps_files_and_its_own_health_check(project):
    services = config(project, *PRODUCTION)["services"]
    worker = services["worker"]
    assert worker["command"][-2:] == ["manage.py", "db_worker"]
    assert worker["image"] == services["web"]["image"]
    # Its own check, not the image's (which calls /healthz, which the worker doesn't serve).
    assert worker["healthcheck"]["test"] == ["CMD", "python", "-m", "config.health", "worker"]
    assert worker["volumes"] == services["web"]["volumes"]  # the same uploaded files
    targets = {volume["source"]: volume["target"] for volume in worker["volumes"]}
    assert targets == {"media": "/app/media", "media_public": "/app/media-public"}


def test_the_worker_gets_time_to_finish_its_job(project):
    # As written: Compose would show 60s as 1m0s.
    services = config(project, *PRODUCTION, as_written=True)["services"]
    grace = services["worker"]["stop_grace_period"]
    assert re.fullmatch(r"\d+s", grace), f"write stop_grace_period in whole seconds: {grace}"
    assert int(grace[:-1]) >= 60


# --- The local HTTP check --------------------------------------------------------


def environment_of(service):
    """A service's environment as a dict: as written, merged files can give a list of
    NAME=value strings instead."""
    environment = service.get("environment", {})
    if isinstance(environment, list):
        return dict(entry.split("=", 1) for entry in environment)
    return environment


def test_only_the_local_http_file_turns_the_https_settings_off(project):
    services = config(project, *LOCAL_HTTP, as_written=True)["services"]
    assert set(environment_of(services["web"])) == {
        *HTTPS_SETTINGS,
        "DJANGO_BEHIND_PROXY",
        "DJANGO_MEDIA_SENT_BY_PROXY",
    }
    assert environment_of(services["caddy"]) == {"SITE_ADDRESS": ":80"}  # plain HTTP
    others = ["db", "redis", "migrate", "worker"]
    assert [name for name in others if "environment" in services[name]] == []


def test_the_local_check_is_only_reachable_from_this_machine(project):
    caddy = config(project, *LOCAL_HTTP)["services"]["caddy"]
    assert [(p["host_ip"], p["published"], p["target"]) for p in caddy["ports"]] == [
        ("127.0.0.1", "8000", 80)
    ]
