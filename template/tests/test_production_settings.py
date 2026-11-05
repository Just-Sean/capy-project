"""Production must be secure and must refuse to start when misconfigured.

Each test runs manage.py in a separate process with a production-style
environment (no .env file), exactly as a server would.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

PRODUCTION_ENV = {
    "DJANGO_READ_DOT_ENV": "false",
    "DJANGO_SECRET_KEY": "a-long-random-production-secret-key-for-testing-0123456789-abcdef",
    "DJANGO_ALLOWED_HOSTS": "example.com",
    "DJANGO_ADMIN_URL": "staff-portal/",
    "DATABASE_URL": "postgres://user:pass@localhost:5432/db",
}


def run_manage(*args, **env_changes):
    env = {"PATH": os.environ["PATH"], **PRODUCTION_ENV, **env_changes}
    env = {key: value for key, value in env.items() if value is not None}
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_passes_djangos_deployment_checklist():
    result = run_manage("check", "--deploy", "--fail-level", "WARNING")
    assert result.returncode == 0, result.stderr


def test_debug_is_off_by_default():
    result = run_manage("shell", "-c", "from django.conf import settings; print(settings.DEBUG)")
    assert result.stdout.strip().splitlines()[-1] == "False", result.stderr


def test_refuses_to_start_without_secret_key():
    result = run_manage("check", DJANGO_SECRET_KEY=None)
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_refuses_to_start_without_allowed_hosts():
    result = run_manage("check", DJANGO_ALLOWED_HOSTS=None)
    assert result.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS" in result.stderr


def test_refuses_default_admin_url():
    result = run_manage("check", DJANGO_ADMIN_URL="admin/")
    assert result.returncode != 0
    assert "DJANGO_ADMIN_URL" in result.stderr
