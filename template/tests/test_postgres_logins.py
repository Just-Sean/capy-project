"""Production's database logins: the app logs in as its own user, which isn't a
superuser, made by deploy/postgres-app-user.sh when Postgres first creates its data.
POSTGRES_USER, the superuser, is only for backups and restores. Needs the Docker daemon
running (it starts a real Postgres)."""

import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from tests.test_compose import PRODUCTION, config, copy_compose_files

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_DIR / "deploy" / "postgres-app-user.sh"
INIT_PATH = "/docker-entrypoint-initdb.d/10-app-user.sh"
ADMIN, ADMIN_PASSWORD = "admin", "admin-only-for-this-test"
APP = "app"
# Quotes, a backslash and SQL in the password: psql must keep it a plain value.
APP_PASSWORD = "it's \"a\" \\ pass'; DROP ROLE admin; --"
DATABASE = "site"
READY_WITHIN_SECONDS = 60
# The names above, written out: fixed queries, nothing built from values.
APP_LOGIN_RIGHTS = (
    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
    "FROM pg_roles WHERE rolname = 'app'"
)
DATABASE_OWNER = "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'site'"
ADMIN_LOGIN_EXISTS = "SELECT 1 FROM pg_roles WHERE rolname = 'admin'"


def docker(*args, check=True, **kwargs):
    executable = shutil.which("docker")
    assert executable, "Docker is needed to run this test"
    return subprocess.run(
        [executable, *args], capture_output=True, text=True, check=check, **kwargs
    )


@pytest.fixture(scope="module")
def db_service(tmp_path_factory):
    project = copy_compose_files(tmp_path_factory.mktemp("compose"))
    return config(project, *PRODUCTION)["services"]["db"]


def test_production_mounts_the_login_script_read_only(db_service):
    mounts = {volume["target"]: volume for volume in db_service["volumes"]}
    script = mounts[INIT_PATH]
    assert Path(script["source"]).name == SCRIPT.name
    assert script["read_only"] is True


@pytest.fixture(scope="module")
def postgres(db_service):
    """The production database image, started fresh with the script, as compose does."""
    name = f"postgres-logins-test-{uuid.uuid4().hex[:8]}"
    docker(
        "run", "--detach", "--name", name,
        "--env", f"POSTGRES_USER={ADMIN}", "--env", f"POSTGRES_PASSWORD={ADMIN_PASSWORD}",
        "--env", f"POSTGRES_DB={DATABASE}",
        "--env", f"APP_DB_USER={APP}", "--env", f"APP_DB_PASSWORD={APP_PASSWORD}",
        "--volume", f"{SCRIPT}:{INIT_PATH}:ro",
        db_service["image"],
    )  # fmt: skip
    try:
        wait_until_ready(name)
        yield name
    finally:
        docker("rm", "--force", name, check=False)


def wait_until_ready(name):
    # Over TCP: during its first setup Postgres only answers on its local socket.
    deadline = time.monotonic() + READY_WITHIN_SECONDS
    while time.monotonic() < deadline:
        ready = docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", ADMIN, check=False)
        if ready.returncode == 0:
            return
        time.sleep(1)
    logs = docker("logs", name, check=False)
    pytest.fail(f"Postgres didn't start:\n{logs.stdout}\n{logs.stderr}")


def sql(name, query, user=ADMIN, password=ADMIN_PASSWORD):
    """Runs one query over TCP with a password, as the app does; returns the result."""
    return docker(
        "exec", "--env", f"PGPASSWORD={password}", name,
        "psql", "-h", "127.0.0.1", "-U", user, "-d", DATABASE, "-tA", "-v", "ON_ERROR_STOP=1",
        "-c", query,
        check=False,
    )  # fmt: skip


def test_the_apps_login_is_not_a_superuser(postgres):
    result = sql(postgres, APP_LOGIN_RIGHTS)
    assert result.stdout.strip() == "f|f|f|f|f", result.stderr


def test_the_app_owns_its_database_so_migrations_work(postgres):
    owner = sql(postgres, DATABASE_OWNER)
    assert owner.stdout.strip() == APP
    created = sql(postgres, "CREATE TABLE migration_check (id bigint)", APP, APP_PASSWORD)
    assert created.returncode == 0, created.stderr


@pytest.mark.parametrize(
    "query",
    [
        "CREATE ROLE intruder LOGIN",
        "CREATE DATABASE another",
        "COPY (SELECT 1) TO PROGRAM 'true'",
        "SELECT pg_read_file('/etc/passwd')",
    ],
)
def test_the_app_can_do_nothing_beyond_its_own_data(postgres, query):
    refused = sql(postgres, query, APP, APP_PASSWORD)
    assert refused.returncode != 0
    assert "permission denied" in refused.stderr or "must be superuser" in refused.stderr


def test_a_password_with_quotes_and_sql_is_kept_as_it_is(postgres):
    # The app logs in with exactly the password from .env.postgres, and the SQL in it
    # didn't run (the admin login still exists).
    assert sql(postgres, "SELECT 1", APP, APP_PASSWORD).stdout.strip() == "1"
    assert sql(postgres, ADMIN_LOGIN_EXISTS).stdout.strip() == "1"


def test_without_the_apps_login_settings_postgres_refuses_to_set_up(db_service):
    name = f"postgres-logins-test-{uuid.uuid4().hex[:8]}"
    try:
        docker(
            "run", "--detach", "--name", name,
            "--env", f"POSTGRES_USER={ADMIN}", "--env", f"POSTGRES_PASSWORD={ADMIN_PASSWORD}",
            "--env", f"POSTGRES_DB={DATABASE}",
            "--volume", f"{SCRIPT}:{INIT_PATH}:ro",
            db_service["image"],
        )  # fmt: skip
        deadline = time.monotonic() + READY_WITHIN_SECONDS
        while docker("inspect", "-f", "{{.State.Running}}", name).stdout.strip() == "true":
            assert time.monotonic() < deadline, "Postgres started without the app's login"
            time.sleep(1)
        logs = docker("logs", name, check=False)
        assert "set APP_DB_USER and APP_DB_PASSWORD" in logs.stdout + logs.stderr
    finally:
        docker("rm", "--force", name, check=False)
