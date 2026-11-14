"""Production must be secure and must refuse to start when misconfigured.

Each test runs manage.py in a separate process with a production-style
environment (no .env file, no DJANGO_ENV, so production), exactly as a server would.
"""

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings

PROJECT_DIR = Path(__file__).resolve().parent.parent

PRODUCTION_ENV = {
    "DJANGO_READ_DOT_ENV": "false",
    "DJANGO_SECRET_KEY": "a-long-random-production-secret-key-for-testing-0123456789-abcdef",
    "DJANGO_ALLOWED_HOSTS": "example.com",
    "DJANGO_ADMIN_URL": "staff-portal/",
    "DATABASE_URL": "postgres://user:pass@localhost:5432/db",
    "CACHE_URL": "redis://app:cache-password@localhost:6379/0",
}


PRINT_SETTINGS = (
    "from django.conf import settings; print(settings.DEBUG, settings.SECURE_SSL_REDIRECT)"
)


def run_manage(*args, **env_changes):
    # Only PATH and coverage's own variables (so `pytest --cov` measures this process
    # too) come from your machine; everything else is the production environment.
    coverage = {k: v for k, v in os.environ.items() if k.startswith("COVERAGE_")}
    env = {"PATH": os.environ["PATH"], **coverage, **PRODUCTION_ENV, **env_changes}
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


def test_refuses_to_start_without_a_cache():
    result = run_manage("check", CACHE_URL=None)
    assert result.returncode != 0
    assert "CACHE_URL" in result.stderr


PRINT_CACHE = (
    "from django.conf import settings; c = settings.CACHES['default']; o = c['OPTIONS']; "
    "print(c['BACKEND'], o['socket_connect_timeout'], o['socket_timeout'], "
    "'health_check_interval' in o)"
)


def test_production_caches_in_redis_and_gives_up_quickly():
    result = run_manage("shell", "-c", PRINT_CACHE)
    assert result.stdout.strip().splitlines()[-1] == (
        "django.core.cache.backends.redis.RedisCache 2 2 False"
    ), result.stderr


def test_options_in_the_cache_url_are_kept():
    url = "redis://app:cache-password@localhost:6379/0?health_check_interval=30"
    result = run_manage("shell", "-c", PRINT_CACHE, CACHE_URL=url)
    assert result.stdout.strip().splitlines()[-1].endswith("2 2 True"), result.stderr


def test_development_also_refuses_to_start_without_a_cache():
    result = run_manage("check", DJANGO_ENV="development", CACHE_URL=None)
    assert result.returncode != 0
    assert "CACHE_URL" in result.stderr


def test_refuses_default_admin_url():
    result = run_manage("check", DJANGO_ADMIN_URL="admin/")
    assert result.returncode != 0
    assert "DJANGO_ADMIN_URL" in result.stderr


def test_refuses_debug_in_production():
    result = run_manage("check", DJANGO_DEBUG="true")
    assert result.returncode != 0
    assert "DJANGO_DEBUG" in result.stderr


def test_refuses_unknown_environment():
    result = run_manage("check", DJANGO_ENV="prod")
    assert result.returncode != 0
    assert "DJANGO_ENV" in result.stderr


def test_development_starts_with_only_database_and_cache_urls():
    result = run_manage(
        "shell",
        "-c",
        PRINT_SETTINGS,
        DJANGO_ENV="development",
        DJANGO_SECRET_KEY=None,
        DJANGO_ALLOWED_HOSTS=None,
        DJANGO_ADMIN_URL=None,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "True False"


def test_pytest_runs_as_the_test_environment():
    assert settings.DJANGO_ENV == "test"
    assert settings.DEBUG is False


def test_tests_cache_in_memory_without_redis():
    assert settings.CACHES["default"]["BACKEND"] == (
        "django.core.cache.backends.locmem.LocMemCache"
    )
