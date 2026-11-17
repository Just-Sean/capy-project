"""Production's database logins: the app logs in as its own user, which isn't a
superuser, made by deploy/postgres-app-user.sh when Postgres first creates its data, or
by deploy/postgres-app-user-upgrade.sql on a database made before that. POSTGRES_USER,
the superuser, is only for backups and restores. Needs the Docker daemon running (it
starts real Postgres containers)."""

import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from tests.test_compose import PRODUCTION, config, copy_compose_files

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_DIR / "deploy" / "postgres-app-user.sh"
UPGRADE = PROJECT_DIR / "deploy" / "postgres-app-user-upgrade.sql"
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
SITE_LOGIN_COUNT = "SELECT count(*) FROM pg_roles WHERE rolname = 'site'"


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


def start_postgres(image, superuser, *env, init_script=True):
    """A fresh production Postgres, as compose starts it; returns the container's name."""
    name = f"postgres-logins-test-{uuid.uuid4().hex[:8]}"
    options = ["--env", f"POSTGRES_USER={superuser}", "--env", f"POSTGRES_DB={DATABASE}"]
    options += ["--env", f"POSTGRES_PASSWORD={ADMIN_PASSWORD}"]
    for setting in env:
        options += ["--env", setting]
    if init_script:
        options += ["--volume", f"{SCRIPT}:{INIT_PATH}:ro"]
    docker("run", "--detach", "--name", name, *options, image)
    return name


def wait_until_ready(name, superuser=ADMIN):
    # Over TCP: during its first setup Postgres only answers on its local socket.
    deadline = time.monotonic() + READY_WITHIN_SECONDS
    while time.monotonic() < deadline:
        ready = docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", superuser, check=False)
        if ready.returncode == 0:
            return
        time.sleep(1)
    logs = docker("logs", name, check=False)
    pytest.fail(f"Postgres didn't start:\n{logs.stdout}\n{logs.stderr}")


# Connects over the container's network address, as the app does from its own container:
# there Postgres checks the password (it trusts 127.0.0.1 and its local socket).
NETWORK_PSQL = (
    'psql -h "$(hostname -i | cut -d" " -f1)" -U "$LOGIN" -d "$DATABASE" -tA '
    '-v ON_ERROR_STOP=1 -c "$QUERY"'
)


def sql(name, query, user=ADMIN, password=ADMIN_PASSWORD):
    """Runs one query with a password over the network, as the app does."""
    return docker(
        "exec", "--env", f"PGPASSWORD={password}", "--env", f"LOGIN={user}",
        "--env", f"DATABASE={DATABASE}", "--env", f"QUERY={query}",
        name, "sh", "-c", NETWORK_PSQL,
        check=False,
    )  # fmt: skip


def test_a_wrong_password_is_refused(postgres):
    # So the other tests' logins really prove the passwords.
    assert sql(postgres, "SELECT 1", APP, "not-the-password").returncode != 0


def test_production_mounts_the_login_script_read_only(db_service):
    mounts = {volume["target"]: volume for volume in db_service["volumes"]}
    script = mounts[INIT_PATH]
    assert Path(script["source"]).name == SCRIPT.name
    assert script["read_only"] is True


@pytest.fixture(scope="module")
def postgres(db_service):
    """A new production database, made with deploy/postgres-app-user.sh."""
    name = start_postgres(
        db_service["image"], ADMIN, f"APP_DB_USER={APP}", f"APP_DB_PASSWORD={APP_PASSWORD}"
    )
    try:
        wait_until_ready(name)
        yield name
    finally:
        docker("rm", "--force", name, check=False)


def test_the_apps_login_is_not_a_superuser(postgres):
    result = sql(postgres, APP_LOGIN_RIGHTS)
    assert result.stdout.strip() == "f|f|f|f|f", result.stderr


def test_the_app_owns_its_database_so_migrations_work(postgres):
    assert sql(postgres, DATABASE_OWNER).stdout.strip() == APP
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


def test_the_password_never_appears_on_a_command_line():
    # Other users of a server can read every process's command line.
    script, upgrade_sql = SCRIPT.read_text(), UPGRADE.read_text()
    assert "\\getenv app_password APP_DB_PASSWORD" in script
    assert "app_password=" not in script  # not passed with --set on psql's command line
    assert "\\getenv site_password APP_DB_PASSWORD" in upgrade_sql
    assert "\\getenv admin_password NEW_POSTGRES_PASSWORD" in upgrade_sql


def test_without_the_apps_login_settings_postgres_refuses_to_set_up(db_service):
    name = start_postgres(db_service["image"], ADMIN)
    try:
        deadline = time.monotonic() + READY_WITHIN_SECONDS
        while docker("inspect", "-f", "{{.State.Running}}", name).stdout.strip() == "true":
            assert time.monotonic() < deadline, "Postgres started without the app's login"
            time.sleep(1)
        logs = docker("logs", name, check=False)
        assert "set APP_DB_USER and APP_DB_PASSWORD" in logs.stdout + logs.stderr
    finally:
        docker("rm", "--force", name, check=False)


# --- deploy/postgres-app-user-upgrade.sql, on a database made the old way ---------------

OLD_SUPERUSER = "app"  # before v1.0.0 the app logged in as the superuser
SITE_PASSWORD = 'site\'s "new" \\ password'
NEW_ADMIN_PASSWORD = 'admin\'s "new" \\ password'
# What a project's migrations and apps may have made, as the old superuser.
OLD_STYLE_OBJECTS = """
CREATE TABLE accounts_user (id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY);
CREATE TABLE notes (id serial PRIMARY KEY, user_id bigint REFERENCES accounts_user);
CREATE SEQUENCE invoice_numbers;
CREATE VIEW note_count AS SELECT count(*) FROM notes;
CREATE MATERIALIZED VIEW note_stats AS SELECT count(*) AS total FROM notes;
CREATE FUNCTION touch() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RETURN NEW; END';
CREATE TYPE mood AS ENUM ('happy', 'sad');
CREATE DOMAIN positive AS integer CHECK (VALUE > 0);
CREATE TYPE pair AS (a integer, b integer);
CREATE SCHEMA reports;
CREATE TABLE reports.daily (id integer);
CREATE EXTENSION pg_trgm;
"""
STILL_OWNED_BY_THE_SUPERUSER = """
SELECT count(*) FROM (
  SELECT relowner AS owner, relnamespace AS ns, oid, 'pg_class'::regclass AS kind
    FROM pg_class WHERE relkind NOT IN ('i', 'I', 't')
  UNION ALL SELECT proowner, pronamespace, oid, 'pg_proc'::regclass FROM pg_proc
  UNION ALL SELECT typowner, typnamespace, oid, 'pg_type'::regclass FROM pg_type
    WHERE typelem = 0 OR typtype <> 'b'
) o JOIN pg_namespace n ON n.oid = o.ns
WHERE o.owner = 'app'::regrole AND n.nspname NOT LIKE 'pg\\_%'
  AND n.nspname <> 'information_schema'
  AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = o.kind AND d.objid = o.oid
                  AND d.deptype = 'e')
"""


@pytest.fixture
def old_style_database(db_service):
    """A database made before v1.0.0: the app's login is the superuser, and it owns
    tables, sequences, views, a materialized view, a function, types and a schema."""
    name = start_postgres(db_service["image"], OLD_SUPERUSER, init_script=False)
    try:
        wait_until_ready(name, OLD_SUPERUSER)
        made = sql(name, OLD_STYLE_OBJECTS, OLD_SUPERUSER)
        assert made.returncode == 0, made.stderr
        yield name
    finally:
        docker("rm", "--force", name, check=False)


def upgrade(name, *env):
    """Runs the upgrade as the README says: as the superuser, one transaction, with the
    passwords only in the environment."""
    options = []
    for setting in env:
        options += ["--env", setting]
    return docker(
        "exec", "--interactive", *options, name,
        "psql", "-U", OLD_SUPERUSER, "-d", DATABASE, "-v", "ON_ERROR_STOP=1",
        "--single-transaction", "-f", "-",
        input=UPGRADE.read_text(), check=False,
    )  # fmt: skip


def test_the_upgrade_hands_everything_to_the_new_login(old_style_database):
    done = upgrade(
        old_style_database,
        f"APP_DB_PASSWORD={SITE_PASSWORD}",
        f"NEW_POSTGRES_PASSWORD={NEW_ADMIN_PASSWORD}",
    )
    assert done.returncode == 0, done.stderr
    left = sql(old_style_database, STILL_OWNED_BY_THE_SUPERUSER, OLD_SUPERUSER, NEW_ADMIN_PASSWORD)
    assert left.stdout.strip() == "0", left.stderr
    # The new login works with its password, can use what it now owns, and is limited.
    for query in [
        "INSERT INTO notes (user_id) VALUES (NULL)",
        "REFRESH MATERIALIZED VIEW note_stats",
        "SELECT nextval('invoice_numbers')",
        "CREATE TABLE reports.weekly (id integer)",
    ]:
        used = sql(old_style_database, query, "site", SITE_PASSWORD)
        assert used.returncode == 0, (query, used.stderr)
    refused = sql(old_style_database, "CREATE ROLE intruder LOGIN", "site", SITE_PASSWORD)
    assert refused.returncode != 0


def test_the_upgrade_changes_the_superusers_password(old_style_database):
    upgrade(
        old_style_database,
        f"APP_DB_PASSWORD={SITE_PASSWORD}",
        f"NEW_POSTGRES_PASSWORD={NEW_ADMIN_PASSWORD}",
    )
    assert sql(old_style_database, "SELECT 1", OLD_SUPERUSER, ADMIN_PASSWORD).returncode != 0
    assert sql(old_style_database, "SELECT 1", OLD_SUPERUSER, NEW_ADMIN_PASSWORD).returncode == 0


def test_the_upgrade_changes_nothing_without_both_passwords(old_style_database):
    stopped = upgrade(old_style_database, f"APP_DB_PASSWORD={SITE_PASSWORD}")
    assert stopped.returncode != 0
    assert "Set NEW_POSTGRES_PASSWORD" in stopped.stderr
    # No new login, the superuser's password unchanged, the database still its own.
    site = sql(old_style_database, SITE_LOGIN_COUNT, OLD_SUPERUSER)
    assert site.stdout.strip() == "0", site.stderr
    owner = sql(old_style_database, DATABASE_OWNER, OLD_SUPERUSER)
    assert owner.stdout.strip() == OLD_SUPERUSER
